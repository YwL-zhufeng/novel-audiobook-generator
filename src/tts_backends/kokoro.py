"""
Kokoro TTS backend - lightweight and fast.
"""

import logging
from typing import Optional

from ..exceptions import TTSError, NotImplementedError
from ..logging_config import get_logger

logger = get_logger(__name__)


class KokoroBackend:
    """Kokoro TTS backend - lightweight, no voice cloning."""
    
    # Default voices available in Kokoro
    DEFAULT_VOICES = [
        "af",  # American female
        "am",  # American male
        "bf",  # British female
        "bm",  # British male
    ]
    
    def __init__(self):
        logger.info("Initialized Kokoro backend")
        logger.warning(
            "Kokoro backend is a placeholder. "
            "For full implementation, install kokoro-onnx package."
        )
    
    def clone_voice(
        self,
        sample_audio_path: str,
        description: Optional[str] = None
    ) -> str:
        """Kokoro doesn't support voice cloning."""
        raise NotImplementedError(
            "Kokoro doesn't support voice cloning. "
            "Use a pre-defined voice instead."
        )
    
    def generate_speech(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75
    ):
        """Generate speech using Kokoro."""
        try:
            # Try to use kokoro-onnx if available
            try:
                from kokoro_onnx import Kokoro
                
                kokoro = Kokoro("kokoro-v0_19.onnx", "voices.json")
                samples, sample_rate = kokoro.create(
                    text, voice=voice_id if voice_id in self.DEFAULT_VOICES else "af"
                )
                
                import wave
                with wave.open(output_path, 'wb') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(sample_rate)
                    f.writeframes(samples.tobytes())
                
                logger.debug(f"Generated speech saved to {output_path}")
                return
                
            except ImportError:
                pass
            
            # Fallback: raise informative error
            raise TTSError(
                "Kokoro backend requires kokoro-onnx package. "
                "Install with: pip install kokoro-onnx",
                backend="kokoro"
            )
            
        except Exception as e:
            if isinstance(e, TTSError):
                raise
            raise TTSError(
                f"TTS generation failed: {e}",
                backend="kokoro"
            )
    
    def list_default_voices(self) -> list:
        """Return list of available default voices."""
        return self.DEFAULT_VOICES.copy()
