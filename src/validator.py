"""
Validation utilities for configuration and inputs.
"""

import re
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class ValidationError:
    """Validation error details."""
    field: str
    message: str
    value: any = None


class ConfigValidator:
    """Validate configuration values."""
    
    # Valid TTS backends
    VALID_BACKENDS = ['elevenlabs', 'xtts', 'kokoro', 'doubao']
    
    # Valid audio formats
    VALID_FORMATS = ['mp3', 'wav', 'm4a', 'ogg', 'flac']
    
    # Valid sample rates
    VALID_SAMPLE_RATES = [8000, 16000, 22050, 24000, 44100, 48000]
    
    @classmethod
    def validate_backend(cls, backend: str) -> Tuple[bool, Optional[str]]:
        """Validate TTS backend."""
        if backend not in cls.VALID_BACKENDS:
            return False, f"Invalid backend '{backend}'. Valid options: {', '.join(cls.VALID_BACKENDS)}"
        return True, None
    
    @classmethod
    def validate_chunk_size(cls, chunk_size: int) -> Tuple[bool, Optional[str]]:
        """Validate text chunk size."""
        if not isinstance(chunk_size, int):
            return False, f"Chunk size must be an integer, got {type(chunk_size)}"
        if chunk_size < 100:
            return False, f"Chunk size too small ({chunk_size}), minimum is 100"
        if chunk_size > 10000:
            return False, f"Chunk size too large ({chunk_size}), maximum is 10000"
        return True, None
    
    @classmethod
    def validate_workers(cls, workers: int) -> Tuple[bool, Optional[str]]:
        """Validate worker count."""
        if not isinstance(workers, int):
            return False, f"Workers must be an integer, got {type(workers)}"
        if workers < 1:
            return False, f"Workers must be at least 1, got {workers}"
        if workers > 32:
            return False, f"Workers too high ({workers}), maximum is 32"
        return True, None
    
    @classmethod
    def validate_audio_format(cls, format: str) -> Tuple[bool, Optional[str]]:
        """Validate audio format."""
        format = format.lower().replace('.', '')
        if format not in cls.VALID_FORMATS:
            return False, f"Invalid format '{format}'. Valid options: {', '.join(cls.VALID_FORMATS)}"
        return True, None
    
    @classmethod
    def validate_bitrate(cls, bitrate: str) -> Tuple[bool, Optional[str]]:
        """Validate audio bitrate."""
        pattern = r'^\d+k$'
        if not re.match(pattern, bitrate):
            return False, f"Invalid bitrate format '{bitrate}'. Expected format: '128k', '192k', etc."
        return True, None
    
    @classmethod
    def validate_file_path(cls, path: str, must_exist: bool = False, 
                          extensions: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
        """Validate file path."""
        try:
            p = Path(path)
        except Exception as e:
            return False, f"Invalid path: {e}"
        
        if must_exist and not p.exists():
            return False, f"File does not exist: {path}"
        
        if extensions and p.suffix.lower() not in extensions:
            ext_list = ', '.join(extensions)
            return False, f"Invalid file extension '{p.suffix}'. Expected: {ext_list}"
        
        return True, None
    
    @classmethod
    def validate_voice_sample(cls, path: str) -> Tuple[bool, Optional[str]]:
        """Validate voice sample file."""
        valid_extensions = ['.wav', '.mp3', '.m4a', '.ogg', '.flac']
        
        is_valid, error = cls.validate_file_path(path, must_exist=True, extensions=valid_extensions)
        if not is_valid:
            return False, error
        
        # Check file size (should be at least 10KB for a valid sample)
        file_size = Path(path).stat().st_size
        if file_size < 10 * 1024:  # 10KB
            return False, f"Voice sample too small ({file_size} bytes), minimum is 10KB"
        
        if file_size > 50 * 1024 * 1024:  # 50MB
            return False, f"Voice sample too large ({file_size / 1024 / 1024:.1f}MB), maximum is 50MB"
        
        return True, None
    
    @classmethod
    def validate_doubao_config(cls, app_id: Optional[str], access_token: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Validate Doubao configuration."""
        if not access_token and not app_id:
            return False, "Doubao backend requires either access_token or api_key"
        return True, None
    
    @classmethod
    def validate_config(cls, config: dict) -> Tuple[bool, List[ValidationError]]:
        """
        Validate full configuration.
        
        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        
        # Validate TTS config
        tts_config = config.get('tts', {})
        backend = tts_config.get('backend', 'elevenlabs')
        
        is_valid, error = cls.validate_backend(backend)
        if not is_valid:
            errors.append(ValidationError('tts.backend', error, backend))
        
        chunk_size = tts_config.get('chunk_size', 4000)
        is_valid, error = cls.validate_chunk_size(chunk_size)
        if not is_valid:
            errors.append(ValidationError('tts.chunk_size', error, chunk_size))
        
        workers = tts_config.get('max_workers', 4)
        is_valid, error = cls.validate_workers(workers)
        if not is_valid:
            errors.append(ValidationError('tts.max_workers', error, workers))
        
        # Validate output config
        output_config = config.get('output', {})
        format = output_config.get('format', 'mp3')
        is_valid, error = cls.validate_audio_format(format)
        if not is_valid:
            errors.append(ValidationError('output.format', error, format))
        
        bitrate = output_config.get('bitrate', '192k')
        is_valid, error = cls.validate_bitrate(bitrate)
        if not is_valid:
            errors.append(ValidationError('output.bitrate', error, bitrate))
        
        return len(errors) == 0, errors


def format_validation_errors(errors: List[ValidationError]) -> str:
    """Format validation errors for display."""
    if not errors:
        return "No validation errors"
    
    lines = ["Configuration errors:"]
    for error in errors:
        lines.append(f"  - {error.field}: {error.message}")
    
    return "\n".join(lines)
