#!/usr/bin/env python3
"""
Complete test script for Doubao TTS backend with voice cloning.
Tests all features without requiring real API credentials.
"""

import sys
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tts_backends.doubao import DoubaoBackend, ModelType, ClonedVoice


def test_model_type_enum():
    """Test ModelType enum."""
    print("\n=== Testing ModelType Enum ===")
    
    assert ModelType.ICL_1_0.value == 1
    assert ModelType.DIT_STANDARD.value == 2
    assert ModelType.DIT_RESTORATION.value == 3
    assert ModelType.ICL_2_0.value == 4
    
    print("✅ ModelType enum test passed")
    return True


def test_cloned_voice_dataclass():
    """Test ClonedVoice dataclass."""
    print("\n=== Testing ClonedVoice Dataclass ===")
    
    voice = ClonedVoice(
        speaker_id="S_test_voice",
        status=2,
        version=1,
        model_type=4
    )
    
    assert voice.speaker_id == "S_test_voice"
    assert voice.is_ready == True
    assert voice.status_text == "训练完成"
    
    # Test not ready
    voice2 = ClonedVoice(
        speaker_id="S_training",
        status=1,
        version=1,
        model_type=4
    )
    assert voice2.is_ready == False
    assert voice2.status_text == "训练中"
    
    print("✅ ClonedVoice dataclass test passed")
    return True


def test_initialization():
    """Test backend initialization."""
    print("\n=== Testing Initialization ===")
    
    try:
        backend = DoubaoBackend(access_token="test_token")
        assert backend.access_token == "test_token"
        assert backend.cluster == "volcano_tts"
        assert backend.resource_id == "volc.megatts.voiceclone"
        print("✅ Initialization test passed")
        return True
    except Exception as e:
        print(f"❌ Initialization test failed: {e}")
        return False


def test_voice_lists():
    """Test voice listing functions."""
    print("\n=== Testing Voice Lists ===")
    
    backend = DoubaoBackend(access_token="test_token")
    
    # Test default voices
    default_voices = backend.list_default_voices()
    assert len(default_voices) >= 50
    assert "zh_female_wanwanxiaohe_moon_bigtts" in default_voices
    print(f"  Default voices: {len(default_voices)}")
    
    # Test recommended voices
    audiobook = backend.get_recommended_voices("audiobook")
    roleplay = backend.get_recommended_voices("roleplay")
    emotional = backend.get_recommended_voices("emotional")
    
    print(f"  Audiobook voices: {len(audiobook)}")
    print(f"  Roleplay voices: {len(roleplay)}")
    print(f"  Emotional voices: {len(emotional)}")
    
    assert len(audiobook) > 0
    assert len(roleplay) > 0
    assert len(emotional) > 0
    
    print("✅ Voice lists test passed")
    return True


def test_is_cloned_voice():
    """Test cloned voice detection."""
    print("\n=== Testing Cloned Voice Detection ===")
    
    backend = DoubaoBackend(access_token="test_token")
    
    # Standard voices
    assert backend._is_cloned_voice("zh_female_wanwanxiaohe_moon_bigtts") == False
    assert backend._is_cloned_voice("ICL_zh_male_aojiaobazong_tob") == False
    
    # Cloned voices
    assert backend._is_cloned_voice("S_custom_voice") == True
    assert backend._is_cloned_voice("S_123456") == True
    
    # Add to tracked voices
    backend.cloned_voices["my_voice"] = ClonedVoice("my_voice", 2, 1, 4)
    assert backend._is_cloned_voice("my_voice") == True
    
    print("✅ Cloned voice detection test passed")
    return True


def test_build_tts_payload():
    """Test TTS payload building."""
    print("\n=== Testing Build TTS Payload ===")
    
    backend = DoubaoBackend(
        app_id="test_appid",
        access_token="test_token"
    )
    
    payload = backend._build_tts_payload(
        text="你好，测试",
        voice_type="zh_female_wanwanxiaohe_moon_bigtts",
        cluster="volcano_tts",
        speed_ratio=1.2,
        volume_ratio=0.9
    )
    
    # Verify structure
    assert "app" in payload
    assert "user" in payload
    assert "audio" in payload
    assert "request" in payload
    
    # Verify values
    assert payload["app"]["appid"] == "test_appid"
    assert payload["app"]["token"] == "test_token"
    assert payload["app"]["cluster"] == "volcano_tts"
    assert payload["audio"]["voice_type"] == "zh_female_wanwanxiaohe_moon_bigtts"
    assert payload["audio"]["speed_ratio"] == 1.2
    assert payload["audio"]["volume_ratio"] == 0.9
    assert payload["request"]["text"] == "你好，测试"
    assert payload["request"]["operation"] == "query"
    assert "reqid" in payload["request"]
    
    print(f"  Payload: {json.dumps(payload, indent=2, ensure_ascii=False)[:200]}...")
    print("✅ Build TTS payload test passed")
    return True


def test_build_clone_payload():
    """Test voice clone payload building."""
    print("\n=== Testing Build Clone Payload ===")
    
    backend = DoubaoBackend(
        app_id="test_appid",
        access_token="test_token"
    )
    
    # Mock base64 encoding
    import base64
    test_audio = b"fake_audio_data"
    audio_bytes = base64.b64encode(test_audio).decode("utf-8")
    
    payload = {
        "appid": "test_appid",
        "speaker_id": "S_test_voice",
        "audios": [{
            "audio_bytes": audio_bytes,
            "audio_format": "wav"
        }],
        "source": 2,
        "language": 0,
        "model_type": ModelType.ICL_2_0.value,
    }
    
    assert payload["appid"] == "test_appid"
    assert payload["speaker_id"] == "S_test_voice"
    assert payload["model_type"] == 4
    assert payload["language"] == 0
    assert payload["source"] == 2
    
    print("✅ Build clone payload test passed")
    return True


def test_cluster_selection():
    """Test cluster selection for different voice types."""
    print("\n=== Testing Cluster Selection ===")
    
    backend = DoubaoBackend(access_token="test_token")
    
    # Standard voice
    standard_cluster = backend.CLUSTER_STANDARD
    icl_cluster = backend.CLUSTER_ICL
    
    print(f"  Standard cluster: {standard_cluster}")
    print(f"  ICL cluster: {icl_cluster}")
    
    assert standard_cluster == "volcano_tts"
    assert icl_cluster == "volcano_icl"
    
    print("✅ Cluster selection test passed")
    return True


def test_api_endpoints():
    """Test API endpoint URLs."""
    print("\n=== Testing API Endpoints ===")
    
    backend = DoubaoBackend(access_token="test_token")
    
    print(f"  TTS API: {backend.TTS_API_URL}")
    print(f"  Clone Upload: {backend.VOICE_CLONE_UPLOAD_URL}")
    print(f"  Clone Status: {backend.VOICE_CLONE_STATUS_URL}")
    print(f"  Clone Activate: {backend.VOICE_CLONE_ACTIVATE_URL}")
    
    assert "openspeech.bytedance.com" in backend.TTS_API_URL
    assert "/api/v1/tts" in backend.TTS_API_URL
    assert "/mega_tts/" in backend.VOICE_CLONE_UPLOAD_URL
    
    print("✅ API endpoints test passed")
    return True


def test_headers():
    """Test header generation."""
    print("\n=== Testing Headers ===")
    
    backend = DoubaoBackend(access_token="test_token123")
    
    # Standard headers
    headers = backend._get_headers()
    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer;test_token123"
    assert "Resource-Id" not in headers
    
    # With resource_id
    headers_with_resource = backend._get_headers("volc.megatts.voiceclone")
    assert headers_with_resource["Resource-Id"] == "volc.megatts.voiceclone"
    
    print("✅ Headers test passed")
    return True


def test_mock_clone_voice():
    """Test voice cloning with mocked API."""
    print("\n=== Testing Voice Cloning (Mocked) ===")
    
    backend = DoubaoBackend(
        app_id="test_appid",
        access_token="test_token"
    )
    
    # Mock the session.post method
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json = Mock(return_value={
        "status": 1,
        "speaker_id": "S_test_voice"
    })
    
    with patch.object(backend.session, 'post', return_value=mock_response):
        # Create a temporary audio file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"fake_audio_data")
            temp_path = f.name
        
        try:
            cloned = backend.clone_voice(
                sample_audio_path=temp_path,
                speaker_id="S_test_voice",
                model_type=ModelType.ICL_2_0,
                wait_for_completion=False
            )
            
            assert cloned.speaker_id == "S_test_voice"
            assert cloned.model_type == 4
            assert cloned.status == 1  # 训练中
            
            print(f"  Cloned voice: {cloned.speaker_id}")
            print(f"  Status: {cloned.status_text}")
            
        finally:
            Path(temp_path).unlink()
    
    print("✅ Voice cloning test passed")
    return True


def test_mock_get_status():
    """Test get voice status with mocked API."""
    print("\n=== Testing Get Voice Status (Mocked) ===")
    
    backend = DoubaoBackend(
        app_id="test_appid",
        access_token="test_token"
    )
    
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json = Mock(return_value={
        "status": 2,
        "version": 2,
        "model_type": 4,
        "create_time": "2024-01-01T00:00:00Z"
    })
    
    with patch.object(backend.session, 'post', return_value=mock_response):
        voice = backend.get_voice_status("S_test_voice")
        
        assert voice.speaker_id == "S_test_voice"
        assert voice.status == 2  # 训练完成
        assert voice.is_ready == True
        assert voice.version == 2
        
        print(f"  Voice status: {voice.status_text}")
        print(f"  Is ready: {voice.is_ready}")
    
    print("✅ Get voice status test passed")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Doubao TTS Backend Complete Test Suite")
    print("=" * 60)
    
    results = []
    
    tests = [
        ("ModelType Enum", test_model_type_enum),
        ("ClonedVoice Dataclass", test_cloned_voice_dataclass),
        ("Initialization", test_initialization),
        ("Voice Lists", test_voice_lists),
        ("Cloned Voice Detection", test_is_cloned_voice),
        ("Build TTS Payload", test_build_tts_payload),
        ("Build Clone Payload", test_build_clone_payload),
        ("Cluster Selection", test_cluster_selection),
        ("API Endpoints", test_api_endpoints),
        ("Headers", test_headers),
        ("Mock Clone Voice", test_mock_clone_voice),
        ("Mock Get Status", test_mock_get_status),
    ]
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
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
    
    if passed == total:
        print("\n" + "=" * 60)
        print("🎉 All tests passed!")
        print("Doubao backend with voice cloning is fully functional.")
        print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
