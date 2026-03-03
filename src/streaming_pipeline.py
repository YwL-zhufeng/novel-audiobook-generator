"""
Streaming processing pipeline for efficient audiobook generation.
"""

import asyncio
import queue
import threading
from typing import (
    AsyncIterator, Iterator, Callable, Optional, TypeVar, Generic, 
    List, Dict, Any, Union, Coroutine
)
from dataclasses import dataclass, field
from enum import Enum, auto
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import datetime

from .logging_config import get_logger
from .memory_monitor import MemoryMonitor, MemorySnapshot

logger = get_logger(__name__)

T = TypeVar('T')
U = TypeVar('U')


class PipelineStageStatus(Enum):
    """Status of a pipeline stage."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class PipelineMetrics:
    """Metrics for pipeline execution."""
    items_processed: int = 0
    items_failed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    stage_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        """Get pipeline duration."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    @property
    def throughput_per_second(self) -> float:
        """Calculate throughput."""
        duration = self.duration_seconds
        if duration <= 0:
            return 0.0
        return self.items_processed / duration
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'items_processed': self.items_processed,
            'items_failed': self.items_failed,
            'duration_seconds': round(self.duration_seconds, 2),
            'throughput_per_second': round(self.throughput_per_second, 2),
            'stage_metrics': self.stage_metrics,
        }


@dataclass
class ProcessingItem(Generic[T]):
    """Item being processed through the pipeline."""
    id: str
    data: T
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    
    def can_retry(self) -> bool:
        """Check if item can be retried."""
        return self.retry_count < self.max_retries


class PipelineStage(Generic[T, U]):
    """A single stage in the processing pipeline."""
    
    def __init__(
        self,
        name: str,
        processor: Callable[[T], U],
        max_workers: int = 4,
        buffer_size: int = 10,
        error_handler: Optional[Callable[[Exception, ProcessingItem[T]], Optional[U]]] = None
    ):
        """
        Initialize pipeline stage.
        
        Args:
            name: Stage name
            processor: Processing function
            max_workers: Maximum concurrent workers
            buffer_size: Input buffer size
            error_handler: Optional error handler
        """
        self.name = name
        self.processor = processor
        self.max_workers = max_workers
        self.buffer_size = buffer_size
        self.error_handler = error_handler
        
        self.input_queue: queue.Queue[ProcessingItem[T]] = queue.Queue(maxsize=buffer_size)
        self.output_queue: queue.Queue[Union[ProcessingItem[U], Exception]] = queue.Queue()
        
        self.status = PipelineStageStatus.PENDING
        self._workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        self._metrics = {
            'items_processed': 0,
            'items_failed': 0,
            'processing_time_ms': 0.0,
        }
        self._lock = threading.Lock()
    
    def start(self):
        """Start the pipeline stage."""
        self.status = PipelineStageStatus.RUNNING
        
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"{self.name}-worker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
        
        logger.debug(f"Started stage '{self.name}' with {self.max_workers} workers")
    
    def stop(self, wait: bool = True):
        """Stop the pipeline stage."""
        self._stop_event.set()
        
        if wait:
            for worker in self._workers:
                worker.join(timeout=5.0)
        
        self.status = PipelineStageStatus.COMPLETED
        logger.debug(f"Stopped stage '{self.name}'")
    
    def _worker_loop(self):
        """Worker thread loop."""
        while not self._stop_event.is_set():
            try:
                item = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            if item is None:  # Poison pill
                break
            
            start_time = datetime.now()
            
            try:
                result = self.processor(item.data)
                
                with self._lock:
                    self._metrics['items_processed'] += 1
                    self._metrics['processing_time_ms'] += (
                        datetime.now() - start_time
                    ).total_seconds() * 1000
                
                output_item = ProcessingItem[U](
                    id=item.id,
                    data=result,
                    metadata={**item.metadata, 'stage': self.name}
                )
                self.output_queue.put(output_item)
                
            except Exception as e:
                with self._lock:
                    self._metrics['items_failed'] += 1
                
                if item.can_retry():
                    item.retry_count += 1
                    logger.warning(
                        f"Retrying item {item.id} in stage '{self.name}' "
                        f"(attempt {item.retry_count}/{item.max_retries})"
                    )
                    self.input_queue.put(item)
                elif self.error_handler:
                    result = self.error_handler(e, item)
                    if result is not None:
                        output_item = ProcessingItem[U](
                            id=item.id,
                            data=result,
                            metadata={**item.metadata, 'stage': self.name, 'recovered': True}
                        )
                        self.output_queue.put(output_item)
                else:
                    self.output_queue.put(e)
            
            finally:
                self.input_queue.task_done()
    
    def put(self, item: ProcessingItem[T], block: bool = True, timeout: Optional[float] = None):
        """Put an item into the input queue."""
        self.input_queue.put(item, block=block, timeout=timeout)
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Union[ProcessingItem[U], Exception]:
        """Get an item from the output queue."""
        return self.output_queue.get(block=block, timeout=timeout)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get stage metrics."""
        with self._lock:
            metrics = self._metrics.copy()
            if metrics['items_processed'] > 0:
                metrics['avg_processing_time_ms'] = (
                    metrics['processing_time_ms'] / metrics['items_processed']
                )
            return metrics


class StreamingPipeline(Generic[T, U]):
    """
    Multi-stage streaming processing pipeline.
    
    Supports both sync and async processing with backpressure control.
    """
    
    def __init__(
        self,
        stages: List[PipelineStage],
        memory_monitor: Optional[MemoryMonitor] = None,
        enable_backpressure: bool = True
    ):
        """
        Initialize streaming pipeline.
        
        Args:
            stages: List of pipeline stages
            memory_monitor: Optional memory monitor
            enable_backpressure: Enable backpressure control
        """
        self.stages = stages
        self.memory_monitor = memory_monitor
        self.enable_backpressure = enable_backpressure
        
        self._metrics = PipelineMetrics()
        self._running = False
        self._executor: Optional[ThreadPoolExecutor] = None
    
    def start(self):
        """Start the pipeline."""
        self._running = True
        self._metrics.start_time = datetime.now()
        
        for stage in self.stages:
            stage.start()
        
        if self.memory_monitor:
            self.memory_monitor.start_monitoring()
        
        logger.info(f"Started pipeline with {len(self.stages)} stages")
    
    def stop(self):
        """Stop the pipeline."""
        self._running = False
        
        for stage in self.stages:
            stage.stop(wait=True)
        
        if self.memory_monitor:
            self.memory_monitor.stop_monitoring()
        
        self._metrics.end_time = datetime.now()
        logger.info("Stopped pipeline")
    
    def process_stream(
        self,
        input_stream: Iterator[ProcessingItem[T]],
        output_callback: Optional[Callable[[ProcessingItem[U]], None]] = None
    ) -> Iterator[ProcessingItem[U]]:
        """
        Process a stream of items through the pipeline.
        
        Args:
            input_stream: Input item stream
            output_callback: Optional callback for each output
            
        Yields:
            Processed items
        """
        if not self._running:
            raise RuntimeError("Pipeline not started. Call start() first.")
        
        # Connect stages with forwarding threads
        for i in range(len(self.stages) - 1):
            current_stage = self.stages[i]
            next_stage = self.stages[i + 1]
            
            def forward(stage_from=current_stage, stage_to=next_stage):
                while self._running:
                    try:
                        item = stage_from.get(timeout=0.1)
                        if isinstance(item, Exception):
                            continue
                        
                        # Backpressure check
                        if self.enable_backpressure and self.memory_monitor:
                            if not self.memory_monitor.check_limits():
                                logger.warning("Backpressure: memory limit exceeded")
                                # Wait and retry
                                import time
                                time.sleep(1.0)
                        
                        stage_to.put(item)
                    except queue.Empty:
                        continue
            
            thread = threading.Thread(target=forward, daemon=True)
            thread.start()
        
        # Feed input stream
        def feed_input():
            for item in input_stream:
                if not self._running:
                    break
                
                # Backpressure
                if self.enable_backpressure:
                    while self.stages[0].input_queue.full():
                        import time
                        time.sleep(0.1)
                
                self.stages[0].put(item)
        
        feeder = threading.Thread(target=feed_input, daemon=True)
        feeder.start()
        
        # Yield output from final stage
        final_stage = self.stages[-1]
        while self._running or not final_stage.output_queue.empty():
            try:
                item = final_stage.get(timeout=0.5)
                
                if isinstance(item, Exception):
                    self._metrics.items_failed += 1
                    logger.error(f"Pipeline error: {item}")
                    continue
                
                self._metrics.items_processed += 1
                
                if output_callback:
                    output_callback(item)
                
                yield item
                
            except queue.Empty:
                if not feeder.is_alive() and final_stage.output_queue.empty():
                    break
                continue
    
    def process_batch(
        self,
        items: List[ProcessingItem[T]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ProcessingItem[U]]:
        """
        Process a batch of items.
        
        Args:
            items: Items to process
            progress_callback: Optional progress callback(current, total)
            
        Returns:
            List of processed items
        """
        results = []
        total = len(items)
        
        for i, item in enumerate(self.process_stream(iter(items))):
            results.append(item)
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
    
    def get_metrics(self) -> PipelineMetrics:
        """Get pipeline metrics."""
        # Update stage metrics
        for stage in self.stages:
            self._metrics.stage_metrics[stage.name] = stage.get_metrics()
        
        return self._metrics


class AsyncStreamingPipeline(Generic[T, U]):
    """Async version of the streaming pipeline."""
    
    def __init__(
        self,
        processor: Callable[[T], Coroutine[Any, Any, U]],
        max_concurrency: int = 10,
        max_queue_size: int = 100
    ):
        """
        Initialize async streaming pipeline.
        
        Args:
            processor: Async processing function
            max_concurrency: Maximum concurrent operations
            max_queue_size: Maximum queue size
        """
        self.processor = processor
        self.max_concurrency = max_concurrency
        self.max_queue_size = max_queue_size
        
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._queue: asyncio.Queue[ProcessingItem[T]] = asyncio.Queue(maxsize=max_queue_size)
        self._results: asyncio.Queue[Union[ProcessingItem[U], Exception]] = asyncio.Queue()
        self._running = False
    
    async def start(self):
        """Start the pipeline."""
        self._running = True
        
        # Start worker tasks
        workers = [
            asyncio.create_task(self._worker())
            for _ in range(self.max_concurrency)
        ]
        
        logger.info(f"Started async pipeline with {self.max_concurrency} workers")
        return workers
    
    async def _worker(self):
        """Worker coroutine."""
        while self._running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            if item is None:  # Poison pill
                break
            
            async with self._semaphore:
                try:
                    result = await self.processor(item.data)
                    output_item = ProcessingItem[U](
                        id=item.id,
                        data=result,
                        metadata=item.metadata
                    )
                    await self._results.put(output_item)
                except Exception as e:
                    await self._results.put(e)
                finally:
                    self._queue.task_done()
    
    async def process_stream(
        self,
        input_stream: AsyncIterator[ProcessingItem[T]]
    ) -> AsyncIterator[ProcessingItem[U]]:
        """Process async stream."""
        # Feed input
        async def feed():
            async for item in input_stream:
                await self._queue.put(item)
        
        feeder = asyncio.create_task(feed())
        
        # Yield results
        completed = 0
        while True:
            try:
                item = await asyncio.wait_for(self._results.get(), timeout=0.5)
                
                if isinstance(item, Exception):
                    logger.error(f"Pipeline error: {item}")
                    continue
                
                completed += 1
                yield item
                
            except asyncio.TimeoutError:
                if feeder.done() and self._queue.empty() and self._results.empty():
                    break
    
    async def stop(self):
        """Stop the pipeline."""
        self._running = False
        
        # Send poison pills
        for _ in range(self.max_concurrency):
            await self._queue.put(None)


@contextmanager
def pipeline_context(stages: List[PipelineStage]):
    """Context manager for pipeline lifecycle."""
    pipeline = StreamingPipeline(stages)
    pipeline.start()
    try:
        yield pipeline
    finally:
        pipeline.stop()
