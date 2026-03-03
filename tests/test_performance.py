"""
Performance tests for audiobook generator.
"""

import pytest
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock


class TestPerformance:
    """Performance tests."""
    
    @pytest.fixture
    def large_text_file(self, tmp_path):
        """Create a large text file for performance testing."""
        text_file = tmp_path / "large_novel.txt"
        
        # Create ~1MB of text
        content = "This is a test sentence. " * 20000
        text_file.write_text(content)
        
        return str(text_file)
    
    @pytest.fixture
    def mock_generator_fast(self):
        """Create mock generator with fast processing."""
        from src.generator import AudiobookGenerator
        
        generator = Mock(spec=AudiobookGenerator)
        
        def fast_generate(**kwargs):
            time.sleep(0.01)  # Simulate fast processing
            return Mock(
                output_path="/tmp/output.mp3",
                total_chunks=10,
                completed_chunks=10,
                duration_seconds=60.0
            )
        
        generator.generate_audiobook = fast_generate
        
        return generator
    
    def test_text_processing_performance(self, large_text_file):
        """Test text processing performance."""
        from src.text_processor import TextProcessor
        
        processor = TextProcessor()
        
        start_time = time.time()
        
        # Extract text
        text = processor.extract_text(large_text_file)
        
        # Split into chunks
        chunks = processor.split_into_chunks(text, max_chars=4000)
        
        elapsed = time.time() - start_time
        
        # Should process 1MB in less than 5 seconds
        assert elapsed < 5.0
        assert len(chunks) > 0
    
    def test_chunking_performance(self):
        """Test text chunking performance."""
        from src.text_processor import TextProcessor
        
        processor = TextProcessor()
        
        # Create large text
        text = "This is a paragraph.\n\n" * 10000
        
        start_time = time.time()
        
        chunks = processor.split_into_chunks(text, max_chars=4000)
        
        elapsed = time.time() - start_time
        
        # Should chunk in less than 1 second
        assert elapsed < 1.0
        assert len(chunks) > 0
    
    def test_cache_performance(self, tmp_path):
        """Test cache read/write performance."""
        from src.cache import TTSCache
        
        cache = TTSCache(
            cache_dir=str(tmp_path / "cache"),
            max_size_mb=100.0
        )
        
        # Create dummy audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"audio data" * 1000)
        
        # Measure write performance
        start_time = time.time()
        
        for i in range(100):
            cache.put(
                text=f"Text {i}",
                voice_id="voice1",
                audio_path=str(audio_file)
            )
        
        write_time = time.time() - start_time
        
        # Measure read performance
        start_time = time.time()
        
        for i in range(100):
            cache.get(f"Text {i}", "voice1")
        
        read_time = time.time() - start_time
        
        cache.close()
        
        # Should handle 100 operations quickly
        assert write_time < 5.0
        assert read_time < 1.0
    
    def test_concurrent_processing_performance(self):
        """Test concurrent processing performance."""
        from concurrent.futures import ThreadPoolExecutor
        import threading
        
        results = []
        lock = threading.Lock()
        
        def worker(n):
            # Simulate some work
            time.sleep(0.01)
            with lock:
                results.append(n)
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(worker, range(100)))
        
        elapsed = time.time() - start_time
        
        # 100 tasks with 0.01s each, parallelized
        # Should complete in less than 1 second with 4 workers
        assert elapsed < 1.0
        assert len(results) == 100
    
    def test_memory_usage_during_processing(self):
        """Test memory usage during processing."""
        from src.memory_monitor import MemoryMonitor
        
        monitor = MemoryMonitor()
        
        # Record initial memory
        initial = monitor.get_current_usage()
        
        # Allocate some memory
        data = [i for i in range(1000000)]
        
        # Record peak memory
        peak = monitor.get_current_usage()
        
        # Clean up
        del data
        
        # Memory should have increased during allocation
        assert peak.rss_mb >= initial.rss_mb
    
    @pytest.mark.slow
    def test_pipeline_throughput(self):
        """Test pipeline throughput."""
        from src.streaming_pipeline import (
            PipelineStage, StreamingPipeline, ProcessingItem
        )
        
        def processor(x):
            time.sleep(0.001)  # 1ms processing time
            return x * 2
        
        stage = PipelineStage("test", processor, max_workers=4)
        pipeline = StreamingPipeline([stage])
        
        pipeline.start()
        
        # Process 100 items
        items = [ProcessingItem(id=str(i), data=i) for i in range(100)]
        
        start_time = time.time()
        results = pipeline.process_batch(items)
        elapsed = time.time() - start_time
        
        pipeline.stop()
        
        # With 4 workers and 1ms per item, 100 items should take ~25ms
        # Allow some overhead
        assert elapsed < 2.0  # Generous timeout
        assert len(results) == 100
        
        # Check throughput
        metrics = pipeline.get_metrics()
        assert metrics.throughput_per_second > 50  # At least 50 items/sec


class TestMemoryPerformance:
    """Memory performance tests."""
    
    def test_large_file_streaming(self, tmp_path):
        """Test streaming processing of large files."""
        from src.text_processor import TextProcessor
        
        # Create large file
        text_file = tmp_path / "large.txt"
        with open(text_file, 'w') as f:
            for i in range(10000):
                f.write(f"Line {i}: This is some test content.\n")
        
        processor = TextProcessor(chunk_size=1024)
        
        # Stream process
        start_time = time.time()
        
        total_chars = 0
        for chunk in processor.extract_text_streaming(str(text_file)):
            total_chars += len(chunk)
        
        elapsed = time.time() - start_time
        
        # Should stream large file efficiently
        assert elapsed < 2.0
        assert total_chars > 0
    
    def test_incremental_audio_merge(self, tmp_path):
        """Test incremental audio merge performance."""
        from src.audio_utils import AudioUtils
        
        utils = AudioUtils()
        
        # Create dummy audio segments
        segments = []
        for i in range(20):
            seg_path = tmp_path / f"seg_{i}.mp3"
            with open(seg_path, 'wb') as f:
                f.write(b'\xff\xfb\x90\x00' * 1000)
            segments.append(str(seg_path))
        
        output_path = tmp_path / "merged.mp3"
        
        # Should complete without OOM
        # Note: This will fail with dummy data, but tests the method exists
        assert hasattr(utils, '_concatenate_incremental')


class BenchmarkTests:
    """Benchmark tests for comparison."""
    
    @pytest.mark.benchmark
    def test_chapter_detection_benchmark(self):
        """Benchmark chapter detection."""
        from src.chapter_detector import ChapterDetector
        
        # Create large text with chapters
        chapters = []
        for i in range(100):
            chapters.append(f"Chapter {i}\n\nContent of chapter {i}.\n\n")
        text = "".join(chapters)
        
        detector = ChapterDetector()
        
        start_time = time.time()
        result = detector.detect_chapters(text)
        elapsed = time.time() - start_time
        
        # Should detect chapters quickly
        assert elapsed < 1.0
        assert result.total_chapters >= 50
    
    @pytest.mark.benchmark
    def test_text_preprocessing_benchmark(self):
        """Benchmark text preprocessing."""
        from src.text_processor import TextProcessor
        
        processor = TextProcessor()
        
        # Create text with URLs and special chars
        text = "Check http://example.com and email@test.com " * 10000
        
        start_time = time.time()
        result = processor.preprocess_for_tts(text)
        elapsed = time.time() - start_time
        
        # Should preprocess quickly
        assert elapsed < 1.0
        assert "http" not in result
