# Novel Audiobook Generator

AI-powered audiobook generator for novels with voice cloning capabilities.

## Features

- 📖 **Novel Text Processing**: Support for TXT, EPUB, PDF formats
- 🎙️ **Voice Cloning**: Clone any voice with **5 seconds** of audio sample
- 🎭 **Character Voice Attribution**: Automatically assign different voices to characters
- 🔬 **Multiple Cloning Models**: ICL 1.0/2.0, DiT Standard/Restoration
- 🚀 **Multiple TTS Backends**: ElevenLabs, XTTS, Kokoro, **Doubao**
- 💰 **Ultra-low Cost**: Doubao ~5 RMB for 1 million characters
- ⚡ **Async Concurrent Processing**: Parallel TTS generation
- 💾 **Resume Support**: Continue from where you left off
- 🎵 **Audio Post-processing**: Volume normalization, ID3 metadata, cover embedding
- 📑 **Smart Chapter Detection**: Automatic chapter boundary detection
- 🧠 **Intelligent Caching**: LRU cache for TTS results and preprocessed data
- ⚙️ **YAML Configuration**: Flexible config-based workflow
- 🌐 **Web UI**: User-friendly Gradio interface
- 🐳 **Docker Support**: Easy containerized deployment
- ✅ **Configuration Validation**: Input validation and error handling
- 📊 **Progress Tracking**: Persistent progress with SQLite
- 🧪 **Comprehensive Testing**: >80% test coverage

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/YwL-zhufeng/novel-audiobook-generator.git
cd novel-audiobook-generator

# Install with pip
pip install -e .

# Or install with all TTS backends
pip install -e ".[all]"
```

### Docker Install

```bash
# Build Docker image
make docker-build

# Run container
make docker-run

# Or use Docker Compose
docker-compose up -d
```

### Development Install

```bash
# Install with development dependencies
make install-dev
```

## Quick Start

### Using Make (Recommended)

```bash
# Launch Web UI
make webui

# Run CLI
make cli ARGS="novel.txt --backend doubao"

# Run tests
make test

# Format code
make format
```

### Web UI

```bash
python webui.py
# Then visit http://localhost:7860
```

### Command Line

```bash
# Basic usage with Doubao (recommended for Chinese)
export DOUBAO_ACCESS_TOKEN="your-token"
python generate_audiobook.py novel.txt --backend doubao

# With voice cloning
python generate_audiobook.py novel.txt --clone-voice sample.mp3

# With character voices
python generate_audiobook.py novel.txt --config config.yaml --characters

# Resume interrupted generation
python generate_audiobook.py novel.txt --resume
```

### Python API

```python
from src.generator import AudiobookGenerator

# Initialize
generator = AudiobookGenerator(
    tts_backend="doubao",
    access_token="your-token",
    max_workers=4
)

# Clone voice
generator.clone_voice(
    voice_name="narrator",
    sample_audio_path="samples/narrator.mp3"
)

# Generate audiobook
output = generator.generate_audiobook(
    input_path="novel.txt",
    voice="narrator",
    metadata={
        "title": "My Novel",
        "artist": "Author Name"
    }
)
```

## Project Structure

```
novel-audiobook-generator/
├── src/
│   ├── generator.py          # Main audiobook generator
│   ├── text_processor.py     # Text extraction and preprocessing
│   ├── dialogue_detector.py  # Character dialogue detection
│   ├── chapter_detector.py   # Chapter detection
│   ├── tts_backends/         # TTS backend implementations
│   ├── voice_manager.py      # Voice cloning and management
│   ├── audio_utils.py        # Audio post-processing
│   ├── config.py             # Configuration management
│   ├── cache.py              # Smart caching system
│   ├── validator.py          # Configuration validation
│   ├── progress_manager.py   # SQLite progress tracking
│   ├── exceptions.py         # Custom exceptions
│   └── logging_config.py     # Structured logging
├── docs/
│   ├── TUTORIAL.md          # Getting started guide
│   ├── TROUBLESHOOTING.md   # Problem solving
│   ├── ARCHITECTURE.md      # System design
│   └── API.md               # API reference
├── tests/                    # Comprehensive test suite
├── generate_audiobook.py     # CLI entry point
├── webui.py                  # Gradio Web UI
├── pyproject.toml           # Modern Python packaging
├── Dockerfile               # Docker configuration
├── docker-compose.yml       # Docker orchestration
├── Makefile                 # Build automation
├── .github/workflows/       # CI/CD pipeline
├── .pre-commit-config.yaml  # Code quality hooks
└── CONTRIBUTING.md          # Contributing guide
```

## Documentation

- **[Tutorial](docs/TUTORIAL.md)** - Step-by-step getting started guide
- **[API Reference](docs/API.md)** - Complete API documentation
- **[Architecture](docs/ARCHITECTURE.md)** - System design and component interactions
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Contributing](CONTRIBUTING.md)** - Development setup and contribution guidelines

## Cost Comparison (1M characters)

| Backend | Cost | Quality | Speed |
|---------|------|---------|-------|
| **Doubao** | ~5 RMB | ★★★★★ | Fast |
| ElevenLabs | ~29 RMB | ★★★★★ | Medium |
| MiniMax | ~130-260 RMB | ★★★★★ | Fast |
| XTTS (Local) | Free | ★★★★☆ | Slow |
| Azure | ~115 RMB | ★★★★☆ | Medium |

## Performance Tips

- Use `max_workers=4` for concurrent API calls (check rate limits)
- Enable resume mode for long novels: `--resume`
- Use Doubao backend for cost-effective Chinese audiobooks
- Enable caching for repeated generations
- Process large files in batches

## License

MIT License

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgments

- [ElevenLabs](https://elevenlabs.io/) for high-quality TTS
- [Coqui AI](https://github.com/coqui-ai/TTS) for XTTS
- [ByteDance](https://www.volcengine.com/) for Doubao TTS
