"""
Progress tracking with persistence and recovery.
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ChunkProgress:
    """Progress for a single chunk."""
    index: int
    status: str  # 'pending', 'processing', 'completed', 'failed'
    attempts: int = 0
    error_message: Optional[str] = None
    audio_path: Optional[str] = None
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ChunkProgress':
        return cls(**data)


@dataclass
class GenerationProgress:
    """Overall generation progress."""
    input_file: str
    input_hash: str
    output_path: str
    total_chunks: int
    chunks: List[ChunkProgress]
    status: str  # 'running', 'paused', 'completed', 'failed'
    started_at: str
    updated_at: str
    backend: str
    voice: str
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        return {
            'input_file': self.input_file,
            'input_hash': self.input_hash,
            'output_path': self.output_path,
            'total_chunks': self.total_chunks,
            'chunks': [c.to_dict() for c in self.chunks],
            'status': self.status,
            'started_at': self.started_at,
            'updated_at': self.updated_at,
            'backend': self.backend,
            'voice': self.voice,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GenerationProgress':
        chunks = [ChunkProgress.from_dict(c) for c in data.get('chunks', [])]
        return cls(
            input_file=data['input_file'],
            input_hash=data['input_hash'],
            output_path=data['output_path'],
            total_chunks=data['total_chunks'],
            chunks=chunks,
            status=data['status'],
            started_at=data['started_at'],
            updated_at=data['updated_at'],
            backend=data['backend'],
            voice=data['voice'],
            metadata=data.get('metadata'),
        )
    
    @property
    def completed_chunks(self) -> int:
        return sum(1 for c in self.chunks if c.status == 'completed')
    
    @property
    def failed_chunks(self) -> int:
        return sum(1 for c in self.chunks if c.status == 'failed')
    
    @property
    def progress_percentage(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return (self.completed_chunks / self.total_chunks) * 100
    
    @property
    def is_complete(self) -> bool:
        return self.completed_chunks == self.total_chunks
    
    @property
    def can_resume(self) -> bool:
        return self.status in ['running', 'paused'] and not self.is_complete


class ProgressTracker:
    """Track and persist generation progress."""
    
    def __init__(self, progress_dir: str = ".progress"):
        self.progress_dir = Path(progress_dir)
        self.progress_dir.mkdir(exist_ok=True)
    
    def _get_progress_file(self, input_file: str) -> Path:
        """Get progress file path for input file."""
        # Use hash of input file path to avoid filesystem issues
        file_hash = hashlib.md5(input_file.encode()).hexdigest()[:16]
        return self.progress_dir / f"{file_hash}.json"
    
    def _compute_file_hash(self, file_path: str) -> str:
        """Compute hash of file contents for change detection."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Could not compute file hash: {e}")
            return ""
    
    def create_progress(
        self,
        input_file: str,
        output_path: str,
        total_chunks: int,
        backend: str,
        voice: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GenerationProgress:
        """Create new progress tracking."""
        input_hash = self._compute_file_hash(input_file)
        now = datetime.now().isoformat()
        
        chunks = [
            ChunkProgress(index=i, status='pending')
            for i in range(total_chunks)
        ]
        
        progress = GenerationProgress(
            input_file=input_file,
            input_hash=input_hash,
            output_path=output_path,
            total_chunks=total_chunks,
            chunks=chunks,
            status='running',
            started_at=now,
            updated_at=now,
            backend=backend,
            voice=voice,
            metadata=metadata,
        )
        
        self._save_progress(progress)
        return progress
    
    def load_progress(self, input_file: str) -> Optional[GenerationProgress]:
        """Load progress for input file."""
        progress_file = self._get_progress_file(input_file)
        
        if not progress_file.exists():
            return None
        
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            progress = GenerationProgress.from_dict(data)
            
            # Verify input file hasn't changed
            current_hash = self._compute_file_hash(input_file)
            if current_hash and current_hash != progress.input_hash:
                logger.warning(f"Input file has changed since last run, starting fresh")
                return None
            
            return progress
            
        except Exception as e:
            logger.error(f"Failed to load progress: {e}")
            return None
    
    def _save_progress(self, progress: GenerationProgress):
        """Save progress to file."""
        progress_file = self._get_progress_file(progress.input_file)
        progress.updated_at = datetime.now().isoformat()
        
        try:
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
    
    def update_chunk(
        self,
        input_file: str,
        chunk_index: int,
        status: str,
        audio_path: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None
    ):
        """Update chunk progress."""
        progress = self.load_progress(input_file)
        if not progress:
            return
        
        if 0 <= chunk_index < len(progress.chunks):
            chunk = progress.chunks[chunk_index]
            chunk.status = status
            
            if status == 'processing':
                chunk.attempts += 1
            
            if audio_path:
                chunk.audio_path = audio_path
            if error_message:
                chunk.error_message = error_message
            if duration_ms:
                chunk.duration_ms = duration_ms
            
            self._save_progress(progress)
    
    def update_status(self, input_file: str, status: str):
        """Update overall status."""
        progress = self.load_progress(input_file)
        if progress:
            progress.status = status
            self._save_progress(progress)
    
    def get_completed_chunk_paths(self, input_file: str) -> List[str]:
        """Get list of completed chunk audio paths."""
        progress = self.load_progress(input_file)
        if not progress:
            return []
        
        return [
            c.audio_path for c in progress.chunks
            if c.status == 'completed' and c.audio_path and Path(c.audio_path).exists()
        ]
    
    def cleanup(self, input_file: str):
        """Remove progress file."""
        progress_file = self._get_progress_file(input_file)
        if progress_file.exists():
            progress_file.unlink()
    
    def list_active_jobs(self) -> List[GenerationProgress]:
        """List all active (non-completed) jobs."""
        jobs = []
        
        for progress_file in self.progress_dir.glob("*.json"):
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                progress = GenerationProgress.from_dict(data)
                if progress.can_resume:
                    jobs.append(progress)
            except Exception as e:
                logger.warning(f"Failed to load progress file {progress_file}: {e}")
        
        return jobs
