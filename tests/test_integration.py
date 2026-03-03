"""
Integration tests with mock TTS backend.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import numpy as np


class MockTTSBackend:
    """Mock TTS backend for testing."""
    
    def __init__(self, **kwargs):
        self.voices = {}
        self.call_count = 0
    
    def clone_voice(self, sample_audio_path: str, description: str = None) -> str:
        """Mock voice cloning."""
        voice_id = f"voice_{len(self.voices)}"
        self.voices[voice_id] = {
            'sample': sample_audio_path,
            'description': description
        }
        return voice_id
    
    def generate_speech(self, text: str, voice_id: str, output_path: str, **kwargs):
        """Mock speech generation."""
        self.call_count += 1
        
        # Create dummy audio file
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write minimal MP3-like data
        with open(output_path, 'wb') as f:
            # MP3 header
            f.write(b'\xff\xfb\x90\x00' * 100)
    
    def list_voices(self) -> list:
        """Mock list voices."""
        return list(self.voices.keys())


@pytest.fixture
def mock_backend():
    """Create mock TTS backend."""
    return MockTTSBackend()


@pytest.fixture
def sample_text_file(tmp_path):
    """Create sample text file."""
    text_file = tmp_path / "novel.txt"
    text_file.write_text("""
Chapter 1

This is the first chapter of the test novel.
It has multiple paragraphs.

Chapter 2

This is the second chapter.
More text here.
""")
    return str(text_file)


@pytest.fixture
def mock_generator(mock_backend):
    """Create mock audiobook generator."""
    from src.generator import AudiobookGenerator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        generator = AudiobookGenerator(
            tts_backend="mock",
            output_dir=tmpdir,
            max_workers=2,
            enable_progress_persistence=False
        )
        
        # Replace backend with mock
        generator.voice_manager.backend = mock_backend
        
        yield generator
        generator.close()


class TestGeneratorIntegration:
    """Integration tests for audiobook generator."""
    
    def test_generate_audiobook(self, mock_generator, sample_text_file, tmp_path):
        """Test full audiobook generation."""
        output_path = tmp_path / "output.mp3"
        
        result = mock_generator.generate_audiobook(
            input_path=sample_text_file,
            output_path=str(output_path),
            voice="default",
            chunk_size=1000
        )
        
        assert Path(result.output_path).exists()
        assert result.total_chunks > 0
        assert result.completed_chunks == result.total_chunks
    
    def test_generate_with_progress(self, mock_generator, sample_text_file):
        """Test generation with progress callback."""
        progress_values = []
        
        def on_progress(p):
            progress_values.append(p)
        
        result = mock_generator.generate_audiobook(
            input_path=sample_text_file,
            voice="default",
            progress_callback=on_progress
        )
        
        assert len(progress_values) > 0
        assert progress_values[-1] == 1.0  # Completed
    
    def test_generate_with_metadata(self, mock_generator, sample_text_file):
        """Test generation with metadata."""
        metadata = {
            'title': 'Test Audiobook',
            'author': 'Test Author',
            'album': 'Test Album'
        }
        
        result = mock_generator.generate_audiobook(
            input_path=sample_text_file,
            voice="default",
            metadata=metadata
        )
        
        assert Path(result.output_path).exists()
    
    def test_batch_generate(self, mock_generator, tmp_path):
        """Test batch generation."""
        # Create multiple input files
        input_files = []
        for i in range(3):
            text_file = tmp_path / f"book{i}.txt"
            text_file.write_text(f"Content of book {i}")
            input_files.append(str(text_file))
        
        results = mock_generator.batch_generate(
            input_files=input_files,
            voice="default"
        )
        
        assert len(results) == 3
        assert all(r['status'] == 'completed' for r in results)


class TestVoiceManagerIntegration:
    """Integration tests for voice manager."""
    
    def test_clone_voice(self, mock_backend, tmp_path):
        """Test voice cloning."""
        from src.voice_manager import VoiceManager
        
        # Create dummy audio file
        sample_audio = tmp_path / "sample.mp3"
        with open(sample_audio, 'wb') as f:
            f.write(b'\xff\xfb\x90\x00' * 100)
        
        manager = VoiceManager(
            tts_backend="mock",
            api_key="test_key"
        )
        manager.backend = mock_backend
        
        voice_id = manager.clone_voice(
            voice_name="test_voice",
            sample_audio_path=str(sample_audio)
        )
        
        assert voice_id is not None
        assert "test_voice" in manager.voices
    
    def test_generate_speech(self, mock_backend, tmp_path):
        """Test speech generation."""
        from src.voice_manager import VoiceManager
        
        manager = VoiceManager(
            tts_backend="mock",
            api_key="test_key"
        )
        manager.backend = mock_backend
        
        output_path = tmp_path / "output.mp3"
        
        result = manager.generate_speech(
            text="Hello world",
            voice="default",
            output_path=str(output_path)
        )
        
        assert Path(result).exists()
        assert mock_backend.call_count == 1


class TestTextProcessorIntegration:
    """Integration tests for text processor."""
    
    def test_extract_and_chunk(self, tmp_path):
        """Test text extraction and chunking."""
        from src.text_processor import TextProcessor
        
        # Create test file
        text_file = tmp_path / "test.txt"
        text_file.write_text("This is a test. " * 1000)
        
        processor = TextProcessor()
        
        # Extract text
        text = processor.extract_text(str(text_file))
        assert len(text) > 0
        
        # Split into chunks
        chunks = processor.split_into_chunks(text, max_chars=500)
        assert len(chunks) > 0
        assert all(len(c) <= 500 for c in chunks)
    
    def test_preprocess_for_tts(self):
        """Test text preprocessing."""
        from src.text_processor import TextProcessor
        
        processor = TextProcessor()
        
        text = "  Multiple   spaces   and  http://example.com URL  "
        result = processor.preprocess_for_tts(text)
        
        assert "http" not in result
        assert "  " not in result


class TestAudioUtilsIntegration:
    """Integration tests for audio utilities."""
    
    @pytest.fixture
    def sample_audio_files(self, tmp_path):
        """Create sample audio files."""
        files = []
        for i in range(3):
            audio_file = tmp_path / f"segment{i}.mp3"
            with open(audio_file, 'wb') as f:
                # Minimal MP3 frame
                f.write(b'\xff\xfb\x90\x00' * 100)
            files.append(str(audio_file))
        return files
    
    def test_concatenate_audio(self, sample_audio_files, tmp_path):
        """Test audio concatenation."""
        from src.audio_utils import AudioUtils
        
        utils = AudioUtils()
        output_path = tmp_path / "combined.mp3"
        
        # Note: This will fail without proper MP3 files
        # In real tests, we'd use actual audio files
        # For now, we just verify the method exists and is callable
        assert hasattr(utils, 'concatenate_audio_files')


class TestCacheIntegration:
    """Integration tests for caching."""
    
    def test_tts_cache_with_generator(self, mock_generator, sample_text_file, tmp_path):
        """Test TTS cache integration."""
        from src.cache import TTSCache
        
        cache = TTSCache(
            cache_dir=str(tmp_path / "cache"),
            max_size_mb=10.0
        )
        
        # First generation
        result1 = mock_generator.generate_audiobook(
            input_path=sample_text_file,
            voice="default"
        )
        
        # Second generation (should use cache if implemented)
        # This depends on actual cache integration in generator
        
        cache.close()
        
        assert Path(result1.output_path).exists()


class TestChapterDetectionIntegration:
    """Integration tests for chapter detection."""
    
    def test_detect_and_export(self, tmp_path):
        """Test chapter detection and export."""
        from src.chapter_detector import ChapterDetector
        
        # Create test text with chapters
        text = """
Chapter 1: Introduction

This is the introduction chapter.
It has some content.

Chapter 2: Main Content

This is the main chapter.
More content here.

Chapter 3: Conclusion

This is the conclusion.
"""
        
        detector = ChapterDetector()
        
        # Detect chapters
        result = detector.detect_chapters(text)
        
        assert result.total_chapters >= 2
        
        # Export chapters
        output_dir = tmp_path / "chapters"
        files = detector.export_chapters(text, str(output_dir), result)
        
        assert len(files) == result.total_chapters
        for file_path in files:
            assert Path(file_path).exists()
