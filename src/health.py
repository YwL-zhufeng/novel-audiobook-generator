"""
Health check and monitoring for the audiobook generator.
"""

import os
import sys
import psutil
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SystemHealth:
    """System health metrics."""
    cpu_percent: float
    memory_percent: float
    disk_free_gb: float
    disk_total_gb: float
    
    @property
    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        return (
            self.cpu_percent < 90 and
            self.memory_percent < 90 and
            self.disk_free_gb > 1.0  # At least 1GB free
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'disk_free_gb': round(self.disk_free_gb, 2),
            'disk_total_gb': round(self.disk_total_gb, 2),
            'is_healthy': self.is_healthy
        }


class HealthChecker:
    """Health checker for the audiobook generator."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / '.novel-audiobook-generator'
    
    def check_system(self) -> SystemHealth:
        """Check system health."""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage(str(self.cache_dir))
        disk_free_gb = disk.free / (1024 ** 3)
        disk_total_gb = disk.total / (1024 ** 3)
        
        return SystemHealth(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_free_gb=disk_free_gb,
            disk_total_gb=disk_total_gb
        )
    
    def check_dependencies(self) -> Dict[str, bool]:
        """Check if required dependencies are installed."""
        dependencies = {
            'pydub': False,
            'requests': False,
            'gradio': False,
            'spacy': False,
            'mutagen': False,
        }
        
        for module in dependencies.keys():
            try:
                __import__(module)
                dependencies[module] = True
            except ImportError:
                pass
        
        return dependencies
    
    def check_tts_backends(self) -> Dict[str, Any]:
        """Check TTS backend availability."""
        backends = {}
        
        # Check ElevenLabs
        try:
            from .tts_backends.elevenlabs import ElevenLabsBackend
            api_key = os.getenv('ELEVENLABS_API_KEY')
            backends['elevenlabs'] = {
                'available': True,
                'configured': bool(api_key)
            }
        except Exception as e:
            backends['elevenlabs'] = {
                'available': False,
                'error': str(e)
            }
        
        # Check XTTS
        try:
            from .tts_backends.xtts import XTTSBackend
            backends['xtts'] = {
                'available': True,
                'gpu': self._check_gpu()
            }
        except Exception as e:
            backends['xtts'] = {
                'available': False,
                'error': str(e)
            }
        
        # Check Doubao
        try:
            from .tts_backends.doubao import DoubaoBackend
            token = os.getenv('DOUBAO_ACCESS_TOKEN')
            backends['doubao'] = {
                'available': True,
                'configured': bool(token)
            }
        except Exception as e:
            backends['doubao'] = {
                'available': False,
                'error': str(e)
            }
        
        return backends
    
    def _check_gpu(self) -> bool:
        """Check if GPU is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except:
            return False
    
    def full_check(self) -> Dict[str, Any]:
        """Run full health check."""
        return {
            'system': self.check_system().to_dict(),
            'dependencies': self.check_dependencies(),
            'tts_backends': self.check_tts_backends(),
            'python_version': sys.version,
            'platform': sys.platform
        }
    
    def print_report(self):
        """Print health check report."""
        report = self.full_check()
        
        print("=" * 60)
        print("Health Check Report")
        print("=" * 60)
        
        # System
        print("\n📊 System:")
        system = report['system']
        print(f"  CPU: {system['cpu_percent']:.1f}%")
        print(f"  Memory: {system['memory_percent']:.1f}%")
        print(f"  Disk: {system['disk_free_gb']:.1f}GB free / {system['disk_total_gb']:.1f}GB total")
        print(f"  Status: {'✅ Healthy' if system['is_healthy'] else '⚠️  Warning'}")
        
        # Dependencies
        print("\n📦 Dependencies:")
        for dep, installed in report['dependencies'].items():
            status = "✅" if installed else "❌"
            print(f"  {status} {dep}")
        
        # TTS Backends
        print("\n🎙️  TTS Backends:")
        for backend, info in report['tts_backends'].items():
            if info.get('available'):
                configured = "✅" if info.get('configured') else "⚠️ "
                print(f"  {configured} {backend}")
            else:
                print(f"  ❌ {backend}: {info.get('error', 'Not available')}")
        
        print("\n" + "=" * 60)


# CLI command
if __name__ == '__main__':
    checker = HealthChecker()
    checker.print_report()
