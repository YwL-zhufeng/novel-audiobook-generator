"""
Unit tests for chapter detection.
"""

import pytest
from src.chapter_detector import ChapterDetector, Chapter, ChapterDetectionResult


class TestChapterDetector:
    """Test chapter detection functionality."""
    
    @pytest.fixture
    def detector(self):
        """Create chapter detector."""
        return ChapterDetector(
            min_chapter_length=100,
            max_chapter_length=10000
        )
    
    def test_detect_numbered_chapters(self, detector):
        """Test detecting numbered chapters."""
        text = """
Chapter 1: The Beginning

This is the first chapter content. It has some text here.
More text continues here.

Chapter 2: The Middle

This is the second chapter. It also has content.
Even more content here.

Chapter 3: The End

Final chapter content goes here.
"""
        
        result = detector.detect_chapters(text)
        
        assert result.total_chapters == 3
        assert len(result.chapters) == 3
        assert result.chapters[0].title == "The Beginning"
        assert result.chapters[1].title == "The Middle"
        assert result.chapters[2].title == "The End"
    
    def test_detect_chinese_chapters(self, detector):
        """Test detecting Chinese chapter markers."""
        text = """
第一章：开始

这是第一章的内容。
有很多文字在这里。

第二章：中间

这是第二章的内容。
更多的文字在这里。

第三章：结束

最后一章的内容。
"""
        
        result = detector.detect_chapters(text)
        
        assert result.total_chapters == 3
        assert "第一章" in result.chapters[0].title or "开始" in result.chapters[0].title
    
    def test_detect_markdown_headings(self, detector):
        """Test detecting markdown headings."""
        text = """
# Introduction

Intro content here.

# Chapter 1

First chapter content.

## Section 1.1

Subsection content.

# Chapter 2

Second chapter content.
"""
        
        result = detector.detect_chapters(text, method="pattern")
        
        assert result.total_chapters >= 2
    
    def test_single_chapter_fallback(self, detector):
        """Test fallback to single chapter when no markers found."""
        text = "This is just some text without any chapter markers. " * 50
        
        result = detector.detect_chapters(text)
        
        assert result.total_chapters == 1
        assert result.chapters[0].title == "Complete Book"
    
    def test_chapter_positions(self, detector):
        """Test chapter position detection."""
        text = """Chapter 1

Content of chapter 1.
More content.

Chapter 2

Content of chapter 2.
"""
        
        result = detector.detect_chapters(text)
        
        assert result.chapters[0].start_pos == 0
        assert result.chapters[0].end_pos > result.chapters[0].start_pos
        assert result.chapters[1].start_pos > result.chapters[0].start_pos
    
    def test_filter_short_chapters(self, detector):
        """Test filtering of short chapters."""
        text = """
Chapter 1

This is a very short chapter.

Chapter 2

This chapter has much more content. " * 100

Chapter 3

Another short one.
"""
        
        result = detector.detect_chapters(text)
        
        # Short chapters should be filtered
        for chapter in result.chapters:
            assert chapter.length >= detector.min_chapter_length
    
    def test_export_chapters(self, detector, tmp_path):
        """Test exporting chapters to files."""
        text = """
Chapter 1: First

Content of first chapter.

Chapter 2: Second

Content of second chapter.
"""
        
        result = detector.detect_chapters(text)
        output_dir = tmp_path / "chapters"
        
        files = detector.export_chapters(text, str(output_dir), result)
        
        assert len(files) == 2
        for file_path in files:
            assert Path(file_path).exists()


class TestChapter:
    """Test Chapter dataclass."""
    
    def test_chapter_creation(self):
        """Test creating a chapter."""
        chapter = Chapter(
            title="Test Chapter",
            start_pos=0,
            end_pos=100,
            level=1,
            content="Test content"
        )
        
        assert chapter.title == "Test Chapter"
        assert chapter.length == 100
    
    def test_chapter_to_dict(self):
        """Test chapter serialization."""
        chapter = Chapter(
            title="Test",
            start_pos=0,
            end_pos=100,
            level=1,
            metadata={"key": "value"}
        )
        
        data = chapter.to_dict()
        
        assert data['title'] == "Test"
        assert data['length'] == 100
        assert data['metadata'] == {"key": "value"}


class TestChapterDetectionResult:
    """Test ChapterDetectionResult."""
    
    def test_empty_result(self):
        """Test empty detection result."""
        result = ChapterDetectionResult(
            chapters=[],
            total_chapters=0,
            avg_chapter_length=0.0
        )
        
        assert result.total_chapters == 0
        assert result.avg_chapter_length == 0.0
    
    def test_result_with_chapters(self):
        """Test result with chapters."""
        chapters = [
            Chapter("Ch1", 0, 100, 1),
            Chapter("Ch2", 100, 300, 1),
        ]
        
        result = ChapterDetectionResult(
            chapters=chapters,
            total_chapters=2,
            avg_chapter_length=200.0
        )
        
        assert result.total_chapters == 2
        assert result.avg_chapter_length == 200.0
    
    def test_result_to_dict(self):
        """Test result serialization."""
        chapters = [Chapter("Ch1", 0, 100, 1)]
        
        result = ChapterDetectionResult(
            chapters=chapters,
            total_chapters=1,
            avg_chapter_length=100.0
        )
        
        data = result.to_dict()
        
        assert data['total_chapters'] == 1
        assert data['avg_chapter_length'] == 100.0
        assert len(data['chapters']) == 1
