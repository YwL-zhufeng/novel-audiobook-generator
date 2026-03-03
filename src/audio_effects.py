"""
Audio effects and post-processing for audiobooks.
"""

from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

try:
    from pydub import AudioSegment
    from pydub.effects import normalize, compress_dynamic_range
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not available, audio effects disabled")


class AudioEffects:
    """Audio effects and post-processing."""
    
    def __init__(self):
        if not PYDUB_AVAILABLE:
            raise ImportError("pydub required for audio effects")
    
    def add_silence_at_start(
        self,
        input_path: str,
        output_path: str,
        duration_ms: int = 500
    ):
        """Add silence at the beginning."""
        audio = AudioSegment.from_file(input_path)
        silence = AudioSegment.silent(duration=duration_ms)
        result = silence + audio
        result.export(output_path, format="mp3")
    
    def add_silence_at_end(
        self,
        input_path: str,
        output_path: str,
        duration_ms: int = 1000
    ):
        """Add silence at the end."""
        audio = AudioSegment.from_file(input_path)
        silence = AudioSegment.silent(duration=duration_ms)
        result = audio + silence
        result.export(output_path, format="mp3")
    
    def fade_in(
        self,
        input_path: str,
        output_path: str,
        duration_ms: int = 1000
    ):
        """Apply fade in effect."""
        audio = AudioSegment.from_file(input_path)
        result = audio.fade_in(duration_ms)
        result.export(output_path, format="mp3")
    
    def fade_out(
        self,
        input_path: str,
        output_path: str,
        duration_ms: int = 2000
    ):
        """Apply fade out effect."""
        audio = AudioSegment.from_file(input_path)
        result = audio.fade_out(duration_ms)
        result.export(output_path, format="mp3")
    
    def normalize_audio(
        self,
        input_path: str,
        output_path: str,
        target_dBFS: float = -14.0
    ):
        """Normalize audio to target dBFS."""
        audio = AudioSegment.from_file(input_path)
        result = normalize(audio, target_dBFS)
        result.export(output_path, format="mp3")
    
    def compress_audio(
        self,
        input_path: str,
        output_path: str,
        threshold: float = -20.0,
        ratio: float = 4.0,
        attack: float = 5.0,
        release: float = 50.0
    ):
        """Apply dynamic range compression."""
        audio = AudioSegment.from_file(input_path)
        result = compress_dynamic_range(
            audio,
            threshold=threshold,
            ratio=ratio,
            attack=attack,
            release=release
        )
        result.export(output_path, format="mp3")
    
    def adjust_speed(
        self,
        input_path: str,
        output_path: str,
        speed: float = 1.0
    ):
        """
        Adjust playback speed.
        
        Args:
            speed: Speed factor (0.5 = half speed, 2.0 = double speed)
        """
        audio = AudioSegment.from_file(input_path)
        # Use frame rate to change speed
        new_frame_rate = int(audio.frame_rate * speed)
        result = audio._spawn(audio.raw_data, overrides={'frame_rate': new_frame_rate})
        # Convert back to original frame rate
        result = result.set_frame_rate(audio.frame_rate)
        result.export(output_path, format="mp3")
    
    def apply_effects_chain(
        self,
        input_path: str,
        output_path: str,
        effects: List[dict]
    ):
        """
        Apply a chain of effects.
        
        Args:
            effects: List of effect dictionaries, e.g.:
                [{'type': 'fade_in', 'duration_ms': 1000},
                 {'type': 'normalize', 'target_dBFS': -14.0}]
        """
        audio = AudioSegment.from_file(input_path)
        
        for effect in effects:
            effect_type = effect.get('type')
            
            if effect_type == 'fade_in':
                audio = audio.fade_in(effect.get('duration_ms', 1000))
            elif effect_type == 'fade_out':
                audio = audio.fade_out(effect.get('duration_ms', 2000))
            elif effect_type == 'normalize':
                audio = normalize(audio, effect.get('target_dBFS', -14.0))
            elif effect_type == 'compress':
                audio = compress_dynamic_range(
                    audio,
                    threshold=effect.get('threshold', -20.0),
                    ratio=effect.get('ratio', 4.0)
                )
            elif effect_type == 'silence_start':
                silence = AudioSegment.silent(duration=effect.get('duration_ms', 500))
                audio = silence + audio
            elif effect_type == 'silence_end':
                silence = AudioSegment.silent(duration=effect.get('duration_ms', 1000))
                audio = audio + silence
        
        audio.export(output_path, format="mp3")
