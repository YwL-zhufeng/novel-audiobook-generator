"""
Unit tests for cache module.
"""

import pytest
import tempfile
from pathlib import Path
import time

from src.cache import TTSCache, PreprocessingCache, CacheStats


class TestTTSCache:
    """Test TTS cache functionality."""
    
    @pytest.fixture
    def cache(self):
        """Create temporary cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TTSCache(
                cache_dir=tmpdir,
                max_size_mb=10.0,
                default_ttl_hours=1
            )
            yield cache
            cache.close()
    
    @pytest.fixture
    def sample_audio(self, tmp_path):
        """Create sample audio file."""
        audio_path = tmp_path / "test.mp3"
        # Create dummy audio file
        audio_path.write_bytes(b"dummy audio data" * 100)
        return str(audio_path)
    
    def test_cache_put_and_get(self, cache, sample_audio):
        """Test storing and retrieving from cache."""
        # Store
        cached_path = cache.put(
            text="Hello world",
            voice_id="voice1",
            audio_path=sample_audio
        )
        
        assert Path(cached_path).exists()
        
        # Retrieve
        result = cache.get(
            text="Hello world",
            voice_id="voice1"
        )
        
        assert result is not None
        assert Path(result).exists()
    
    def test_cache_miss(self, cache):
        """Test cache miss."""
        result = cache.get(
            text="Nonexistent text",
            voice_id="voice1"
        )
        
        assert result is None
        
        stats = cache.get_stats()
        assert stats.misses == 1
    
    def test_cache_expiry(self, cache, sample_audio):
        """Test cache entry expiry."""
        # Store with short TTL
        cache.put(
            text="Expiring text",
            voice_id="voice1",
            audio_path=sample_audio,
            ttl_hours=0  # Immediate expiry
        )
        
        # Should be expired
        result = cache.get("Expiring text", "voice1")
        assert result is None
    
    def test_cache_stats(self, cache, sample_audio):
        """Test cache statistics."""
        # Store and retrieve
        cache.put("Text 1", "voice1", sample_audio)
        cache.get("Text 1", "voice1")
        cache.get("Text 2", "voice1")  # Miss
        
        stats = cache.get_stats()
        
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5
        assert stats.entry_count == 1
    
    def test_cache_clear(self, cache, sample_audio):
        """Test clearing cache."""
        cache.put("Text 1", "voice1", sample_audio)
        cache.put("Text 2", "voice1", sample_audio)
        
        cache.clear()
        
        assert cache.get("Text 1", "voice1") is None
        assert cache.get("Text 2", "voice1") is None
        
        stats = cache.get_stats()
        assert stats.entry_count == 0


class TestPreprocessingCache:
    """Test preprocessing cache."""
    
    @pytest.fixture
    def cache(self):
        """Create temporary cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PreprocessingCache(
                cache_dir=tmpdir,
                max_size_mb=10.0
            )
            yield cache
    
    def test_put_and_get(self, cache):
        """Test storing and retrieving preprocessed results."""
        text = "Sample text for preprocessing"
        result = {"chunks": ["chunk1", "chunk2"], "metadata": {}}
        
        cache.put(text, result)
        
        retrieved = cache.get(text)
        
        assert retrieved == result
    
    def test_cache_miss(self, cache):
        """Test cache miss."""
        result = cache.get("Nonexistent text")
        assert result is None
    
    def test_different_texts(self, cache):
        """Test caching different texts."""
        text1 = "First text"
        text2 = "Second text"
        result1 = {"id": 1}
        result2 = {"id": 2}
        
        cache.put(text1, result1)
        cache.put(text2, result2)
        
        assert cache.get(text1) == result1
        assert cache.get(text2) == result2


class TestCacheStats:
    """Test cache statistics."""
    
    def test_initial_stats(self):
        """Test initial stats values."""
        stats = CacheStats()
        
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0
        assert stats.evictions == 0
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats()
        stats.hits = 75
        stats.misses = 25
        
        assert stats.hit_rate == 0.75
    
    def test_to_dict(self):
        """Test stats serialization."""
        stats = CacheStats()
        stats.hits = 10
        stats.misses = 5
        stats.total_size_bytes = 1024
        
        data = stats.to_dict()
        
        assert data['hits'] == 10
        assert data['misses'] == 5
        assert data['hit_rate'] == 10/15
        assert data['total_size_bytes'] == 1024
