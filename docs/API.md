# API Reference

## AudiobookGenerator

Main class for generating audiobooks.

### Constructor

```python
AudiobookGenerator(
    tts_backend: str = "elevenlabs",
    api_key: Optional[str] = None,
    app_id: Optional[str] = None,
    access_token: Optional[str] = None,
    output_dir: str = "output",
    temp_dir: Optional[str] = None,
    max_workers: int = 4,
    config: Optional[Config] = None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tts_backend` | str | "elevenlabs" | TTS backend: "elevenlabs", "xtts", "kokoro", "doubao" |
| `api_key` | str | None | API key for cloud TTS services |
| `app_id` | str | None | App ID for Doubao/Volcano Engine |
| `access_token` | str | None | Access token for Doubao |
| `output_dir` | str | "output" | Directory for output files |
| `temp_dir` | str | None | Directory for temporary files |
| `max_workers` | int | 4 | Maximum concurrent workers |
| `config` | Config | None | Configuration object |

### Methods

#### clone_voice

```python
clone_voice(
    voice_name: str,
    sample_audio_path: str,
    description: Optional[str] = None
) -> str
```

Clone a voice from an audio sample.

**Parameters:**
- `voice_name`: Name for the cloned voice
- `sample_audio_path`: Path to the voice sample (5-20 seconds)
- `description`: Optional voice description

**Returns:** Voice ID

**Example:**
```python
generator = AudiobookGenerator(tts_backend="doubao", access_token="xxx")
voice_id = generator.clone_voice(
    voice_name="narrator",
    sample_audio_path="samples/narrator.mp3"
)
```

#### generate_audiobook

```python
generate_audiobook(
    input_path: str,
    output_path: Optional[str] = None,
    voice: str = "default",
    chunk_size: int = 5000,
    progress_callback: Optional[Callable[[float], None]] = None,
    resume: bool = True,
    metadata: Optional[Dict[str, Any]] = None
) -> str
```

Generate an audiobook from a novel file.

**Parameters:**
- `input_path`: Path to the novel file (TXT, EPUB, PDF)
- `output_path`: Output audio file path (optional)
- `voice`: Voice to use (name or ID)
- `chunk_size`: Maximum characters per chunk
- `progress_callback`: Progress callback function (0.0 to 1.0)
- `resume`: Whether to resume from previous run
- `metadata`: Audiobook metadata (title, artist, album, cover_image, etc.)

**Returns:** Path to the generated audiobook file

**Example:**
```python
def on_progress(progress):
    print(f"{progress*100:.1f}% complete")

output = generator.generate_audiobook(
    input_path="novel.txt",
    voice="narrator",
    progress_callback=on_progress,
    metadata={
        "title": "My Novel",
        "artist": "Author Name",
        "cover_image": "cover.jpg"
    }
)
```

#### generate_with_characters

```python
generate_with_characters(
    input_path: str,
    narrator_voice: str = "default",
    character_voices: Optional[Dict[str, str]] = None,
    output_path: Optional[str] = None,
    auto_assign: bool = True
) -> str
```

Generate an audiobook with different voices for characters.

**Parameters:**
- `input_path`: Path to the novel file
- `narrator_voice`: Voice for narration
- `character_voices`: Mapping of character names to voice names
- `output_path`: Output audio file path
- `auto_assign`: Auto-assign voices to characters if not provided

**Returns:** Path to the generated audiobook file

**Example:**
```python
output = generator.generate_with_characters(
    input_path="novel.txt",
    narrator_voice="narrator",
    character_voices={
        "李逍遥": "hero_voice",
        "赵灵儿": "heroine_voice"
    }
)
```

#### generate_preview

```python
generate_preview(
    text: str,
    voice: str = "default",
    preview_length: int = 200,
    output_path: Optional[str] = None
) -> str
```

Generate a short preview audio.

**Parameters:**
- `text`: Source text
- `voice`: Voice to use
- `preview_length`: Maximum characters for preview
- `output_path`: Output file path (optional)

**Returns:** Path to the generated preview file

#### batch_generate

```python
batch_generate(
    input_files: List[str],
    voice: str = "default",
    chunk_size: int = 5000,
    use_character_voices: bool = False,
    metadata_list: Optional[List[Dict[str, Any]]] = None,
    progress_callback: Optional[Callable[[int, int, float], None]] = None
) -> List[Dict[str, Any]]
```

Batch generate audiobooks from multiple files.

**Parameters:**
- `input_files`: List of input file paths
- `voice`: Voice to use
- `chunk_size`: Maximum characters per chunk
- `use_character_voices`: Whether to use character voice attribution
- `metadata_list`: Optional list of metadata dicts (one per file)
- `progress_callback`: Callback(current_file_index, total_files, file_progress)

**Returns:** List of result dicts with 'input', 'output', 'status', 'error' keys

## Configuration

### Config

```python
from src.config import Config

# Load from YAML
config = Config.from_yaml("config.yaml")

# Create from dict
config = Config.from_dict({
    "tts": {"backend": "doubao", "max_workers": 8},
    "text": {"chunk_size": 3000},
})

# Save to YAML
config.to_yaml("config.yaml")
```

### Configuration Schema

```yaml
tts:
  backend: string          # "elevenlabs", "xtts", "kokoro", "doubao"
  api_key: string          # API key (or use env var)
  max_workers: integer     # 1-32, default 4
  app_id: string          # Doubao app ID
  access_token: string    # Doubao access token

voices:
  voice_name:
    sample: string        # Path to voice sample
    stability: float      # 0.0-1.0
    similarity_boost: float  # 0.0-1.0

text:
  chunk_size: integer     # 100-10000, default 4000
  detect_dialogue: boolean  # default true
  dialogue_patterns: list   # Regex patterns for dialogue
  language: string        # "auto", "chinese", "english"

output:
  format: string          # "mp3", "wav", "m4a"
  bitrate: string         # "128k", "192k", "320k"
  normalize: boolean      # default true
  split_chapters: boolean # default false
  output_dir: string      # default "output"
```

## TextProcessor

```python
from src.text_processor import TextProcessor

processor = TextProcessor()

# Extract text from file
text = processor.extract_text("novel.epub")

# Split into chunks
chunks = processor.split_into_chunks(text, max_chars=4000)

# Preprocess for TTS
cleaned = processor.preprocess_for_tts(text)
```

## AudioUtils

```python
from src.audio_utils import AudioUtils

utils = AudioUtils()

# Concatenate audio files
utils.concatenate_audio_files(
    ["chunk1.mp3", "chunk2.mp3"],
    "output.mp3",
    metadata={"title": "My Book", "artist": "Author"}
)

# Add metadata
utils.add_metadata("audiobook.mp3", {
    "title": "My Book",
    "artist": "Narrator Name",
    "cover_image": "cover.jpg"
})

# Normalize volume
utils.normalize_volume("input.mp3", "output.mp3", target_db=-14.0)
```

## ProgressTracker

```python
from src.progress_tracker import ProgressTracker

tracker = ProgressTracker(progress_dir=".progress")

# Create progress tracking
progress = tracker.create_progress(
    input_file="novel.txt",
    output_path="output.mp3",
    total_chunks=100,
    backend="doubao",
    voice="narrator"
)

# Update chunk status
tracker.update_chunk("novel.txt", chunk_index=5, status="completed")

# Load existing progress
progress = tracker.load_progress("novel.txt")
if progress and progress.can_resume:
    print(f"Resuming from {progress.progress_percentage:.1f}%")

# Get completed chunks
completed = tracker.get_completed_chunk_paths("novel.txt")
```

## Exceptions

### AudiobookError

Base exception for all audiobook generator errors.

### ValidationError

Configuration validation error.

```python
from src.validator import ConfigValidator, ValidationError

is_valid, errors = ConfigValidator.validate_config(config_dict)
if not is_valid:
    for error in errors:
        print(f"{error.field}: {error.message}")
```

### BackendError

TTS backend error.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `DOUBAO_ACCESS_TOKEN` | Doubao access token |
| `DOUBAO_APP_ID` | Doubao app ID |
| `AUDIOBOOK_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `AUDIOBOOK_LOG_FILE` | Log file path |
