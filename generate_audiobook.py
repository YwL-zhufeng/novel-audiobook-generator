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

from src.generator import AudiobookGenerator
from src.config import Config


def main():
    parser = argparse.ArgumentParser(
        description="Generate audiobooks from novels using AI TTS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with ElevenLabs
  python generate_audiobook.py novel.txt --clone-voice sample.mp3
  
  # Use local XTTS
  python generate_audiobook.py novel.txt --backend xtts --clone-voice sample.wav
  
  # With config file
  python generate_audiobook.py novel.txt --config config.yaml
  
  # Resume interrupted generation
  python generate_audiobook.py novel.txt --resume
  
  # Generate with character voices
  python generate_audiobook.py novel.txt --characters --config config.yaml
        """
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
        "--config", "-c",
        help="Configuration file (YAML)",
        default=None
    )
    
    parser.add_argument(
        "--backend",
        choices=["elevenlabs", "xtts", "kokoro", "doubao"],
        default=None,
        help="TTS backend to use"
    )
    
    parser.add_argument(
        "--app-id",
        help="App ID for Doubao/Volcano Engine",
        default=os.getenv("DOUBAO_APP_ID")
    )
    
    parser.add_argument(
        "--access-token",
        help="Access token for Doubao (alternative to API key)",
        default=os.getenv("DOUBAO_ACCESS_TOKEN")
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
        default=None,
        help="Maximum characters per TTS chunk"
    )
    
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=4,
        help="Number of concurrent workers (default: 4)"
    )
    
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous interrupted run"
    )
    
    parser.add_argument(
        "--characters",
        action="store_true",
        help="Enable character voice attribution"
    )
    
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Don't resume, start fresh"
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    # Load config if provided
    config = None
    if args.config:
        if not Path(args.config).exists():
            print(f"Error: Config file not found: {args.config}")
            sys.exit(1)
        config = Config.from_yaml(args.config)
        print(f"Loaded configuration from {args.config}")
    
    # Determine settings (CLI args override config)
    backend = args.backend or (config.tts.backend if config else "elevenlabs")
    api_key = args.api_key or (config.tts.api_key if config else None)
    app_id = args.app_id or (config.tts.app_id if config else None)
    access_token = args.access_token or (config.tts.access_token if config else None)
    chunk_size = args.chunk_size or (config.text.chunk_size if config else 4000)
    workers = args.workers or (config.tts.max_workers if config else 4)
    
    # Initialize generator
    try:
        generator = AudiobookGenerator(
            tts_backend=backend,
            api_key=api_key,
            app_id=app_id,
            access_token=access_token,
            max_workers=workers,
            config=config
        )
    except Exception as e:
        print(f"Error initializing generator: {e}")
        sys.exit(1)
    
    # Clone voices from config
    if config and config.voices:
        for voice_name, voice_data in config.voices.items():
            if isinstance(voice_data, dict) and 'sample' in voice_data:
                if Path(voice_data['sample']).exists():
                    print(f"Cloning voice: {voice_name}")
                    generator.clone_voice(
                        voice_name=voice_name,
                        sample_audio_path=voice_data['sample'],
                        description=voice_data.get('description')
                    )
    
    # Clone voice from CLI if provided
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
    print(f"Backend: {backend}, Workers: {workers}")
    
    def progress_callback(progress):
        percent = int(progress * 100)
        bar = "█" * (percent // 5) + "░" * (20 - percent // 5)
        print(f"\r[{bar}] {percent}%", end="", flush=True)
    
    try:
        if args.characters:
            # Character voice mode
            output_path = generator.generate_with_characters(
                input_path=args.input,
                narrator_voice=args.voice,
                output_path=args.output
            )
        else:
            # Standard mode
            output_path = generator.generate_audiobook(
                input_path=args.input,
                output_path=args.output,
                voice=args.voice,
                chunk_size=chunk_size,
                progress_callback=progress_callback,
                resume=args.resume and not args.no_resume
            )
        
        print(f"\n✅ Audiobook saved to: {output_path}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted. Progress saved. Run with --resume to continue.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error generating audiobook: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
