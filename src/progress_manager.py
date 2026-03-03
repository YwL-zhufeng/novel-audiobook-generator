"""
Progress persistence with SQLite for reliability.
"""

import os
import json
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from contextlib import contextmanager

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProgressState:
    """Progress state for a generation task."""
    task_id: str
    input_file: str
    output_file: str
    total_chunks: int
    completed_chunks: Set[int]
    failed_chunks: Set[int]
    status: str  # 'pending', 'running', 'paused', 'completed', 'failed'
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        if isinstance(self.completed_chunks, list):
            self.completed_chunks = set(self.completed_chunks)
        if isinstance(self.failed_chunks, list):
            self.failed_chunks = set(self.failed_chunks)
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_chunks == 0:
            return 0.0
        return len(self.completed_chunks) / self.total_chunks * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'task_id': self.task_id,
            'input_file': self.input_file,
            'output_file': self.output_file,
            'total_chunks': self.total_chunks,
            'completed_chunks': list(self.completed_chunks),
            'failed_chunks': list(self.failed_chunks),
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProgressState":
        """Create from dictionary."""
        return cls(
            task_id=data['task_id'],
            input_file=data['input_file'],
            output_file=data['output_file'],
            total_chunks=data['total_chunks'],
            completed_chunks=set(data.get('completed_chunks', [])),
            failed_chunks=set(data.get('failed_chunks', [])),
            status=data['status'],
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            metadata=data.get('metadata', {}),
        )


class ProgressManager:
    """Manager for progress persistence using SQLite."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize progress manager.
        
        Args:
            db_path: Path to SQLite database (default: ~/.novel-audiobook-generator/progress.db)
        """
        if db_path is None:
            db_path = Path.home() / '.novel-audiobook-generator' / 'progress.db'
        else:
            db_path = Path(db_path)
        
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS progress (
                task_id TEXT PRIMARY KEY,
                input_file TEXT NOT NULL,
                output_file TEXT NOT NULL,
                total_chunks INTEGER NOT NULL,
                completed_chunks TEXT NOT NULL,  -- JSON array
                failed_chunks TEXT NOT NULL,     -- JSON array
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT                    -- JSON object
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status ON progress(status)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_input_file ON progress(input_file)
        ''')
        
        conn.commit()
        logger.debug(f"Initialized progress database at {self.db_path}")
    
    def create_task(
        self,
        task_id: str,
        input_file: str,
        output_file: str,
        total_chunks: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProgressState:
        """
        Create a new progress task.
        
        Args:
            task_id: Unique task identifier
            input_file: Input file path
            output_file: Output file path
            total_chunks: Total number of chunks
            metadata: Optional metadata
            
        Returns:
            ProgressState object
        """
        now = datetime.utcnow().isoformat()
        state = ProgressState(
            task_id=task_id,
            input_file=input_file,
            output_file=output_file,
            total_chunks=total_chunks,
            completed_chunks=set(),
            failed_chunks=set(),
            status='pending',
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
        
        self._save_state(state)
        logger.info(f"Created progress task: {task_id}")
        return state
    
    def get_task(self, task_id: str) -> Optional[ProgressState]:
        """
        Get progress state for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            ProgressState or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM progress WHERE task_id = ?',
            (task_id,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return self._row_to_state(row)
    
    def update_task(
        self,
        task_id: str,
        completed_chunks: Optional[Set[int]] = None,
        failed_chunks: Optional[Set[int]] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ProgressState]:
        """
        Update progress state.
        
        Args:
            task_id: Task identifier
            completed_chunks: Set of completed chunk indices
            failed_chunks: Set of failed chunk indices
            status: New status
            metadata: Metadata updates (merged with existing)
            
        Returns:
            Updated ProgressState or None if not found
        """
        state = self.get_task(task_id)
        if state is None:
            logger.warning(f"Task not found: {task_id}")
            return None
        
        if completed_chunks is not None:
            state.completed_chunks = completed_chunks
        if failed_chunks is not None:
            state.failed_chunks = failed_chunks
        if status is not None:
            state.status = status
        if metadata is not None:
            state.metadata.update(metadata)
        
        state.updated_at = datetime.utcnow().isoformat()
        self._save_state(state)
        
        return state
    
    def mark_chunk_complete(self, task_id: str, chunk_idx: int) -> Optional[ProgressState]:
        """Mark a chunk as completed."""
        state = self.get_task(task_id)
        if state is None:
            return None
        
        state.completed_chunks.add(chunk_idx)
        state.failed_chunks.discard(chunk_idx)
        state.updated_at = datetime.utcnow().isoformat()
        
        # Auto-update status
        if len(state.completed_chunks) == state.total_chunks:
            state.status = 'completed'
        else:
            state.status = 'running'
        
        self._save_state(state)
        return state
    
    def mark_chunk_failed(self, task_id: str, chunk_idx: int, error: str) -> Optional[ProgressState]:
        """Mark a chunk as failed."""
        state = self.get_task(task_id)
        if state is None:
            return None
        
        state.failed_chunks.add(chunk_idx)
        state.updated_at = datetime.utcnow().isoformat()
        
        # Record error in metadata
        if 'errors' not in state.metadata:
            state.metadata['errors'] = {}
        state.metadata['errors'][str(chunk_idx)] = error
        
        self._save_state(state)
        return state
    
    def get_incomplete_tasks(self) -> List[ProgressState]:
        """Get all incomplete tasks."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM progress WHERE status IN ('pending', 'running', 'paused')"
        )
        
        return [self._row_to_state(row) for row in cursor.fetchall()]
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM progress WHERE task_id = ?', (task_id,))
        conn.commit()
        
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted progress task: {task_id}")
        return deleted
    
    def cleanup_old_tasks(self, days: int = 30) -> int:
        """Clean up tasks older than specified days."""
        from datetime import timedelta
        
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'DELETE FROM progress WHERE updated_at < ? AND status IN (\'completed\', \'failed\')',
            (cutoff,)
        )
        conn.commit()
        
        deleted = cursor.rowcount
        logger.info(f"Cleaned up {deleted} old progress tasks")
        return deleted
    
    def _save_state(self, state: ProgressState):
        """Save state to database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO progress
            (task_id, input_file, output_file, total_chunks, completed_chunks,
             failed_chunks, status, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            state.task_id,
            state.input_file,
            state.output_file,
            state.total_chunks,
            json.dumps(list(state.completed_chunks)),
            json.dumps(list(state.failed_chunks)),
            state.status,
            state.created_at,
            state.updated_at,
            json.dumps(state.metadata)
        ))
        
        conn.commit()
    
    def _row_to_state(self, row: sqlite3.Row) -> ProgressState:
        """Convert database row to ProgressState."""
        return ProgressState(
            task_id=row['task_id'],
            input_file=row['input_file'],
            output_file=row['output_file'],
            total_chunks=row['total_chunks'],
            completed_chunks=set(json.loads(row['completed_chunks'])),
            failed_chunks=set(json.loads(row['failed_chunks'])),
            status=row['status'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )
    
    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
