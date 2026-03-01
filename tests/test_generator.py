"""
Test suite for audiobook generator.
"""

import unittest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from text_processor import TextProcessor
from dialogue_detector import DialogueDetector, DialogueSegment
from audio_utils import AudioUtils
from config import Config, TTSConfig, TextConfig


class TestTextProcessor(unittest.TestCase):
    """Test text processing functionality."""
    
    def setUp(self):
        self.processor = TextProcessor()
    
    def test_split_into_chunks(self):
        """Test text chunking."""
        text = "This is a test. " * 100
        chunks = self.processor.split_into_chunks(text, max_chars=500)
        
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 600)  # Allow some overflow
    
    def test_preprocess_for_tts(self):
        """Test text preprocessing."""
        text = "  Hello   world  !  "
        cleaned = self.processor.preprocess_for_tts(text)
        self.assertEqual(cleaned, "Hello world!")
    
    def test_clean_html(self):
        """Test HTML cleaning."""
        html = "<p>Hello <b>world</b>!</p>"
        cleaned = self.processor._clean_html(html)
        self.assertEqual(cleaned, "Hello world !")


class TestDialogueDetector(unittest.TestCase):
    """Test dialogue detection."""
    
    def setUp(self):
        self.detector = DialogueDetector(language='chinese')
    
    def test_detect_dialogue_chinese(self):
        """Test Chinese dialogue detection."""
        text = '李逍遥说道：「我要去蜀山！」赵灵儿回答：「我陪你。」'
        segments = self.detector.detect_dialogue(text)
        
        # Should have narration + dialogue + narration + dialogue
        self.assertGreaterEqual(len(segments), 2)
        
        # Check dialogue segments
        dialogue_segments = [s for s in segments if s.is_dialogue]
        self.assertEqual(len(dialogue_segments), 2)
    
    def test_detect_dialogue_english(self):
        """Test English dialogue detection."""
        detector = DialogueDetector(language='english')
        text = 'John said, "Hello there!" Mary replied, "Hi John!"'
        segments = detector.detect_dialogue(text)
        
        dialogue_segments = [s for s in segments if s.is_dialogue]
        self.assertGreaterEqual(len(dialogue_segments), 2)
    
    def test_extract_characters(self):
        """Test character extraction."""
        segments = [
            DialogueSegment("Hello", "Alice", 0, 10, True),
            DialogueSegment("Hi", "Bob", 10, 20, True),
            DialogueSegment("How are you?", "Alice", 20, 35, True),
        ]
        
        characters = self.detector.extract_characters(segments)
        self.assertEqual(characters["Alice"], 2)
        self.assertEqual(characters["Bob"], 1)


class TestConfig(unittest.TestCase):
    """Test configuration management."""
    
    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            'tts': {'backend': 'xtts', 'max_workers': 8},
            'text': {'chunk_size': 3000},
        }
        config = Config.from_dict(data)
        
        self.assertEqual(config.tts.backend, 'xtts')
        self.assertEqual(config.tts.max_workers, 8)
        self.assertEqual(config.text.chunk_size, 3000)
    
    def test_config_expand_env_vars(self):
        """Test environment variable expansion."""
        import os
        os.environ['TEST_API_KEY'] = 'secret123'
        
        data = {'tts': {'api_key': '${TEST_API_KEY}'}}
        config = Config.from_dict(data)
        
        self.assertEqual(config.tts.api_key, 'secret123')


class TestAudioUtils(unittest.TestCase):
    """Test audio utilities."""
    
    def setUp(self):
        try:
            self.utils = AudioUtils()
            self.pydub_available = True
        except ImportError:
            self.pydub_available = False
    
    def test_add_silence(self):
        """Test adding silence to audio."""
        if not self.pydub_available:
            self.skipTest("pydub not available")
        
        # Would require a test audio file
        pass


class TestAudiobookGenerator(unittest.TestCase):
    """Test main audiobook generator."""
    
    def test_initialization(self):
        """Test generator initialization."""
        # Would require API keys or local models
        pass


if __name__ == "__main__":
    unittest.main()
