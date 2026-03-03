"""
Batch task queue for processing multiple audiobook generation tasks.
"""

import json
import sqlite3
import threading
import uuid
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
import logging
from queue import Queue, Empty

from .logging_config import get_logger
from .exceptions import AudiobookGeneratorError

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a batch processing task."""
    id: str
    input_path: str
    output_path: Optional[str]
    voice: str
    chunk_size: int
    status: TaskStatus
    priority: int  # Lower = higher priority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'input_path': self.input_path,
            'output_path': self.output_path,
            'voice': self.voice,
            'chunk_size': self.chunk_size,
            'status': self.status.value,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': self.progress,
            'error_message': self.error_message,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        return cls(
            id=data['id'],
            input_path=data['input_path'],
            output_path=data.get('output_path'),
            voice=data['voice'],
            chunk_size=data['chunk_size'],
            status=TaskStatus(data['status']),
            priority=data['priority'],
            created_at=datetime.fromisoformat(data['created_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            progress=data.get('progress', 0.0),
            error_message=data.get('error_message'),
            metadata=data.get('metadata', {}),
        )


@dataclass
class QueueStats:
    """Queue statistics."""
    total_tasks: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_tasks': self.total_tasks,
            'pending': self.pending,
            'running': self.running,
            'completed': self.completed,
            'failed': self.failed,
            'cancelled': self.cancelled,
        }


class TaskQueue:
    """
    Persistent task queue for batch audiobook generation.
    
    Features:
    - SQLite-backed persistence
    - Priority-based scheduling
    - Progress tracking
    - Pause/resume support
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        max_concurrent: int = 1,
        auto_start: bool = False
    ):
        """
        Initialize task queue.
        
        Args:
            db_path: Path to SQLite database
            max_concurrent: Maximum concurrent tasks
            auto_start: Auto-start processing on init
        """
        if db_path is None:
            db_path = Path.home() / '.novel-audiobook-generator' / 'task_queue.db'
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.max_concurrent = max_concurrent
        self._local = threading.local()
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._current_tasks: Dict[str, Task] = {}
        self._progress_callbacks: List[Callable[[str, float], None]] = []
        
        self._init_db()
        
        if auto_start:
            self.start()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(str(self.db_path))
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                input_path TEXT NOT NULL,
                output_path TEXT,
                voice TEXT NOT NULL,
                chunk_size INTEGER NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                progress REAL DEFAULT 0.0,
                error_message TEXT,
                metadata TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority)
        ''')
        
        conn.commit()
        logger.debug(f"Initialized task queue database at {self.db_path}")
    
    def add_task(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        voice: str = "default",
        chunk_size: int = 5000,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a task to the queue.
        
        Args:
            input_path: Input file path
            output_path: Output file path (optional)
            voice: Voice to use
            chunk_size: Text chunk size
            priority: Task priority (lower = higher priority)
            metadata: Additional metadata
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())[:8]
        
        task = Task(
            id=task_id,
            input_path=input_path,
            output_path=output_path,
            voice=voice,
            chunk_size=chunk_size,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=datetime.now(),
            metadata=metadata or {}
        )
        
        self._save_task(task)
        logger.info(f"Added task {task_id}: {input_path}")
        
        return task_id
    
    def add_tasks_batch(
        self,
        input_paths: List[str],
        output_paths: Optional[List[str]] = None,
        voice: str = "default",
        chunk_size: int = 5000,
        priority: int = 0
    ) -> List[str]:
        """
        Add multiple tasks to the queue.
        
        Args:
            input_paths: List of input file paths
            output_paths: Optional list of output paths
            voice: Voice to use
            chunk_size: Text chunk size
            priority: Task priority
            
        Returns:
            List of task IDs
        """
        if output_paths and len(output_paths) != len(input_paths):
            raise ValueError("output_paths must have same length as input_paths")
        
        task_ids = []
        for i, input_path in enumerate(input_paths):
            output_path = output_paths[i] if output_paths else None
            task_id = self.add_task(
                input_path=input_path,
                output_path=output_path,
                voice=voice,
                chunk_size=chunk_size,
                priority=priority
            )
            task_ids.append(task_id)
        
        return task_ids
    
    def _save_task(self, task: Task):
        """Save task to database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO tasks
            (id, input_path, output_path, voice, chunk_size, status, priority,
             created_at, started_at, completed_at, progress, error_message, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.id,
            task.input_path,
            task.output_path,
            task.voice,
            task.chunk_size,
            task.status.value,
            task.priority,
            task.created_at.isoformat(),
            task.started_at.isoformat() if task.started_at else None,
            task.completed_at.isoformat() if task.completed_at else None,
            task.progress,
            task.error_message,
            json.dumps(task.metadata)
        ))
        
        conn.commit()
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return self._row_to_task(row)
    
    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert database row to Task."""
        return Task(
            id=row['id'],
            input_path=row['input_path'],
            output_path=row['output_path'],
            voice=row['voice'],
            chunk_size=row['chunk_size'],
            status=TaskStatus(row['status']),
            priority=row['priority'],
            created_at=datetime.fromisoformat(row['created_at']),
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            progress=row['progress'],
            error_message=row['error_message'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )
    
    def get_pending_tasks(self, limit: Optional[int] = None) -> List[Task]:
        """Get pending tasks ordered by priority."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM tasks 
            WHERE status IN ('pending', 'queued')
            ORDER BY priority ASC, created_at ASC
        '''
        if limit:
            query += f' LIMIT {limit}'
        
        cursor.execute(query)
        return [self._row_to_task(row) for row in cursor.fetchall()]
    
    def get_all_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: Optional[int] = None
    ) -> List[Task]:
        """Get all tasks, optionally filtered by status."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if status:
            query = 'SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC'
            params = (status.value,)
        else:
            query = 'SELECT * FROM tasks ORDER BY created_at DESC'
            params = ()
        
        if limit:
            query += f' LIMIT {limit}'
        
        cursor.execute(query, params)
        return [self._row_to_task(row) for row in cursor.fetchall()]
    
    def update_task_progress(self, task_id: str, progress: float):
        """Update task progress."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE tasks SET progress = ? WHERE id = ?',
            (progress, task_id)
        )
        conn.commit()
        
        # Notify callbacks
        for callback in self._progress_callbacks:
            try:
                callback(task_id, progress)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or queued task."""
        task = self.get_task(task_id)
        if task is None:
            return False
        
        if task.status not in [TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.PAUSED]:
            logger.warning(f"Cannot cancel task {task_id} with status {task.status.value}")
            return False
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        self._save_task(task)
        
        logger.info(f"Cancelled task {task_id}")
        return True
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        
        return cursor.rowcount > 0
    
    def clear_completed(self, include_failed: bool = False) -> int:
        """Clear completed tasks from the queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if include_failed:
            cursor.execute(
                "DELETE FROM tasks WHERE status IN ('completed', 'failed', 'cancelled')"
            )
        else:
            cursor.execute("DELETE FROM tasks WHERE status = 'completed'")
        
        conn.commit()
        
        count = cursor.rowcount
        logger.info(f"Cleared {count} completed tasks")
        return count
    
    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM tasks 
            GROUP BY status
        ''')
        
        stats = QueueStats()
        for row in cursor.fetchall():
            status = row['status']
            count = row['count']
            
            if status in ['pending', 'queued']:
                stats.pending += count
            elif status == 'running':
                stats.running = count
            elif status == 'completed':
                stats.completed = count
            elif status == 'failed':
                stats.failed = count
            elif status == 'cancelled':
                stats.cancelled = count
        
        stats.total_tasks = sum([
            stats.pending, stats.running, stats.completed,
            stats.failed, stats.cancelled
        ])
        
        return stats
    
    def start(self):
        """Start processing tasks."""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._worker_thread.start()
        
        logger.info("Task queue started")
    
    def stop(self, wait: bool = True):
        """Stop processing tasks."""
        self._running = False
        
        if wait and self._worker_thread:
            self._worker_thread.join(timeout=30.0)
        
        logger.info("Task queue stopped")
    
    def pause(self):
        """Pause processing (current task will complete)."""
        self._running = False
        logger.info("Task queue paused")
    
    def _process_loop(self):
        """Main processing loop."""
        while self._running:
            try:
                # Get next pending task
                pending = self.get_pending_tasks(limit=1)
                
                if not pending:
                    # No pending tasks, wait a bit
                    import time
                    time.sleep(1.0)
                    continue
                
                task = pending[0]
                
                # Mark as running
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
                self._save_task(task)
                
                with self._lock:
                    self._current_tasks[task.id] = task
                
                # Process task (this should be overridden by subclass)
                try:
                    self._process_task(task)
                    
                    task.status = TaskStatus.COMPLETED
                    task.progress = 1.0
                    
                except Exception as e:
                    logger.error(f"Task {task.id} failed: {e}")
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                
                finally:
                    task.completed_at = datetime.now()
                    self._save_task(task)
                    
                    with self._lock:
                        self._current_tasks.pop(task.id, None)
                
            except Exception as e:
                logger.error(f"Error in process loop: {e}")
                import time
                time.sleep(1.0)
    
    def _process_task(self, task: Task):
        """
        Process a single task.
        
        This method should be overridden by subclasses to implement
        actual task processing logic.
        """
        raise NotImplementedError("Subclasses must implement _process_task")
    
    def on_progress(self, callback: Callable[[str, float], None]):
        """Register progress callback."""
        self._progress_callbacks.append(callback)
    
    def close(self):
        """Close the task queue."""
        self.stop(wait=True)
        
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


class AudiobookTaskQueue(TaskQueue):
    """
    Task queue specifically for audiobook generation.
    """
    
    def __init__(
        self,
        generator_factory: Callable,
        db_path: Optional[str] = None,
        max_concurrent: int = 1
    ):
        """
        Initialize audiobook task queue.
        
        Args:
            generator_factory: Factory function that returns AudiobookGenerator
            db_path: Path to SQLite database
            max_concurrent: Maximum concurrent tasks
        """
        super().__init__(db_path=db_path, max_concurrent=max_concurrent)
        self.generator_factory = generator_factory
        self._current_generator = None
    
    def _process_task(self, task: Task):
        """Process an audiobook generation task."""
        from .generator import AudiobookGenerator
        
        # Create generator
        generator = self.generator_factory()
        self._current_generator = generator
        
        try:
            # Progress callback
            def on_progress(progress: float):
                self.update_task_progress(task.id, progress)
            
            # Generate audiobook
            result = generator.generate_audiobook(
                input_path=task.input_path,
                output_path=task.output_path,
                voice=task.voice,
                chunk_size=task.chunk_size,
                progress_callback=on_progress
            )
            
            # Update metadata
            task.metadata['output_path'] = result.output_path
            task.metadata['duration_seconds'] = result.duration_seconds
            task.metadata['total_chunks'] = result.total_chunks
            
            logger.info(f"Task {task.id} completed: {result.output_path}")
            
        finally:
            generator.close()
            self._current_generator = None
    
    def pause_current_task(self):
        """Pause the currently running task (if supported by generator)."""
        # This would require generator to support pause/resume
        logger.warning("Pause not yet implemented for audiobook generation")
