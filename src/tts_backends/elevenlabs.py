"""
ElevenLabs TTS backend implementation.
"""

import logging
from typing import Optional

try:
    from elevenlabs import ElevenLabs, VoiceSettings
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ElevenLabsBackend:
    """ElevenLabs API backend for TTS."""
    
    def __init__(self, api_key: Optional[str] = None):
        if not ELEVENLABS_AVAILABLE:
            raise ImportError("elevenlabs package required. Install with: pip install elevenlabs")
        
        self.client = ElevenLabs(api_key=api_key)
        logger.info("Initialized ElevenLabs backend")
    
    def clone_voice(
        self,
        sample_audio_path: str,
        description: Optional[str] = None
    ) -> str:
        """
        Clone a voice from audio sample.
        
        Args:
            sample_audio_path: Path to voice sample
            description: Voice description
            
        Returns:
            Voice ID
        """
        with open(sample_audio_path, 'rb') as f:
            voice = self.client.voices.add(
                name="cloned_voice",
                description=description or "Cloned voice for audiobook",
                files=[f]
            )
        
        return voice.voice_id
    
    def generate_speech(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        model: str = "eleven_multilingual_v2"
    ):
        """
        Generate speech from text.
        
        Args:
            text: Text to synthesize
            voice_id: Voice ID
            output_path: Output audio file path
            stability: Voice stability
            similarity_boost: Similarity boost
            model: TTS model to use
        """
        audio = self.client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model,
            voice_settings=VoiceSettings(
                stability=stability,
                similarity_boost=similarity_boost
            )
        )
        
        # Save audio
        with open(output_path, 'wb') as f:
            for chunk in audio:
                if chunk:
                    f.write(chunk)
        
        logger.debug(f"Generated speech saved to {output_path}")
