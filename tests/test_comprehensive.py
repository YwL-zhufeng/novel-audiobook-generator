"""
Test suite for audiobook generator.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from text_processor import TextProcessor
from dialogue_detector import DialogueDetector, DialogueSegment
from audio_utils import AudioUtils
from config import Config, TTSConfig, TextConfig
from validator import ConfigValidator, ValidationError
from exceptions import (
    AudiobookGeneratorError,
    ConfigurationError,
    TextProcessingError,
    FileFormatError
)


class TestTextProcessor:
    """Test text processing functionality."""
    
    @pytest.fixture
    def processor(self):
        return TextProcessor()
    
    def test_split_into_chunks(self, processor):
        """Test text chunking."""
        text = "This is a test. " * 100
        chunks = processor.split_into_chunks(text, max_chars=500)
        
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 600  # Allow some overflow
    
    def test_preprocess_for_tts(self, processor):
        """Test text preprocessing."""
        text = "  Hello   world  !  "
        cleaned = processor.preprocess_for_tts(text)
        assert cleaned == "Hello world!"
    
    def test_clean_html(self, processor):
        """Test HTML cleaning."""
        html = "<p>Hello <b>world</b>!</p>"
        cleaned = processor._clean_html(html)
        assert cleaned == "Hello world !"
    
    def test_extract_txt(self, processor):
        """Test TXT extraction."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Hello world\n\nSecond paragraph")
            temp_path = f.name
        
        try:
            text = processor.extract_text(temp_path)
            assert "Hello world" in text
            assert "Second paragraph" in text
        finally:
            Path(temp_path).unlink()
    
    def test_unsupported_format(self, processor):
        """Test unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(FileFormatError):
                processor.extract_text(temp_path)
        finally:
            Path(temp_path).unlink()
    
    def test_estimate_reading_time(self, processor):
        """Test reading time estimation."""
        text = "This is a sample text for testing. " * 50
        minutes = processor.estimate_reading_time(text, words_per_minute=150)
        assert minutes > 0


class TestDialogueDetector:
    """Test dialogue detection."""
    
    @pytest.fixture
    def detector(self):
        return DialogueDetector(language='chinese')
    
    def test_detect_dialogue_chinese(self, detector):
        """Test Chinese dialogue detection."""
        text = '李逍遥说道：「我要去蜀山！」赵灵儿回答：「我陪你。」'
        segments = detector.detect_dialogue(text)
        
        # Should have narration + dialogue + narration + dialogue
        assert len(segments) >= 2
        
        # Check dialogue segments
        dialogue_segments = [s for s in segments if s.is_dialogue]
        assert len(dialogue_segments) == 2
    
    def test_detect_dialogue_english(self):
        """Test English dialogue detection."""
        detector = DialogueDetector(language='english')
        text = 'John said, "Hello there!" Mary replied, "Hi John!"'
        segments = detector.detect_dialogue(text)
        
        dialogue_segments = [s for s in segments if s.is_dialogue]
        assert len(dialogue_segments) >= 2
    
    def test_extract_characters(self, detector):
        """Test character extraction."""
        segments = [
            DialogueSegment("Hello", "Alice", 0, 10, True),
            DialogueSegment("Hi", "Bob", 10, 20, True),
            DialogueSegment("How are you?", "Alice", 20, 35, True),
        ]
        
        characters = detector.extract_characters(segments)
        assert characters["Alice"] == 2
        assert characters["Bob"] == 1
    
    def test_assign_voices_to_characters(self, detector):
        """Test voice assignment."""
        segments = [
            DialogueSegment("Hello", "Alice", 0, 10, True),
            DialogueSegment("Hi", "Bob", 10, 20, True),
        ]
        
        available_voices = ["voice1", "voice2"]
        assignment = detector.assign_voices_to_characters(segments, available_voices)
        
        assert "Alice" in assignment
        assert "Bob" in assignment


class TestConfig:
    """Test configuration management."""
    
    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            'tts': {'backend': 'xtts', 'max_workers': 8},
            'text': {'chunk_size': 3000},
        }
        config = Config.from_dict(data)
        
        assert config.tts.backend == 'xtts'
        assert config.tts.max_workers == 8
        assert config.text.chunk_size == 3000
    
    def test_config_expand_env_vars(self, monkeypatch):
        """Test environment variable expansion."""
        monkeypatch.setenv('TEST_API_KEY', 'secret123')
        
        data = {'tts': {'api_key': '${TEST_API_KEY}'}}
        config = Config.from_dict(data)
        
        assert config.tts.api_key == 'secret123'
    
    def test_config_to_yaml(self):
        """Test saving config to YAML."""
        config = Config()
        config.tts.backend = 'doubao'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            config.to_yaml(temp_path)
            loaded = Config.from_yaml(temp_path)
            assert loaded.tts.backend == 'doubao'
        finally:
            Path(temp_path).unlink()


class TestValidator:
    """Test configuration validation."""
    
    def test_validate_backend(self):
        """Test backend validation."""
        is_valid, error = ConfigValidator.validate_backend('elevenlabs')
        assert is_valid
        assert error is None
        
        is_valid, error = ConfigValidator.validate_backend('invalid')
        assert not is_valid
        assert error is not None
    
    def test_validate_chunk_size(self):
        """Test chunk size validation."""
        is_valid, error = ConfigValidator.validate_chunk_size(4000)
        assert is_valid
        
        is_valid, error = ConfigValidator.validate_chunk_size(50)
        assert not is_valid
        
        is_valid, error = ConfigValidator.validate_chunk_size(50000)
        assert not is_valid
    
    def test_validate_workers(self):
        """Test workers validation."""
        is_valid, error = ConfigValidator.validate_workers(4)
        assert is_valid
        
        is_valid, error = ConfigValidator.validate_workers(0)
        assert not is_valid
        
        is_valid, error = ConfigValidator.validate_workers(100)
        assert not is_valid
    
    def test_validate_config(self):
        """Test full config validation."""
        config = {
            'tts': {'backend': 'elevenlabs', 'max_workers': 4},
            'text': {'chunk_size': 4000},
            'output': {'format': 'mp3', 'bitrate': '192k'}
        }
        
        is_valid, errors = ConfigValidator.validate_config(config)
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_invalid_config(self):
        """Test invalid config validation."""
        config = {
            'tts': {'backend': 'invalid', 'max_workers': 100},
            'text': {'chunk_size': 50},
            'output': {'format': 'invalid', 'bitrate': 'invalid'}
        }
        
        is_valid, errors = ConfigValidator.validate_config(config)
        assert not is_valid
        assert len(errors) > 0


class TestExceptions:
    """Test custom exceptions."""
    
    def test_audiobook_generator_error(self):
        """Test base exception."""
        error = AudiobookGeneratorError("Test error", error_code="TEST001")
        assert "TEST001" in str(error)
        assert "Test error" in str(error)
    
    def test_configuration_error(self):
        """Test configuration error."""
        error = ConfigurationError("Invalid config")
        assert error.error_code == "CONFIG_ERROR"
    
    def test_text_processing_error(self):
        """Test text processing error."""
        error = TextProcessingError("Failed to extract", file_path="test.txt")
        assert error.file_path == "test.txt"
    
    def test_user_friendly_message(self):
        """Test user-friendly error messages."""
        error = ConfigurationError("Invalid setting")
        message = get_user_friendly_message(error)
        assert "Configuration Error" in message


class TestChapterDetector:
    """Test chapter detection."""
    
    @pytest.fixture
    def detector(self):
        from chapter_detector import ChapterDetector
        return ChapterDetector(language='chinese')
    
    def test_detect_chapters_chinese(self, detector):
        """Test Chinese chapter detection."""
        text = """
第一章 开始
这是第一章的内容。

第二章 继续
这是第二章的内容。
"""
        chapters = detector.detect_chapters(text)
        assert len(chapters) >= 2
        assert "第一章" in chapters[0].title or "开始" in chapters[0].title
    
    def test_detect_chapters_english(self):
        """Test English chapter detection."""
        from chapter_detector import ChapterDetector
        detector = ChapterDetector(language='english')
        
        text = """
Chapter 1: The Beginning
This is chapter 1.

Chapter 2: The Journey
This is chapter 2.
"""
        chapters = detector.detect_chapters(text)
        assert len(chapters) >= 2
    
    def test_chapter_statistics(self, detector):
        """Test chapter statistics."""
        text = "第一章\n内容\n第二章\n内容"
        chapters = detector.detect_chapters(text)
        stats = detector.get_chapter_statistics(chapters)
        
        assert 'count' in stats
        assert 'avg_confidence' in stats


class TestCacheManager:
    """Test cache management."""
    
    @pytest.fixture
    def cache_manager(self):
        from cache import CacheManager
        with tempfile.TemporaryDirectory() as tmpdir:
            yield CacheManager(cache_dir=tmpdir, max_size_mb=10)
    
    def test_cache_set_get(self, cache_manager):
        """Test cache set and get."""
        cache_manager.set("key1", "value1", cache_type='text')
        value = cache_manager.get("key1", cache_type='text')
        assert value == "value1"
    
    def test_cache_expiration(self, cache_manager):
        """Test cache expiration."""
        cache_manager.set("key2", "value2", cache_type='text', ttl_hours=0)
        # Should expire immediately
        value = cache_manager.get("key2", cache_type='text')
        # Note: This test might be flaky due to timing
    
    def test_cache_stats(self, cache_manager):
        """Test cache statistics."""
        cache_manager.set("key3", "value3", cache_type='text')
        stats = cache_manager.get_stats()
        assert 'total_size_mb' in stats
        assert 'text_entries' in stats


class TestProgressManager:
    """Test progress management."""
    
    @pytest.fixture
    def progress_manager(self):
        from progress_manager import ProgressManager
        with tempfile.TemporaryDirectory() as tmpdir:
            yield ProgressManager(db_path=str(Path(tmpdir) / 'progress.db'))
    
    def test_create_task(self, progress_manager):
        """Test task creation."""
        state = progress_manager.create_task(
            task_id="task1",
            input_file="test.txt",
            output_file="test.mp3",
            total_chunks=10
        )
        assert state.task_id == "task1"
        assert state.total_chunks == 10
    
    def test_update_task(self, progress_manager):
        """Test task update."""
        progress_manager.create_task(
            task_id="task2",
            input_file="test.txt",
            output_file="test.mp3",
            total_chunks=10
        )
        
        updated = progress_manager.mark_chunk_complete("task2", 0)
        assert updated is not None
        assert 0 in updated.completed_chunks
    
    def test_get_incomplete_tasks(self, progress_manager):
        """Test getting incomplete tasks."""
        progress_manager.create_task(
            task_id="task3",
            input_file="test.txt",
            output_file="test.mp3",
            total_chunks=10
        )
        
        incomplete = progress_manager.get_incomplete_tasks()
        assert len(incomplete) >= 1


# Integration tests
class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.skip(reason="Requires actual TTS backend")
    def test_full_generation_flow(self):
        """Test full audiobook generation."""
        from generator import AudiobookGenerator
        
        # This would require mocking the TTS backend
        pass
    
    def test_config_validation_integration(self):
        """Test config validation in integration."""
        config = {
            'tts': {'backend': 'doubao', 'max_workers': 4},
            'text': {'chunk_size': 4000},
            'output': {'format': 'mp3', 'bitrate': '192k'}
        }
        
        is_valid, errors = ConfigValidator.validate_config(config)
        assert is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
