"""
Preset configurations for common use cases.
"""

from typing import Dict, Any


# Preset configurations for different use cases
AUDIOBOOK_PRESETS: Dict[str, Dict[str, Any]] = {
    'novel': {
        'name': '📖 Novel (Standard)',
        'description': 'Standard settings for novels',
        'tts': {
            'backend': 'doubao',
            'max_workers': 4,
        },
        'text': {
            'chunk_size': 4000,
            'detect_dialogue': True,
        },
        'output': {
            'format': 'mp3',
            'bitrate': '192k',
            'normalize': True,
        },
        'voice_recommendation': 'zh_female_wanwanxiaohe_moon_bigtts',
    },
    
    'audiobook_high_quality': {
        'name': '🎧 Audiobook (High Quality)',
        'description': 'High quality settings for professional audiobooks',
        'tts': {
            'backend': 'doubao',
            'max_workers': 2,  # Slower but more stable
        },
        'text': {
            'chunk_size': 3000,
            'detect_dialogue': True,
        },
        'output': {
            'format': 'mp3',
            'bitrate': '320k',
            'normalize': True,
        },
        'voice_recommendation': 'zh_female_shuangkuaisisi_moon_bigtts',
        'effects': [
            {'type': 'normalize', 'target_dBFS': -14.0},
            {'type': 'silence_start', 'duration_ms': 500},
            {'type': 'silence_end', 'duration_ms': 1000},
        ]
    },
    
    'podcast': {
        'name': '🎙️ Podcast',
        'description': 'Settings optimized for podcast-style narration',
        'tts': {
            'backend': 'doubao',
            'max_workers': 4,
        },
        'text': {
            'chunk_size': 3500,
            'detect_dialogue': False,  # Usually no dialogue in podcasts
        },
        'output': {
            'format': 'mp3',
            'bitrate': '192k',
            'normalize': True,
        },
        'voice_recommendation': 'zh_male_shenyeboke_moon_bigtts',
    },
    
    'children_book': {
        'name': '👶 Children\'s Book',
        'description': 'Settings for children\'s books with character voices',
        'tts': {
            'backend': 'doubao',
            'max_workers': 4,
        },
        'text': {
            'chunk_size': 3000,
            'detect_dialogue': True,
        },
        'output': {
            'format': 'mp3',
            'bitrate': '192k',
            'normalize': True,
        },
        'voice_recommendation': 'zh_female_tianmeitaozi_mars_bigtts',
        'use_character_voices': True,
    },
    
    'study_material': {
        'name': '📚 Study Material',
        'description': 'Clear, slow narration for study materials',
        'tts': {
            'backend': 'doubao',
            'max_workers': 4,
        },
        'text': {
            'chunk_size': 2000,  # Smaller chunks for clarity
            'detect_dialogue': False,
        },
        'output': {
            'format': 'mp3',
            'bitrate': '192k',
            'normalize': True,
        },
        'voice_recommendation': 'zh_female_qinqienvsheng_moon_bigtts',
        'speed': 0.9,  # Slightly slower
    },
    
    'quick_preview': {
        'name': '⚡ Quick Preview',
        'description': 'Fast generation for previewing',
        'tts': {
            'backend': 'doubao',
            'max_workers': 8,  # Maximum workers
        },
        'text': {
            'chunk_size': 5000,  # Larger chunks
            'detect_dialogue': False,
        },
        'output': {
            'format': 'mp3',
            'bitrate': '128k',  # Lower quality
            'normalize': False,
        },
        'voice_recommendation': 'zh_male_yangguangqingnian_moon_bigtts',
    },
    
    'english_audiobook': {
        'name': '🇬🇧 English Audiobook',
        'description': 'Settings for English audiobooks',
        'tts': {
            'backend': 'elevenlabs',
            'max_workers': 2,
        },
        'text': {
            'chunk_size': 4000,
            'detect_dialogue': True,
        },
        'output': {
            'format': 'mp3',
            'bitrate': '192k',
            'normalize': True,
        },
        'voice_recommendation': 'default',
    },
}


# Voice recommendations by genre
VOICE_RECOMMENDATIONS: Dict[str, Dict[str, str]] = {
    'romance': {
        'narrator': 'zh_female_wenrouxiaoya_moon_bigtts',
        'male_lead': 'zh_male_wennuanahu_moon_bigtts',
        'female_lead': 'zh_female_meilinvyou_moon_bigtts',
    },
    'scifi': {
        'narrator': 'zh_male_dongfanghaoran_moon_bigtts',
        'ai': 'zh_female_gaolengyujie_moon_bigtts',
    },
    'mystery': {
        'narrator': 'zh_male_shenyeboke_moon_bigtts',
        'detective': 'zh_male_jieshuoxiaoming_moon_bigtts',
    },
    'fantasy': {
        'narrator': 'zh_female_xinlingjitang_moon_bigtts',
        'wizard': 'zh_male_yuanboxiaoshu_moon_bigtts',
    },
    'business': {
        'narrator': 'zh_male_shaonianzixin_moon_bigtts',
    },
    'history': {
        'narrator': 'zh_male_jingqiangkanye_moon_bigtts',
    },
}


def get_preset(name: str) -> Dict[str, Any]:
    """
    Get a preset configuration by name.
    
    Args:
        name: Preset name
        
    Returns:
        Preset configuration
    """
    if name not in AUDIOBOOK_PRESETS:
        raise ValueError(f"Unknown preset: {name}. Available: {list(AUDIOBOOK_PRESETS.keys())}")
    
    return AUDIOBOOK_PRESETS[name]


def list_presets() -> Dict[str, str]:
    """List all available presets with descriptions."""
    return {
        key: f"{preset['name']}: {preset['description']}"
        for key, preset in AUDIOBOOK_PRESETS.items()
    }


def get_voice_recommendation(genre: str, character_type: str = 'narrator') -> str:
    """
    Get voice recommendation for genre and character type.
    
    Args:
        genre: Book genre
        character_type: Type of character (narrator, male_lead, etc.)
        
    Returns:
        Voice ID recommendation
    """
    genre_voices = VOICE_RECOMMENDATIONS.get(genre.lower(), {})
    return genre_voices.get(character_type, 'default')


def apply_preset(config: Dict[str, Any], preset_name: str) -> Dict[str, Any]:
    """
    Apply a preset to an existing configuration.
    
    Args:
        config: Existing configuration
        preset_name: Preset to apply
        
    Returns:
        Merged configuration
    """
    from .utils import merge_dicts
    
    preset = get_preset(preset_name)
    
    # Remove metadata fields
    preset_config = {k: v for k, v in preset.items() if k not in ['name', 'description', 'voice_recommendation']}
    
    return merge_dicts(config, preset_config)


# CLI helper
if __name__ == '__main__':
    print("Available Presets:")
    print("=" * 60)
    for key, desc in list_presets().items():
        print(f"  {key}: {desc}")
    
    print("\n\nVoice Recommendations by Genre:")
    print("=" * 60)
    for genre, voices in VOICE_RECOMMENDATIONS.items():
        print(f"\n{genre.title()}:")
        for char_type, voice in voices.items():
            print(f"  {char_type}: {voice}")
