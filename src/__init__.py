"""
Novel Audiobook Generator
Main generator class for converting novels to audiobooks.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, List
import tempfile

from .text_processor import TextProcessor
from .voice_manager import VoiceManager
from .audio_utils import AudioUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudiobookGenerator:
    """Main class for generating audiobooks from novels."""
    
    def __init__(
        self,
        tts_backend: str = "elevenlabs",
        api_key: Optional[str] = None,
        output_dir: str = "output",
        temp_dir: Optional[str] = None
    ):
        """
        Initialize the audiobook generator.
        
        Args:
            tts_backend: TTS backend to use ('elevenlabs', 'xtts', 'kokoro')
            api_key: API key for cloud TTS services
            output_dir: Directory for output files
            temp_dir: Directory for temporary files
        """
        self.tts_backend = tts_backend
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "audiobook_gen"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.text_processor = TextProcessor()
        self.voice_manager = VoiceManager(tts_backend, api_key)
        self.audio_utils = AudioUtils()
        
        logger.info(f"Initialized AudiobookGenerator with {tts_backend} backend")
    
    def clone_voice(
        self,
        voice_name: str,
        sample_audio_path: str,
        description: Optional[str] = None
    ) -> str:
        """
        Clone a voice from audio sample.
        
        Args:
            voice_name: Name for the cloned voice
            sample_audio_path: Path to voice sample audio file
            description: Optional voice description
            
        Returns:
            Voice ID for the cloned voice
        """
        return self.voice_manager.clone_voice(voice_name, sample_audio_path, description)
    
    def generate_audiobook(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        voice: str = "default",
        chunk_size: int = 5000,
        progress_callback: Optional[callable] = None
    ) -> str:
        """
        Generate audiobook from novel file.
        
        Args:
            input_path: Path to novel file (TXT, EPUB, PDF)
            output_path: Output audio file path
            voice: Voice to use (name or ID)
            chunk_size: Maximum characters per TTS chunk
            progress_callback: Optional callback for progress updates
            
        Returns:
            Path to generated audiobook file
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Set default output path
        if output_path is None:
            output_path = self.output_dir / f"{input_path.stem}_audiobook.mp3"
        else:
            output_path = Path(output_path)
        
        logger.info(f"Processing {input_path}")
        
        # Extract text
        text = self.text_processor.extract_text(str(input_path))
        logger.info(f"Extracted {len(text)} characters")
        
        # Split into chunks
        chunks = self.text_processor.split_into_chunks(text, chunk_size)
        logger.info(f"Split into {len(chunks)} chunks")
        
        # Generate audio for each chunk
        audio_segments = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            
            # Generate audio
            audio_path = self.temp_dir / f"chunk_{i:04d}.mp3"
            self.voice_manager.generate_speech(chunk, voice, str(audio_path))
            audio_segments.append(str(audio_path))
            
            if progress_callback:
                progress_callback((i + 1) / len(chunks))
        
        # Concatenate audio segments
        logger.info("Concatenating audio segments...")
        self.audio_utils.concatenate_audio_files(audio_segments, str(output_path))
        
        # Cleanup temp files
        for segment in audio_segments:
            Path(segment).unlink(missing_ok=True)
        
        logger.info(f"Audiobook saved to {output_path}")
        return str(output_path)
    
    def generate_with_character_voices(
        self,
        input_path: str,
        character_voices: Dict[str, str],
        narrator_voice: str = "default",
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate audiobook with different voices for characters.
        
        Args:
            input_path: Path to novel file
            character_voices: Mapping of character names to voice IDs
            narrator_voice: Voice for narration
            output_path: Output audio file path
            
        Returns:
            Path to generated audiobook file
        """
        # TODO: Implement dialogue detection and character voice assignment
        raise NotImplementedError("Character voice feature coming soon")
