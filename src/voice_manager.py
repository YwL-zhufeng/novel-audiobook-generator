"""
Voice management module for cloning and managing voices.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict
import json

logger = logging.getLogger(__name__)


class VoiceManager:
    """Manage voice cloning and TTS generation."""
    
    def __init__(self, tts_backend: str, api_key: Optional[str] = None):
        """
        Initialize voice manager.
        
        Args:
            tts_backend: TTS backend ('elevenlabs', 'xtts', 'kokoro')
            api_key: API key for cloud services
        """
        self.tts_backend = tts_backend
        self.api_key = api_key
        self.voices: Dict[str, str] = {}  # name -> voice_id
        
        # Initialize backend
        if tts_backend == "elevenlabs":
            from .tts_backends.elevenlabs import ElevenLabsBackend
            self.backend = ElevenLabsBackend(api_key)
        elif tts_backend == "xtts":
            from .tts_backends.xtts import XTTSBackend
            self.backend = XTTSBackend()
        elif tts_backend == "kokoro":
            from .tts_backends.kokoro import KokoroBackend
            self.backend = KokoroBackend()
        else:
            raise ValueError(f"Unknown TTS backend: {tts_backend}")
        
        logger.info(f"Initialized VoiceManager with {tts_backend} backend")
    
    def clone_voice(
        self,
        voice_name: str,
        sample_audio_path: str,
        description: Optional[str] = None
    ) -> str:
        """
        Clone a voice from audio sample.
        
        Args:
            voice_name: Name for the cloned voice
            sample_audio_path: Path to voice sample
            description: Optional voice description
            
        Returns:
            Voice ID
        """
        if not Path(sample_audio_path).exists():
            raise FileNotFoundError(f"Sample audio not found: {sample_audio_path}")
        
        voice_id = self.backend.clone_voice(sample_audio_path, description)
        self.voices[voice_name] = voice_id
        
        logger.info(f"Cloned voice '{voice_name}' with ID: {voice_id}")
        return voice_id
    
    def generate_speech(
        self,
        text: str,
        voice: str,
        output_path: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75
    ) -> str:
        """
        Generate speech from text.
        
        Args:
            text: Text to synthesize
            voice: Voice name or ID
            output_path: Output audio file path
            stability: Voice stability (0-1)
            similarity_boost: Similarity to cloned voice (0-1)
            
        Returns:
            Path to generated audio file
        """
        # Resolve voice ID
        voice_id = self.voices.get(voice, voice)
        
        # Generate speech
        self.backend.generate_speech(
            text=text,
            voice_id=voice_id,
            output_path=output_path,
            stability=stability,
            similarity_boost=similarity_boost
        )
        
        return output_path
    
    def list_voices(self) -> Dict[str, str]:
        """List available voices."""
        return self.voices.copy()
    
    def save_voices_config(self, config_path: str):
        """Save voice configuration to file."""
        with open(config_path, 'w') as f:
            json.dump(self.voices, f, indent=2)
    
    def load_voices_config(self, config_path: str):
        """Load voice configuration from file."""
        with open(config_path, 'r') as f:
            self.voices = json.load(f)
