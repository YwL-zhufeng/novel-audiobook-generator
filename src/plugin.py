"""
Plugin system for custom TTS backends.
"""

import importlib
from pathlib import Path
from typing import Dict, Type, Optional, Any
from abc import ABC, abstractmethod

from .logging_config import get_logger

logger = get_logger(__name__)


class TTSBackendPlugin(ABC):
    """Base class for TTS backend plugins."""
    
    name: str = ""
    description: str = ""
    
    @abstractmethod
    def __init__(self, **kwargs):
        """Initialize the backend."""
        pass
    
    @abstractmethod
    def generate_speech(self, text: str, voice_id: str, output_path: str, **kwargs):
        """Generate speech from text."""
        pass
    
    def clone_voice(self, sample_audio_path: str, voice_name: str, **kwargs) -> str:
        """
        Clone a voice (optional).
        
        Returns:
            Voice ID
        """
        raise NotImplementedError("Voice cloning not supported")
    
    def list_voices(self) -> Dict[str, str]:
        """
        List available voices.
        
        Returns:
            Dictionary of voice_id -> description
        """
        return {}
    
    @property
    def supports_cloning(self) -> bool:
        """Whether this backend supports voice cloning."""
        return False
    
    @property
    def supports_streaming(self) -> bool:
        """Whether this backend supports streaming."""
        return False


class PluginManager:
    """Manager for TTS backend plugins."""
    
    def __init__(self):
        self.plugins: Dict[str, Type[TTSBackendPlugin]] = {}
        self._load_builtin_plugins()
    
    def _load_builtin_plugins(self):
        """Load built-in TTS backends as plugins."""
        try:
            from .tts_backends.elevenlabs import ElevenLabsBackend
            self.register('elevenlabs', ElevenLabsBackend)
        except ImportError:
            pass
        
        try:
            from .tts_backends.xtts import XTTSBackend
            self.register('xtts', XTTSBackend)
        except ImportError:
            pass
        
        try:
            from .tts_backends.kokoro import KokoroBackend
            self.register('kokoro', KokoroBackend)
        except ImportError:
            pass
        
        try:
            from .tts_backends.doubao import DoubaoBackend
            self.register('doubao', DoubaoBackend)
        except ImportError:
            pass
    
    def register(self, name: str, plugin_class: Type[TTSBackendPlugin]):
        """
        Register a plugin.
        
        Args:
            name: Plugin name
            plugin_class: Plugin class
        """
        self.plugins[name] = plugin_class
        logger.info(f"Registered plugin: {name}")
    
    def load_plugin_from_file(self, file_path: str, name: str):
        """
        Load a plugin from a Python file.
        
        Args:
            file_path: Path to plugin file
            name: Plugin name
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Plugin file not found: {file_path}")
        
        # Load module
        spec = importlib.util.spec_from_file_location(name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find plugin class
        plugin_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, TTSBackendPlugin) and 
                attr is not TTSBackendPlugin):
                plugin_class = attr
                break
        
        if not plugin_class:
            raise ValueError(f"No TTSBackendPlugin subclass found in {file_path}")
        
        self.register(name, plugin_class)
    
    def get_plugin(self, name: str) -> Optional[Type[TTSBackendPlugin]]:
        """
        Get a plugin by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin class or None
        """
        return self.plugins.get(name)
    
    def create_instance(self, name: str, **kwargs) -> TTSBackendPlugin:
        """
        Create a plugin instance.
        
        Args:
            name: Plugin name
            **kwargs: Arguments for plugin constructor
            
        Returns:
            Plugin instance
        """
        plugin_class = self.get_plugin(name)
        if not plugin_class:
            raise ValueError(f"Unknown plugin: {name}")
        
        return plugin_class(**kwargs)
    
    def list_plugins(self) -> Dict[str, str]:
        """
        List all registered plugins.
        
        Returns:
            Dictionary of name -> description
        """
        return {
            name: getattr(plugin, 'description', 'No description')
            for name, plugin in self.plugins.items()
        }


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


# Example custom plugin template
EXAMPLE_PLUGIN_TEMPLATE = '''
"""
Example custom TTS backend plugin.
"""

from src.plugin import TTSBackendPlugin


class MyCustomBackend(TTSBackendPlugin):
    """My custom TTS backend."""
    
    name = "my_custom"
    description = "My custom TTS backend"
    
    def __init__(self, api_key=None, **kwargs):
        self.api_key = api_key
    
    def generate_speech(self, text: str, voice_id: str, output_path: str, **kwargs):
        # Implement TTS generation
        pass
    
    def list_voices(self):
        return {
            "voice1": "Voice 1",
            "voice2": "Voice 2",
        }
'''


if __name__ == '__main__':
    manager = get_plugin_manager()
    print("Registered Plugins:")
    for name, desc in manager.list_plugins().items():
        print(f"  {name}: {desc}")
