"""
Novel Audiobook Generator package.
"""

from .generator import AudiobookGenerator
from .config import Config, TTSConfig, VoiceConfig, TextConfig, OutputConfig
from .dialogue_detector import DialogueDetector, DialogueSegment
from .text_processor import TextProcessor
from .voice_manager import VoiceManager
from .audio_utils import AudioUtils

__all__ = [
    'AudiobookGenerator',
    'Config',
    'TTSConfig',
    'VoiceConfig', 
    'TextConfig',
    'OutputConfig',
    'DialogueDetector',
    'DialogueSegment',
    'TextProcessor',
    'VoiceManager',
    'AudioUtils',
]
