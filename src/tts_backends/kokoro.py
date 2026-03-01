"""
Kokoro TTS backend - lightweight and fast.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class KokoroBackend:
    """Kokoro TTS backend - lightweight, no voice cloning."""
    
    def __init__(self):
        logger.info("Initialized Kokoro backend (placeholder)")
        logger.warning("Kokoro backend not fully implemented yet")
    
    def clone_voice(
        self,
        sample_audio_path: str,
        description: Optional[str] = None
    ) -> str:
        """Kokoro doesn't support voice cloning."""
        raise NotImplementedError("Kokoro doesn't support voice cloning")
    
    def generate_speech(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75
    ):
        """Generate speech using Kokoro."""
        # TODO: Implement Kokoro TTS integration
        raise NotImplementedError("Kokoro backend not fully implemented")
