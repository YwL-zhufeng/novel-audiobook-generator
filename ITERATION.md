# Novel Audiobook Generator - Iteration Log

## v1.0.0 - Initial Release
- Basic TTS generation with ElevenLabs, XTTS, Kokoro backends
- Text extraction (TXT, EPUB, PDF)
- Voice cloning support
- Audio concatenation and normalization

## v1.1.0 - Current Iteration

### New Features

1. **Async Concurrent Processing**
   - Multi-threaded TTS generation with `max_workers` parameter
   - Significant speedup for long novels
   - Progress bar with visual feedback

2. **Dialogue Detection & Character Voices**
   - Automatic dialogue extraction using regex patterns
   - Support for Chinese and English quotation marks
   - Speaker attribution from context
   - Auto-assign voices to characters

3. **Resume Support**
   - Progress persistence in JSON format
   - Continue from interrupted runs
   - Avoid re-generating completed chunks

4. **YAML Configuration**
   - External config file support
   - Environment variable expansion
   - Structured voice and output settings

5. **Enhanced CLI**
   - `--config` flag for YAML configs
   - `--resume` flag for continuation
   - `--characters` flag for character voice mode
   - `--workers` for concurrency control
   - Better help text with examples

### Technical Improvements

- Modular architecture with separate components
- spaCy integration for NLP-based dialogue detection
- Type hints throughout codebase
- Comprehensive test suite

## v1.3.0 - Doubao TTS Support

### New Features

1. **Doubao (ByteDance) TTS Backend**
   - Support for Volcano Engine TTS API
   - Ultra-low pricing: 0.0008 RMB per 1K tokens (~5 RMB for 1M characters)
   - 5-second voice cloning with high similarity
   - Multiple built-in Chinese voices
   - Optimized for Chinese audiobook generation

2. **Enhanced Voice Management**
   - Support for Doubao-specific authentication (app_id + access_token)
   - Automatic voice ID resolution for default and cloned voices
   - Backend-specific parameter handling

### Technical Changes

- New `DoubaoBackend` class in `tts_backends/doubao.py`
- Updated `VoiceManager` to support Doubao authentication
- Updated `AudiobookGenerator` with `app_id` and `access_token` parameters
- CLI updated with `--app-id` and `--access-token` flags
- Added `doubao` to supported backend choices

### Usage

```bash
# Using Doubao backend
export DOUBAO_ACCESS_TOKEN="your-token"
python generate_audiobook.py novel.txt --backend doubao --voice zh_female_qingxin

# With voice cloning
python generate_audiobook.py novel.txt --backend doubao --clone-voice sample.mp3

# With app_id
python generate_audiobook.py novel.txt --backend doubao --app-id your-app-id --access-token your-token
```

### Cost Comparison (1M characters)

| Backend | Cost |
|---------|------|
| Doubao | ~5 RMB |
| MiniMax | ~130-260 RMB |
| ElevenLabs | ~29 RMB |
| Azure | ~115 RMB |

## v1.5.1 - Full Voice Cloning Support

### New Features

1. **Complete Voice Cloning Implementation**
   - Full MegaTTS API integration for voice cloning
   - Support for multiple cloning models:
     - ICL 1.0 (声音复刻ICL1.0)
     - ICL 2.0 (声音复刻ICL2.0) - Recommended
     - DiT Standard (音色还原)
     - DiT Restoration (音色+风格还原)
   - 5-second voice cloning capability
   - Training status monitoring
   - Voice activation (locks voice for production)

2. **Voice Management**
   - ClonedVoice dataclass with status tracking
   - List and manage cloned voices
   - Automatic cluster selection (volcano_icl for cloned voices)
   - Training completion waiting

3. **API Compliance**
   - Upload API: `/api/v1/mega_tts/audio/upload`
   - Status API: `/api/v1/mega_tts/status`
   - Activate API: `/api/v1/mega_tts/audio/activate`
   - Proper Resource-Id headers

### Usage Example

```python
from src.tts_backends.doubao import DoubaoBackend, ModelType

backend = DoubaoBackend(
    app_id="your-app-id",
    access_token="your-token"
)

# Clone voice
cloned = backend.clone_voice(
    sample_audio_path="sample.mp3",
    speaker_id="S_my_voice",
    model_type=ModelType.ICL_2_0,
    wait_for_completion=True
)

# Use cloned voice
backend.generate_speech(
    text="你好，这是克隆的声音",
    voice_id="S_my_voice",
    output_path="output.mp3"
)
```

### Next Iteration Ideas

- [x] Web UI with Gradio/Streamlit
- [x] Real-time preview mode
- [x] Audiobook metadata (ID3 tags)
- [x] Batch processing multiple files
- [x] Doubao TTS backend
- [x] Docker containerization
- [x] Configuration validation
- [x] Progress tracking hardening
- [x] Smart caching system
- [x] Chapter detection
- [x] CI/CD pipeline
- [x] Comprehensive testing
- [x] Full voice cloning support
- [ ] Voice blending/mixing (MegaTTS mix feature)
- [ ] Streaming generation for infinite-length novels
- [ ] Web API server (REST/GraphQL)
- [ ] Plugin system for custom TTS backends

---

### New Features

1. **Smart Cache System**
   - File-based caching with LRU eviction
   - Separate caches for TTS, text, and audio
   - Configurable TTL and size limits
   - Cache statistics and management

2. **Intelligent Chapter Detection**
   - Pattern-based chapter detection (Chinese/English)
   - Structural analysis for unstructured texts
   - Confidence scoring
   - Chapter boundary extraction

3. **Enhanced Audio Processing**
   - Incremental audio merge for large files
   - Parallel audio processing
   - Memory-efficient batch processing
   - Audio duration detection

4. **Comprehensive Testing**
   - Full test suite with pytest
   - Unit tests for all core modules
   - Integration tests
   - Performance benchmarks

5. **CI/CD Pipeline**
   - GitHub Actions workflow
   - Multi-version Python testing (3.9-3.12)
   - Code coverage reporting
   - Docker image building

6. **Development Tools**
   - Pre-commit hooks (black, isort, flake8, mypy)
   - Makefile with common commands
   - Docker Compose configuration
   - Health checks

### Documentation

1. **Tutorial** (`docs/TUTORIAL.md`)
   - Step-by-step getting started guide
   - Backend-specific instructions
   - Voice cloning tutorial
   - Character voice setup
   - Batch processing examples

2. **Troubleshooting Guide** (`docs/TROUBLESHOOTING.md`)
   - Common issues and solutions
   - Error code reference
   - Debugging techniques
   - Performance optimization

3. **Complete API Reference** (`docs/API.md`)
   - All public methods documented
   - Configuration schema
   - Environment variables

### Engineering Improvements

- **Type Safety**: Complete type hints throughout
- **Error Handling**: Comprehensive exception hierarchy
- **Logging**: Structured logging with rotation
- **Validation**: Input validation at all entry points
- **Progress Tracking**: SQLite-based with transactions
- **Performance**: Streaming and incremental processing

### Project Structure

```
novel-audiobook-generator/
├── src/
│   ├── cache.py              # Smart caching system
│   ├── chapter_detector.py   # Chapter detection
│   ├── exceptions.py         # Custom exceptions
│   ├── logging_config.py     # Structured logging
│   ├── progress_manager.py   # SQLite progress tracking
│   └── validator.py          # Config validation
├── tests/
│   └── test_comprehensive.py # Full test suite
├── docs/
│   ├── TUTORIAL.md          # Getting started
│   ├── TROUBLESHOOTING.md   # Problem solving
│   ├── ARCHITECTURE.md      # System design
│   └── API.md              # API reference
├── .github/
│   └── workflows/
│       └── ci.yml           # CI/CD pipeline
├── docker-compose.yml       # Docker orchestration
├── .pre-commit-config.yaml  # Code quality hooks
└── Makefile                # Build automation
```

### Quality Metrics

- **Test Coverage**: >80%
- **Type Coverage**: Complete
- **Documentation**: Comprehensive
- **Code Quality**: Black + isort + flake8 + mypy
- **CI/CD**: Automated testing and deployment

### Next Iteration Ideas

- [x] Web UI with Gradio/Streamlit
- [x] Real-time preview mode
- [x] Audiobook metadata (ID3 tags)
- [x] Batch processing multiple files
- [x] Doubao TTS backend
- [x] Docker containerization
- [x] Configuration validation
- [x] Progress tracking hardening
- [x] Smart caching system
- [x] Chapter detection
- [x] CI/CD pipeline
- [x] Comprehensive testing
- [ ] Voice blending/morphing
- [ ] Streaming generation for infinite-length novels
- [ ] Web API server (REST/GraphQL)
- [ ] Plugin system for custom TTS backends

---

### New Features

1. **Robust Progress Tracking**
   - New `ProgressTracker` class with persistent state
   - File hash-based change detection
   - Chunk-level status tracking (pending/processing/completed/failed)
   - Resume capability with automatic recovery
   - Progress directory management

2. **Configuration Validation**
   - New `ConfigValidator` class
   - Comprehensive validation for all config options
   - Type checking and range validation
   - User-friendly error messages
   - File path validation with extension checking

3. **Enhanced Logging**
   - New `logger.py` module with structured logging
   - Rotating file logs (10MB per file, 5 backups)
   - Console and file output
   - Configurable log levels
   - Separate loggers per module

4. **Docker Support**
   - Dockerfile for containerized deployment
   - Multi-stage build optimization
   - Pre-installed spaCy models
   - Volume mounting for output
   - Exposed port 7860 for web UI

5. **Package Installation**
   - `pyproject.toml` with modern Python packaging
   - Optional dependencies for each TTS backend
   - Development dependencies (pytest, black, mypy)
   - Console script entry point
   - pip installable

6. **Build Automation**
   - Makefile with common commands
   - `make install`, `make test`, `make lint`
   - Docker build and run commands
   - Code formatting automation

### Documentation

1. **Architecture Documentation**
   - Complete system architecture diagram
   - Component interaction flows
   - Data flow visualization
   - Extension points for new backends

2. **API Reference**
   - Full API documentation
   - Method signatures and examples
   - Configuration schema
   - Environment variables

3. **Contributing Guide**
   - Development setup instructions
   - Code style guidelines
   - Testing requirements
   - Pull request process

### Engineering Improvements

- Type hints throughout codebase
- Comprehensive error handling
- Input validation at all entry points
- Resource cleanup guarantees
- Thread-safe progress tracking

### Next Iteration Ideas

- [x] Web UI with Gradio/Streamlit
- [x] Real-time preview mode
- [x] Audiobook metadata (ID3 tags)
- [x] Batch processing multiple files
- [x] Doubao TTS backend
- [x] Docker containerization
- [x] Configuration validation
- [x] Progress tracking hardening
- [ ] Chapter detection using ML
- [ ] Voice blending/morphing
- [ ] Streaming generation for infinite-length novels

---

### New Features

1. **Batch Processing**
   - Process multiple novels in one run
   - Queue-based processing with progress tracking
   - Individual file success/failure tracking
   - Results table with download links

2. **Batch UI in Web Interface**
   - Multi-file upload (drag & drop multiple files)
   - Batch settings panel
   - Real-time progress for entire batch
   - Results summary (success/failed count)

3. **Batch API**
   - `batch_generate()` method in AudiobookGenerator
   - Progress callback with (current, total, file_progress)
   - Returns detailed results for each file
   - Continues on individual file failures

### Technical Changes

- New `batch_generate()` method supporting list of input files
- Batch progress callback with granular progress
- Error isolation - one file failure doesn't stop batch
- Results data structure for batch tracking

### Next Iteration Ideas

- [x] Web UI with Gradio/Streamlit
- [x] Real-time preview mode
- [x] Audiobook metadata (ID3 tags)
- [x] Batch processing multiple files
- [ ] Chapter detection using ML
- [ ] Voice blending/morphing
- [ ] Docker containerization

## v1.2.2 - Audiobook Metadata (ID3 Tags)

### New Features

1. **ID3 Metadata Support**
   - Add title, artist, album, composer tags to generated MP3
   - Cover image embedding (JPEG)
   - Duration metadata (TLEN)
   - Custom TXXX tags for extended metadata
   - Chapter information storage

2. **Metadata Editor in Web UI**
   - Book title input
   - Author/narrator field
   - Series/album name
   - Cover image upload (drag & drop)
   - All metadata embedded in final audiobook

3. **Metadata Reading**
   - Read metadata from existing audiobooks
   - Display in compatible players

### Technical Changes

- Added `mutagen` dependency for ID3 tag handling
- New `add_metadata()` method in AudioUtils
- New `read_metadata()` method for reading tags
- Updated `concatenate_audio_files()` to support metadata
- Updated `generate_audiobook()` to accept metadata dict

### Next Iteration Ideas

- [x] Web UI with Gradio/Streamlit
- [x] Real-time preview mode
- [x] Audiobook metadata (ID3 tags)
- [ ] Batch processing multiple files
- [ ] Chapter detection using ML
- [ ] Voice blending/morphing
- [ ] Docker containerization

## v1.2.1 - Real-time Preview

### New Features

1. **Real-time Preview Mode**
   - Generate short audio previews before full generation
   - Adjustable preview length (100-1000 characters)
   - Support character voice attribution in preview
   - Preview text editor (auto-load from file or manual input)
   - Audio player with playback controls

2. **Preview with Characters**
   - Automatically detect characters in preview section
   - Assign cloned voices to detected characters
   - Show segment-by-segment voice attribution info

### Technical Changes

- Added `generate_preview()` method to AudiobookGenerator
- Added `preview_with_characters()` for multi-voice preview
- New "👂 Preview" tab in Web UI
- Smart sentence boundary detection for natural previews

## v1.2.0 - Web UI Release

### New Features

1. **Gradio Web UI**
   - User-friendly web interface at `http://localhost:7860`
   - Three-tab layout: Quick Start, Voice Cloning, Advanced Settings
   - Drag-and-drop file upload with preview
   - Real-time progress tracking with visual progress bar
   - Audio player for generated results

2. **Voice Cloning Interface**
   - Upload audio samples directly in browser
   - Name and describe cloned voices
   - Voice registry management

3. **Character Detection UI**
   - Automatic character detection display
   - Dialogue count statistics
   - Character-voice assignment table

4. **Advanced Configuration Panel**
   - Chunk size adjustment
   - Output format selection (MP3/WAV/M4A)
   - Bitrate and normalization controls
   - Language detection settings

### Usage

```bash
# Launch Web UI
python webui.py

# Access at http://localhost:7860
```

### Next Iteration Ideas

- [x] Web UI with Gradio/Streamlit
- [x] Real-time preview mode
- [ ] Batch processing multiple files
- [ ] Audiobook metadata (ID3 tags)
- [ ] Chapter detection using ML
- [ ] Voice blending/morphing
- [ ] Docker containerization
