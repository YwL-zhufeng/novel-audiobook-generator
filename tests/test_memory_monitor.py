"""
Unit tests for memory monitoring.
"""

import pytest
import time
from unittest.mock import Mock, patch

from src.memory_monitor import (
    MemoryMonitor,
    MemorySnapshot,
    MemoryStats,
    MemoryLimitedGenerator,
    get_memory_info,
    format_bytes
)


class TestMemorySnapshot:
    """Test MemorySnapshot dataclass."""
    
    def test_snapshot_creation(self):
        """Test creating memory snapshot."""
        from datetime import datetime
        
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            rss_mb=100.5,
            vms_mb=200.0,
            percent=25.0,
            available_mb=3000.0,
            total_mb=4000.0
        )
        
        assert snapshot.rss_mb == 100.5
        assert snapshot.percent == 25.0
    
    def test_snapshot_to_dict(self):
        """Test snapshot serialization."""
        from datetime import datetime
        
        snapshot = MemorySnapshot(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            rss_mb=100.0,
            vms_mb=200.0,
            percent=25.0,
            available_mb=3000.0,
            total_mb=4000.0
        )
        
        data = snapshot.to_dict()
        
        assert data['rss_mb'] == 100.0
        assert data['percent'] == 25.0


class TestMemoryStats:
    """Test MemoryStats."""
    
    def test_initial_stats(self):
        """Test initial stats."""
        stats = MemoryStats()
        
        assert stats.peak_rss_mb == 0.0
        assert stats.get_average_usage() == 0.0
    
    def test_add_snapshot(self):
        """Test adding snapshots."""
        from datetime import datetime
        
        stats = MemoryStats()
        
        snapshot1 = MemorySnapshot(
            timestamp=datetime.now(),
            rss_mb=100.0,
            vms_mb=200.0,
            percent=25.0,
            available_mb=3000.0,
            total_mb=4000.0
        )
        
        snapshot2 = MemorySnapshot(
            timestamp=datetime.now(),
            rss_mb=150.0,
            vms_mb=250.0,
            percent=30.0,
            available_mb=2900.0,
            total_mb=4000.0
        )
        
        stats.add_snapshot(snapshot1)
        stats.add_snapshot(snapshot2)
        
        assert stats.peak_rss_mb == 150.0
        assert stats.peak_percent == 30.0
        assert stats.get_average_usage() == 125.0


class TestMemoryMonitor:
    """Test MemoryMonitor."""
    
    @pytest.fixture
    def monitor(self):
        """Create memory monitor."""
        return MemoryMonitor(
            max_memory_mb=1000.0,
            check_interval_seconds=0.1
        )
    
    def test_get_current_usage(self, monitor):
        """Test getting current memory usage."""
        snapshot = monitor.get_current_usage()
        
        assert snapshot.rss_mb > 0
        assert snapshot.total_mb > 0
        assert 0 <= snapshot.percent <= 100
    
    def test_check_limits(self, monitor):
        """Test limit checking."""
        # Should be within limits initially
        assert monitor.check_limits() is True
    
    def test_callbacks(self, monitor):
        """Test callback registration."""
        warning_called = []
        critical_called = []
        
        def on_warning(snapshot):
            warning_called.append(True)
        
        def on_critical(snapshot):
            critical_called.append(True)
        
        monitor.on_warning(on_warning)
        monitor.on_critical(on_critical)
        
        # Verify callbacks are registered
        assert len(monitor._callbacks['warning']) == 1
        assert len(monitor._callbacks['critical']) == 1
    
    def test_start_stop_monitoring(self, monitor):
        """Test starting and stopping monitoring."""
        monitor.start_monitoring()
        assert monitor._monitoring is True
        
        time.sleep(0.2)  # Let it run briefly
        
        monitor.stop_monitoring()
        assert monitor._monitoring is False
    
    def test_get_stats(self, monitor):
        """Test getting statistics."""
        # Add a snapshot
        snapshot = monitor.get_current_usage()
        monitor._stats.add_snapshot(snapshot)
        
        stats = monitor.get_stats()
        
        assert stats.peak_rss_mb >= snapshot.rss_mb


class TestMemoryLimitedGenerator:
    """Test MemoryLimitedGenerator."""
    
    def test_initialization(self):
        """Test generator initialization."""
        gen = MemoryLimitedGenerator(
            max_memory_mb=500.0,
            gc_threshold_percent=70.0
        )
        
        assert gen.max_memory_mb == 500.0
        assert gen.gc_threshold == 70.0
    
    def test_generate_with_backpressure(self):
        """Test backpressure generation."""
        gen = MemoryLimitedGenerator(max_memory_mb=10000.0)
        
        items = list(range(10))
        
        def process_func(item):
            return item * 2
        
        results = gen.generate_with_backpressure(
            items,
            process_func,
            batch_size=3
        )
        
        assert len(results) == 10
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_get_memory_info(self):
        """Test getting memory info."""
        info = get_memory_info()
        
        assert 'total_gb' in info
        assert 'available_gb' in info
        assert 'used_gb' in info
        assert 'percent' in info
        
        assert info['total_gb'] > 0
        assert 0 <= info['percent'] <= 100
    
    def test_format_bytes(self):
        """Test byte formatting."""
        assert format_bytes(0) == "0.00 B"
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
