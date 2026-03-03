"""
Unit tests for streaming pipeline.
"""

import pytest
import time
import threading
from queue import Queue

from src.streaming_pipeline import (
    PipelineStage,
    StreamingPipeline,
    ProcessingItem,
    PipelineStageStatus,
    PipelineMetrics
)


class TestProcessingItem:
    """Test ProcessingItem."""
    
    def test_item_creation(self):
        """Test creating processing item."""
        item = ProcessingItem(
            id="test-1",
            data="test data",
            metadata={"key": "value"}
        )
        
        assert item.id == "test-1"
        assert item.data == "test data"
        assert item.can_retry() is True
    
    def test_retry_limit(self):
        """Test retry limit."""
        item = ProcessingItem(
            id="test-1",
            data="test",
            retry_count=2,
            max_retries=3
        )
        
        assert item.can_retry() is True
        
        item.retry_count = 3
        assert item.can_retry() is False


class TestPipelineStage:
    """Test PipelineStage."""
    
    def test_stage_creation(self):
        """Test creating pipeline stage."""
        def processor(x):
            return x * 2
        
        stage = PipelineStage(
            name="test_stage",
            processor=processor,
            max_workers=2
        )
        
        assert stage.name == "test_stage"
        assert stage.max_workers == 2
        assert stage.status == PipelineStageStatus.PENDING
    
    def test_stage_processing(self):
        """Test stage processing."""
        def processor(x):
            return x * 2
        
        stage = PipelineStage(
            name="test",
            processor=processor,
            max_workers=1
        )
        
        stage.start()
        
        # Add item
        item = ProcessingItem(id="1", data=5)
        stage.put(item)
        
        # Get result
        result = stage.get(timeout=2.0)
        
        stage.stop()
        
        assert isinstance(result, ProcessingItem)
        assert result.data == 10
    
    def test_stage_error_handling(self):
        """Test stage error handling."""
        def failing_processor(x):
            raise ValueError("Test error")
        
        stage = PipelineStage(
            name="test",
            processor=failing_processor,
            max_workers=1
        )
        
        stage.start()
        
        item = ProcessingItem(id="1", data="test")
        stage.put(item)
        
        # Should get exception
        result = stage.get(timeout=2.0)
        
        stage.stop()
        
        assert isinstance(result, Exception)
    
    def test_stage_metrics(self):
        """Test stage metrics."""
        def processor(x):
            time.sleep(0.01)
            return x
        
        stage = PipelineStage(
            name="test",
            processor=processor,
            max_workers=1
        )
        
        stage.start()
        
        item = ProcessingItem(id="1", data="test")
        stage.put(item)
        
        result = stage.get(timeout=2.0)
        
        stage.stop()
        
        metrics = stage.get_metrics()
        
        assert metrics['items_processed'] == 1
        assert 'avg_processing_time_ms' in metrics


class TestStreamingPipeline:
    """Test StreamingPipeline."""
    
    def test_pipeline_creation(self):
        """Test creating pipeline."""
        stage1 = PipelineStage("stage1", lambda x: x + 1, max_workers=1)
        stage2 = PipelineStage("stage2", lambda x: x * 2, max_workers=1)
        
        pipeline = StreamingPipeline([stage1, stage2])
        
        assert len(pipeline.stages) == 2
    
    def test_pipeline_start_stop(self):
        """Test pipeline start and stop."""
        stage = PipelineStage("test", lambda x: x, max_workers=1)
        pipeline = StreamingPipeline([stage])
        
        pipeline.start()
        assert pipeline._running is True
        
        pipeline.stop()
        assert pipeline._running is False
    
    def test_pipeline_batch_processing(self):
        """Test batch processing through pipeline."""
        stage1 = PipelineStage("add", lambda x: x + 1, max_workers=2)
        stage2 = PipelineStage("mul", lambda x: x * 2, max_workers=2)
        
        pipeline = StreamingPipeline([stage1, stage2])
        pipeline.start()
        
        items = [ProcessingItem(id=str(i), data=i) for i in range(5)]
        
        results = pipeline.process_batch(items)
        
        pipeline.stop()
        
        assert len(results) == 5
        
        # Verify: (i + 1) * 2
        expected = [(i + 1) * 2 for i in range(5)]
        actual = [r.data for r in results]
        assert sorted(actual) == sorted(expected)
    
    def test_pipeline_metrics(self):
        """Test pipeline metrics."""
        stage = PipelineStage("test", lambda x: x, max_workers=1)
        pipeline = StreamingPipeline([stage])
        
        pipeline.start()
        
        items = [ProcessingItem(id=str(i), data=i) for i in range(3)]
        pipeline.process_batch(items)
        
        pipeline.stop()
        
        metrics = pipeline.get_metrics()
        
        assert metrics.items_processed == 3
        assert metrics.duration_seconds > 0


class TestPipelineMetrics:
    """Test PipelineMetrics."""
    
    def test_initial_metrics(self):
        """Test initial metrics."""
        metrics = PipelineMetrics()
        
        assert metrics.items_processed == 0
        assert metrics.duration_seconds == 0.0
        assert metrics.throughput_per_second == 0.0
    
    def test_metrics_calculation(self):
        """Test metrics calculation."""
        from datetime import datetime, timedelta
        
        metrics = PipelineMetrics()
        metrics.start_time = datetime.now()
        metrics.items_processed = 100
        metrics.end_time = metrics.start_time + timedelta(seconds=10)
        
        assert metrics.duration_seconds == 10.0
        assert metrics.throughput_per_second == 10.0
    
    def test_metrics_to_dict(self):
        """Test metrics serialization."""
        from datetime import datetime
        
        metrics = PipelineMetrics()
        metrics.start_time = datetime.now()
        metrics.items_processed = 50
        
        data = metrics.to_dict()
        
        assert data['items_processed'] == 50
        assert 'duration_seconds' in data
        assert 'throughput_per_second' in data
