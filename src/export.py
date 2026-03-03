"""
Export utilities for multiple audiobook formats.
"""

import os
import subprocess
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import logging
import tempfile

from .logging_config import get_logger
from .exceptions import AudioProcessingError
from .chapter_detector import Chapter, ChapterDetectionResult

logger = get_logger(__name__)

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

try:
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4, MP4Cover
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCOM, TDRC, CHAP, CTOC, CTOCFlags
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


@dataclass
class ExportOptions:
    """Options for audiobook export."""
    format: str = "mp3"  # mp3, m4b, m4a, ogg, wav
    bitrate: str = "192k"
    sample_rate: int = 44100
    split_chapters: bool = False
    add_metadata: bool = True
    cover_image: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    album: Optional[str] = None
    year: Optional[str] = None
    description: Optional[str] = None


class AudiobookExporter:
    """
    Export audiobooks in various formats.
    
    Supported formats:
    - MP3 (single file or split by chapters)
    - M4B (Audiobook format with chapters)
    - M4A (AAC audio)
    - OGG (Vorbis)
    - WAV (Uncompressed)
    """
    
    def __init__(self):
        if not PYDUB_AVAILABLE:
            raise ImportError("pydub required for export. Install with: pip install pydub")
    
    def export(
        self,
        audio_path: str,
        output_path: str,
        options: Optional[ExportOptions] = None,
        chapters: Optional[ChapterDetectionResult] = None
    ) -> str:
        """
        Export audiobook to specified format.
        
        Args:
            audio_path: Source audio file
            output_path: Output file path
            options: Export options
            chapters: Optional chapter information
            
        Returns:
            Path to exported file
        """
        if options is None:
            options = ExportOptions()
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine format from extension if not specified
        if options.format == "auto":
            options.format = output_path.suffix.lstrip('.').lower()
        
        if options.split_chapters and chapters:
            return self._export_split_chapters(
                audio_path, output_path, options, chapters
            )
        
        # Export as single file
        if options.format in ['m4b', 'm4a']:
            return self._export_m4b(audio_path, output_path, options, chapters)
        elif options.format == 'mp3':
            return self._export_mp3(audio_path, output_path, options, chapters)
        else:
            return self._export_generic(audio_path, output_path, options)
    
    def _export_mp3(
        self,
        audio_path: str,
        output_path: Path,
        options: ExportOptions,
        chapters: Optional[ChapterDetectionResult]
    ) -> str:
        """Export as MP3 with metadata and chapters."""
        # Load audio
        audio = AudioSegment.from_file(audio_path)
        
        # Export with specified parameters
        audio.export(
            output_path,
            format="mp3",
            bitrate=options.bitrate,
            parameters=["-ar", str(options.sample_rate)]
        )
        
        # Add metadata
        if options.add_metadata and MUTAGEN_AVAILABLE:
            self._add_mp3_metadata(output_path, options, chapters)
        
        logger.info(f"Exported MP3: {output_path}")
        return str(output_path)
    
    def _export_m4b(
        self,
        audio_path: str,
        output_path: Path,
        options: ExportOptions,
        chapters: Optional[ChapterDetectionResult]
    ) -> str:
        """
        Export as M4B audiobook format.
        
        M4B is the standard audiobook format with chapter support.
        """
        # Convert to AAC first using ffmpeg
        temp_aac = output_path.with_suffix('.temp.aac')
        
        try:
            # Use ffmpeg for high-quality AAC encoding
            cmd = [
                'ffmpeg', '-y', '-i', audio_path,
                '-c:a', 'aac', '-b:a', options.bitrate,
                '-ar', str(options.sample_rate),
                '-f', 'adts',
                str(temp_aac)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                # Fallback to pydub
                audio = AudioSegment.from_file(audio_path)
                audio.export(temp_aac, format="adts", bitrate=options.bitrate)
            
            # Create M4B container with chapters
            self._create_m4b_with_chapters(
                temp_aac, output_path, options, chapters
            )
            
        finally:
            if temp_aac.exists():
                temp_aac.unlink()
        
        logger.info(f"Exported M4B: {output_path}")
        return str(output_path)
    
    def _create_m4b_with_chapters(
        self,
        audio_path: Path,
        output_path: Path,
        options: ExportOptions,
        chapters: Optional[ChapterDetectionResult]
    ):
        """Create M4B file with chapter markers."""
        if not MUTAGEN_AVAILABLE:
            # Just copy the file
            import shutil
            shutil.copy2(audio_path, output_path)
            return
        
        # Copy to output
        import shutil
        shutil.copy2(audio_path, output_path)
        
        # Add metadata and chapters
        try:
            audio = MP4(output_path)
            
            # Basic metadata
            if options.title:
                audio['\xa9nam'] = options.title
            if options.author:
                audio['\xa9ART'] = options.author
            if options.album:
                audio['\xa9alb'] = options.album
            if options.year:
                audio['\xa9day'] = options.year
            if options.description:
                audio['desc'] = options.description
            
            # Mark as audiobook
            audio['stik'] = [2]  # Audiobook
            
            # Add cover image
            if options.cover_image and Path(options.cover_image).exists():
                with open(options.cover_image, 'rb') as f:
                    cover_data = f.read()
                audio['covr'] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
            
            # Add chapters
            if chapters and chapters.chapters:
                self._add_m4b_chapters(audio, chapters)
            
            audio.save()
            
        except Exception as e:
            logger.warning(f"Failed to add M4B metadata: {e}")
    
    def _add_m4b_chapters(self, audio: MP4, chapters: ChapterDetectionResult):
        """Add chapter markers to M4B file."""
        # M4B chapters are complex - this is a simplified version
        # Full implementation would require mp4v2 or similar
        
        # Store chapter info as custom metadata
        chapter_data = []
        for ch in chapters.chapters:
            chapter_data.append({
                'title': ch.title,
                'start': ch.start_pos,
            })
        
        import json
        audio['----:com.apple.iTunes:Chapters'] = json.dumps(chapter_data).encode()
    
    def _add_mp3_metadata(
        self,
        output_path: Path,
        options: ExportOptions,
        chapters: Optional[ChapterDetectionResult]
    ):
        """Add metadata to MP3 file."""
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCOM, TDRC, TXXX, APIC
            
            audio = MP3(output_path)
            
            if audio.tags is None:
                audio.add_tags()
            
            tags = audio.tags
            
            if options.title:
                tags['TIT2'] = TIT2(encoding=3, text=options.title)
            if options.author:
                tags['TPE1'] = TPE1(encoding=3, text=options.author)
            if options.album:
                tags['TALB'] = TALB(encoding=3, text=options.album)
            if options.year:
                tags['TDRC'] = TDRC(encoding=3, text=options.year)
            if options.description:
                tags['TXXX:Description'] = TXXX(encoding=3, desc='Description', text=options.description)
            
            # Add cover
            if options.cover_image and Path(options.cover_image).exists():
                with open(options.cover_image, 'rb') as f:
                    cover_data = f.read()
                tags['APIC'] = APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=cover_data
                )
            
            # Add chapters as JSON
            if chapters:
                import json
                chapter_json = json.dumps([c.to_dict() for c in chapters.chapters], ensure_ascii=False)
                tags['TXXX:Chapters'] = TXXX(encoding=3, desc='Chapters', text=chapter_json)
            
            audio.save()
            
        except Exception as e:
            logger.warning(f"Failed to add MP3 metadata: {e}")
    
    def _export_generic(
        self,
        audio_path: str,
        output_path: Path,
        options: ExportOptions
    ) -> str:
        """Export to generic format using pydub."""
        audio = AudioSegment.from_file(audio_path)
        
        format_map = {
            'wav': 'wav',
            'ogg': 'ogg',
            'flac': 'flac',
            'aac': 'adts',
        }
        
        fmt = format_map.get(options.format, options.format)
        
        audio.export(
            output_path,
            format=fmt,
            bitrate=options.bitrate if fmt != 'wav' else None
        )
        
        logger.info(f"Exported {options.format.upper()}: {output_path}")
        return str(output_path)
    
    def _export_split_chapters(
        self,
        audio_path: str,
        output_path: Path,
        options: ExportOptions,
        chapters: ChapterDetectionResult
    ) -> str:
        """
        Export audiobook split by chapters.
        
        Returns path to output directory.
        """
        # Create output directory
        output_dir = output_path.with_suffix('')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load audio
        audio = AudioSegment.from_file(audio_path)
        
        # Calculate chapter positions in milliseconds
        total_duration_ms = len(audio)
        text_length = sum(ch.length for ch in chapters.chapters)
        
        exported_files = []
        
        for i, chapter in enumerate(chapters.chapters):
            # Estimate time position based on text proportion
            start_ratio = sum(chapters.chapters[j].length for j in range(i)) / text_length if text_length > 0 else 0
            end_ratio = sum(chapters.chapters[j].length for j in range(i + 1)) / text_length if text_length > 0 else 1
            
            start_ms = int(start_ratio * total_duration_ms)
            end_ms = int(end_ratio * total_duration_ms)
            
            # Extract chapter audio
            chapter_audio = audio[start_ms:end_ms]
            
            # Generate filename
            safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in chapter.title)
            safe_title = safe_title[:50].strip()
            
            chapter_filename = f"{i+1:03d}_{safe_title}.{options.format}"
            chapter_path = output_dir / chapter_filename
            
            # Export
            chapter_audio.export(
                chapter_path,
                format=options.format if options.format != 'm4b' else 'mp4',
                bitrate=options.bitrate
            )
            
            exported_files.append(str(chapter_path))
            logger.debug(f"Exported chapter {i+1}: {chapter_path}")
        
        logger.info(f"Exported {len(exported_files)} chapters to {output_dir}")
        return str(output_dir)
    
    def export_with_ffmpeg(
        self,
        audio_path: str,
        output_path: str,
        options: ExportOptions,
        chapters: Optional[ChapterDetectionResult] = None
    ) -> str:
        """
        Export using ffmpeg for maximum compatibility.
        
        This method requires ffmpeg to be installed.
        """
        output_path = Path(output_path)
        
        # Build ffmpeg command
        cmd = ['ffmpeg', '-y', '-i', audio_path]
        
        # Audio codec settings
        if options.format in ['m4b', 'm4a']:
            cmd.extend(['-c:a', 'aac', '-b:a', options.bitrate])
        elif options.format == 'mp3':
            cmd.extend(['-c:a', 'libmp3lame', '-b:a', options.bitrate])
        elif options.format == 'ogg':
            cmd.extend(['-c:a', 'libvorbis', '-q:a', '4'])
        elif options.format == 'wav':
            cmd.extend(['-c:a', 'pcm_s16le'])
        
        # Sample rate
        cmd.extend(['-ar', str(options.sample_rate)])
        
        # Metadata
        if options.add_metadata:
            if options.title:
                cmd.extend(['-metadata', f'title={options.title}'])
            if options.author:
                cmd.extend(['-metadata', f'artist={options.author}'])
            if options.album:
                cmd.extend(['-metadata', f'album={options.album}'])
            if options.year:
                cmd.extend(['-metadata', f'date={options.year}'])
            if options.description:
                cmd.extend(['-metadata', f'description={options.description}'])
        
        cmd.append(str(output_path))
        
        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise AudioProcessingError(
                f"ffmpeg export failed: {result.stderr}",
                file_path=str(output_path)
            )
        
        logger.info(f"Exported with ffmpeg: {output_path}")
        return str(output_path)
