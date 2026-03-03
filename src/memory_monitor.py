"""
Memory monitoring and resource management.
"""

import os
import sys
import psutil
import threading
import gc
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager
import logging

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    timestamp: datetime
    rss_mb: float  # Resident Set Size in MB
    vms_mb: float  # Virtual Memory Size in MB
    percent: float  # Percentage of total memory
    available_mb: float
    total_mb: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'rss_mb': round(self.rss_mb, 2),
            'vms_mb': round(self.vms_mb, 2),
            'percent': round(self.percent, 2),
            'available_mb': round(self.available_mb, 2),
            'total_mb': round(self.total_mb, 2),
        }


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    snapshots: List[MemorySnapshot] = field(default_factory=list)
    peak_rss_mb: float = 0.0
    peak_percent: float = 0.0
    
    def add_snapshot(self, snapshot: MemorySnapshot):
        """Add a memory snapshot."""
        self.snapshots.append(snapshot)
        self.peak_rss_mb = max(self.peak_rss_mb, snapshot.rss_mb)
        self.peak_percent = max(self.peak_percent, snapshot.percent)
    
    def get_average_usage(self) -> float:
        """Get average memory usage."""
        if not self.snapshots:
            return 0.0
        return sum(s.rss_mb for s in self.snapshots) / len(self.snapshots)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'snapshot_count': len(self.snapshots),
            'peak_rss_mb': round(self.peak_rss_mb, 2),
            'peak_percent': round(self.peak_percent, 2),
            'average_rss_mb': round(self.get_average_usage(), 2),
        }


class MemoryMonitor:
    """Monitor memory usage with configurable limits and callbacks."""
    
    def __init__(
        self,
        max_memory_mb: Optional[float] = None,
        max_memory_percent: Optional[float] = None,
        check_interval_seconds: float = 5.0,
        warning_threshold_percent: float = 80.0,
        critical_threshold_percent: float = 90.0
    ):
        """
        Initialize memory monitor.
        
        Args:
            max_memory_mb: Maximum allowed memory in MB (None for no limit)
            max_memory_percent: Maximum allowed memory percentage (None for no limit)
            check_interval_seconds: Interval between memory checks
            warning_threshold_percent: Warning threshold percentage
            critical_threshold_percent: Critical threshold percentage
        """
        self.max_memory_mb = max_memory_mb
        self.max_memory_percent = max_memory_percent
        self.check_interval = check_interval_seconds
        self.warning_threshold = warning_threshold_percent
        self.critical_threshold = critical_threshold_percent
        
        self._process = psutil.Process()
        self._stats = MemoryStats()
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: Dict[str, List[Callable]] = {
            'warning': [],
            'critical': [],
            'limit_exceeded': [],
        }
        self._lock = threading.Lock()
    
    def get_current_usage(self) -> MemorySnapshot:
        """Get current memory usage."""
        mem_info = self._process.memory_info()
        system_mem = psutil.virtual_memory()
        
        return MemorySnapshot(
            timestamp=datetime.now(),
            rss_mb=mem_info.rss / 1024 / 1024,
            vms_mb=mem_info.vms / 1024 / 1024,
            percent=system_mem.percent,
            available_mb=system_mem.available / 1024 / 1024,
            total_mb=system_mem.total / 1024 / 1024,
        )
    
    def start_monitoring(self):
        """Start background memory monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Memory monitoring started")
    
    def stop_monitoring(self):
        """Stop background memory monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=self.check_interval + 1)
        logger.info("Memory monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                snapshot = self.get_current_usage()
                
                with self._lock:
                    self._stats.add_snapshot(snapshot)
                
                # Check thresholds
                if self.max_memory_mb and snapshot.rss_mb > self.max_memory_mb:
                    self._trigger_callbacks('limit_exceeded', snapshot)
                elif self.max_memory_percent and snapshot.percent > self.max_memory_percent:
                    self._trigger_callbacks('limit_exceeded', snapshot)
                elif snapshot.percent > self.critical_threshold:
                    self._trigger_callbacks('critical', snapshot)
                elif snapshot.percent > self.warning_threshold:
                    self._trigger_callbacks('warning', snapshot)
                
            except Exception as e:
                logger.error(f"Error in memory monitor: {e}")
            
            # Sleep with interrupt check
            for _ in range(int(self.check_interval)):
                if not self._monitoring:
                    break
                threading.Event().wait(1)
    
    def _trigger_callbacks(self, event: str, snapshot: MemorySnapshot):
        """Trigger callbacks for an event."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(snapshot)
            except Exception as e:
                logger.error(f"Error in {event} callback: {e}")
    
    def on_warning(self, callback: Callable[[MemorySnapshot], None]):
        """Register warning callback."""
        self._callbacks['warning'].append(callback)
    
    def on_critical(self, callback: Callable[[MemorySnapshot], None]):
        """Register critical callback."""
        self._callbacks['critical'].append(callback)
    
    def on_limit_exceeded(self, callback: Callable[[MemorySnapshot], None]):
        """Register limit exceeded callback."""
        self._callbacks['limit_exceeded'].append(callback)
    
    def get_stats(self) -> MemoryStats:
        """Get memory statistics."""
        with self._lock:
            return MemoryStats(
                snapshots=self._stats.snapshots.copy(),
                peak_rss_mb=self._stats.peak_rss_mb,
                peak_percent=self._stats.peak_percent,
            )
    
    def check_limits(self) -> bool:
        """
        Check if current memory usage is within limits.
        
        Returns:
            True if within limits, False if exceeded
        """
        snapshot = self.get_current_usage()
        
        if self.max_memory_mb and snapshot.rss_mb > self.max_memory_mb:
            logger.warning(f"Memory limit exceeded: {snapshot.rss_mb:.1f}MB > {self.max_memory_mb}MB")
            return False
        
        if self.max_memory_percent and snapshot.percent > self.max_memory_percent:
            logger.warning(f"Memory percent limit exceeded: {snapshot.percent:.1f}% > {self.max_memory_percent}%")
            return False
        
        return True
    
    @contextmanager
    def monitor_context(self):
        """Context manager for monitoring a block of code."""
        self.start_monitoring()
        try:
            yield self
        finally:
            self.stop_monitoring()


class MemoryLimitedGenerator:
    """Generator wrapper that respects memory limits."""
    
    def __init__(
        self,
        max_memory_mb: Optional[float] = None,
        gc_threshold_percent: float = 75.0
    ):
        """
        Initialize memory-limited generator.
        
        Args:
            max_memory_mb: Maximum memory limit in MB
            gc_threshold_percent: GC trigger threshold percentage
        """
        self.max_memory_mb = max_memory_mb
        self.gc_threshold = gc_threshold_percent
        self.monitor = MemoryMonitor(max_memory_mb=max_memory_mb)
        
        # Setup automatic GC on warning
        self.monitor.on_warning(self._on_memory_warning)
    
    def _on_memory_warning(self, snapshot: MemorySnapshot):
        """Handle memory warning by triggering GC."""
        if snapshot.percent > self.gc_threshold:
            logger.info("Triggering garbage collection due to high memory usage")
            gc.collect()
    
    def generate_with_backpressure(
        self,
        items: List[Any],
        process_func: Callable[[Any], Any],
        batch_size: int = 10
    ) -> List[Any]:
        """
        Process items with memory-aware backpressure.
        
        Args:
            items: Items to process
            process_func: Function to process each item
            batch_size: Number of items to process before checking memory
            
        Returns:
            List of processed results
        """
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # Check memory before processing
            if self.max_memory_mb:
                snapshot = self.monitor.get_current_usage()
                if snapshot.rss_mb > self.max_memory_mb * 0.9:
                    logger.warning("Approaching memory limit, triggering GC")
                    gc.collect()
                    
                    # Check again
                    snapshot = self.monitor.get_current_usage()
                    if snapshot.rss_mb > self.max_memory_mb * 0.95:
                        raise MemoryError(
                            f"Memory limit approaching: {snapshot.rss_mb:.1f}MB"
                        )
            
            # Process batch
            for item in batch:
                result = process_func(item)
                results.append(result)
            
            # Periodic GC
            if i % (batch_size * 10) == 0:
                gc.collect()
        
        return results


def get_memory_info() -> Dict[str, Any]:
    """Get system memory information."""
    mem = psutil.virtual_memory()
    return {
        'total_gb': round(mem.total / 1024 / 1024 / 1024, 2),
        'available_gb': round(mem.available / 1024 / 1024 / 1024, 2),
        'used_gb': round(mem.used / 1024 / 1024 / 1024, 2),
        'percent': mem.percent,
    }


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"
