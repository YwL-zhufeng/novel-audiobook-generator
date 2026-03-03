"""
Background task queue for audiobook generation.
"""

import json
import uuid
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from .logging_config import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a generation task."""
    id: str
    input_file: str
    output_file: str
    voice: str
    status: TaskStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    progress: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """Create from dictionary."""
        data['status'] = TaskStatus(data['status'])
        return cls(**data)


class TaskQueue:
    """Background task queue for audiobook generation."""
    
    def __init__(self, queue_dir: Optional[str] = None, max_workers: int = 2):
        """
        Initialize task queue.
        
        Args:
            queue_dir: Directory for queue persistence
            max_workers: Maximum concurrent workers
        """
        if queue_dir is None:
            queue_dir = Path.home() / '.novel-audiobook-generator' / 'queue'
        else:
            queue_dir = Path(queue_dir)
        
        self.queue_dir = queue_dir
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_workers = max_workers
        self.tasks: Dict[str, Task] = {}
        self.running = False
        self._callbacks: List[Callable[[Task], None]] = []
        
        # Load existing tasks
        self._load_tasks()
    
    def _load_tasks(self):
        """Load tasks from disk."""
        tasks_file = self.queue_dir / 'tasks.json'
        if tasks_file.exists():
            try:
                with open(tasks_file, 'r') as f:
                    data = json.load(f)
                for task_data in data.values():
                    task = Task.from_dict(task_data)
                    self.tasks[task.id] = task
                logger.info(f"Loaded {len(self.tasks)} tasks from queue")
            except Exception as e:
                logger.error(f"Failed to load tasks: {e}")
    
    def _save_tasks(self):
        """Save tasks to disk."""
        tasks_file = self.queue_dir / 'tasks.json'
        try:
            data = {task_id: task.to_dict() for task_id, task in self.tasks.items()}
            with open(tasks_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")
    
    def submit(
        self,
        input_file: str,
        output_file: str,
        voice: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Submit a new task.
        
        Args:
            input_file: Input novel file
            output_file: Output audiobook file
            voice: Voice to use
            metadata: Optional metadata
            
        Returns:
            Created task
        """
        task = Task(
            id=str(uuid.uuid4()),
            input_file=input_file,
            output_file=output_file,
            voice=voice,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
            metadata=metadata
        )
        
        self.tasks[task.id] = task
        self._save_tasks()
        
        logger.info(f"Task submitted: {task.id}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> List[Task]:
        """
        List tasks.
        
        Args:
            status: Filter by status
            limit: Maximum number of tasks
            
        Returns:
            List of tasks
        """
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # Sort by creation time (newest first)
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return tasks[:limit]
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now().isoformat()
            self._save_tasks()
            logger.info(f"Task cancelled: {task_id}")
            return True
        
        return False
    
    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task.
        
        Args:
            task_id: Task ID to delete
            
        Returns:
            True if deleted successfully
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save_tasks()
            return True
        return False
    
    def on_task_update(self, callback: Callable[[Task], None]):
        """Register callback for task updates."""
        self._callbacks.append(callback)
    
    def _notify_update(self, task: Task):
        """Notify all callbacks of task update."""
        for callback in self._callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def update_progress(self, task_id: str, progress: float):
        """Update task progress."""
        task = self.tasks.get(task_id)
        if task:
            task.progress = progress
            self._save_tasks()
            self._notify_update(task)
    
    def mark_completed(self, task_id: str):
        """Mark task as completed."""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.completed_at = datetime.now().isoformat()
            self._save_tasks()
            self._notify_update(task)
    
    def mark_failed(self, task_id: str, error: str):
        """Mark task as failed."""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = error
            task.completed_at = datetime.now().isoformat()
            self._save_tasks()
            self._notify_update(task)
    
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        stats = {
            'total': len(self.tasks),
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }
        
        for task in self.tasks.values():
            stats[task.status.value] += 1
        
        return stats
    
    def cleanup_old_tasks(self, days: int = 7):
        """Clean up completed tasks older than specified days."""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        to_delete = []
        
        for task_id, task in self.tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                if task.completed_at:
                    completed_time = datetime.fromisoformat(task.completed_at)
                    if completed_time < cutoff:
                        to_delete.append(task_id)
        
        for task_id in to_delete:
            del self.tasks[task_id]
        
        if to_delete:
            self._save_tasks()
            logger.info(f"Cleaned up {len(to_delete)} old tasks")
        
        return len(to_delete)
