"""
Advanced caching system for TTS results and preprocessing.
"""

import os
import json
import hashlib
import sqlite3
import pickle
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable, TypeVar, Generic, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from functools import wraps
from contextlib import contextmanager
import logging

from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Cache entry metadata."""
    key: str
    data: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size_bytes: int = 0


class CacheStats:
    """Cache performance statistics."""
    
    def __init__(self):
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0
        self.total_size_bytes: int = 0
        self.entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hit_rate,
            'evictions': self.evictions,
            'total_size_bytes': self.total_size_bytes,
            'entry_count': self.entry_count,
        }


class TTSCache:
    """
    Persistent cache for TTS results.
    
    Uses SQLite for metadata and filesystem for binary audio data.
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_size_mb: float = 1024.0,
        default_ttl_hours: Optional[int] = 168,  # 7 days
        cleanup_interval_hours: int = 24
    ):
        """
        Initialize TTS cache.
        
        Args:
            cache_dir: Directory for cache storage
            max_size_mb: Maximum cache size in MB
            default_ttl_hours: Default TTL for cache entries (None for no expiry)
            cleanup_interval_hours: Cleanup interval for expired entries
        """
        if cache_dir is None:
            cache_dir = Path.home() / '.novel-audiobook-generator' / 'cache'
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.audio_dir = self.cache_dir / 'audio'
        self.audio_dir.mkdir(exist_ok=True)
        
        self.db_path = self.cache_dir / 'cache.db'
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.default_ttl = timedelta(hours=default_ttl_hours) if default_ttl_hours else None
        self.cleanup_interval = timedelta(hours=cleanup_interval_hours)
        
        self._local = threading.local()
        self._stats = CacheStats()
        self._last_cleanup = datetime.now()
        
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(str(self.db_path))
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_db(self):
        """Initialize cache database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tts_cache (
                key TEXT PRIMARY KEY,
                audio_path TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                voice_id TEXT NOT NULL,
                params_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                size_bytes INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_expires ON tts_cache(expires_at)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_voice ON tts_cache(voice_id)
        ''')
        
        conn.commit()
        logger.debug(f"Initialized TTS cache at {self.cache_dir}")
    
    def _generate_key(
        self,
        text: str,
        voice_id: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        model: Optional[str] = None
    ) -> str:
        """Generate cache key from TTS parameters."""
        key_data = f"{text}:{voice_id}:{stability}:{similarity_boost}:{model or 'default'}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(
        self,
        text: str,
        voice_id: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Get cached audio file path.
        
        Args:
            text: Text that was synthesized
            voice_id: Voice ID used
            stability: Stability parameter
            similarity_boost: Similarity boost parameter
            model: Model name
            
        Returns:
            Path to cached audio file or None if not found
        """
        self._maybe_cleanup()
        
        key = self._generate_key(text, voice_id, stability, similarity_boost, model)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM tts_cache WHERE key = ?',
            (key,)
        )
        row = cursor.fetchone()
        
        if row is None:
            self._stats.misses += 1
            return None
        
        # Check expiry
        expires_at = row['expires_at']
        if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
            self._remove_entry(key)
            self._stats.misses += 1
            return None
        
        audio_path = row['audio_path']
        if not Path(audio_path).exists():
            # File was deleted externally
            self._remove_entry(key)
            self._stats.misses += 1
            return None
        
        # Update access stats
        cursor.execute('''
            UPDATE tts_cache 
            SET access_count = access_count + 1, last_accessed = ?
            WHERE key = ?
        ''', (datetime.now().isoformat(), key))
        conn.commit()
        
        self._stats.hits += 1
        logger.debug(f"Cache hit for key {key[:8]}...")
        return audio_path
    
    def put(
        self,
        text: str,
        voice_id: str,
        audio_path: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        model: Optional[str] = None,
        ttl_hours: Optional[int] = None
    ) -> str:
        """
        Store audio file in cache.
        
        Args:
            text: Text that was synthesized
            voice_id: Voice ID used
            audio_path: Path to audio file to cache
            stability: Stability parameter
            similarity_boost: Similarity boost parameter
            model: Model name
            ttl_hours: TTL for this entry (None for default)
            
        Returns:
            Path to cached audio file
        """
        key = self._generate_key(text, voice_id, stability, similarity_boost, model)
        
        # Copy audio to cache directory
        cached_path = self.audio_dir / f"{key}.mp3"
        
        try:
            import shutil
            shutil.copy2(audio_path, cached_path)
        except Exception as e:
            logger.warning(f"Failed to cache audio file: {e}")
            return audio_path
        
        # Calculate size
        size_bytes = cached_path.stat().st_size
        
        # Calculate expiry
        ttl = timedelta(hours=ttl_hours) if ttl_hours else self.default_ttl
        expires_at = (datetime.now() + ttl).isoformat() if ttl else None
        
        # Store metadata
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO tts_cache
            (key, audio_path, text_hash, voice_id, params_hash, created_at, 
             expires_at, access_count, last_accessed, size_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            key,
            str(cached_path),
            hashlib.sha256(text.encode()).hexdigest()[:16],
            voice_id,
            hashlib.sha256(f"{stability}:{similarity_boost}:{model}".encode()).hexdigest()[:16],
            datetime.now().isoformat(),
            expires_at,
            0,
            None,
            size_bytes
        ))
        
        conn.commit()
        
        # Check if we need to evict
        self._maybe_evict()
        
        logger.debug(f"Cached audio for key {key[:8]}... ({size_bytes} bytes)")
        return str(cached_path)
    
    def _remove_entry(self, key: str):
        """Remove cache entry and associated file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT audio_path FROM tts_cache WHERE key = ?', (key,))
        row = cursor.fetchone()
        
        if row:
            audio_path = row['audio_path']
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete cached file: {e}")
        
        cursor.execute('DELETE FROM tts_cache WHERE key = ?', (key,))
        conn.commit()
    
    def _maybe_cleanup(self):
        """Clean up expired entries if cleanup interval has passed."""
        if datetime.now() - self._last_cleanup < self.cleanup_interval:
            return
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Find expired entries
        cursor.execute(
            'SELECT key FROM tts_cache WHERE expires_at < ?',
            (datetime.now().isoformat(),)
        )
        expired = cursor.fetchall()
        
        for row in expired:
            self._remove_entry(row['key'])
        
        self._last_cleanup = datetime.now()
        logger.info(f"Cleaned up {len(expired)} expired cache entries")
    
    def _maybe_evict(self):
        """Evict entries if cache size exceeds limit."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT SUM(size_bytes) FROM tts_cache')
        total_size = cursor.fetchone()[0] or 0
        
        if total_size <= self.max_size_bytes:
            return
        
        # Need to evict - use LRU policy
        overflow = total_size - int(self.max_size_bytes * 0.9)  # Target 90%
        
        cursor.execute('''
            SELECT key, size_bytes FROM tts_cache
            ORDER BY last_accessed ASC NULLS FIRST, access_count ASC
        ''')
        
        evicted = 0
        for row in cursor.fetchall():
            if overflow <= 0:
                break
            
            self._remove_entry(row['key'])
            overflow -= row['size_bytes']
            evicted += 1
        
        self._stats.evictions += evicted
        logger.info(f"Evicted {evicted} cache entries to maintain size limit")
    
    def clear(self):
        """Clear all cache entries."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT audio_path FROM tts_cache')
        for row in cursor.fetchall():
            try:
                Path(row['audio_path']).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete cached file: {e}")
        
        cursor.execute('DELETE FROM tts_cache')
        conn.commit()
        
        logger.info("Cache cleared")
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*), SUM(size_bytes) FROM tts_cache')
        row = cursor.fetchone()
        
        self._stats.entry_count = row[0] or 0
        self._stats.total_size_bytes = row[1] or 0
        
        return self._stats
    
    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


class PreprocessingCache:
    """Cache for text preprocessing results."""
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_size_mb: float = 100.0
    ):
        """
        Initialize preprocessing cache.
        
        Args:
            cache_dir: Directory for cache storage
            max_size_mb: Maximum cache size in MB
        """
        if cache_dir is None:
            cache_dir = Path.home() / '.novel-audiobook-generator' / 'preprocess_cache'
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        
        self._cache: Dict[str, Any] = {}
        self._access_times: Dict[str, datetime] = {}
        self._lock = threading.Lock()
        
        self._load_cache()
    
    def _get_cache_file(self, text_hash: str) -> Path:
        """Get cache file path for text hash."""
        return self.cache_dir / f"{text_hash}.pkl"
    
    def _load_cache(self):
        """Load cache index from disk."""
        index_file = self.cache_dir / 'index.json'
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    index = json.load(f)
                    self._access_times = {
                        k: datetime.fromisoformat(v)
                        for k, v in index.get('access_times', {}).items()
                    }
            except Exception as e:
                logger.warning(f"Failed to load cache index: {e}")
    
    def _save_index(self):
        """Save cache index to disk."""
        index_file = self.cache_dir / 'index.json'
        try:
            with open(index_file, 'w') as f:
                json.dump({
                    'access_times': {
                        k: v.isoformat()
                        for k, v in self._access_times.items()
                    }
                }, f)
        except Exception as e:
            logger.warning(f"Failed to save cache index: {e}")
    
    def get(self, text: str) -> Optional[Any]:
        """Get preprocessed result for text."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:32]
        
        with self._lock:
            # Check memory cache first
            if text_hash in self._cache:
                self._access_times[text_hash] = datetime.now()
                return self._cache[text_hash]
        
        # Check disk cache
        cache_file = self._get_cache_file(text_hash)
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    result = pickle.load(f)
                
                with self._lock:
                    self._cache[text_hash] = result
                    self._access_times[text_hash] = datetime.now()
                
                return result
            except Exception as e:
                logger.warning(f"Failed to load cache file: {e}")
        
        return None
    
    def put(self, text: str, result: Any):
        """Store preprocessed result."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:32]
        
        with self._lock:
            self._cache[text_hash] = result
            self._access_times[text_hash] = datetime.now()
            
            # Save to disk
            cache_file = self._get_cache_file(text_hash)
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(result, f)
            except Exception as e:
                logger.warning(f"Failed to save cache file: {e}")
            
            # Maybe evict from memory
            self._maybe_evict_memory()
        
        self._save_index()
    
    def _maybe_evict_memory(self):
        """Evict old entries from memory cache."""
        max_memory_entries = 1000
        
        if len(self._cache) <= max_memory_entries:
            return
        
        # Sort by access time and remove oldest
        sorted_items = sorted(
            self._access_times.items(),
            key=lambda x: x[1]
        )
        
        to_remove = len(sorted_items) - int(max_memory_entries * 0.9)
        for text_hash, _ in sorted_items[:to_remove]:
            self._cache.pop(text_hash, None)
            self._access_times.pop(text_hash, None)


def cached_tts(cache: Optional[TTSCache] = None):
    """
    Decorator to cache TTS results.
    
    Usage:
        @cached_tts()
        def generate_speech(text, voice_id, output_path):
            # TTS generation logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Try to extract text and voice_id from args/kwargs
            text = kwargs.get('text') or (args[0] if len(args) > 0 else None)
            voice_id = kwargs.get('voice_id') or (args[1] if len(args) > 1 else None)
            output_path = kwargs.get('output_path') or (args[2] if len(args) > 2 else None)
            
            if cache and text and voice_id:
                cached_path = cache.get(text, voice_id)
                if cached_path:
                    import shutil
                    shutil.copy2(cached_path, output_path)
                    return output_path
                
                # Generate and cache
                result = func(*args, **kwargs)
                cache.put(text, voice_id, output_path)
                return result
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
