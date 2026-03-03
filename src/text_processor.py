"""
Text processing module for extracting and preprocessing novel text.
"""

import re
import html
import logging
from pathlib import Path
from typing import List, Optional, Iterator, Union, BinaryIO
from io import StringIO

from .exceptions import TextProcessingError, FileFormatError
from .logging_config import get_logger

logger = get_logger(__name__)

try:
    import ebooklib
    from ebooklib import epub
    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False
    logger.warning("ebooklib not available, EPUB support disabled")

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logger.warning("PyPDF2 not available, PDF support disabled")


class TextProcessor:
    """Process and extract text from various novel formats."""
    
    # Supported formats
    SUPPORTED_FORMATS = {'.txt', '.epub', '.pdf'}
    
    # Default chunk size for streaming
    DEFAULT_CHUNK_SIZE = 8192
    
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE):
        """
        Initialize text processor.
        
        Args:
            chunk_size: Buffer size for file reading
        """
        self.chunk_size = chunk_size
    
    def extract_text(self, file_path: Union[str, Path]) -> str:
        """
        Extract text from novel file.
        
        Args:
            file_path: Path to novel file
            
        Returns:
            Extracted text content
            
        Raises:
            FileFormatError: If file format is not supported
            TextProcessingError: If extraction fails
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        extension = path.suffix.lower()
        
        if extension == '.txt':
            return self._extract_txt(path)
        elif extension == '.epub':
            return self._extract_epub(path)
        elif extension == '.pdf':
            return self._extract_pdf(path)
        else:
            raise FileFormatError(
                f"Unsupported file format: {extension}",
                file_path=str(path),
                supported_formats=list(self.SUPPORTED_FORMATS)
            )
    
    def extract_text_streaming(
        self,
        file_path: Union[str, Path],
        max_chars: Optional[int] = None
    ) -> Iterator[str]:
        """
        Extract text in streaming fashion for large files.
        
        Args:
            file_path: Path to novel file
            max_chars: Maximum characters to extract (None for all)
            
        Yields:
            Text chunks
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension == '.txt':
            yield from self._extract_txt_streaming(path, max_chars)
        elif extension == '.epub':
            # EPUB doesn't support true streaming, yield whole text
            text = self._extract_epub(path)
            if max_chars:
                text = text[:max_chars]
            yield text
        elif extension == '.pdf':
            # PDF doesn't support true streaming, yield whole text
            text = self._extract_pdf(path)
            if max_chars:
                text = text[:max_chars]
            yield text
        else:
            raise FileFormatError(
                f"Unsupported file format: {extension}",
                file_path=str(path),
                supported_formats=list(self.SUPPORTED_FORMATS)
            )
    
    def _extract_txt(self, file_path: Path) -> str:
        """Extract text from TXT file."""
        try:
            # Try UTF-8 first
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fall back to other encodings
            for encoding in ['gbk', 'gb2312', 'big5', 'latin-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            # Last resort: read with errors ignored
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    
    def _extract_txt_streaming(
        self,
        file_path: Path,
        max_chars: Optional[int] = None
    ) -> Iterator[str]:
        """Stream text from TXT file."""
        chars_read = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    if max_chars:
                        remaining = max_chars - chars_read
                        if remaining <= 0:
                            break
                        if len(chunk) > remaining:
                            chunk = chunk[:remaining]
                    
                    chars_read += len(chunk)
                    yield chunk
        except UnicodeDecodeError:
            # Fall back to reading whole file with error handling
            text = self._extract_txt(file_path)
            if max_chars:
                text = text[:max_chars]
            yield text
    
    def _extract_epub(self, file_path: Path) -> str:
        """Extract text from EPUB file."""
        if not EBOOKLIB_AVAILABLE:
            raise ImportError(
                "ebooklib is required for EPUB processing. "
                "Install with: pip install ebooklib"
            )
        
        try:
            book = epub.read_epub(str(file_path))
            texts = []
            
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    # Extract text from HTML content
                    content = item.get_content().decode('utf-8', errors='ignore')
                    text = self._clean_html(content)
                    if text.strip():
                        texts.append(text)
            
            return '\n\n'.join(texts)
        except Exception as e:
            raise TextProcessingError(
                f"Failed to extract EPUB: {e}",
                file_path=str(file_path)
            )
    
    def _extract_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        if not PYPDF2_AVAILABLE:
            raise ImportError(
                "PyPDF2 is required for PDF processing. "
                "Install with: pip install PyPDF2"
            )
        
        try:
            texts = []
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text:
                        texts.append(text)
            
            return '\n\n'.join(texts)
        except Exception as e:
            raise TextProcessingError(
                f"Failed to extract PDF: {e}",
                file_path=str(file_path)
            )
    
    def _clean_html(self, html_content: str) -> str:
        """Remove HTML tags and clean text."""
        # Remove script and style elements
        text = re.sub(r'<script.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        text = re.sub(r'<[^\u003e]+?>', ' ', text)
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def split_into_chunks(self, text: str, max_chars: int = 5000) -> List[str]:
        """
        Split text into chunks for TTS processing.
        
        Args:
            text: Full text content
            max_chars: Maximum characters per chunk
            
        Returns:
            List of text chunks
        """
        chunks = []
        current_chunk = []
        current_length = 0
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # If paragraph itself is too long, split by sentences
            if len(paragraph) > max_chars:
                sentences = self._split_into_sentences(paragraph)
                for sentence in sentences:
                    if current_length + len(sentence) > max_chars:
                        if current_chunk:
                            chunks.append(' '.join(current_chunk))
                            current_chunk = []
                            current_length = 0
                    
                    current_chunk.append(sentence)
                    current_length += len(sentence)
            else:
                if current_length + len(paragraph) > max_chars:
                    if current_chunk:
                        chunks.append(' '.join(current_chunk))
                        current_chunk = []
                        current_length = 0
                
                current_chunk.append(paragraph)
                current_length += len(paragraph)
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Handles both English and Chinese sentence boundaries.
        """
        # Pattern for sentence boundaries
        # Matches: . ! ? 。 ！ ？ followed by space or end of string
        pattern = r'(?<=[.!?。！？])\s+'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def preprocess_for_tts(self, text: str) -> str:
        """
        Preprocess text for better TTS quality.
        
        Args:
            text: Raw text
            
        Returns:
            Preprocessed text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove URLs
        text = re.sub(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            '',
            text
        )
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Clean up punctuation spacing
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        
        # Remove control characters
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        return text.strip()
    
    def estimate_reading_time(self, text: str, words_per_minute: int = 150) -> float:
        """
        Estimate reading time in minutes.
        
        Args:
            text: Text content
            words_per_minute: Average reading speed
            
        Returns:
            Estimated reading time in minutes
        """
        # Count words (rough estimate)
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        other_words = len(re.findall(r'\b\w+\b', text))
        
        # Chinese characters count as words, plus other word tokens
        total_words = chinese_chars + other_words
        
        return total_words / words_per_minute
