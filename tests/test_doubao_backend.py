#!/usr/bin/env python3
"""
Test script for Doubao TTS backend.
Tests the API integration without generating full audiobooks.
"""

import sys
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Direct import to avoid relative import issues
import importlib.util
spec = importlib.util.spec_from_file_location("doubao", str(Path(__file__).parent.parent / "src" / "tts_backends" / "doubao.py"))
doubao_module = importlib.util.module_from_spec(spec)
sys.modules["doubao"] = doubao_module

# Mock the relative imports
class MockExceptions:
    class TTSError(Exception):
        pass
    class APIError(Exception):
        pass
    class RateLimitError(Exception):
        pass
    class ValidationError(Exception):
        pass

class MockLogging:
    def get_logger(self, name):
        import logging
        return logging.getLogger(name)

sys.modules["..exceptions"] = MockExceptions()
sys.modules["..logging_config"] = MockLogging()

spec.loader.exec_module(doubao_module)
DoubaoBackend = doubao_module.DoubaoBackend

# Setup logging
setup_logging(level="DEBUG")


def test_list_voices():
    """Test listing available voices."""
    print("\n=== Testing List Voices ===")
    
    # Create backend without API key for this test
    try:
        backend = DoubaoBackend(access_token="dummy_token")
        voices = backend.list_default_voices()
        
        print(f"Available voices: {len(voices)}")
        
        # Print first 10 voices
        for i, (voice_id, desc) in enumerate(list(voices.items())[:10]):
            print(f"  {voice_id}: {desc}")
        
        # Check specific voices exist
        assert "zh_female_wanwanxiaohe_moon_bigtts" in voices
        assert "zh_male_yangguangqingnian_moon_bigtts" in voices
        
        print("✅ List voices test passed")
        return True
        
    except Exception as e:
        print(f"❌ List voices test failed: {e}")
        return False


def test_get_recommended_voices():
    """Test getting recommended voices for different scenarios."""
    print("\n=== Testing Recommended Voices ===")
    
    try:
        backend = DoubaoBackend(access_token="dummy_token")
        
        # Test audiobook scenario
        audiobook_voices = backend.get_recommended_voices("audiobook")
        print(f"Audiobook voices: {len(audiobook_voices)}")
        for voice_id, desc in list(audiobook_voices.items())[:5]:
            print(f"  {voice_id}: {desc}")
        
        # Test roleplay scenario
        roleplay_voices = backend.get_recommended_voices("roleplay")
        print(f"\nRoleplay voices: {len(roleplay_voices)}")
        for voice_id, desc in list(roleplay_voices.items())[:5]:
            print(f"  {voice_id}: {desc}")
        
        # Test emotional scenario
        emotional_voices = backend.get_recommended_voices("emotional")
        print(f"\nEmotional voices: {len(emotional_voices)}")
        for voice_id, desc in list(emotional_voices.items())[:5]:
            print(f"  {voice_id}: {desc}")
        
        print("✅ Recommended voices test passed")
        return True
        
    except Exception as e:
        print(f"❌ Recommended voices test failed: {e}")
        return False


def test_build_payload():
    """Test building API request payload."""
    print("\n=== Testing Build Payload ===")
    
    try:
        backend = DoubaoBackend(
            app_id="test_appid",
            access_token="test_token"
        )
        
        payload = backend._build_request_payload(
            text="你好，这是测试文本",
            voice_type="zh_female_wanwanxiaohe_moon_bigtts",
            speed_ratio=1.0,
            volume_ratio=1.0,
            sample_rate=24000,
            encoding="mp3"
        )
        
        # Verify payload structure
        assert "app" in payload
        assert "user" in payload
        assert "audio" in payload
        assert "request" in payload
        
        assert payload["app"]["appid"] == "test_appid"
        assert payload["app"]["token"] == "test_token"
        assert payload["app"]["cluster"] == "volcano_tts"
        
        assert payload["audio"]["voice_type"] == "zh_female_wanwanxiaohe_moon_bigtts"
        assert payload["audio"]["encoding"] == "mp3"
        assert payload["audio"]["speed_ratio"] == 1.0
        
        assert payload["request"]["text"] == "你好，这是测试文本"
        assert payload["request"]["operation"] == "query"
        
        print(f"Payload structure: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        print("✅ Build payload test passed")
        return True
        
    except Exception as e:
        print(f"❌ Build payload test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_text_truncation():
    """Test text length handling."""
    print("\n=== Testing Text Truncation ===")
    
    try:
        backend = DoubaoBackend(access_token="dummy_token")
        
        # Test with text exceeding 1024 bytes
        long_text = "这是一个很长的测试文本。" * 100  # ~3000 bytes
        
        # Build payload should handle truncation
        payload = backend._build_request_payload(
            text=long_text,
            voice_type="zh_female_wanwanxiaohe_moon_bigtts"
        )
        
        text_bytes = payload["request"]["text"].encode('utf-8')
        assert len(text_bytes) <= 1024
        
        print(f"Original text: {len(long_text.encode('utf-8'))} bytes")
        print(f"Truncated text: {len(text_bytes)} bytes")
        print("✅ Text truncation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Text truncation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_call_with_real_credentials():
    """Test actual API call (requires real credentials)."""
    print("\n=== Testing Real API Call ===")
    
    # Get credentials from environment
    app_id = os.getenv("DOUBAO_APP_ID")
    access_token = os.getenv("DOUBAO_ACCESS_TOKEN")
    
    if not access_token:
        print("⚠️  Skipping real API test (no credentials)")
        print("   Set DOUBAO_ACCESS_TOKEN to run this test")
        return True
    
    try:
        backend = DoubaoBackend(
            app_id=app_id,
            access_token=access_token
        )
        
        # Generate short test audio
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            output_path = f.name
        
        print(f"Generating test audio to: {output_path}")
        
        backend.generate_speech(
            text="你好，这是豆包语音合成的测试。",
            voice_id="zh_female_wanwanxiaohe_moon_bigtts",
            output_path=output_path
        )
        
        # Check file was created and has content
        output_file = Path(output_path)
        assert output_file.exists()
        assert output_file.stat().st_size > 1000  # At least 1KB
        
        print(f"Generated audio: {output_file.stat().st_size} bytes")
        print("✅ Real API call test passed")
        
        # Cleanup
        output_file.unlink()
        return True
        
    except Exception as e:
        print(f"❌ Real API call test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Doubao TTS Backend Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("List Voices", test_list_voices()))
    results.append(("Recommended Voices", test_get_recommended_voices()))
    results.append(("Build Payload", test_build_payload()))
    results.append(("Text Truncation", test_text_truncation()))
    results.append(("Real API Call", test_api_call_with_real_credentials()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    import json
    success = main()
    sys.exit(0 if success else 1)
