"""
Novel Audiobook Generator
Main generator class for converting novels to audiobooks.
"""

import os
import sys
import json
import asyncio
import hashlib
import tempfile
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .text_processor import TextProcessor
from .dialogue_detector import DialogueDetector, DialogueSegment
from .voice_manager import VoiceManager
from .audio_utils import AudioUtils
from .config import Config
from .progress_manager import ProgressManager, ProgressState
from .logging_config import get_logger, PerformanceLogger
from .exceptions import (
    AudiobookGeneratorError,
    TextProcessingError,
    TTSError,
    AudioProcessingError,
    get_user_friendly_message
)

logger = get_logger(__name__)


@dataclass
class GenerationResult:
    """Result of audiobook generation."""
    output_path: str
    total_chunks: int
    completed_chunks: int
    failed_chunks: int
    duration_seconds: float
    metadata: Dict[str, Any]


class AudiobookGenerator:
    """Main class for generating audiobooks from novels."""
    
    def __init__(
        self,
        tts_backend: str = "elevenlabs",
        api_key: Optional[str] = None,
        app_id: Optional[str] = None,
        access_token: Optional[str] = None,
        output_dir: str = "output",
        temp_dir: Optional[str] = None,
        max_workers: int = 4,
        config: Optional[Config] = None,
        enable_progress_persistence: bool = True
    ):
        """
        Initialize the audiobook generator.
        
        Args:
            tts_backend: TTS backend to use ('elevenlabs', 'xtts', 'kokoro', 'doubao')
            api_key: API key for cloud TTS services
            app_id: App ID for Doubao/Volcano Engine
            access_token: Access token for Doubao (alternative to api_key)
            output_dir: Directory for output files
            temp_dir: Directory for temporary files
            max_workers: Maximum concurrent workers for TTS generation
            config: Configuration object
            enable_progress_persistence: Whether to enable SQLite progress persistence
        """
        self.config = config
        self.tts_backend = tts_backend
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "audiobook_gen"
        self.temp_dir.mkdir(exist_ok=True)
        
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Initialize performance logger
        self.perf_logger = PerformanceLogger(logger)
        
        # Initialize progress manager
        self.progress_manager: Optional[ProgressManager] = None
        if enable_progress_persistence:
            self.progress_manager = ProgressManager()
        
        # Initialize components
        self.text_processor = TextProcessor()
        self.dialogue_detector = DialogueDetector()
        self.voice_manager = VoiceManager(
            tts_backend=tts_backend,
            api_key=api_key,
            app_id=app_id,
            access_token=access_token
        )
        self.audio_utils = AudioUtils()
        
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
        progress_callback: Optional[Callable[[float], None]] = None,
        resume: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GenerationResult:
        """
        Generate audiobook from novel file with concurrent processing.
        
        Args:
            input_path: Path to novel file
            output_path: Output audio file path
            voice: Voice to use
            chunk_size: Maximum characters per chunk
            progress_callback: Optional progress callback (receives 0.0-1.0)
            resume: Whether to resume from previous run
            metadata: Optional metadata dict (title, artist, album, cover_image, etc.)
            
        Returns:
            GenerationResult with details about the generation
            
        Raises:
            TextProcessingError: If text extraction fails
            TTSError: If TTS generation fails
            AudioProcessingError: If audio processing fails
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        if output_path is None:
            output_path = self.output_dir / f"{input_path.stem}_audiobook.mp3"
        else:
            output_path = Path(output_path)
        
        # Generate task ID
        task_id = self._generate_task_id(input_path, voice, chunk_size)
        
        # Load or create progress
        progress_state = None
        if resume and self.progress_manager:
            progress_state = self.progress_manager.get_task(task_id)
            if progress_state:
                logger.info(f"Resuming task {task_id}: {progress_state.progress_percentage:.1f}% complete")
        
        logger.info(f"Processing {input_path}")
        
        # Extract and process text
        with self.perf_logger.timer("text_extraction"):
            text = self.text_processor.extract_text(str(input_path))
        logger.info(f"Extracted {len(text)} characters")
        
        # Split into chunks
        chunks = self.text_processor.split_into_chunks(text, chunk_size)
        logger.info(f"Split into {len(chunks)} chunks")
        
        # Create progress state if not resuming
        if progress_state is None and self.progress_manager:
            progress_state = self.progress_manager.create_task(
                task_id=task_id,
                input_file=str(input_path),
                output_file=str(output_path),
                total_chunks=len(chunks),
                metadata={'voice': voice, 'chunk_size': chunk_size}
            )
        
        # Track completed chunks
        completed_chunks: Set[int] = set(progress_state.completed_chunks) if progress_state else set()
        failed_chunks: Set[int] = set()
        
        # Generate audio concurrently
        audio_segments: List[Optional[str]] = [None] * len(chunks)
        
        def generate_chunk(args: Tuple[int, str]) -> Tuple[int, str, Optional[str]]:
            """Generate audio for a single chunk."""
            idx, chunk_text = args
            
            # Check if already completed
            if idx in completed_chunks:
                existing_path = self.temp_dir / f"chunk_{idx:04d}.mp3"
                if existing_path.exists():
                    logger.debug(f"Reusing chunk {idx+1}/{len(chunks)}")
                    return idx, str(existing_path), None
            
            audio_path = self.temp_dir / f"chunk_{idx:04d}.mp3"
            
            try:
                self.voice_manager.generate_speech(chunk_text, voice, str(audio_path))
                logger.debug(f"Generated chunk {idx+1}/{len(chunks)}")
                return idx, str(audio_path), None
            except Exception as e:
                logger.error(f"Failed to generate chunk {idx+1}: {e}")
                return idx, None, str(e)
        
        # Process chunks in parallel with progress tracking
        total_tasks = len(chunks)
        completed_count = len(completed_chunks)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(generate_chunk, (i, chunk)): i
                for i, chunk in enumerate(chunks)
                if i not in completed_chunks
            }
            
            # Process completed futures
            for future in as_completed(futures):
                idx, audio_path, error = future.result()
                
                if error:
                    failed_chunks.add(idx)
                    if self.progress_manager:
                        self.progress_manager.mark_chunk_failed(task_id, idx, error)
                else:
                    audio_segments[idx] = audio_path
                    completed_chunks.add(idx)
                    completed_count += 1
                    
                    # Save progress
                    if self.progress_manager:
                        self.progress_manager.mark_chunk_complete(task_id, idx)
                
                # Call progress callback
                if progress_callback:
                    progress_callback(completed_count / total_tasks)
        
        # Check for failures
        if failed_chunks:
            logger.warning(f"{len(failed_chunks)} chunks failed to generate")
            if len(failed_chunks) > len(chunks) * 0.1:  # More than 10% failed
                raise TTSError(
                    f"Too many chunks failed ({len(failed_chunks)}/{len(chunks)}). "
                    "Check logs for details."
                )
        
        # Concatenate audio
        with self.perf_logger.timer("audio_concatenation"):
            logger.info("Concatenating audio segments...")
            valid_segments = [s for s in audio_segments if s is not None]
            self.audio_utils.concatenate_audio_files(
                valid_segments,
                str(output_path),
                metadata=metadata
            )
        
        # Get audio duration
        duration = self.audio_utils.get_audio_duration(str(output_path))
        
        # Cleanup temp files
        self._cleanup_temp_files([s for s in audio_segments if s])
        
        # Mark task as completed
        if self.progress_manager:
            self.progress_manager.update_task(
                task_id,
                status='completed',
                metadata={'duration_seconds': duration}
            )
        
        logger.info(f"Audiobook saved to {output_path}")
        
        return GenerationResult(
            output_path=str(output_path),
            total_chunks=len(chunks),
            completed_chunks=len(completed_chunks),
            failed_chunks=len(failed_chunks),
            duration_seconds=duration,
            metadata=metadata or {}
        )
    
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
        else:
            output_path = Path(output_path)
        
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
    ) -> Tuple[str, str]:
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
                    gen_result = self.generate_audiobook(
                        input_path=input_path,
                        voice=voice,
                        chunk_size=chunk_size,
                        progress_callback=file_progress,
                        metadata=metadata
                    )
                    output_path = gen_result.output_path
                
                result['output'] = output_path
                result['status'] = 'completed'
                logger.info(f"Completed: {output_path}")
                
            except Exception as e:
                result['status'] = 'failed'
                result['error'] = str(e)
                logger.error(f"Failed to process {input_path}: {e}")
            
            results.append(result)
        
        return results
    
    def get_incomplete_tasks(self) -> List[ProgressState]:
        """Get list of incomplete generation tasks."""
        if self.progress_manager:
            return self.progress_manager.get_incomplete_tasks()
        return []
    
    def resume_task(self, task_id: str, progress_callback: Optional[Callable[[float], None]] = None) -> GenerationResult:
        """
        Resume a specific task.
        
        Args:
            task_id: Task ID to resume
            progress_callback: Optional progress callback
            
        Returns:
            GenerationResult
        """
        if not self.progress_manager:
            raise AudiobookGeneratorError("Progress persistence not enabled")
        
        state = self.progress_manager.get_task(task_id)
        if not state:
            raise ResourceNotFoundError(f"Task not found: {task_id}")
        
        # Extract voice and chunk_size from metadata
        voice = state.metadata.get('voice', 'default')
        chunk_size = state.metadata.get('chunk_size', 5000)
        
        return self.generate_audiobook(
            input_path=state.input_file,
            output_path=state.output_file,
            voice=voice,
            chunk_size=chunk_size,
            progress_callback=progress_callback,
            resume=True
        )
    
    def _generate_task_id(self, input_path: Path, voice: str, chunk_size: int) -> str:
        """Generate unique task ID based on input parameters."""
        data = f"{input_path.absolute()}:{voice}:{chunk_size}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    def _cleanup_temp_files(self, files: List[str]):
        """Clean up temporary audio files."""
        for file_path in files:
            if file_path:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
    
    def close(self):
        """Clean up resources."""
        self.executor.shutdown(wait=True)
        if self.progress_manager:
            self.progress_manager.close()
        logger.info("AudiobookGenerator closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
