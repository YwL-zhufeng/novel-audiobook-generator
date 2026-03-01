#!/usr/bin/env python3
"""
CLI interface for novel audiobook generator.
"""

import argparse
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src import AudiobookGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Generate audiobooks from novels using AI TTS"
    )
    
    parser.add_argument(
        "input",
        help="Input novel file (TXT, EPUB, PDF)"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output audiobook file path",
        default=None
    )
    
    parser.add_argument(
        "--backend",
        choices=["elevenlabs", "xtts", "kokoro"],
        default="elevenlabs",
        help="TTS backend to use"
    )
    
    parser.add_argument(
        "--api-key",
        help="API key for cloud TTS services",
        default=os.getenv("ELEVENLABS_API_KEY")
    )
    
    parser.add_argument(
        "--voice",
        help="Voice to use (name or ID)",
        default="default"
    )
    
    parser.add_argument(
        "--clone-voice",
        help="Clone voice from sample audio",
        metavar="SAMPLE_AUDIO"
    )
    
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5000,
        help="Maximum characters per TTS chunk"
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    # Initialize generator
    try:
        generator = AudiobookGenerator(
            tts_backend=args.backend,
            api_key=args.api_key
        )
    except Exception as e:
        print(f"Error initializing generator: {e}")
        sys.exit(1)
    
    # Clone voice if requested
    if args.clone_voice:
        if not Path(args.clone_voice).exists():
            print(f"Error: Voice sample not found: {args.clone_voice}")
            sys.exit(1)
        
        print(f"Cloning voice from {args.clone_voice}...")
        voice_id = generator.clone_voice(
            voice_name=args.voice,
            sample_audio_path=args.clone_voice
        )
        print(f"Voice cloned with ID: {voice_id}")
    
    # Generate audiobook
    print(f"Generating audiobook from {args.input}...")
    
    def progress_callback(progress):
        percent = int(progress * 100)
        print(f"\rProgress: {percent}%", end="", flush=True)
    
    try:
        output_path = generator.generate_audiobook(
            input_path=args.input,
            output_path=args.output,
            voice=args.voice,
            chunk_size=args.chunk_size,
            progress_callback=progress_callback
        )
        print(f"\nAudiobook saved to: {output_path}")
    except Exception as e:
        print(f"\nError generating audiobook: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
