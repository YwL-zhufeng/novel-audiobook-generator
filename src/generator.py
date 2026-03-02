"""
Novel Audiobook Generator
Main generator class for converting novels to audiobooks.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, List, Callable
from concurrent.futures import ThreadPoolExecutor
import tempfile

from .text_processor import TextProcessor
from .dialogue_detector import DialogueDetector, DialogueSegment
from .voice_manager import VoiceManager
from .audio_utils import AudioUtils
from .config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudiobookGenerator:
    """Main class for generating audiobooks from novels."""
    
    def __init__(
        self,
        tts_backend: str = "elevenlabs",
        api_key: Optional[str] = None,
        output_dir: str = "output",
        temp_dir: Optional[str] = None,
        max_workers: int = 4,
        config: Optional[Config] = None
    ):
        """
        Initialize the audiobook generator.
        
        Args:
            tts_backend: TTS backend to use ('elevenlabs', 'xtts', 'kokoro')
            api_key: API key for cloud TTS services
            output_dir: Directory for output files
            temp_dir: Directory for temporary files
            max_workers: Maximum concurrent workers for TTS generation
            config: Configuration object
        """
        self.config = config
        self.tts_backend = tts_backend
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "audiobook_gen"
        self.temp_dir.mkdir(exist_ok=True)
        
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Initialize components
        self.text_processor = TextProcessor()
        self.dialogue_detector = DialogueDetector()
        self.voice_manager = VoiceManager(tts_backend, api_key)
        self.audio_utils = AudioUtils()
        
        # Progress tracking
        self.progress_file = self.temp_dir / "progress.json"
        
        logger.info(f"Initialized AudiobookGenerator with {tts_backend} backend ({max_workers} workers)")
    
    def clone_voice(
        self,
        voice_name: str,
        sample_audio_path: str,
        description: Optional[str] = None
    ) -> str:
        """Clone a voice from audio sample."""
        return self.voice_manager.clone_voice(voice_name, sample_audio_path, description)
    
    def generate_audiobook(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        voice: str = "default",
        chunk_size: int = 5000,
        progress_callback: Optional[Callable] = None,
        resume: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate audiobook from novel file with concurrent processing.
        
        Args:
            input_path: Path to novel file
            output_path: Output audio file path
            voice: Voice to use
            chunk_size: Maximum characters per chunk
            progress_callback: Optional progress callback
            resume: Whether to resume from previous run
            metadata: Optional metadata dict (title, artist, album, cover_image, etc.)
            
        Returns:
            Path to generated audiobook file
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        if output_path is None:
            output_path = self.output_dir / f"{input_path.stem}_audiobook.mp3"
        else:
            output_path = Path(output_path)
        
        # Load progress if resuming
        progress = self._load_progress() if resume else {}
        completed_chunks = set(progress.get('completed_chunks', []))
        
        logger.info(f"Processing {input_path}")
        
        # Extract and process text
        text = self.text_processor.extract_text(str(input_path))
        logger.info(f"Extracted {len(text)} characters")
        
        chunks = self.text_processor.split_into_chunks(text, chunk_size)
        logger.info(f"Split into {len(chunks)} chunks")
        
        # Generate audio concurrently
        audio_segments = [None] * len(chunks)
        
        def generate_chunk(args):
            idx, chunk_text = args
            if idx in completed_chunks:
                # Reuse existing audio
                existing_path = self.temp_dir / f"chunk_{idx:04d}.mp3"
                if existing_path.exists():
                    logger.info(f"Reusing chunk {idx+1}/{len(chunks)}")
                    return idx, str(existing_path)
            
            audio_path = self.temp_dir / f"chunk_{idx:04d}.mp3"
            try:
                self.voice_manager.generate_speech(chunk_text, voice, str(audio_path))
                logger.info(f"Generated chunk {idx+1}/{len(chunks)}")
                return idx, str(audio_path)
            except Exception as e:
                logger.error(f"Failed to generate chunk {idx+1}: {e}")
                raise
        
        # Process chunks in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(generate_chunk, (i, chunk))
                for i, chunk in enumerate(chunks)
            ]
            
            for i, future in enumerate(futures):
                idx, audio_path = future.result()
                audio_segments[idx] = audio_path
                completed_chunks.add(idx)
                
                # Save progress
                self._save_progress({
                    'input_file': str(input_path),
                    'completed_chunks': list(completed_chunks),
                    'total_chunks': len(chunks)
                })
                
                if progress_callback:
                    progress_callback((i + 1) / len(chunks))
        
        # Concatenate audio with metadata
        logger.info("Concatenating audio segments...")
        self.audio_utils.concatenate_audio_files(
            [s for s in audio_segments if s],
            str(output_path),
            metadata=metadata
        )
        
        # Cleanup
        self._cleanup_temp_files(audio_segments)
        self.progress_file.unlink(missing_ok=True)
        
        logger.info(f"Audiobook saved to {output_path}")
        return str(output_path)
    
    def generate_with_characters(
        self,
        input_path: str,
        narrator_voice: str = "default",
        character_voices: Optional[Dict[str, str]] = None,
        output_path: Optional[str] = None,
        auto_assign: bool = True
    ) -> str:
        """
        Generate audiobook with different voices for characters.
        
        Args:
            input_path: Path to novel file
            narrator_voice: Voice for narration
            character_voices: Mapping of character names to voice names
            output_path: Output audio file path
            auto_assign: Auto-assign voices to characters if not provided
            
        Returns:
            Path to generated audiobook file
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        if output_path is None:
            output_path = self.output_dir / f"{input_path.stem}_audiobook.mp3"
        
        # Extract text
        text = self.text_processor.extract_text(str(input_path))
        
        # Detect dialogue
        logger.info("Detecting dialogue segments...")
        segments = self.dialogue_detector.detect_dialogue(text)
        
        # Auto-assign voices if needed
        if auto_assign and not character_voices:
            available_voices = list(self.voice_manager.list_voices().keys())
            character_voices = self.dialogue_detector.assign_voices_to_characters(
                segments, available_voices
            )
            logger.info(f"Auto-assigned voices: {character_voices}")
        
        # Generate audio for each segment
        segment_files = []
        for i, segment in enumerate(segments):
            if segment.is_dialogue and segment.speaker and segment.speaker in character_voices:
                voice = character_voices[segment.speaker]
            else:
                voice = narrator_voice
            
            audio_path = self.temp_dir / f"segment_{i:04d}.mp3"
            self.voice_manager.generate_speech(segment.text, voice, str(audio_path))
            segment_files.append(str(audio_path))
            
            logger.info(f"Generated segment {i+1}/{len(segments)} ({segment.speaker or 'narrator'})")
        
        # Concatenate
        self.audio_utils.concatenate_audio_files(segment_files, str(output_path))
        self._cleanup_temp_files(segment_files)
        
        return str(output_path)
    
    def _load_progress(self) -> dict:
        """Load progress from file."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_progress(self, progress: dict):
        """Save progress to file."""
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f)
    
    def _cleanup_temp_files(self, files: List[str]):
        """Clean up temporary audio files."""
        for file_path in files:
            if file_path:
                Path(file_path).unlink(missing_ok=True)
    
    def generate_preview(
        self,
        text: str,
        voice: str = "default",
        preview_length: int = 200,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate a short preview audio from text.
        
        Args:
            text: Source text
            voice: Voice to use
            preview_length: Maximum characters for preview
            output_path: Output file path (optional)
            
        Returns:
            Path to generated preview audio
        """
        # Extract preview text (first N chars or first paragraph)
        preview_text = text[:preview_length].strip()
        
        # Try to end at a sentence boundary
        for end_char in ['.', '!', '?', '。', '！', '？', '\n']:
            if end_char in preview_text[100:]:  # At least 100 chars
                idx = preview_text.rfind(end_char, 100)
                if idx > 0:
                    preview_text = preview_text[:idx+1]
                    break
        
        if not output_path:
            output_path = self.temp_dir / f"preview_{voice}.mp3"
        else:
            output_path = Path(output_path)
        
        # Generate speech
        self.voice_manager.generate_speech(preview_text, voice, str(output_path))
        
        logger.info(f"Preview generated: {output_path} ({len(preview_text)} chars)")
        return str(output_path)
    
    def preview_with_characters(
        self,
        text: str,
        narrator_voice: str = "default",
        character_voices: Optional[Dict[str, str]] = None,
        preview_length: int = 500,
        output_path: Optional[str] = None
    ) -> tuple:
        """
        Generate preview with character voices.
        
        Returns:
            Tuple of (audio_path, preview_info)
        """
        # Detect dialogue in preview section
        segments = self.dialogue_detector.detect_dialogue(text[:preview_length*2])
        
        # Build preview segments
        preview_segments = []
        current_length = 0
        
        for segment in segments:
            if current_length + len(segment.text) > preview_length:
                break
            
            preview_segments.append(segment)
            current_length += len(segment.text)
        
        if not preview_segments:
            # Fallback to simple preview
            return self.generate_preview(text, narrator_voice, preview_length, output_path), "Narration only"
        
        # Generate audio for each segment
        segment_files = []
        segment_info = []
        
        for i, segment in enumerate(preview_segments):
            if segment.is_dialogue and segment.speaker and character_voices and segment.speaker in character_voices:
                voice = character_voices[segment.speaker]
                speaker = segment.speaker
            else:
                voice = narrator_voice
                speaker = "Narrator"
            
            audio_path = self.temp_dir / f"preview_seg_{i:03d}.mp3"
            self.voice_manager.generate_speech(segment.text, voice, str(audio_path))
            segment_files.append(str(audio_path))
            segment_info.append(f"{speaker}: {segment.text[:50]}...")
        
        # Concatenate
        if not output_path:
            output_path = self.temp_dir / "preview_characters.mp3"
        else:
            output_path = Path(output_path)
        
        self.audio_utils.concatenate_audio_files(segment_files, str(output_path))
        
        # Cleanup segment files
        self._cleanup_temp_files(segment_files)
        
        info_text = "\n".join(segment_info)
        return str(output_path), info_text
    
    def batch_generate(
        self,
        input_files: List[str],
        voice: str = "default",
        chunk_size: int = 5000,
        use_character_voices: bool = False,
        metadata_list: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Batch generate audiobooks from multiple files.
        
        Args:
            input_files: List of input file paths
            voice: Voice to use
            chunk_size: Maximum characters per chunk
            use_character_voices: Whether to use character voice attribution
            metadata_list: Optional list of metadata dicts (one per file)
            progress_callback: Callback(current_file_index, total_files, file_progress)
            
        Returns:
            List of result dicts with 'input', 'output', 'status', 'error' keys
        """
        results = []
        total_files = len(input_files)
        
        for i, input_path in enumerate(input_files):
            result = {
                'input': input_path,
                'output': None,
                'status': 'pending',
                'error': None
            }
            
            try:
                logger.info(f"Batch processing [{i+1}/{total_files}]: {input_path}")
                result['status'] = 'processing'
                
                # Get metadata for this file
                metadata = metadata_list[i] if metadata_list and i < len(metadata_list) else None
                
                # Create file-specific progress callback
                def file_progress(p: float):
                    if progress_callback:
                        progress_callback(i, total_files, p)
                
                if use_character_voices:
                    output_path = self.generate_with_characters(
                        input_path=input_path,
                        narrator_voice=voice
                    )
                    # Add metadata after generation
                    if metadata:
                        self.audio_utils.add_metadata(output_path, metadata)
                else:
                    output_path = self.generate_audiobook(
                        input_path=input_path,
                        voice=voice,
                        chunk_size=chunk_size,
                        progress_callback=file_progress,
                        metadata=metadata
                    )
                
                result['output'] = output_path
                result['status'] = 'completed'
                logger.info(f"Completed: {output_path}")
                
            except Exception as e:
                result['status'] = 'failed'
                result['error'] = str(e)
                logger.error(f"Failed to process {input_path}: {e}")
            
            results.append(result)
        
        return results
