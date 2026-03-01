"""
Configuration management for audiobook generator.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TTSConfig:
    """TTS backend configuration."""
    backend: str = "elevenlabs"
    api_key: Optional[str] = None
    max_workers: int = 4
    
    def __post_init__(self):
        # Resolve API key from environment if not set
        if self.api_key is None:
            self.api_key = os.getenv("ELEVENLABS_API_KEY")


@dataclass
class VoiceConfig:
    """Voice configuration."""
    sample: Optional[str] = None
    stability: float = 0.5
    similarity_boost: float = 0.75
    model: Optional[str] = None


@dataclass
class TextConfig:
    """Text processing configuration."""
    chunk_size: int = 4000
    detect_dialogue: bool = True
    dialogue_patterns: list = field(default_factory=list)
    language: str = "auto"


@dataclass
class OutputConfig:
    """Output configuration."""
    format: str = "mp3"
    bitrate: str = "192k"
    normalize: bool = True
    split_chapters: bool = False
    output_dir: str = "output"


@dataclass
class Config:
    """Main configuration class."""
    tts: TTSConfig = field(default_factory=TTSConfig)
    voices: Dict[str, Any] = field(default_factory=dict)
    text: TextConfig = field(default_factory=TextConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """Load configuration from YAML file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Expand environment variables
        data = cls._expand_env_vars(data)
        
        # Parse sections
        tts_config = TTSConfig(**data.get('tts', {}))
        text_config = TextConfig(**data.get('text', {}))
        output_config = OutputConfig(**data.get('output', {}))
        
        return cls(
            tts=tts_config,
            voices=data.get('voices', {}),
            text=text_config,
            output=output_config
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create configuration from dictionary."""
        data = cls._expand_env_vars(data)
        
        return cls(
            tts=TTSConfig(**data.get('tts', {})),
            voices=data.get('voices', {}),
            text=TextConfig(**data.get('text', {})),
            output=OutputConfig(**data.get('output', {}))
        )
    
    @staticmethod
    def _expand_env_vars(obj: Any) -> Any:
        """Recursively expand environment variables in config."""
        if isinstance(obj, dict):
            return {k: Config._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [Config._expand_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Expand ${VAR} syntax
            result = obj
            for match in re.finditer(r'\$\{(\w+)\}', obj):
                var_name = match.group(1)
                var_value = os.getenv(var_name, '')
                result = result.replace(match.group(0), var_value)
            return result
        return obj
    
    def to_yaml(self, path: str):
        """Save configuration to YAML file."""
        data = {
            'tts': {
                'backend': self.tts.backend,
                'max_workers': self.tts.max_workers,
            },
            'voices': self.voices,
            'text': {
                'chunk_size': self.text.chunk_size,
                'detect_dialogue': self.text.detect_dialogue,
                'dialogue_patterns': self.text.dialogue_patterns,
                'language': self.text.language,
            },
            'output': {
                'format': self.output.format,
                'bitrate': self.output.bitrate,
                'normalize': self.output.normalize,
                'split_chapters': self.output.split_chapters,
                'output_dir': self.output.output_dir,
            }
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def get_voice_config(self, voice_name: str) -> VoiceConfig:
        """Get configuration for a specific voice."""
        voice_data = self.voices.get(voice_name, {})
        if isinstance(voice_data, dict):
            return VoiceConfig(**voice_data)
        return VoiceConfig()


import re
