"""
TTS backends package.
"""

from .elevenlabs import ElevenLabsBackend
from .xtts import XTTSBackend
from .kokoro import KokoroBackend
from .doubao import DoubaoBackend

__all__ = ['ElevenLabsBackend', 'XTTSBackend', 'KokoroBackend', 'DoubaoBackend']
