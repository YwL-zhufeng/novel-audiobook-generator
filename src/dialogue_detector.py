"""
Dialogue detection module for identifying characters and their speech.
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

logger = logging.getLogger(__name__)


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
            r'[「""']([^""'"」]+)[""'"」]',  # Chinese quotes
            r'["""]([^"""]+)["""]',           # English double quotes
            r["'"'"]([^'"'"]+)["'"'"'],       # English single quotes
        ],
        'english': [
            r'["""]([^"""]+)["""]',           # Double quotes
            r["'"'"]([^'"'"]+)["'"'"'],       # Single quotes
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
        segments = []
        
        # Determine language if auto
        if self.language == 'auto':
            lang = self._detect_language(text)
        else:
            lang = self.language
        
        # Get patterns
        patterns = custom_patterns or self.DIALOGUE_PATTERNS.get(lang, self.DIALOGUE_PATTERNS['english'])
        
        # Find all dialogue segments
        dialogue_spans = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                dialogue_spans.append((match.start(), match.end(), match.group(1)))
        
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
                if narration.strip():
                    segments.append(DialogueSegment(
                        text=narration.strip(),
                        speaker=None,
                        start_pos=last_end,
                        end_pos=start,
                        is_dialogue=False
                    ))
            
            # Try to identify speaker
            speaker = self._identify_speaker(text, start, end)
            
            # Add dialogue segment
            segments.append(DialogueSegment(
                text=content,
                speaker=speaker,
                start_pos=start,
                end_pos=end,
                is_dialogue=True
            ))
            
            last_end = end
        
        # Add remaining narration
        if last_end < len(text):
            narration = text[last_end:]
            if narration.strip():
                segments.append(DialogueSegment(
                    text=narration.strip(),
                    speaker=None,
                    start_pos=last_end,
                    end_pos=len(text),
                    is_dialogue=False
                ))
        
        return segments
    
    def _detect_language(self, text: str) -> str:
        """Detect if text is primarily Chinese or English."""
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        return 'chinese' if chinese_chars > len(text) * 0.1 else 'english'
    
    def _merge_overlapping_spans(
        self,
        spans: List[Tuple[int, int, str]]
    ) -> List[Tuple[int, int, str]]:
        """Merge overlapping dialogue spans."""
        if not spans:
            return spans
        
        merged = [spans[0]]
        for current in spans[1:]:
            last = merged[-1]
            if current[0] < last[1]:  # Overlapping
                # Keep the longer one
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
        """Try to identify who is speaking."""
        # Look for speaker attribution within 50 chars before dialogue
        context_start = max(0, dialogue_start - 50)
        context = text[context_start:dialogue_start]
        
        for pattern in self.SPEAKER_PATTERNS:
            match = re.search(pattern, context)
            if match:
                return match.group(1).strip()
        
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
        
        Args:
            segments: List of dialogue segments
            available_voices: List of available voice names
            
        Returns:
            Mapping of character names to voice names
        """
        characters = self.extract_characters(segments)
        sorted_chars = sorted(characters.items(), key=lambda x: x[1], reverse=True)
        
        assignment = {}
        for i, (char, _) in enumerate(sorted_chars):
            if i < len(available_voices):
                assignment[char] = available_voices[i]
            else:
                assignment[char] = available_voices[-1] if available_voices else "default"
        
        return assignment
