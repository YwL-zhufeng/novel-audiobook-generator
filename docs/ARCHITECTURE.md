# Architecture Design

## Overview

The Novel Audiobook Generator is designed with a modular architecture that separates concerns into distinct components, allowing for easy extension and maintenance.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Entry Points                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │     CLI      │  │    Web UI    │  │      Python API      │  │
│  │ generate_    │  │   webui.py   │  │  AudiobookGenerator  │  │
│  │ audiobook.py │  │   (Gradio)   │  │       class          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
└─────────┼─────────────────┼─────────────────────┼──────────────┘
          │                 │                     │
          └─────────────────┼─────────────────────┘
                            │
          ┌─────────────────▼─────────────────────┐
          │      AudiobookGenerator (Core)        │
          │  ┌─────────────┐  ┌───────────────┐   │
          │  │   Config    │  │    Logger     │   │
          │  │  Management │  │               │   │
          │  └─────────────┘  └───────────────┘   │
          └─────────────────┬─────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼───────┐  ┌────────▼────────┐  ┌──────▼──────┐
│  Text         │  │  Voice          │  │  Audio      │
│  Processing   │  │  Management     │  │  Processing │
│               │  │                 │  │             │
│ • Extract     │  │ • Clone voices  │  │ • Concat    │
│ • Clean       │  │ • Voice registry│  │ • Normalize │
│ • Chunk       │  │ • Generate      │  │ • Metadata  │
│ • Dialogue    │  │                 │  │             │
└───────┬───────┘  └────────┬────────┘  └─────────────┘
        │                   │
        │         ┌─────────▼──────────┐
        │         │   TTS Backends     │
        │         │  ┌───┐┌───┐┌───┐  │
        │         │  │ E ││ X ││ K │  │
        │         │  │ L ││ T ││ O │  │
        │         │  │   ││ T ││ K │  │
        │         │  │   ││ S ││   │  │
        │         │  │   ││   ││ D │  │
        │         │  └───┘└───┘└───┘  │
        │         └──────────────────┘
        │
┌───────▼───────────────────────────────┐
│      Progress Tracking                │
│  • Persistent state                   │
│  • Resume capability                  │
│  • Error recovery                     │
└───────────────────────────────────────┘
```

## Component Details

### 1. Entry Points

**CLI (`generate_audiobook.py`)**
- Argument parsing with argparse
- Environment variable integration
- Progress display
- Error handling

**Web UI (`webui.py`)**
- Gradio-based interface
- File upload/download
- Real-time preview
- Batch processing UI

**Python API (`AudiobookGenerator`)**
- Programmatic interface
- Configurable components
- Callback support

### 2. Core Components

#### TextProcessor
```python
class TextProcessor:
    def extract_text(file_path) -> str
    def split_into_chunks(text, max_chars) -> List[str]
    def preprocess_for_tts(text) -> str
    def detect_chapters(text) -> List[Chapter]
```

**Responsibilities:**
- Extract text from various formats (TXT, EPUB, PDF)
- Clean and normalize text
- Split into TTS-friendly chunks
- Detect dialogue and narration

#### VoiceManager
```python
class VoiceManager:
    def clone_voice(name, sample_path) -> voice_id
    def generate_speech(text, voice, output_path)
    def list_voices() -> Dict[str, str]
```

**Responsibilities:**
- Abstract TTS backend differences
- Manage voice registry
- Handle voice cloning

#### AudioUtils
```python
class AudioUtils:
    def concatenate(files, output_path, metadata)
    def add_metadata(file_path, metadata)
    def normalize_volume(input_path, output_path)
    def split_by_chapters(audio_path, markers)
```

**Responsibilities:**
- Audio post-processing
- Metadata embedding (ID3)
- Volume normalization
- Chapter splitting

### 3. TTS Backends

Each backend implements a common interface:

```python
class TTSBackend:
    def __init__(self, **kwargs)
    def clone_voice(sample_path, voice_name, description) -> voice_id
    def generate_speech(text, voice_id, output_path, **options)
    def list_default_voices() -> Dict[str, str]
```

**Current Backends:**

| Backend | Type | Cloning | Quality | Cost |
|---------|------|---------|---------|------|
| ElevenLabs | Cloud | Yes | ★★★★★ | $$$ |
| XTTS | Local | Yes | ★★★★☆ | Free |
| Kokoro | Local | Limited | ★★★☆☆ | Free |
| Doubao | Cloud | Yes | ★★★★★ | ¥ |

### 4. Configuration System

**Hierarchical Configuration:**
1. Default values
2. Config file (YAML)
3. Environment variables
4. CLI arguments

```yaml
# config.yaml
tts:
  backend: doubao
  max_workers: 4
  
voices:
  narrator:
    sample: samples/narrator.mp3
    
text:
  chunk_size: 4000
  detect_dialogue: true
  
output:
  format: mp3
  bitrate: 192k
```

### 5. Progress Tracking

**Features:**
- Persistent progress state
- Input file change detection (hash-based)
- Chunk-level status tracking
- Resume from interruption
- Error recovery

```
.progress/
├── a1b2c3d4.json  # Job 1
├── e5f6g7h8.json  # Job 2
└── ...
```

## Data Flow

```
Input File
    │
    ▼
┌─────────────┐
│   Extract   │ ──► Text
│    Text     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Preprocess  │ ──► Cleaned Text
│    Text     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Split    │ ──► Chunks[]
│   Chunks    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│   Process   │────►│   TTS API   │
│   Chunks    │     │   (Async)   │
│  (Parallel) │◄────└─────────────┘
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Concat    │ ──► Audio Segments
│   Audio     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Post-proc  │ ──► Final Audiobook
│  & Metadata │
└─────────────┘
```

## Error Handling Strategy

```
┌─────────────────┐
│   Operation     │
└────────┬────────┘
         │
    ┌────▼────┐
    │  Try    │
    └────┬────┘
         │
    ┌────▼────┐     ┌─────────────┐
    │ Success │────►│   Return    │
    └────┬────┘     └─────────────┘
         │
    ┌────▼────┐     ┌─────────────┐
    │  Error  │────►│   Retry?    │
    └────┬────┘     └──────┬──────┘
         │                 │
         │            ┌────▼────┐
         │            │  Yes    │────► Retry with backoff
         │            └────┬────┘
         │                 │
         │            ┌────▼────┐
         │            │   No    │
         │            └────┬────┘
         │                 │
         │            ┌────▼─────────────┐
         └───────────►│  Save Progress   │
                      │  Raise Exception │
                      └──────────────────┘
```

## Extension Points

### Adding a New TTS Backend

1. Create `src/tts_backends/new_backend.py`
2. Implement `TTSBackend` interface
3. Register in `src/tts_backends/__init__.py`
4. Update `ConfigValidator`

### Adding a New Text Format

1. Update `TextProcessor.supported_formats`
2. Add `_extract_{format}` method
3. Add optional dependency

### Adding Post-processing Effects

1. Extend `AudioUtils` class
2. Add configuration options
3. Update pipeline in `AudiobookGenerator`

## Performance Considerations

### Concurrency
- ThreadPoolExecutor for I/O-bound TTS calls
- max_workers configurable (default: 4)
- Backend-specific rate limiting

### Memory Management
- Streaming text processing for large files
- Temporary file cleanup
- Chunk-based processing

### Caching
- Voice cloning results cached by hash
- Progress state persisted to disk
- Config file caching

## Security

- API keys via environment variables
- No sensitive data in logs
- Input file validation
- Output path sanitization
