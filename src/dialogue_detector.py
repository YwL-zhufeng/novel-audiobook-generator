"""
Dialogue detection module for identifying characters and their speech.
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

from .logging_config import get_logger

logger = get_logger(__name__)

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spacy not available, using regex-only dialogue detection")


@dataclass
class DialogueSegment:
    """Represents a segment of dialogue or narration."""
    text: str
    speaker: Optional[str]  # None for narration
    start_pos: int
    end_pos: int
    is_dialogue: bool


class DialogueDetector:
    """Detect dialogue and attribute to characters."""
    
    # Default dialogue patterns for different languages
    DIALOGUE_PATTERNS = {
        'chinese': [
            r'[「""\']([^""\'」]+)[""\'」]',  # Chinese quotes
            r'["""]([^"""]+)["""]',           # English double quotes
            r["'"'"]([^'"'"]+)["'"'"],       # English single quotes
        ],
        'english': [
            r'["""]([^"""]+)["""]',           # Double quotes
            r["'"'"]([^'"'"]+)["'"'"],       # Single quotes
        ]
    }
    
    # Speaker attribution patterns
    SPEAKER_PATTERNS = [
        r'([^，。！？\s]{1,8})[说|道|问|答|喊|叫|嘀咕|喃喃]',  # Chinese
        r'([A-Z][a-zA-Z\s]{0,20})(?:said|cried|asked|replied|shouted)',  # English
    ]
    
    def __init__(self, language: str = 'auto'):
        """
        Initialize dialogue detector.
        
        Args:
            language: Language code ('chinese', 'english', or 'auto')
        """
        self.language = language
        self.nlp = None
        
        if SPACY_AVAILABLE and language != 'auto':
            try:
                model = 'zh_core_web_sm' if language == 'chinese' else 'en_core_web_sm'
                self.nlp = spacy.load(model)
                logger.info(f"Loaded spaCy model: {model}")
            except OSError:
                logger.warning(f"spaCy model {model} not found. Using regex only.")
    
    def detect_dialogue(
        self,
        text: str,
        custom_patterns: Optional[List[str]] = None
    ) -> List[DialogueSegment]:
        """
        Detect dialogue segments in text.
        
        Args:
            text: Input text
            custom_patterns: Custom regex patterns for dialogue
            
        Returns:
            List of dialogue segments
        """
        if not text:
            return []
        
        segments = []
        
        # Determine language if auto
        if self.language == 'auto':
            lang = self._detect_language(text)
        else:
            lang = self.language
        
        # Get patterns
        patterns = custom_patterns or self.DIALOGUE_PATTERNS.get(lang, self.DIALOGUE_PATTERNS['english'])
        
        # Find all dialogue spans
        dialogue_spans = []
        for pattern in patterns:
            try:
                for match in re.finditer(pattern, text):
                    dialogue_spans.append((match.start(), match.end(), match.group(1)))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")
        
        # Sort by position
        dialogue_spans.sort(key=lambda x: x[0])
        
        # Merge overlapping segments
        dialogue_spans = self._merge_overlapping_spans(dialogue_spans)
        
        # Build segments
        last_end = 0
        for start, end, content in dialogue_spans:
            # Add narration before dialogue
            if start > last_end:
                narration = text[last_end:start]
                narration = narration.strip()
                if narration:
                    segments.append(DialogueSegment(
                        text=narration,
                        speaker=None,
                        start_pos=last_end,
                        end_pos=start,
                        is_dialogue=False
                    ))
            
            # Try to identify speaker
            speaker = self._identify_speaker(text, start, end)
            
            # Add dialogue segment
            segments.append(DialogueSegment(
                text=content.strip(),
                speaker=speaker,
                start_pos=start,
                end_pos=end,
                is_dialogue=True
            ))
            
            last_end = end
        
        # Add remaining narration
        if last_end < len(text):
            narration = text[last_end:]
            narration = narration.strip()
            if narration:
                segments.append(DialogueSegment(
                    text=narration,
                    speaker=None,
                    start_pos=last_end,
                    end_pos=len(text),
                    is_dialogue=False
                ))
        
        return segments
    
    def _detect_language(self, text: str) -> str:
        """Detect if text is primarily Chinese or English."""
        if not text:
            return 'english'
        
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        return 'chinese' if chinese_chars > len(text) * 0.1 else 'english'
    
    def _merge_overlapping_spans(
        self,
        spans: List[Tuple[int, int, str]]
    ) -> List[Tuple[int, int, str]]:
        """
        Merge overlapping dialogue spans.
        
        Uses a sweep line algorithm for efficiency.
        """
        if not spans:
            return spans
        
        # Sort by start position
        spans = sorted(spans, key=lambda x: x[0])
        
        merged = [spans[0]]
        for current in spans[1:]:
            last = merged[-1]
            
            # Check for overlap (current starts before last ends)
            if current[0] < last[1]:
                # Overlapping - keep the longer one
                if len(current[2]) > len(last[2]):
                    merged[-1] = current
            else:
                merged.append(current)
        
        return merged
    
    def _identify_speaker(
        self,
        text: str,
        dialogue_start: int,
        dialogue_end: int
    ) -> Optional[str]:
        """
        Try to identify who is speaking.
        
        Looks for speaker attribution within 50 chars before dialogue.
        """
        # Look for speaker attribution within 50 chars before dialogue
        context_start = max(0, dialogue_start - 50)
        context = text[context_start:dialogue_start]
        
        for pattern in self.SPEAKER_PATTERNS:
            match = re.search(pattern, context)
            if match:
                speaker = match.group(1).strip()
                # Filter out common false positives
                if speaker and len(speaker) >= 2:
                    return speaker
        
        return None
    
    def extract_characters(self, segments: List[DialogueSegment]) -> Dict[str, int]:
        """
        Extract all character names and their dialogue counts.
        
        Args:
            segments: List of dialogue segments
            
        Returns:
            Dictionary of character names to dialogue count
        """
        character_counts = defaultdict(int)
        
        for segment in segments:
            if segment.is_dialogue and segment.speaker:
                character_counts[segment.speaker] += 1
        
        return dict(character_counts)
    
    def assign_voices_to_characters(
        self,
        segments: List[DialogueSegment],
        available_voices: List[str]
    ) -> Dict[str, str]:
        """
        Automatically assign voices to characters.
        
        Assigns voices based on dialogue frequency - most frequent characters
        get the first available voices.
        
        Args:
            segments: List of dialogue segments
            available_voices: List of available voice names
            
        Returns:
            Mapping of character names to voice names
        """
        if not available_voices:
            logger.warning("No available voices provided")
            return {}
        
        characters = self.extract_characters(segments)
        
        if not characters:
            logger.info("No characters found in segments")
            return {}
        
        # Sort by dialogue count (descending)
        sorted_chars = sorted(characters.items(), key=lambda x: x[1], reverse=True)
        
        assignment = {}
        for i, (char, count) in enumerate(sorted_chars):
            if i < len(available_voices):
                assignment[char] = available_voices[i]
            else:
                # Cycle through voices if more characters than voices
                assignment[char] = available_voices[i % len(available_voices)]
        
        logger.info(f"Assigned voices to {len(assignment)} characters")
        return assignment
    
    def get_dialogue_statistics(self, segments: List[DialogueSegment]) -> Dict[str, any]:
        """
        Get statistics about dialogue in the text.
        
        Args:
            segments: List of dialogue segments
            
        Returns:
            Dictionary with statistics
        """
        total_segments = len(segments)
        dialogue_segments = [s for s in segments if s.is_dialogue]
        narration_segments = [s for s in segments if not s.is_dialogue]
        
        dialogue_chars = sum(len(s.text) for s in dialogue_segments)
        narration_chars = sum(len(s.text) for s in narration_segments)
        total_chars = dialogue_chars + narration_chars
        
        characters = self.extract_characters(segments)
        
        return {
            'total_segments': total_segments,
            'dialogue_segments': len(dialogue_segments),
            'narration_segments': len(narration_segments),
            'dialogue_percentage': (dialogue_chars / total_chars * 100) if total_chars > 0 else 0,
            'narration_percentage': (narration_chars / total_chars * 100) if total_chars > 0 else 0,
            'total_characters': len(characters),
            'character_dialogues': characters,
        }
