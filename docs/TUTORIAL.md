# Tutorial: Getting Started with Novel Audiobook Generator

This tutorial will guide you through using the novel-audiobook-generator to convert your favorite novels into audiobooks.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Basic Usage](#basic-usage)
4. [Advanced Features](#advanced-features)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites

- Python 3.9 or higher
- FFmpeg (for audio processing)
- At least 4GB RAM (8GB+ recommended)

### Install from PyPI

```bash
pip install novel-audiobook-generator
```

### Install from Source

```bash
git clone https://github.com/YwL-zhufeng/novel-audiobook-generator.git
cd novel-audiobook-generator
pip install -e .
```

### Install with Optional Dependencies

```bash
# For ElevenLabs support
pip install novel-audiobook-generator[elevenlabs]

# For local XTTS support
pip install novel-audiobook-generator[xtts]

# For development
pip install novel-audiobook-generator[dev]

# Install everything
pip install novel-audiobook-generator[all]
```

## Quick Start

### 1. Set up API Keys

```bash
export ELEVENLABS_API_KEY="your-api-key-here"
```

### 2. Generate Your First Audiobook

```bash
novel-audiobook-generator my-novel.txt --voice Rachel
```

That's it! Your audiobook will be saved to `output/my-novel_audiobook.mp3`.

## Basic Usage

### Command Line Interface

#### Generate from a text file

```bash
novel-audiobook-generator novel.txt --voice Rachel --output my-audiobook.mp3
```

#### Use a cloned voice

```bash
# First, clone a voice
novel-audiobook-generator novel.txt --clone-voice sample-voice.mp3

# Then use it
novel-audiobook-generator novel.txt --voice my-cloned-voice
```

#### Resume interrupted generation

```bash
novel-audiobook-generator novel.txt --resume
```

#### Process multiple files

```bash
novel-audiobook-generator book1.txt book2.txt book3.txt --voice default
```

### Web Interface

Launch the web UI:

```bash
audiobook-webui
```

Then open your browser to `http://localhost:7860`.

## Advanced Features

### Voice Cloning

Clone a voice from a sample audio file:

```python
from src.generator import AudiobookGenerator

generator = AudiobookGenerator(tts_backend="elevenlabs", api_key="your-key")
generator.clone_voice(
    voice_name="my-voice",
    sample_audio_path="sample.mp3",
    description="A warm, friendly voice"
)

# Use the cloned voice
generator.generate_audiobook(
    input_path="novel.txt",
    voice="my-voice"
)
```

### Character Voices

Enable different voices for different characters:

```bash
novel-audiobook-generator novel.txt --characters --config config.yaml
```

Example `config.yaml`:

```yaml
voices:
  narrator:
    sample: voices/narrator.mp3
  alice:
    sample: voices/alice.mp3
  bob:
    sample: voices/bob.mp3
```

### Chapter Detection

Automatically detect and export chapters:

```python
from src.chapter_detector import ChapterDetector
from src.export import AudiobookExporter, ExportOptions

detector = ChapterDetector()
chapters = detector.detect_chapters(text)

# Export as M4B with chapters
exporter = AudiobookExporter()
exporter.export(
    audio_path="audiobook.mp3",
    output_path="audiobook.m4b",
    options=ExportOptions(format="m4b"),
    chapters=chapters
)
```

### Batch Processing

Process multiple books:

```python
from src.task_queue import AudiobookTaskQueue

def generator_factory():
    return AudiobookGenerator(tts_backend="elevenlabs", api_key="key")

queue = AudiobookTaskQueue(generator_factory, max_concurrent=2)

# Add tasks
task_ids = queue.add_tasks_batch(
    input_paths=["book1.txt", "book2.txt", "book3.txt"],
    voice="default"
)

# Start processing
queue.start()

# Monitor progress
while True:
    stats = queue.get_stats()
    print(f"Pending: {stats.pending}, Running: {stats.running}, Completed: {stats.completed}")
    if stats.pending == 0 and stats.running == 0:
        break
    time.sleep(5)
```

## Configuration

### Configuration File

Create a `config.yaml` file:

```yaml
tts:
  backend: elevenlabs  # or xtts, kokoro, doubao
  max_workers: 4
  api_key: ${ELEVENLABS_API_KEY}

text:
  chunk_size: 4000
  detect_dialogue: true
  language: auto

output:
  format: mp3
  bitrate: 192k
  normalize: true
  split_chapters: false
  output_dir: output

voices:
  narrator:
    sample: voices/narrator.mp3
    stability: 0.5
    similarity_boost: 0.75
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `DOUBAO_APP_ID` | Doubao App ID |
| `DOUBAO_ACCESS_TOKEN` | Doubao access token |
| `MAX_WORKERS` | Maximum concurrent workers |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Troubleshooting

### Common Issues

#### Out of Memory Errors

If you encounter OOM errors with large files:

```python
from src.memory_monitor import MemoryLimitedGenerator

generator = MemoryLimitedGenerator(max_memory_mb=2048)
```

Or use streaming processing:

```python
from src.text_processor import TextProcessor

processor = TextProcessor()
for chunk in processor.extract_text_streaming("large-novel.txt"):
    # Process chunk by chunk
    pass
```

#### Rate Limiting

If you hit API rate limits:

```bash
# Reduce concurrent workers
novel-audiobook-generator novel.txt --workers 2
```

#### Audio Quality Issues

Check audio quality before voice cloning:

```python
from src.audio_quality import AudioQualityDetector

detector = AudioQualityDetector()
is_valid, issues = detector.validate_for_voice_cloning("sample.mp3")

if not is_valid:
    for issue in issues:
        print(f"Issue: {issue}")
```

### Getting Help

- Check the [FAQ](FAQ.md)
- Open an issue on [GitHub](https://github.com/YwL-zhufeng/novel-audiobook-generator/issues)
- Join our [Discord community](https://discord.gg/novel-audiobook-generator)

## Examples

See the `examples/` directory for more usage examples:

- `basic_usage.py` - Simple audiobook generation
- `voice_cloning.py` - Voice cloning example
- `batch_processing.py` - Batch processing multiple files
- `custom_pipeline.py` - Custom processing pipeline
