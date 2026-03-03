#!/usr/bin/env python3
"""
Simple validation of Doubao TTS backend implementation.
This checks the code structure without running actual API calls.
"""

import ast
import sys
from pathlib import Path


def check_doubao_backend():
    """Check Doubao backend implementation against API documentation."""
    print("=" * 60)
    print("Doubao TTS Backend Validation")
    print("=" * 60)
    
    backend_file = Path(__file__).parent.parent / "src" / "tts_backends" / "doubao.py"
    
    if not backend_file.exists():
        print("❌ doubao.py not found")
        return False
    
    with open(backend_file, 'r') as f:
        source = f.read()
    
    # Parse the source
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"❌ Syntax error: {e}")
        return False
    
    checks = []
    
    # Check 1: API URL is correct
    if "https://openspeech.bytedance.com/api/v1/tts" in source:
        checks.append(("API URL (V1 HTTP)", True))
    else:
        checks.append(("API URL (V1 HTTP)", False))
    
    # Check 2: Bearer token format
    if 'Bearer;{self.access_token}' in source or 'Bearer;{token}' in source:
        checks.append(("Bearer Token Format", True))
    else:
        checks.append(("Bearer Token Format", False))
    
    # Check 3: Request payload structure
    required_fields = ['"app"', '"user"', '"audio"', '"request"', '"reqid"', '"operation"']
    missing_fields = [f for f in required_fields if f not in source]
    if not missing_fields:
        checks.append(("Request Payload Structure", True))
    else:
        checks.append(("Request Payload Structure", False))
        print(f"   Missing fields: {missing_fields}")
    
    # Check 4: Voice list is comprehensive
    voice_count = source.count('"zh_') + source.count('"en_') + source.count('"ICL_')
    if voice_count >= 50:
        checks.append(("Voice List (50+ voices)", True))
    else:
        checks.append((f"Voice List ({voice_count} voices)", False))
    
    # Check 5: Error handling
    if "TTSError" in source and "RateLimitError" in source:
        checks.append(("Error Handling", True))
    else:
        checks.append(("Error Handling", False))
    
    # Check 6: Retry mechanism
    if "retry_on_rate_limit" in source:
        checks.append(("Rate Limit Retry", True))
    else:
        checks.append(("Rate Limit Retry", False))
    
    # Check 7: Text length validation
    if "1024" in source and "encode('utf-8')" in source:
        checks.append(("Text Length Validation", True))
    else:
        checks.append(("Text Length Validation", False))
    
    # Check 8: Response code handling
    if "3000" in source:  # Success code
        checks.append(("API Response Code Handling", True))
    else:
        checks.append(("API Response Code Handling", False))
    
    # Print results
    print("\nValidation Results:")
    print("-" * 60)
    
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")
    
    passed_count = sum(1 for _, p in checks if p)
    total_count = len(checks)
    
    print("-" * 60)
    print(f"Passed: {passed_count}/{total_count}")
    
    # API Compliance Checklist
    print("\n" + "=" * 60)
    print("API Compliance Checklist")
    print("=" * 60)
    
    compliance_items = [
        ("HTTP POST method", "POST" in source),
        ("JSON Content-Type", "application/json" in source),
        ("Base64 audio decoding", "b64decode" in source),
        ("UUID for reqid", "uuid" in source.lower()),
        ("App ID in payload", '"appid"' in source),
        ("Token in payload", '"token"' in source),
        ("Cluster in payload", '"cluster"' in source),
        ("Voice type parameter", '"voice_type"' in source),
        ("Speed ratio support", "speed_ratio" in source),
        ("Volume ratio support", "volume_ratio" in source),
        ("Sample rate support", "sample_rate" in source),
        ("Encoding support", '"encoding"' in source),
        ("Operation=query", '"operation"' in source and '"query"' in source),
    ]
    
    for item_name, present in compliance_items:
        status = "✅" if present else "❌"
        print(f"{status} {item_name}")
    
    compliance_passed = sum(1 for _, p in compliance_items if p)
    print(f"\nCompliance: {compliance_passed}/{len(compliance_items)}")
    
    return passed_count == total_count


def main():
    success = check_doubao_backend()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All validation checks passed!")
        print("\nThe Doubao backend implementation appears to be")
        print("correctly aligned with the official API documentation.")
    else:
        print("⚠️  Some validation checks failed.")
        print("\nPlease review the implementation against:")
        print("https://www.volcengine.com/docs/6561/1257584")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
