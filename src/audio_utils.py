"""
Audio utilities for post-processing.
"""

import logging
from pathlib import Path
from typing import List

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

logger = logging.getLogger(__name__)


class AudioUtils:
    """Audio processing utilities."""
    
    def __init__(self):
        if not PYDUB_AVAILABLE:
            raise ImportError("pydub required. Install with: pip install pydub")
    
    def concatenate_audio_files(
        self,
        audio_files: List[str],
        output_path: str,
        crossfade: int = 100
    ):
        """
        Concatenate multiple audio files.
        
        Args:
            audio_files: List of audio file paths
            output_path: Output file path
            crossfade: Crossfade duration in milliseconds
        """
        if not audio_files:
            raise ValueError("No audio files to concatenate")
        
        # Load first file
        combined = AudioSegment.from_file(audio_files[0])
        
        # Append remaining files
        for audio_file in audio_files[1:]:
            segment = AudioSegment.from_file(audio_file)
            combined = combined.append(segment, crossfade=crossfade)
        
        # Export
        combined.export(output_path, format="mp3", bitrate="192k")
        logger.info(f"Concatenated audio saved to {output_path}")
    
    def normalize_volume(
        self,
        input_path: str,
        output_path: str,
        target_db: float = -14.0
    ):
        """
        Normalize audio volume.
        
        Args:
            input_path: Input audio file
            output_path: Output audio file
            target_db: Target dB level
        """
        audio = AudioSegment.from_file(input_path)
        
        # Normalize
        change_in_db = target_db - audio.dBFS
        normalized = audio.apply_gain(change_in_db)
        
        # Export
        normalized.export(output_path, format="mp3")
        logger.info(f"Normalized audio saved to {output_path}")
    
    def split_by_chapters(
        self,
        audio_path: str,
        chapter_markers: List[int],
        output_dir: str
    ) -> List[str]:
        """
        Split audiobook by chapters.
        
        Args:
            audio_path: Full audiobook path
            chapter_markers: List of chapter start times in milliseconds
            output_dir: Output directory
            
        Returns:
            List of chapter file paths
        """
        audio = AudioSegment.from_file(audio_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        chapter_files = []
        
        for i, start in enumerate(chapter_markers):
            end = chapter_markers[i + 1] if i + 1 < len(chapter_markers) else len(audio)
            chapter = audio[start:end]
            
            chapter_path = output_dir / f"chapter_{i+1:03d}.mp3"
            chapter.export(str(chapter_path), format="mp3")
            chapter_files.append(str(chapter_path))
        
        logger.info(f"Split into {len(chapter_files)} chapters")
        return chapter_files
    
    def add_silence(
        self,
        input_path: str,
        output_path: str,
        silence_duration: int = 1000
    ):
        """
        Add silence at the beginning and end.
        
        Args:
            input_path: Input audio file
            output_path: Output audio file
            silence_duration: Silence duration in milliseconds
        """
        audio = AudioSegment.from_file(input_path)
        silence = AudioSegment.silent(duration=silence_duration)
        
        result = silence + audio + silence
        result.export(output_path, format="mp3")
