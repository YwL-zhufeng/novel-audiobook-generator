"""
Health check and monitoring endpoints.
"""

import os
import time
import psutil
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

from .logging_config import get_logger
from .cache import TTSCache
from .task_queue import TaskQueue

logger = get_logger(__name__)


@dataclass
class HealthStatus:
    """Health check status."""
    status: str  # 'healthy', 'degraded', 'unhealthy'
    timestamp: str
    version: str
    uptime_seconds: float
    checks: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status,
            'timestamp': self.timestamp,
            'version': self.version,
            'uptime_seconds': round(self.uptime_seconds, 2),
            'checks': self.checks,
        }


@dataclass
class SystemMetrics:
    """System metrics."""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cpu_percent': round(self.cpu_percent, 2),
            'memory_percent': round(self.memory_percent, 2),
            'memory_available_mb': round(self.memory_available_mb, 2),
            'disk_usage_percent': round(self.disk_usage_percent, 2),
            'disk_free_gb': round(self.disk_free_gb, 2),
        }


class HealthChecker:
    """Health checker for the audiobook generator."""
    
    def __init__(
        self,
        version: str = "1.3.0",
        start_time: Optional[float] = None
    ):
        """
        Initialize health checker.
        
        Args:
            version: Application version
            start_time: Process start time
        """
        self.version = version
        self.start_time = start_time or time.time()
        self._checks: Dict[str, callable] = {}
        
        # Register default checks
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register default health checks."""
        self.register_check("disk_space", self._check_disk_space)
        self.register_check("memory", self._check_memory)
        self.register_check("temp_directory", self._check_temp_directory)
    
    def register_check(self, name: str, check_func: callable):
        """
        Register a health check.
        
        Args:
            name: Check name
            check_func: Function that returns (passed: bool, details: dict)
        """
        self._checks[name] = check_func
    
    def check_health(self) -> HealthStatus:
        """
        Perform health checks.
        
        Returns:
            HealthStatus with overall status and individual check results
        """
        checks = {}
        all_passed = True
        any_failed = False
        
        for name, check_func in self._checks.items():
            try:
                passed, details = check_func()
                checks[name] = {
                    'status': 'pass' if passed else 'fail',
                    'details': details
                }
                
                if not passed:
                    all_passed = False
                    any_failed = True
                    
            except Exception as e:
                checks[name] = {
                    'status': 'error',
                    'error': str(e)
                }
                all_passed = False
                any_failed = True
        
        # Determine overall status
        if all_passed:
            status = 'healthy'
        elif any_failed:
            status = 'unhealthy'
        else:
            status = 'degraded'
        
        return HealthStatus(
            status=status,
            timestamp=datetime.now().isoformat(),
            version=self.version,
            uptime_seconds=time.time() - self.start_time,
            checks=checks
        )
    
    def _check_disk_space(self) -> tuple:
        """Check available disk space."""
        disk = psutil.disk_usage('/')
        
        # Warn if less than 1GB free
        free_gb = disk.free / (1024 ** 3)
        passed = free_gb > 1.0
        
        return passed, {
            'free_gb': round(free_gb, 2),
            'total_gb': round(disk.total / (1024 ** 3), 2),
            'percent_used': round(disk.percent, 2)
        }
    
    def _check_memory(self) -> tuple:
        """Check available memory."""
        mem = psutil.virtual_memory()
        
        # Warn if less than 500MB available
        available_mb = mem.available / (1024 ** 2)
        passed = available_mb > 500
        
        return passed, {
            'available_mb': round(available_mb, 2),
            'total_mb': round(mem.total / (1024 ** 2), 2),
            'percent_used': round(mem.percent, 2)
        }
    
    def _check_temp_directory(self) -> tuple:
        """Check temp directory is writable."""
        import tempfile
        
        try:
            temp_dir = Path(tempfile.gettempdir())
            test_file = temp_dir / '.audiobook_health_check'
            test_file.write_text('test')
            test_file.unlink()
            
            return True, {'temp_dir': str(temp_dir), 'writable': True}
        except Exception as e:
            return False, {'error': str(e), 'writable': False}
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=mem.percent,
            memory_available_mb=mem.available / (1024 ** 2),
            disk_usage_percent=disk.percent,
            disk_free_gb=disk.free / (1024 ** 3)
        )


class MetricsCollector:
    """Collect and expose application metrics."""
    
    def __init__(
        self,
        cache: Optional[TTSCache] = None,
        task_queue: Optional[TaskQueue] = None
    ):
        """
        Initialize metrics collector.
        
        Args:
            cache: TTS cache instance
            task_queue: Task queue instance
        """
        self.cache = cache
        self.task_queue = task_queue
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = {}
    
    def increment_counter(self, name: str, value: int = 1):
        """Increment a counter metric."""
        self._counters[name] = self._counters.get(name, 0) + value
    
    def set_gauge(self, name: str, value: float):
        """Set a gauge metric."""
        self._gauges[name] = value
    
    def record_histogram(self, name: str, value: float):
        """Record a value in a histogram."""
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        metrics = {
            'counters': self._counters.copy(),
            'gauges': self._gauges.copy(),
            'histograms': {
                name: {
                    'count': len(values),
                    'sum': sum(values),
                    'avg': sum(values) / len(values) if values else 0,
                    'min': min(values) if values else 0,
                    'max': max(values) if values else 0,
                }
                for name, values in self._histograms.items()
            },
        }
        
        # Add cache metrics if available
        if self.cache:
            cache_stats = self.cache.get_stats()
            metrics['cache'] = cache_stats.to_dict()
        
        # Add queue metrics if available
        if self.task_queue:
            queue_stats = self.task_queue.get_stats()
            metrics['queue'] = queue_stats.to_dict()
        
        return metrics
    
    def get_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        
        # Counters
        for name, value in self._counters.items():
            lines.append(f'# TYPE {name} counter')
            lines.append(f'{name} {value}')
        
        # Gauges
        for name, value in self._gauges.items():
            lines.append(f'# TYPE {name} gauge')
            lines.append(f'{name} {value}')
        
        # Cache metrics
        if self.cache:
            stats = self.cache.get_stats()
            lines.append('# TYPE audiobook_cache_hits counter')
            lines.append(f'audiobook_cache_hits {stats.hits}')
            lines.append('# TYPE audiobook_cache_misses counter')
            lines.append(f'audiobook_cache_misses {stats.misses}')
            lines.append('# TYPE audiobook_cache_entries gauge')
            lines.append(f'audiobook_cache_entries {stats.entry_count}')
        
        return '\n'.join(lines)


# Global instances
_health_checker: Optional[HealthChecker] = None
_metrics_collector: Optional[MetricsCollector] = None


def init_health_monitoring(
    version: str = "1.3.0",
    cache: Optional[TTSCache] = None,
    task_queue: Optional[TaskQueue] = None
):
    """Initialize global health monitoring."""
    global _health_checker, _metrics_collector
    
    _health_checker = HealthChecker(version=version)
    _metrics_collector = MetricsCollector(cache=cache, task_queue=task_queue)


def get_health_checker() -> Optional[HealthChecker]:
    """Get global health checker."""
    return _health_checker


def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get global metrics collector."""
    return _metrics_collector
