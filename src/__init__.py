"""
Novel Audiobook Generator package.
"""

from .generator import AudiobookGenerator, GenerationResult
from .config import Config, TTSConfig, TextConfig, OutputConfig, VoiceConfig
from .text_processor import TextProcessor
from .dialogue_detector import DialogueDetector, DialogueSegment
from .voice_manager import VoiceManager
from .audio_utils import AudioUtils
from .progress_manager import ProgressManager, ProgressState
from .logging_config import setup_logging, get_logger
from .exceptions import (
    AudiobookGeneratorError,
    ConfigurationError,
    TTSError,
    VoiceCloneError,
    TextProcessingError,
    AudioProcessingError,
    FileFormatError,
    APIError,
    RateLimitError,
    ValidationError,
    ResourceNotFoundError,
    get_user_friendly_message
)

__version__ = "1.3.0"
__all__ = [
    'AudiobookGenerator',
    'GenerationResult',
    'Config',
    'TTSConfig',
    'TextConfig',
    'OutputConfig',
    'VoiceConfig',
    'TextProcessor',
    'DialogueDetector',
    'DialogueSegment',
    'VoiceManager',
    'AudioUtils',
    'ProgressManager',
    'ProgressState',
    'setup_logging',
    'get_logger',
    'AudiobookGeneratorError',
    'ConfigurationError',
    'TTSError',
    'VoiceCloneError',
    'TextProcessingError',
    'AudioProcessingError',
    'FileFormatError',
    'APIError',
    'RateLimitError',
    'ValidationError',
    'ResourceNotFoundError',
    'get_user_friendly_message',
]
