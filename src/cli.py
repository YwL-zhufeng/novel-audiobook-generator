"""
CLI enhancements for better user experience.
"""

import click
from pathlib import Path
from typing import Optional

from .generator import AudiobookGenerator
from .config import Config
from .tts_backends.doubao import DoubaoBackend, ModelType


@click.group()
@click.option('--config', '-c', type=click.Path(), help='Configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, config, verbose):
    """Novel Audiobook Generator CLI"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    ctx.obj['verbose'] = verbose


@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--backend', '-b', default='doubao', 
              type=click.Choice(['elevenlabs', 'xtts', 'kokoro', 'doubao']),
              help='TTS backend')
@click.option('--voice', '-v', default='default', help='Voice to use')
@click.option('--workers', '-w', default=4, help='Number of concurrent workers')
@click.option('--resume/--no-resume', default=True, help='Resume from interrupted run')
@click.option('--characters', is_flag=True, help='Enable character voice attribution')
@click.pass_context
def generate(ctx, input_file, output, backend, voice, workers, resume, characters):
    """Generate audiobook from novel file"""
    # Implementation
    pass


@cli.group()
def voice():
    """Voice management commands"""
    pass


@voice.command('list')
@click.option('--backend', '-b', default='doubao', help='TTS backend')
def list_voices(backend):
    """List available voices"""
    if backend == 'doubao':
        backend = DoubaoBackend(access_token='dummy')
        voices = backend.list_default_voices()
        for voice_id, desc in voices.items():
            click.echo(f"{voice_id}: {desc}")


@voice.command('clone')
@click.argument('audio_file', type=click.Path(exists=True))
@click.argument('speaker_id')
@click.option('--model', '-m', default='icl2',
              type=click.Choice(['icl1', 'icl2', 'dit_standard', 'dit_restoration']),
              help='Cloning model')
@click.option('--language', '-l', default=0, type=int, help='Language code')
@click.option('--app-id', help='Doubao App ID')
@click.option('--token', help='Doubao Access Token')
def clone_voice(audio_file, speaker_id, model, language, app_id, token):
    """Clone a voice from audio sample"""
    # Implementation
    pass


@voice.command('status')
@click.argument('speaker_id')
@click.option('--app-id', help='Doubao App ID')
@click.option('--token', help='Doubao Access Token')
def voice_status(speaker_id, app_id, token):
    """Check voice cloning status"""
    # Implementation
    pass


@cli.command()
@click.argument('files', nargs=-1, required=True, type=click.Path(exists=True))
@click.option('--voice', '-v', default='default', help='Voice to use')
@click.option('--workers', '-w', default=4, help='Number of concurrent workers')
@click.option('--output-dir', '-d', default='output', help='Output directory')
def batch(files, voice, workers, output_dir):
    """Batch process multiple files"""
    # Implementation
    pass


@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--voice', '-v', default='default', help='Voice to use')
@click.option('--length', '-l', default=300, help='Preview length in characters')
def preview(input_file, voice, length):
    """Generate preview audio"""
    # Implementation
    pass


@cli.command()
def init():
    """Initialize configuration file"""
    config_path = Path('config.yaml')
    if config_path.exists():
        click.confirm('Config file already exists. Overwrite?', abort=True)
    
    # Create default config
    config = Config()
    config.to_yaml(str(config_path))
    click.echo(f"Created configuration file: {config_path}")


if __name__ == '__main__':
    cli()
