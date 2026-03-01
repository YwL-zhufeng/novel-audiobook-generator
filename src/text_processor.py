"""
Text processing module for extracting and preprocessing novel text.
"""

import re
import logging
from pathlib import Path
from typing import List, Optional

try:
    import ebooklib
    from ebooklib import epub
    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

logger = logging.getLogger(__name__)


class TextProcessor:
    """Process and extract text from various novel formats."""
    
    def __init__(self):
        self.supported_formats = ['.txt', '.epub', '.pdf']
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from novel file.
        
        Args:
            file_path: Path to novel file
            
        Returns:
            Extracted text content
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension == '.txt':
            return self._extract_txt(file_path)
        elif extension == '.epub':
            return self._extract_epub(file_path)
        elif extension == '.pdf':
            return self._extract_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file format: {extension}")
    
    def _extract_txt(self, file_path: str) -> str:
        """Extract text from TXT file."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _extract_epub(self, file_path: str) -> str:
        """Extract text from EPUB file."""
        if not EBOOKLIB_AVAILABLE:
            raise ImportError("ebooklib is required for EPUB processing. Install with: pip install ebooklib")
        
        book = epub.read_epub(file_path)
        texts = []
        
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # Extract text from HTML content
                content = item.get_content().decode('utf-8', errors='ignore')
                text = self._clean_html(content)
                texts.append(text)
        
        return '\n\n'.join(texts)
    
    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        if not PYPDF2_AVAILABLE:
            raise ImportError("PyPDF2 is required for PDF processing. Install with: pip install PyPDF2")
        
        texts = []
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
        
        return '\n\n'.join(texts)
    
    def _clean_html(self, html: str) -> str:
        """Remove HTML tags and clean text."""
        # Remove script and style elements
        text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+?>', ' ', text)
        
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        
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
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
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
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Clean up punctuation spacing
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        
        return text.strip()
