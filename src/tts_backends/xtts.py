"""
Coqui XTTS v2 backend for local voice cloning.
"""

import logging
from pathlib import Path
from typing import Optional

from ..exceptions import TTSError
from ..logging_config import get_logger

logger = get_logger(__name__)

try:
    from TTS.api import TTS
    import torch
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False
    logger.warning("TTS package not available, XTTS backend disabled")


class XTTSBackend:
    """Coqui XTTS v2 backend for local TTS with voice cloning."""
    
    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"):
        if not COQUI_AVAILABLE:
            raise ImportError(
                "TTS package required. "
                "Install with: pip install TTS"
            )
        
        self.model_name = model_name
        self.tts = None
        self._load_model()
        
        logger.info("Initialized XTTS v2 backend")
    
    def _load_model(self):
        """Load the TTS model."""
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading XTTS model on {device}...")
            
            self.tts = TTS(self.model_name).to(device)
            logger.info("XTTS model loaded successfully")
            
        except Exception as e:
            raise TTSError(
                f"Failed to load XTTS model: {e}",
                backend="xtts"
            )
    
    def clone_voice(
        self,
        sample_audio_path: str,
        description: Optional[str] = None
    ) -> str:
        """
        XTTS uses reference audio directly, no need to clone.
        Returns the sample path as voice ID.
        
        Args:
            sample_audio_path: Path to voice sample
            description: Ignored for XTTS
            
        Returns:
            Voice ID (sample path)
        """
        path = Path(sample_audio_path).absolute()
        if not path.exists():
            raise TTSError(
                f"Sample audio not found: {sample_audio_path}",
                backend="xtts"
            )
        return str(path)
    
    def generate_speech(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75
    ):
        """
        Generate speech from text using XTTS.
        
        Args:
            text: Text to synthesize
            voice_id: Path to reference audio
            output_path: Output audio file path
            stability: Ignored for XTTS
            similarity_boost: Ignored for XTTS
        """
        try:
            self.tts.tts_to_file(
                text=text,
                speaker_wav=voice_id,
                language="zh" if self._is_chinese(text) else "en",
                file_path=output_path
            )
            
            logger.debug(f"Generated speech saved to {output_path}")
            
        except Exception as e:
            raise TTSError(
                f"TTS generation failed: {e}",
                backend="xtts"
            )
    
    def _is_chinese(self, text: str) -> bool:
        """Check if text is primarily Chinese."""
        if not text:
            return False
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        return chinese_chars > len(text) * 0.3
