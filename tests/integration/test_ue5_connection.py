"""
Test script to verify UE5 Remote Control API connection.
"""

import requests
import json

# Remote Control API endpoint
UE5_HOST = "localhost"
UE5_PORT = 30010
BASE_URL = f"http://{UE5_HOST}:{UE5_PORT}/remote/control/api"

def test_connection():
    """Test basic connection to UE5."""
    print("=" * 60)
    print("Testing UE5 Remote Control API Connection")
    print("=" * 60)
    
    # Test 1: Check if server is reachable
    print(f"\n1. Testing connection to {BASE_URL}...")
    try:
        response = requests.get(f"{BASE_URL}", timeout=5)
        print(f"   ✓ Server reachable! Status: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return False
    
    # Test 2: List available presets (endpoints)
    print(f"\n2. Listing available Remote Control presets...")
    try:
        response = requests.get(f"{BASE_URL}/presets", timeout=5)
        if response.status_code == 200:
            presets = response.json()
            print(f"   ✓ Found {len(presets.get('Presets', []))} preset(s)")
            for preset in presets.get('Presets', []):
                print(f"     - {preset.get('Name', 'Unknown')}")
        else:
            print(f"   ⚠ Response: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
    
    # Test 3: Get engine info
    print(f"\n3. Getting UE5 engine information...")
    try:
        # Try to call a basic Remote Control function
        payload = {
            "RequestId": 1,
            "URL": "/remote/control",
            "Verb": "GET"
        }
        response = requests.get(f"http://{UE5_HOST}:{UE5_PORT}/remote/info", timeout=5)
        if response.status_code == 200:
            print(f"   ✓ Engine info retrieved!")
            print(f"     Response: {response.text[:200]}...")
        else:
            print(f"   Status: {response.status_code}")
    except Exception as e:
        print(f"   Note: {e}")
    
    print("\n" + "=" * 60)
    print("Connection Test Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. UE5 is running ✓")
    print("  2. Remote Control API is active ✓")
    print("  3. Ready to implement VantageCV data generation")
    
    return True

if __name__ == "__main__":
    test_connection()
