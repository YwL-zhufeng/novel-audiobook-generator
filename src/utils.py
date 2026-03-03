"""
Utility functions for the audiobook generator.
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Optional, Union


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    Sanitize a filename by removing invalid characters.
    
    Args:
        filename: Original filename
        max_length: Maximum length for the filename
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    sanitized = re.sub(r'[\u003c\u003e:"/\\|?*]', '', filename)
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    # Strip leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rsplit(' ', 1)[0]
    return sanitized or "untitled"


def compute_file_hash(file_path: Union[str, Path], algorithm: str = "md5") -> str:
    """
    Compute hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha256)
        
    Returns:
        Hex digest of the file hash
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return ""
    
    hash_obj = hashlib.new(algorithm)
    
    # Read in chunks to handle large files
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2h 30m 45s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes to human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Original text
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, create if not.
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_safe_output_path(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    suffix: str = "_audiobook",
    extension: str = ".mp3"
) -> Path:
    """
    Generate safe output path based on input file.
    
    Args:
        input_path: Input file path
        output_dir: Output directory
        suffix: Suffix to add to filename
        extension: Output file extension
        
    Returns:
        Safe output path
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    
    # Sanitize stem
    safe_stem = sanitize_filename(input_path.stem)
    
    # Generate output filename
    output_name = f"{safe_stem}{suffix}{extension}"
    output_path = output_dir / output_name
    
    # Handle duplicates
    counter = 1
    while output_path.exists():
        output_name = f"{safe_stem}{suffix}_{counter}{extension}"
        output_path = output_dir / output_name
        counter += 1
    
    return output_path


def parse_time_string(time_str: str) -> Optional[int]:
    """
    Parse time string to milliseconds.
    
    Supports formats like:
    - "1:30" -> 90 seconds
    - "1:30:00" -> 5400 seconds
    - "90s" -> 90 seconds
    - "1m30s" -> 90 seconds
    
    Args:
        time_str: Time string
        
    Returns:
        Time in milliseconds or None if invalid
    """
    time_str = time_str.strip()
    
    # Try HH:MM:SS or MM:SS format
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:  # MM:SS
            try:
                minutes, seconds = int(parts[0]), int(parts[1])
                return (minutes * 60 + seconds) * 1000
            except ValueError:
                return None
        elif len(parts) == 3:  # HH:MM:SS
            try:
                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                return (hours * 3600 + minutes * 60 + seconds) * 1000
            except ValueError:
                return None
    
    # Try XmYs format
    match = re.match(r'^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?$', time_str, re.IGNORECASE)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return (hours * 3600 + minutes * 60 + seconds) * 1000
    
    # Try plain seconds
    try:
        return int(time_str) * 1000
    except ValueError:
        return None


def chunk_list(lst: list, chunk_size: int):
    """Split list into chunks."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def merge_dicts(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
