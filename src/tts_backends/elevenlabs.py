"""
ElevenLabs TTS backend implementation with retry support.
"""

import time
import logging
from typing import Optional
from functools import wraps

from ..exceptions import TTSError, APIError, RateLimitError
from ..logging_config import get_logger

logger = get_logger(__name__)

try:
    from elevenlabs import ElevenLabs, VoiceSettings
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    logger.warning("elevenlabs package not available")


def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator to retry on rate limit errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    if 'rate limit' in error_str or '429' in error_str:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(f"Rate limited, retrying in {delay}s...")
                            time.sleep(delay)
                            continue
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ElevenLabsBackend:
    """ElevenLabs API backend for TTS."""
    
    def __init__(self, api_key: Optional[str] = None):
        if not ELEVENLABS_AVAILABLE:
            raise ImportError(
                "elevenlabs package required. "
                "Install with: pip install elevenlabs"
            )
        
        if not api_key:
            raise TTSError(
                "ElevenLabs API key is required",
                backend="elevenlabs"
            )
        
        try:
            self.client = ElevenLabs(api_key=api_key)
            logger.info("Initialized ElevenLabs backend")
        except Exception as e:
            raise TTSError(
                f"Failed to initialize ElevenLabs client: {e}",
                backend="elevenlabs"
            )
    
    @retry_on_rate_limit(max_retries=3)
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
        try:
            with open(sample_audio_path, 'rb') as f:
                voice = self.client.voices.add(
                    name="cloned_voice",
                    description=description or "Cloned voice for audiobook",
                    files=[f]
                )
            
            return voice.voice_id
            
        except Exception as e:
            error_str = str(e)
            if 'rate limit' in error_str.lower():
                raise RateLimitError("ElevenLabs rate limit exceeded")
            raise TTSError(
                f"Voice cloning failed: {e}",
                backend="elevenlabs"
            )
    
    @retry_on_rate_limit(max_retries=3)
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
        try:
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
            
        except Exception as e:
            error_str = str(e)
            if 'rate limit' in error_str.lower():
                raise RateLimitError("ElevenLabs rate limit exceeded")
            raise TTSError(
                f"TTS generation failed: {e}",
                backend="elevenlabs"
            )
    
    def list_voices(self) -> list:
        """List available voices."""
        try:
            voices = self.client.voices.get_all()
            return [v.name for v in voices.voices]
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []
    
    def delete_voice(self, voice_id: str):
        """Delete a cloned voice."""
        try:
            self.client.voices.delete(voice_id)
            logger.info(f"Deleted voice: {voice_id}")
        except Exception as e:
            logger.error(f"Failed to delete voice: {e}")
            raise TTSError(
                f"Failed to delete voice: {e}",
                backend="elevenlabs"
            )
