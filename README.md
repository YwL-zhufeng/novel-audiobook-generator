# Novel Audiobook Generator

AI-powered audiobook generator for novels with voice cloning capabilities.

## Features

- 📖 **Novel Text Processing**: Support for TXT, EPUB, PDF formats
- 🎙️ **Voice Cloning**: Clone any voice with 10-20 seconds of audio sample
- 🎭 **Character Voice Attribution**: Automatically assign different voices to characters
- 🚀 **Multiple TTS Backends**: Support for ElevenLabs API, Coqui XTTS v2, Kokoro TTS
- ⚡ **Async Concurrent Processing**: Parallel TTS generation for faster output
- 💾 **Resume Support**: Continue from where you left off
- 🎵 **Audio Post-processing**: Volume normalization, chapter splitting
- ⚙️ **YAML Configuration**: Flexible config-based workflow

## Tech Stack

- **Python 3.9+**
- **TTS Models**:
  - ElevenLabs API (best quality, cloud)
  - Coqui XTTS v2 (open source, local)
  - Kokoro TTS (lightweight, fast)
- **Text Processing**: ebooklib, PyPDF2, nltk, spacy
- **Audio**: pydub, soundfile
- **Concurrency**: asyncio, aiohttp

## Installation

```bash
# Clone the repository
git clone https://github.com/YwL-zhufeng/novel-audiobook-generator.git
cd novel-audiobook-generator

# Install dependencies
pip install -r requirements.txt

# Download XTTS v2 model (optional, for local voice cloning)
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"

# Download spaCy model for dialogue detection
python -m spacy download zh_core_web_sm  # For Chinese
python -m spacy download en_core_web_sm  # For English
```

## Quick Start

### Command Line

```bash
# Basic usage with ElevenLabs
export ELEVENLABS_API_KEY="your-key"
python generate_audiobook.py novel.txt --clone-voice sample.mp3

# Use local XTTS (no API key needed)
python generate_audiobook.py novel.txt --backend xtts --clone-voice sample.wav

# With character voices (config file)
python generate_audiobook.py novel.txt --config config.yaml
```

### Python API

```python
from audiobook_generator import AudiobookGenerator

# Initialize generator
generator = AudiobookGenerator(
    tts_backend="elevenlabs",
    api_key="your-elevenlabs-api-key",
    max_workers=4  # Concurrent processing
)

# Clone voices
generator.clone_voice(
    voice_name="narrator",
    sample_audio_path="samples/narrator.mp3"
)
generator.clone_voice(
    voice_name="hero",
    sample_audio_path="samples/hero.mp3"
)

# Generate with character voices
generator.generate_with_characters(
    input_path="novel.txt",
    character_config={
        "narrator": "narrator",
        "characters": {
            "李逍遥": "hero",
            "赵灵儿": "heroine"
        }
    }
)
```

## Configuration File

Create `config.yaml`:

```yaml
# TTS Backend settings
tts:
  backend: elevenlabs  # or xtts, kokoro
  api_key: ${ELEVENLABS_API_KEY}
  max_workers: 4

# Voice configuration
voices:
  narrator:
    sample: samples/narrator.mp3
    stability: 0.5
    similarity_boost: 0.75
  
  characters:
    李逍遥:
      sample: samples/hero.mp3
      stability: 0.6
    赵灵儿:
      sample: samples/heroine.mp3
      stability: 0.6

# Text processing
text:
  chunk_size: 4000
  detect_dialogue: true
  dialogue_patterns:
    - '"([^"]+)"'
    - '「([^」]+)」'
    - '“([^”]+)”'

# Output settings
output:
  format: mp3
  bitrate: 192k
  normalize: true
  split_chapters: true
```

## Project Structure

```
novel-audiobook-generator/
├── src/
│   ├── __init__.py
│   ├── generator.py          # Main audiobook generator
│   ├── text_processor.py     # Text extraction and preprocessing
│   ├── dialogue_detector.py  # Character dialogue detection
│   ├── tts_backends/         # TTS backend implementations
│   ├── voice_manager.py      # Voice cloning and management
│   ├── audio_utils.py        # Audio post-processing
│   └── config.py             # Configuration management
├── generate_audiobook.py     # CLI entry point
├── requirements.txt
├── config.example.yaml
└── README.md
```

## Performance Tips

- Use `max_workers=4` for concurrent API calls (ElevenLabs rate limits apply)
- XTTS runs locally and benefits from GPU acceleration
- Enable resume mode for long novels: `--resume`

## License

MIT License
