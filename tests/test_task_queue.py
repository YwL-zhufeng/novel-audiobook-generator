"""
Unit tests for task queue.
"""

import pytest
import tempfile
import time
from pathlib import Path

from src.task_queue import TaskQueue, Task, TaskStatus, QueueStats


class TestTask:
    """Test Task dataclass."""
    
    def test_task_creation(self):
        """Test creating a task."""
        from datetime import datetime
        
        task = Task(
            id="test-1",
            input_path="/path/to/input.txt",
            output_path="/path/to/output.mp3",
            voice="default",
            chunk_size=5000,
            status=TaskStatus.PENDING,
            priority=0,
            created_at=datetime.now()
        )
        
        assert task.id == "test-1"
        assert task.can_retry() is True
    
    def test_task_to_dict(self):
        """Test task serialization."""
        from datetime import datetime
        
        task = Task(
            id="test-1",
            input_path="/path/to/input.txt",
            output_path="/path/to/output.mp3",
            voice="default",
            chunk_size=5000,
            status=TaskStatus.PENDING,
            priority=0,
            created_at=datetime.now()
        )
        
        data = task.to_dict()
        
        assert data['id'] == "test-1"
        assert data['status'] == "pending"
    
    def test_task_from_dict(self):
        """Test task deserialization."""
        from datetime import datetime
        
        data = {
            'id': 'test-1',
            'input_path': '/path/input.txt',
            'output_path': '/path/output.mp3',
            'voice': 'default',
            'chunk_size': 5000,
            'status': 'pending',
            'priority': 0,
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'progress': 0.0,
            'error_message': None,
            'metadata': {}
        }
        
        task = Task.from_dict(data)
        
        assert task.id == 'test-1'
        assert task.status == TaskStatus.PENDING


class TestTaskQueue:
    """Test TaskQueue."""
    
    @pytest.fixture
    def queue(self):
        """Create temporary task queue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = TaskQueue(
                db_path=str(Path(tmpdir) / "queue.db"),
                max_concurrent=1,
                auto_start=False
            )
            yield queue
            queue.close()
    
    def test_add_task(self, queue):
        """Test adding a task."""
        task_id = queue.add_task(
            input_path="/path/to/input.txt",
            output_path="/path/to/output.mp3",
            voice="default",
            chunk_size=5000
        )
        
        assert task_id is not None
        assert len(task_id) > 0
    
    def test_get_task(self, queue):
        """Test retrieving a task."""
        task_id = queue.add_task(
            input_path="/path/to/input.txt",
            voice="default"
        )
        
        task = queue.get_task(task_id)
        
        assert task is not None
        assert task.id == task_id
        assert task.input_path == "/path/to/input.txt"
    
    def test_get_nonexistent_task(self, queue):
        """Test retrieving non-existent task."""
        task = queue.get_task("nonexistent")
        
        assert task is None
    
    def test_add_tasks_batch(self, queue):
        """Test adding multiple tasks."""
        input_paths = [
            "/path/to/book1.txt",
            "/path/to/book2.txt",
            "/path/to/book3.txt"
        ]
        
        task_ids = queue.add_tasks_batch(input_paths)
        
        assert len(task_ids) == 3
    
    def test_get_pending_tasks(self, queue):
        """Test getting pending tasks."""
        queue.add_task(input_path="/path/to/book1.txt", voice="default")
        queue.add_task(input_path="/path/to/book2.txt", voice="default")
        
        pending = queue.get_pending_tasks()
        
        assert len(pending) == 2
    
    def test_update_task_progress(self, queue):
        """Test updating task progress."""
        task_id = queue.add_task(
            input_path="/path/to/input.txt",
            voice="default"
        )
        
        queue.update_task_progress(task_id, 0.5)
        
        task = queue.get_task(task_id)
        assert task.progress == 0.5
    
    def test_cancel_task(self, queue):
        """Test cancelling a task."""
        task_id = queue.add_task(
            input_path="/path/to/input.txt",
            voice="default"
        )
        
        result = queue.cancel_task(task_id)
        
        assert result is True
        
        task = queue.get_task(task_id)
        assert task.status == TaskStatus.CANCELLED
    
    def test_cancel_nonexistent_task(self, queue):
        """Test cancelling non-existent task."""
        result = queue.cancel_task("nonexistent")
        
        assert result is False
    
    def test_remove_task(self, queue):
        """Test removing a task."""
        task_id = queue.add_task(
            input_path="/path/to/input.txt",
            voice="default"
        )
        
        result = queue.remove_task(task_id)
        
        assert result is True
        assert queue.get_task(task_id) is None
    
    def test_get_stats(self, queue):
        """Test getting queue statistics."""
        queue.add_task(input_path="/path/to/book1.txt", voice="default")
        queue.add_task(input_path="/path/to/book2.txt", voice="default")
        
        stats = queue.get_stats()
        
        assert stats.total_tasks == 2
        assert stats.pending == 2
    
    def test_progress_callback(self, queue):
        """Test progress callback."""
        callbacks = []
        
        def on_progress(task_id, progress):
            callbacks.append((task_id, progress))
        
        queue.on_progress(on_progress)
        
        task_id = queue.add_task(
            input_path="/path/to/input.txt",
            voice="default"
        )
        
        queue.update_task_progress(task_id, 0.5)
        
        assert len(callbacks) == 1
        assert callbacks[0] == (task_id, 0.5)


class TestQueueStats:
    """Test QueueStats."""
    
    def test_initial_stats(self):
        """Test initial stats."""
        stats = QueueStats()
        
        assert stats.total_tasks == 0
        assert stats.pending == 0
        assert stats.running == 0
    
    def test_stats_to_dict(self):
        """Test stats serialization."""
        stats = QueueStats()
        stats.total_tasks = 10
        stats.pending = 5
        stats.completed = 3
        
        data = stats.to_dict()
        
        assert data['total_tasks'] == 10
        assert data['pending'] == 5
        assert data['completed'] == 3
