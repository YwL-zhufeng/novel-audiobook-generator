"""
Audio utilities for post-processing with streaming support.
"""

import os
import json
import logging
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Iterator, Union
from contextlib import contextmanager

from .exceptions import AudioProcessingError
from .logging_config import get_logger

logger = get_logger(__name__)

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not available, audio processing disabled")

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCOM, TDRC, TLEN, TXXX, APIC
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logger.warning("mutagen not available, metadata editing disabled")


class AudioUtils:
    """Audio processing utilities with streaming support."""
    
    # Default crossfade duration in milliseconds
    DEFAULT_CROSSFADE = 100
    
    # Default bitrate
    DEFAULT_BITRATE = "192k"
    
    # Batch size for incremental merge (number of files to merge at once)
    MERGE_BATCH_SIZE = 10
    
    def __init__(self):
        if not PYDUB_AVAILABLE:
            raise ImportError(
                "pydub required. Install with: pip install pydub"
            )
    
    def concatenate_audio_files(
        self,
        audio_files: List[str],
        output_path: str,
        crossfade: int = DEFAULT_CROSSFADE,
        metadata: Optional[Dict[str, Any]] = None,
        use_streaming: bool = True
    ):
        """
        Concatenate multiple audio files.
        
        Args:
            audio_files: List of audio file paths
            output_path: Output file path
            crossfade: Crossfade duration in milliseconds
            metadata: Optional metadata dict
            use_streaming: Use incremental merge for large number of files
            
        Raises:
            AudioProcessingError: If concatenation fails
        """
        if not audio_files:
            raise AudioProcessingError("No audio files to concatenate")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if use_streaming and len(audio_files) > self.MERGE_BATCH_SIZE:
                # Use incremental merge for large number of files
                self._concatenate_incremental(audio_files, output_path, crossfade)
            else:
                # Load all files at once for small number of files
                self._concatenate_batch(audio_files, output_path, crossfade)
            
            # Add metadata if provided
            if metadata:
                self.add_metadata(str(output_path), metadata)
            
            logger.info(f"Concatenated audio saved to {output_path}")
            
        except Exception as e:
            raise AudioProcessingError(
                f"Failed to concatenate audio: {e}",
                file_path=str(output_path)
            )
    
    def _concatenate_batch(
        self,
        audio_files: List[str],
        output_path: Path,
        crossfade: int
    ):
        """Concatenate files by loading all at once."""
        # Load first file
        combined = AudioSegment.from_file(audio_files[0])
        
        # Append remaining files
        for audio_file in audio_files[1:]:
            segment = AudioSegment.from_file(audio_file)
            combined = combined.append(segment, crossfade=crossfade)
        
        # Export
        combined.export(output_path, format="mp3", bitrate=self.DEFAULT_BITRATE)
    
    def _concatenate_incremental(
        self,
        audio_files: List[str],
        output_path: Path,
        crossfade: int
    ):
        """
        Concatenate files incrementally to reduce memory usage.
        
        Uses a divide-and-conquer approach:
        1. Merge files in batches
        2. Merge the batch results
        """
        if len(audio_files) <= self.MERGE_BATCH_SIZE:
            self._concatenate_batch(audio_files, output_path, crossfade)
            return
        
        # Create temporary directory for intermediate files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            batch_files = []
            
            # Process in batches
            for i in range(0, len(audio_files), self.MERGE_BATCH_SIZE):
                batch = audio_files[i:i + self.MERGE_BATCH_SIZE]
                batch_output = temp_path / f"batch_{i:04d}.mp3"
                
                # Load and merge batch
                combined = AudioSegment.from_file(batch[0])
                for audio_file in batch[1:]:
                    segment = AudioSegment.from_file(audio_file)
                    combined = combined.append(segment, crossfade=crossfade)
                
                combined.export(batch_output, format="mp3", bitrate=self.DEFAULT_BITRATE)
                batch_files.append(str(batch_output))
                
                logger.debug(f"Created batch file: {batch_output}")
            
            # Recursively merge batch files
            self._concatenate_incremental(batch_files, output_path, crossfade)
    
    def add_metadata(
        self,
        audio_path: str,
        metadata: Dict[str, Any]
    ):
        """
        Add ID3 metadata to MP3 file.
        
        Args:
            audio_path: Path to MP3 file
            metadata: Dictionary containing metadata
        """
        if not MUTAGEN_AVAILABLE:
            logger.warning("mutagen not installed, skipping metadata")
            return
        
        try:
            audio = MP3(audio_path)
            
            # Create ID3 tag if it doesn't exist
            if audio.tags is None:
                audio.add_tags()
            
            tags = audio.tags
            
            # Basic metadata
            if metadata.get('title'):
                tags['TIT2'] = TIT2(encoding=3, text=metadata['title'])
            
            if metadata.get('artist'):
                tags['TPE1'] = TPE1(encoding=3, text=metadata['artist'])
            
            if metadata.get('album'):
                tags['TALB'] = TALB(encoding=3, text=metadata['album'])
            
            if metadata.get('composer'):
                tags['TCOM'] = TCOM(encoding=3, text=metadata['composer'])
            
            if metadata.get('year'):
                tags['TDRC'] = TDRC(encoding=3, text=str(metadata['year']))
            
            # Duration in milliseconds
            duration_ms = len(audio) * 1000
            tags['TLEN'] = TLEN(encoding=3, text=str(int(duration_ms)))
            
            # Add cover image if provided
            if metadata.get('cover_image') and Path(metadata['cover_image']).exists():
                with open(metadata['cover_image'], 'rb') as img_file:
                    cover_data = img_file.read()
                    tags['APIC'] = APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,  # Cover (front)
                        desc='Cover',
                        data=cover_data
                    )
            
            # Add chapter information as custom tag
            if metadata.get('chapters'):
                chapters_json = json.dumps(metadata['chapters'], ensure_ascii=False)
                tags['TXXX:Chapters'] = TXXX(
                    encoding=3,
                    desc='Chapters',
                    text=chapters_json
                )
            
            # Additional custom metadata
            for key, value in metadata.items():
                if key not in ['title', 'artist', 'album', 'composer', 'year', 
                              'cover_image', 'chapters'] and value:
                    tag_name = f'TXXX:{key.capitalize()}'
                    tags[tag_name] = TXXX(
                        encoding=3,
                        desc=key.capitalize(),
                        text=str(value)
                    )
            
            audio.save()
            logger.info(f"Metadata added to {audio_path}")
            
        except Exception as e:
            logger.error(f"Failed to add metadata: {e}")
            raise AudioProcessingError(
                f"Failed to add metadata: {e}",
                file_path=audio_path
            )
    
    def read_metadata(self, audio_path: str) -> Dict[str, Any]:
        """
        Read ID3 metadata from MP3 file.
        
        Args:
            audio_path: Path to MP3 file
            
        Returns:
            Dictionary of metadata
        """
        if not MUTAGEN_AVAILABLE:
            return {}
        
        try:
            audio = MP3(audio_path)
            if audio.tags is None:
                return {}
            
            tags = audio.tags
            metadata = {}
            
            # Basic tags
            if 'TIT2' in tags:
                metadata['title'] = str(tags['TIT2'])
            if 'TPE1' in tags:
                metadata['artist'] = str(tags['TPE1'])
            if 'TALB' in tags:
                metadata['album'] = str(tags['TALB'])
            if 'TCOM' in tags:
                metadata['composer'] = str(tags['TCOM'])
            if 'TDRC' in tags:
                metadata['year'] = str(tags['TDRC'])
            if 'TLEN' in tags:
                metadata['duration_ms'] = str(tags['TLEN'])
            
            # Custom tags
            for key in tags.keys():
                if key.startswith('TXXX:'):
                    desc = key[5:]
                    metadata[desc.lower()] = str(tags[key])
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to read metadata: {e}")
            return {}
    
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
        try:
            audio = AudioSegment.from_file(input_path)
            
            # Normalize
            change_in_db = target_db - audio.dBFS
            normalized = audio.apply_gain(change_in_db)
            
            # Export
            normalized.export(output_path, format="mp3")
            logger.info(f"Normalized audio saved to {output_path}")
            
        except Exception as e:
            raise AudioProcessingError(
                f"Failed to normalize volume: {e}",
                file_path=input_path
            )
    
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
        try:
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
            
        except Exception as e:
            raise AudioProcessingError(
                f"Failed to split by chapters: {e}",
                file_path=audio_path
            )
    
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
        try:
            audio = AudioSegment.from_file(input_path)
            silence = AudioSegment.silent(duration=silence_duration)
            
            result = silence + audio + silence
            result.export(output_path, format="mp3")
            
        except Exception as e:
            raise AudioProcessingError(
                f"Failed to add silence: {e}",
                file_path=input_path
            )
    
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Get audio duration in seconds.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Duration in seconds
        """
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # Convert ms to seconds
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0
    
    def merge_audio_files_parallel(
        self,
        audio_files: List[str],
        output_path: str,
        num_workers: int = 4
    ):
        """
        Merge audio files using parallel processing.
        
        This is useful for very large number of files.
        
        Args:
            audio_files: List of audio file paths
            output_path: Output file path
            num_workers: Number of parallel workers
        """
        from concurrent.futures import ProcessPoolExecutor
        
        if len(audio_files) <= self.MERGE_BATCH_SIZE:
            self.concatenate_audio_files(audio_files, output_path)
            return
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Split files into chunks for parallel processing
            chunks = [
                audio_files[i:i + self.MERGE_BATCH_SIZE]
                for i in range(0, len(audio_files), self.MERGE_BATCH_SIZE)
            ]
            
            batch_files = []
            
            # Process chunks in parallel
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                futures = []
                for i, chunk in enumerate(chunks):
                    batch_output = temp_path / f"batch_{i:04d}.mp3"
                    future = executor.submit(
                        self._merge_chunk,
                        chunk,
                        batch_output
                    )
                    futures.append((future, str(batch_output)))
                
                for future, output in futures:
                    try:
                        future.result()
                        batch_files.append(output)
                    except Exception as e:
                        logger.error(f"Failed to merge chunk: {e}")
            
            # Final merge
            self.concatenate_audio_files(batch_files, output_path)
    
    def _merge_chunk(self, audio_files: List[str], output_path: Path):
        """Merge a chunk of audio files (for parallel processing)."""
        combined = AudioSegment.from_file(audio_files[0])
        for audio_file in audio_files[1:]:
            segment = AudioSegment.from_file(audio_file)
            combined = combined.append(segment, crossfade=self.DEFAULT_CROSSFADE)
        combined.export(output_path, format="mp3", bitrate=self.DEFAULT_BITRATE)
