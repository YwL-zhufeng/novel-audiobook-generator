"""
Comprehensive test suite for novel-audiobook-generator.
"""

import pytest
import tempfile
from pathlib import Path

# Configure pytest
pytest_plugins = ["pytest_asyncio"]

def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "requires_api: marks tests that require API keys")
