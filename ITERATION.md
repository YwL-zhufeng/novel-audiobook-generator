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

## v1.2.3 - Batch Processing

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
