"""
Test suite for audiobook generator.
"""

import unittest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from text_processor import TextProcessor
from audio_utils import AudioUtils


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


class TestAudioUtils(unittest.TestCase):
    """Test audio utilities."""
    
    def setUp(self):
        self.utils = AudioUtils()
    
    def test_add_silence(self):
        """Test adding silence to audio."""
        # This would require a test audio file
        pass


class TestAudiobookGenerator(unittest.TestCase):
    """Test main audiobook generator."""
    
    def test_initialization(self):
        """Test generator initialization."""
        # Would require API keys
        pass


if __name__ == "__main__":
    unittest.main()
