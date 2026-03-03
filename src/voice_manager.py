"""
Voice management module for cloning and managing voices.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
from functools import lru_cache

from .exceptions import VoiceCloneError, TTSError, ResourceNotFoundError
from .logging_config import get_logger

logger = get_logger(__name__)


class VoiceManager:
    """Manage voice cloning and TTS generation."""
    
    def __init__(
        self,
        tts_backend: str,
        api_key: Optional[str] = None,
        app_id: Optional[str] = None,
        access_token: Optional[str] = None,
        cache_size: int = 128
    ):
        """
        Initialize voice manager.
        
        Args:
            tts_backend: TTS backend ('elevenlabs', 'xtts', 'kokoro', 'doubao')
            api_key: API key for cloud services (ElevenLabs, Doubao)
            app_id: App ID for Doubao/Volcano Engine
            access_token: Access token for Doubao (alternative to API key)
            cache_size: Size of TTS result cache
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
        elif tts_backend == "doubao":
            from .tts_backends.doubao import DoubaoBackend
            # Doubao can use api_key or access_token
            token = access_token or api_key
            self.backend = DoubaoBackend(app_id=app_id, access_token=token, api_key=api_key)
        else:
            raise ValueError(f"Unknown TTS backend: {tts_backend}")
        
        # Setup cache
        self._generate_speech_cached = lru_cache(maxsize=cache_size)(self._generate_speech_impl)
        
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
            
        Raises:
            VoiceCloneError: If cloning fails
            ResourceNotFoundError: If sample file not found
        """
        sample_path = Path(sample_audio_path)
        if not sample_path.exists():
            raise ResourceNotFoundError(
                f"Sample audio not found: {sample_audio_path}",
                resource_type="audio_file",
                resource_id=sample_audio_path
            )
        
        try:
            # Doubao uses different signature
            if self.tts_backend == "doubao":
                voice_id = self.backend.clone_voice(
                    sample_audio_path=str(sample_path.absolute()),
                    voice_name=voice_name,
                    description=description
                )
            else:
                voice_id = self.backend.clone_voice(
                    sample_audio_path=str(sample_path.absolute()),
                    description=description
                )
            
            self.voices[voice_name] = voice_id
            logger.info(f"Cloned voice '{voice_name}' with ID: {voice_id}")
            return voice_id
            
        except Exception as e:
            raise VoiceCloneError(
                f"Failed to clone voice: {e}",
                sample_path=str(sample_audio_path)
            )
    
    def generate_speech(
        self,
        text: str,
        voice: str,
        output_path: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        use_cache: bool = True
    ) -> str:
        """
        Generate speech from text.
        
        Args:
            text: Text to synthesize
            voice: Voice name or ID
            output_path: Output audio file path
            stability: Voice stability (0-1) - ElevenLabs only
            similarity_boost: Similarity to cloned voice (0-1) - ElevenLabs only
            use_cache: Whether to use TTS cache
            
        Returns:
            Path to generated audio file
            
        Raises:
            TTSError: If generation fails
        """
        # Resolve voice ID
        voice_id = self.voices.get(voice, voice)
        
        # Create cache key
        if use_cache:
            cache_key = self._get_cache_key(text, voice_id, stability, similarity_boost)
            cached_path = self._generate_speech_cached(
                cache_key, text, voice_id, output_path, stability, similarity_boost
            )
            if cached_path != output_path:
                # Copy cached file to output path
                import shutil
                shutil.copy2(cached_path, output_path)
            return output_path
        else:
            return self._generate_speech_impl(
                None, text, voice_id, output_path, stability, similarity_boost
            )
    
    def _generate_speech_impl(
        self,
        cache_key: Optional[str],
        text: str,
        voice_id: str,
        output_path: str,
        stability: float,
        similarity_boost: float
    ) -> str:
        """
        Internal implementation of speech generation.
        
        Returns path to generated file (may be cached path).
        """
        try:
            # Generate speech - backend-specific parameters
            if self.tts_backend == "doubao":
                self.backend.generate_speech(
                    text=text,
                    voice_id=voice_id,
                    output_path=output_path
                )
            else:
                self.backend.generate_speech(
                    text=text,
                    voice_id=voice_id,
                    output_path=output_path,
                    stability=stability,
                    similarity_boost=similarity_boost
                )
            
            return output_path
            
        except Exception as e:
            raise TTSError(
                f"TTS generation failed: {e}",
                backend=self.tts_backend
            )
    
    def _get_cache_key(
        self,
        text: str,
        voice_id: str,
        stability: float,
        similarity_boost: float
    ) -> str:
        """Generate cache key for TTS result."""
        import hashlib
        key_data = f"{text}:{voice_id}:{stability}:{similarity_boost}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def list_voices(self) -> Dict[str, str]:
        """List available voices."""
        voices = self.voices.copy()
        
        # Add default voices for Doubao
        if self.tts_backend == "doubao":
            try:
                default_voices = self.backend.list_default_voices()
                voices.update({f"[default] {k}": k for k in default_voices.keys()})
            except Exception as e:
                logger.warning(f"Failed to list default voices: {e}")
        
        return voices
    
    def get_voice_id(self, voice_name: str) -> Optional[str]:
        """Get voice ID by name."""
        return self.voices.get(voice_name, voice_name if voice_name in self.voices.values() else None)
    
    def save_voices_config(self, config_path: str):
        """Save voice configuration to file."""
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.voices, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved voice configuration to {config_path}")
    
    def load_voices_config(self, config_path: str):
        """Load voice configuration from file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise ResourceNotFoundError(
                f"Voice config file not found: {config_path}",
                resource_type="config_file",
                resource_id=str(config_path)
            )
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.voices = json.load(f)
        
        logger.info(f"Loaded {len(self.voices)} voices from {config_path}")
    
    def delete_voice(self, voice_name: str) -> bool:
        """
        Delete a cloned voice.
        
        Args:
            voice_name: Name of the voice to delete
            
        Returns:
            True if deleted, False if not found
        """
        if voice_name not in self.voices:
            return False
        
        voice_id = self.voices[voice_name]
        
        # Try to delete from backend if supported
        try:
            if hasattr(self.backend, 'delete_voice'):
                self.backend.delete_voice(voice_id)
        except Exception as e:
            logger.warning(f"Failed to delete voice from backend: {e}")
        
        del self.voices[voice_name]
        logger.info(f"Deleted voice: {voice_name}")
        return True
    
    def validate_voice_sample(self, sample_audio_path: str) -> Dict[str, any]:
        """
        Validate a voice sample for cloning.
        
        Args:
            sample_audio_path: Path to voice sample
            
        Returns:
            Validation result with 'valid' boolean and 'issues' list
        """
        from .audio_utils import AudioUtils
        
        issues = []
        
        try:
            # Check file exists
            sample_path = Path(sample_audio_path)
            if not sample_path.exists():
                return {'valid': False, 'issues': ['File not found']}
            
            # Check file size
            file_size = sample_path.stat().st_size
            if file_size < 1024:  # Less than 1KB
                issues.append('File too small (minimum 1KB)')
            if file_size > 50 * 1024 * 1024:  # More than 50MB
                issues.append('File too large (maximum 50MB)')
            
            # Check audio duration
            try:
                utils = AudioUtils()
                duration = utils.get_audio_duration(sample_audio_path)
                if duration < 5:
                    issues.append(f'Audio too short ({duration:.1f}s, minimum 5s)')
                if duration > 60:
                    issues.append(f'Audio too long ({duration:.1f}s, maximum 60s recommended)')
            except Exception as e:
                issues.append(f'Failed to analyze audio: {e}')
            
            return {
                'valid': len(issues) == 0,
                'issues': issues,
                'file_size': file_size,
                'duration': duration if 'duration' in dir() else None
            }
            
        except Exception as e:
            return {'valid': False, 'issues': [f'Validation error: {e}']}
