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

### Next Iteration Ideas

- [ ] Web UI with Gradio/Streamlit
- [ ] Real-time preview mode
- [ ] Batch processing multiple files
- [ ] Audiobook metadata (ID3 tags)
- [ ] Chapter detection using ML
- [ ] Voice blending/morphing
- [ ] Docker containerization
