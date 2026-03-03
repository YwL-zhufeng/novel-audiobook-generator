"""
Smart chapter detection based on text analysis.
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import logging

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Chapter:
    """Represents a detected chapter."""
    title: str
    start_pos: int  # Character position in text
    end_pos: int
    level: int  # Heading level (1 = top level)
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def length(self) -> int:
        """Get chapter length in characters."""
        return self.end_pos - self.start_pos
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'start_pos': self.start_pos,
            'end_pos': self.end_pos,
            'level': self.level,
            'length': self.length,
            'metadata': self.metadata,
        }


@dataclass
class ChapterDetectionResult:
    """Result of chapter detection."""
    chapters: List[Chapter]
    total_chapters: int
    avg_chapter_length: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_chapters': self.total_chapters,
            'avg_chapter_length': round(self.avg_chapter_length, 2),
            'chapters': [c.to_dict() for c in self.chapters],
        }


class ChapterDetector:
    """
    Detect chapters in novel text using multiple strategies.
    
    Supports:
    - Pattern-based detection (numbered chapters, titles)
    - Content-based detection (paragraph density changes)
    - Structure-based detection (HTML/markdown headings)
    """
    
    # Common chapter patterns
    CHAPTER_PATTERNS = [
        # English patterns
        (r'^(?:Chapter|CHAPTER)\s+(\d+|[IVX]+)[\s:.-]*(.+)?$', 1),
        (r'^(?:Ch\.?|CH\.?)\s*(\d+)[\s:.-]*(.+)?$', 1),
        (r'^\s*(\d+)[\.\s]+(.+)$', 1),  # "1. Chapter Title"
        
        # Chinese patterns
        (r'^(?:第\s*(\d+|[一二三四五六七八九十百千]+)\s*章)[\s:：]*(.+)?$', 1),
        (r'^(?:第\s*(\d+)\s*节)[\s:：]*(.+)?$', 2),
        (r'^(?:第\s*(\d+)\s*回)[\s:：]*(.+)?$', 1),
        
        # Markdown/HTML headings
        (r'^(#{1,6})\s+(.+)$', 0),  # Will calculate level from # count
        
        # Special markers
        (r'^\*{3,}\s*(.+?)\s*\*{3,}$', 1),
        (r'^={3,}\s*(.+?)\s*={3,}$', 1),
        (r'^-{3,}\s*(.+?)\s*-{3,}$', 1),
    ]
    
    def __init__(
        self,
        min_chapter_length: int = 500,
        max_chapter_length: int = 50000,
        confidence_threshold: float = 0.7
    ):
        """
        Initialize chapter detector.
        
        Args:
            min_chapter_length: Minimum characters per chapter
            max_chapter_length: Maximum characters per chapter
            confidence_threshold: Minimum confidence for pattern matches
        """
        self.min_chapter_length = min_chapter_length
        self.max_chapter_length = max_chapter_length
        self.confidence_threshold = confidence_threshold
    
    def detect_chapters(
        self,
        text: str,
        method: str = "auto"
    ) -> ChapterDetectionResult:
        """
        Detect chapters in text.
        
        Args:
            text: Text to analyze
            method: Detection method ('pattern', 'content', 'structure', 'auto')
            
        Returns:
            ChapterDetectionResult
        """
        if method == "auto":
            # Try pattern-based first, fall back to content-based
            chapters = self._detect_by_pattern(text)
            if len(chapters) < 2:
                chapters = self._detect_by_content(text)
        elif method == "pattern":
            chapters = self._detect_by_pattern(text)
        elif method == "content":
            chapters = self._detect_by_content(text)
        elif method == "structure":
            chapters = self._detect_by_structure(text)
        else:
            raise ValueError(f"Unknown detection method: {method}")
        
        # Filter and validate chapters
        chapters = self._filter_chapters(chapters, len(text))
        
        # Calculate statistics
        if chapters:
            avg_length = sum(c.length for c in chapters) / len(chapters)
        else:
            avg_length = 0.0
        
        logger.info(f"Detected {len(chapters)} chapters (avg length: {avg_length:.0f} chars)")
        
        return ChapterDetectionResult(
            chapters=chapters,
            total_chapters=len(chapters),
            avg_chapter_length=avg_length
        )
    
    def _detect_by_pattern(self, text: str) -> List[Chapter]:
        """Detect chapters using pattern matching."""
        chapters = []
        lines = text.split('\n')
        
        current_pos = 0
        last_chapter_end = 0
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            
            for pattern, default_level in self.CHAPTER_PATTERNS:
                match = re.match(pattern, line_stripped, re.IGNORECASE)
                if match:
                    # Calculate level
                    if default_level == 0:
                        # Markdown heading - count #
                        level = len(match.group(1))
                        title = match.group(2).strip() if match.group(2) else f"Chapter {len(chapters) + 1}"
                    else:
                        level = default_level
                        # Try to extract chapter number and title
                        groups = match.groups()
                        if len(groups) >= 2 and groups[1]:
                            title = groups[1].strip()
                        elif len(groups) >= 1 and groups[0]:
                            title = f"Chapter {groups[0]}"
                        else:
                            title = f"Chapter {len(chapters) + 1}"
                    
                    # Close previous chapter
                    if chapters:
                        chapters[-1].end_pos = current_pos
                        chapters[-1].content = text[chapters[-1].start_pos:chapters[-1].end_pos]
                    
                    # Create new chapter
                    chapter = Chapter(
                        title=title,
                        start_pos=current_pos,
                        end_pos=len(text),  # Will be updated
                        level=level
                    )
                    chapters.append(chapter)
                    last_chapter_end = current_pos
                    break
            
            current_pos += len(line) + 1  # +1 for newline
        
        # Close final chapter
        if chapters:
            chapters[-1].end_pos = len(text)
            chapters[-1].content = text[chapters[-1].start_pos:chapters[-1].end_pos]
        
        return chapters
    
    def _detect_by_content(self, text: str) -> List[Chapter]:
        """
        Detect chapters by analyzing content structure.
        
        Uses paragraph density and spacing to identify chapter boundaries.
        """
        chapters = []
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if len(paragraphs) < 10:
            # Too short - treat as single chapter
            return [Chapter(
                title="Chapter 1",
                start_pos=0,
                end_pos=len(text),
                level=1,
                content=text
            )]
        
        # Look for significant spacing or paragraph count changes
        chapter_starts = [0]  # First paragraph is always a chapter start
        
        prev_para_length = len(paragraphs[0])
        current_pos = len(paragraphs[0]) + 2  # +2 for \n\n
        
        for i, para in enumerate(paragraphs[1:], 1):
            para_length = len(para)
            
            # Heuristics for chapter boundaries
            is_chapter_start = False
            
            # 1. Very short paragraph followed by longer one (chapter title)
            if para_length < 100 and prev_para_length > 500:
                is_chapter_start = True
            
            # 2. Paragraph starts with common chapter indicators
            if re.match(r'^(Chapter|CHAPTER|第\d+章|第[一二三四五六七八九十]+章)', para):
                is_chapter_start = True
            
            # 3. Significant change in paragraph length (possible scene break)
            if i > 0 and para_length > prev_para_length * 3 and para_length > 1000:
                # Check if previous paragraph was short (scene break)
                if prev_para_length < 200:
                    is_chapter_start = True
            
            if is_chapter_start:
                chapter_starts.append(current_pos)
            
            prev_para_length = para_length
            current_pos += para_length + 2
        
        # Create chapters from detected boundaries
        for i, start in enumerate(chapter_starts):
            end = chapter_starts[i + 1] if i + 1 < len(chapter_starts) else len(text)
            
            # Extract title from first line of content
            content = text[start:end]
            first_line = content.split('\n')[0].strip()
            
            # Clean up title
            title = first_line[:100] if len(first_line) < 100 else first_line[:97] + "..."
            
            chapter = Chapter(
                title=title or f"Chapter {i + 1}",
                start_pos=start,
                end_pos=end,
                level=1,
                content=content
            )
            chapters.append(chapter)
        
        return chapters
    
    def _detect_by_structure(self, text: str) -> List[Chapter]:
        """Detect chapters from HTML/markdown structure."""
        chapters = []
        
        # Find all heading tags
        heading_pattern = r'<(h[1-6])(?:[^\u003e]*?)\u003e(.*?)\u003c/\1\u003e'
        matches = list(re.finditer(heading_pattern, text, re.IGNORECASE | re.DOTALL))
        
        if not matches:
            # Try markdown style
            return self._detect_by_pattern(text)
        
        for i, match in enumerate(matches):
            level = int(match.group(1)[1])  # h1 -> 1, h2 -> 2, etc.
            title = re.sub(r'<[^\u003e]+>', '', match.group(2)).strip()  # Remove inner tags
            
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            
            chapter = Chapter(
                title=title or f"Section {i + 1}",
                start_pos=start,
                end_pos=end,
                level=level,
                content=text[start:end]
            )
            chapters.append(chapter)
        
        return chapters
    
    def _filter_chapters(self, chapters: List[Chapter], text_length: int) -> List[Chapter]:
        """Filter and validate detected chapters."""
        if not chapters:
            # Create single chapter for entire text
            return [Chapter(
                title="Complete Book",
                start_pos=0,
                end_pos=text_length,
                level=1,
                content=text
            )]
        
        filtered = []
        
        for chapter in chapters:
            # Skip chapters that are too short
            if chapter.length < self.min_chapter_length:
                logger.debug(f"Skipping chapter '{chapter.title}' - too short ({chapter.length} chars)")
                continue
            
            # Split chapters that are too long
            if chapter.length > self.max_chapter_length:
                sub_chapters = self._split_long_chapter(chapter)
                filtered.extend(sub_chapters)
            else:
                filtered.append(chapter)
        
        # Merge chapters that are too close together
        merged = self._merge_close_chapters(filtered)
        
        return merged if merged else chapters
    
    def _split_long_chapter(self, chapter: Chapter) -> List[Chapter]:
        """Split a chapter that exceeds max length."""
        sub_chapters = []
        content = chapter.content
        
        # Split into roughly equal parts
        num_parts = (len(content) // self.max_chapter_length) + 1
        part_length = len(content) // num_parts
        
        for i in range(num_parts):
            start = i * part_length
            end = (i + 1) * part_length if i < num_parts - 1 else len(content)
            
            # Adjust to paragraph boundary
            if i < num_parts - 1:
                # Find next paragraph break
                next_break = content.find('\n\n', end - 100, end + 100)
                if next_break != -1:
                    end = next_break
            
            sub_content = content[start:end]
            sub_chapter = Chapter(
                title=f"{chapter.title} (Part {i + 1})",
                start_pos=chapter.start_pos + start,
                end_pos=chapter.start_pos + end,
                level=chapter.level + 1,
                content=sub_content
            )
            sub_chapters.append(sub_chapter)
        
        return sub_chapters
    
    def _merge_close_chapters(self, chapters: List[Chapter]) -> List[Chapter]:
        """Merge chapters that are too close together."""
        if len(chapters) <= 1:
            return chapters
        
        merged = [chapters[0]]
        
        for chapter in chapters[1:]:
            prev = merged[-1]
            
            # If chapters are very close, merge them
            if chapter.start_pos - prev.end_pos < 100:
                prev.end_pos = chapter.end_pos
                prev.content = prev.content + '\n\n' + chapter.content
                prev.title = f"{prev.title} / {chapter.title}"
            else:
                merged.append(chapter)
        
        return merged
    
    def get_chapter_positions(self, result: ChapterDetectionResult) -> List[Tuple[str, int]]:
        """
        Get list of chapter titles with their start positions.
        
        Useful for creating chapter markers in audio files.
        """
        return [(c.title, c.start_pos) for c in result.chapters]
    
    def export_chapters(
        self,
        text: str,
        output_dir: str,
        result: Optional[ChapterDetectionResult] = None
    ) -> List[str]:
        """
        Export chapters as separate text files.
        
        Args:
            text: Full text
            output_dir: Output directory
            result: Optional pre-computed detection result
            
        Returns:
            List of output file paths
        """
        if result is None:
            result = self.detect_chapters(text)
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        files = []
        for i, chapter in enumerate(result.chapters):
            # Sanitize filename
            safe_title = re.sub(r'[^\w\s-]', '', chapter.title).strip()[:50]
            filename = f"chapter_{i+1:03d}_{safe_title}.txt"
            
            file_path = output_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {chapter.title}\n\n")
                f.write(chapter.content)
            
            files.append(str(file_path))
        
        logger.info(f"Exported {len(files)} chapters to {output_dir}")
        return files
