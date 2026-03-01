# Novel Audiobook Generator

AI-powered audiobook generator for novels with voice cloning capabilities.

## Features

- 📖 **Novel Text Processing**: Support for TXT, EPUB, PDF formats
- 🎙️ **Voice Cloning**: Clone any voice with 10-20 seconds of audio sample
- 🎭 **Character Voice Attribution**: Automatically assign different voices to characters
- 🚀 **Multiple TTS Backends**: Support for ElevenLabs API, Coqui XTTS v2, Kokoro TTS
- ⚡ **Batch Processing**: Efficiently process long novels in chunks
- 🎵 **Audio Post-processing**: Volume normalization, chapter splitting

## Tech Stack

- **Python 3.9+**
- **TTS Models**:
  - ElevenLabs API (best quality, cloud)
  - Coqui XTTS v2 (open source, local)
  - Kokoro TTS (lightweight, fast)
- **Text Processing**: ebooklib, PyPDF2, nltk
- **Audio**: pydub, soundfile

## Installation

```bash
# Clone the repository
git clone https://github.com/YwL-zhufeng/novel-audiobook-generator.git
cd novel-audiobook-generator

# Install dependencies
pip install -r requirements.txt

# Download XTTS v2 model (optional, for local voice cloning)
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

## Quick Start

```python
from audiobook_generator import AudiobookGenerator

# Initialize generator
generator = AudiobookGenerator(
    tts_backend="elevenlabs",  # or "xtts", "kokoro"
    api_key="your-elevenlabs-api-key"
)

# Clone a voice from sample audio
generator.clone_voice(
    voice_name="narrator",
    sample_audio_path="samples/narrator_voice.mp3"
)

# Generate audiobook
generator.generate_audiobook(
    input_path="novel.txt",
    output_path="audiobook.mp3",
    voice="narrator"
)
```

## Project Structure

```
novel-audiobook-generator/
├── src/
│   ├── __init__.py
│   ├── generator.py          # Main audiobook generator
│   ├── text_processor.py     # Text extraction and preprocessing
│   ├── tts_backends/         # TTS backend implementations
│   │   ├── __init__.py
│   │   ├── elevenlabs.py
│   │   ├── xtts.py
│   │   └── kokoro.py
│   ├── voice_manager.py      # Voice cloning and management
│   └── audio_utils.py        # Audio post-processing
├── samples/                  # Voice sample storage
├── output/                   # Generated audiobooks
├── tests/
├── requirements.txt
└── README.md
```

## License

MIT License
