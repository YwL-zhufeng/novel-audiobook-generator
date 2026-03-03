# Contributing to Novel Audiobook Generator

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YwL-zhufeng/novel-audiobook-generator.git
   cd novel-audiobook-generator
   ```

2. **Install with development dependencies**
   ```bash
   make install-dev
   # or
   pip install -e ".[dev]"
   ```

3. **Install all TTS backends (optional)**
   ```bash
   make install-all
   # or
   pip install -e ".[all]"
   ```

## Code Style

We use the following tools for code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking

Run all checks:
```bash
make lint
```

Format code:
```bash
make format
```

## Testing

Run the test suite:
```bash
make test
```

Run with coverage:
```bash
make test-cov
```

## Project Structure

```
novel-audiobook-generator/
├── src/                    # Source code
│   ├── tts_backends/      # TTS backend implementations
│   ├── generator.py       # Main generator class
│   ├── text_processor.py  # Text extraction and processing
│   ├── dialogue_detector.py # Dialogue detection
│   ├── voice_manager.py   # Voice management
│   ├── audio_utils.py     # Audio processing
│   ├── config.py          # Configuration management
│   ├── logger.py          # Logging utilities
│   ├── validator.py       # Configuration validation
│   └── progress_tracker.py # Progress tracking
├── tests/                 # Test suite
├── generate_audiobook.py  # CLI entry point
├── webui.py              # Web UI entry point
├── requirements.txt      # Dependencies
├── pyproject.toml       # Project configuration
├── Dockerfile           # Docker configuration
└── Makefile            # Build automation
```

## Adding a New TTS Backend

To add support for a new TTS service:

1. Create a new file in `src/tts_backends/{backend_name}.py`
2. Implement the backend class with these methods:
   - `__init__(self, api_key=None, **kwargs)`
   - `clone_voice(self, sample_audio_path, voice_name, description=None)` → voice_id
   - `generate_speech(self, text, voice_id, output_path, **kwargs)`
   - `list_default_voices(self)` → dict of voice_id: voice_name

3. Add to `src/tts_backends/__init__.py`
4. Update `ConfigValidator.VALID_BACKENDS`
5. Add tests in `tests/`

Example:
```python
class MyBackend:
    def __init__(self, api_key=None):
        self.api_key = api_key
        
    def clone_voice(self, sample_audio_path, voice_name, description=None):
        # Implementation
        return voice_id
        
    def generate_speech(self, text, voice_id, output_path, **kwargs):
        # Implementation
        pass
```

## Pull Request Process

1. **Create a branch** for your feature or bug fix
2. **Make your changes** following the code style guidelines
3. **Add tests** for new functionality
4. **Run the test suite** to ensure nothing is broken
5. **Update documentation** if needed
6. **Submit a pull request** with a clear description

## Commit Messages

Use clear, descriptive commit messages:

- `feat: Add Doubao TTS backend`
- `fix: Handle empty text chunks`
- `docs: Update README with Docker instructions`
- `test: Add tests for audio concatenation`

## Reporting Issues

When reporting issues, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages and stack traces

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
