"""
Export formats for audiobooks (M4B, chaptered MP3, etc.)
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Chapter:
    """Represents a chapter in an audiobook."""
    title: str
    start_time_ms: int
    end_time_ms: int
    file_path: Optional[str] = None


class M4BExporter:
    """Export audiobook to M4B format (iTunes audiobook)."""
    
    def __init__(self):
        self.chapters: List[Chapter] = []
    
    def add_chapter(self, title: str, start_ms: int, end_ms: int, file_path: Optional[str] = None):
        """Add a chapter."""
        self.chapters.append(Chapter(title, start_ms, end_ms, file_path))
    
    def export(
        self,
        audio_files: List[str],
        output_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Export to M4B format.
        
        Note: This is a placeholder. Full M4B export requires ffmpeg with specific options.
        """
        logger.info(f"Exporting M4B to {output_path}")
        
        # M4B export would require:
        # 1. Concatenate audio files
        # 2. Add chapter metadata
        # 3. Add book metadata (title, author, cover)
        # 4. Convert to M4B format
        
        # For now, just create a placeholder
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save chapter info as JSON for now
        chapter_file = output_path.with_suffix('.chapters.json')
        chapter_data = [
            {
                'title': c.title,
                'start_time_ms': c.start_time_ms,
                'end_time_ms': c.end_time_ms
            }
            for c in self.chapters
        ]
        
        with open(chapter_file, 'w') as f:
            json.dump(chapter_data, f, indent=2)
        
        logger.info(f"Chapter info saved to {chapter_file}")
        logger.warning("Full M4B export requires ffmpeg. Use: ffmpeg -i input.mp3 -f mp4 -c copy output.m4b")


class ChapteredMP3Exporter:
    """Export audiobook as chaptered MP3 files."""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_chapters(
        self,
        chapters: List[Chapter],
        base_filename: str = "chapter"
    ) -> List[str]:
        """
        Export chapters as separate MP3 files.
        
        Args:
            chapters: List of chapters with file paths
            base_filename: Base name for output files
            
        Returns:
            List of output file paths
        """
        output_files = []
        
        for i, chapter in enumerate(chapters):
            if chapter.file_path and Path(chapter.file_path).exists():
                output_name = f"{base_filename}_{i+1:03d}_{self._sanitize_filename(chapter.title)}.mp3"
                output_path = self.output_dir / output_name
                
                # Copy file (in real implementation, would extract segment)
                import shutil
                shutil.copy2(chapter.file_path, output_path)
                
                output_files.append(str(output_path))
                logger.debug(f"Exported chapter {i+1}: {output_path}")
        
        return output_files
    
    def create_m3u_playlist(self, chapters: List[Chapter], playlist_name: str = "audiobook"):
        """Create M3U playlist for chapters."""
        playlist_path = self.output_dir / f"{playlist_name}.m3u"
        
        with open(playlist_path, 'w') as f:
            f.write("#EXTM3U\n")
            
            for i, chapter in enumerate(chapters):
                duration_sec = (chapter.end_time_ms - chapter.start_time_ms) // 1000
                f.write(f"#EXTINF:{duration_sec},{chapter.title}\n")
                
                filename = f"chapter_{i+1:03d}_{self._sanitize_filename(chapter.title)}.mp3"
                f.write(f"{filename}\n")
        
        logger.info(f"Playlist created: {playlist_path}")
        return str(playlist_path)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem."""
        import re
        sanitized = re.sub(r'[\u003c\u003e:"/\\|?*]', '', filename)
        sanitized = re.sub(r'\s+', '_', sanitized)
        return sanitized[:50]  # Limit length


class AudiobookExporter:
    """Main exporter class supporting multiple formats."""
    
    SUPPORTED_FORMATS = ['mp3', 'm4b', 'm4a', 'wav', 'ogg']
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export(
        self,
        audio_file: str,
        format: str,
        metadata: Optional[Dict[str, Any]] = None,
        chapters: Optional[List[Chapter]] = None
    ) -> str:
        """
        Export audiobook to specified format.
        
        Args:
            audio_file: Input audio file
            format: Output format (mp3, m4b, etc.)
            metadata: Book metadata
            chapters: Chapter information
            
        Returns:
            Output file path
        """
        format = format.lower()
        
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {format}")
        
        input_path = Path(audio_file)
        output_path = self.output_dir / f"{input_path.stem}.{format}"
        
        if format == 'm4b':
            # Use M4B exporter
            exporter = M4BExporter()
            if chapters:
                for ch in chapters:
                    exporter.add_chapter(ch.title, ch.start_time_ms, ch.end_time_ms)
            exporter.export([audio_file], str(output_path), metadata)
        else:
            # For other formats, use pydub
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(audio_file)
                audio.export(str(output_path), format=format)
                logger.info(f"Exported to {output_path}")
            except Exception as e:
                logger.error(f"Export failed: {e}")
                raise
        
        return str(output_path)
