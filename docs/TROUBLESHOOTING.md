# Troubleshooting Guide

Common issues and solutions for Novel Audiobook Generator.

## Installation Issues

### ImportError: No module named 'xxx'

**Cause**: Missing dependencies

**Solution**:
```bash
# Reinstall with all dependencies
pip install -e ".[all]"

# Or install specific backend
pip install -e ".[elevenlabs]"
pip install -e ".[xtts]"
```

### Error installing PyTorch

**Cause**: PyTorch requires specific CUDA version

**Solution**:
```bash
# For CPU only
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# For CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### spaCy model not found

**Cause**: Language models not downloaded

**Solution**:
```bash
python -m spacy download zh_core_web_sm
python -m spacy download en_core_web_sm
```

## TTS Backend Issues

### Doubao: "Authentication failed"

**Cause**: Invalid or missing access token

**Solution**:
1. Get token from [Volcano Engine](https://www.volcengine.com/)
2. Set environment variable: `export DOUBAO_ACCESS_TOKEN="xxx"`
3. Or pass via CLI: `--access-token xxx`

### ElevenLabs: "Rate limit exceeded"

**Cause**: Too many concurrent requests

**Solution**:
```bash
# Reduce workers
python generate_audiobook.py novel.txt --workers 1

# Or add delays in config
```

### XTTS: "CUDA out of memory"

**Cause**: GPU memory insufficient

**Solution**:
```bash
# Use CPU
export CUDA_VISIBLE_DEVICES=""

# Or reduce batch size in code
```

### Kokoro: "Not implemented"

**Cause**: Kokoro backend is a placeholder

**Solution**: Use ElevenLabs, XTTS, or Doubao instead

## Generation Issues

### "Text extraction failed"

**Cause**: Unsupported file format or corrupted file

**Solution**:
1. Check file format (supported: TXT, EPUB, PDF)
2. Try converting to TXT first
3. Check file encoding (UTF-8 recommended)

### "Out of memory"

**Cause**: Large file with high concurrency

**Solution**:
```bash
# Reduce workers and chunk size
python generate_audiobook.py novel.txt \
  --workers 2 \
  --chunk-size 2000

# Enable streaming mode (if available)
```

### "Resume not working"

**Cause**: Progress file corrupted or input file changed

**Solution**:
```bash
# Clear progress and start fresh
rm -rf ~/.novel-audiobook-generator/progress.db

# Or use --no-resume flag
python generate_audiobook.py novel.txt --no-resume
```

### Audio quality is poor

**Causes and Solutions**:

1. **Voice sample quality**
   - Use 15-20 seconds of clear speech
   - Record in quiet environment
   - Avoid background noise

2. **TTS backend limitations**
   - Try ElevenLabs for best quality
   - Adjust stability settings

3. **Text preprocessing**
   - Check for unusual characters
   - Ensure proper punctuation

## Configuration Issues

### "Config validation failed"

**Cause**: Invalid configuration values

**Solution**:
```bash
# Validate config
python -c "
from src.config import Config
from src.validator import ConfigValidator

config = Config.from_yaml('config.yaml')
is_valid, errors = ConfigValidator.validate_config(config.__dict__)
for e in errors:
    print(f'{e.field}: {e.message}')
"
```

### Environment variables not expanding

**Cause**: Wrong syntax

**Solution**: Use `${VAR}` syntax in YAML:
```yaml
tts:
  api_key: ${ELEVENLABS_API_KEY}
```

## Performance Issues

### Generation is too slow

**Solutions**:

1. **Increase workers** (if API allows):
   ```bash
   python generate_audiobook.py novel.txt --workers 8
   ```

2. **Use faster backend**:
   - Doubao: Fast for Chinese
   - Kokoro: Fast but lower quality

3. **Enable caching**:
   ```python
   from src.cache import CacheManager
   cache = CacheManager()
   ```

### High memory usage

**Solutions**:

1. **Reduce chunk size**:
   ```bash
   python generate_audiobook.py novel.txt --chunk-size 2000
   ```

2. **Use incremental audio merge** (automatic for large files)

3. **Process in smaller batches**:
   ```python
   # Split novel into parts
   ```

## Docker Issues

### "Cannot connect to Docker daemon"

**Solution**:
```bash
# Start Docker service
sudo systemctl start docker

# Or use Docker Desktop
```

### Port already in use

**Solution**:
```bash
# Use different port
docker run -p 7861:7860 novel-audiobook-generator
```

### Volume permissions

**Solution**:
```bash
# Fix permissions
sudo chown -R $USER:$USER ./output
```

## Web UI Issues

### "Connection refused"

**Cause**: Server not running or wrong port

**Solution**:
```bash
# Check if running
python webui.py

# Check port
# Default is 7860
```

### "File upload failed"

**Cause**: File too large or wrong format

**Solution**:
- Check file size (max 100MB typical)
- Ensure supported format (TXT, EPUB, PDF)

### Gradio errors in browser console

**Solution**:
```bash
# Update Gradio
pip install -U gradio
```

## Debugging

### Enable debug logging

```bash
export AUDIOBOOK_LOG_LEVEL=DEBUG
export AUDIOBOOK_LOG_FILE=debug.log
```

### Check progress database

```bash
# View active tasks
python -c "
from src.progress_manager import ProgressManager
pm = ProgressManager()
for task in pm.get_incomplete_tasks():
    print(f'{task.task_id}: {task.progress_percentage:.1f}%')
"
```

### Profile performance

```python
from src.logging_config import PerformanceLogger
from src.generator import AudiobookGenerator

logger = PerformanceLogger(get_logger(__name__))
generator = AudiobookGenerator()

with logger.timer("full_generation"):
    generator.generate_audiobook("novel.txt")

print(logger.get_metrics())
```

## Getting More Help

1. **Check logs**: `~/.novel-audiobook-generator/logs/`
2. **Enable debug mode**: Set `AUDIOBOOK_LOG_LEVEL=DEBUG`
3. **Open an issue**: Include logs and error messages
4. **Check documentation**: [API Reference](API.md), [Tutorial](TUTORIAL.md)

## Common Error Codes

| Error Code | Meaning | Solution |
|------------|---------|----------|
| CONFIG_ERROR | Invalid configuration | Check config file |
| TTS_ERROR | TTS generation failed | Check API key and limits |
| VOICE_CLONE_ERROR | Voice cloning failed | Check sample quality |
| TEXT_PROCESS_ERROR | Text extraction failed | Check file format |
| AUDIO_PROCESS_ERROR | Audio processing failed | Check disk space |
| FILE_FORMAT_ERROR | Unsupported format | Convert file |
| API_ERROR | API request failed | Check network and credentials |
| RATE_LIMIT_ERROR | Too many requests | Reduce workers |
| NOT_FOUND | Resource not found | Check file paths |
| VALIDATION_ERROR | Input validation failed | Check input values |
