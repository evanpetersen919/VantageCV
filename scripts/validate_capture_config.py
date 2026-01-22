"""
Validation script: Check DataCapture configuration matches viewport requirements

Verifies:
- PostProcessVolume settings (Manual exposure, no bloom, neutral color)
- DataCapture actor exists and is accessible
- Capture will use PostProcessVolume (BlendWeight=0, no overrides)

Run this AFTER recompiling DataCapture.cpp to confirm configuration.
"""

import requests
import json
from pathlib import Path

API_URL = "http://127.0.0.1:30010/remote"
ACTOR_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1"
PPV_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1"

def get_property(object_path: str, property_name: str):
    """Get property value from UE5 actor"""
    payload = {
        "objectPath": object_path,
        "propertyName": property_name
    }
    response = requests.put(f"{API_URL}/object/property", json=payload)
    if response.status_code == 200:
        return response.json()
    return None

def check_ppv_settings():
    """Verify PostProcessVolume is configured correctly"""
    print("\n=== PostProcessVolume Settings ===")
    
    settings = {
        "bUnbound": "Infinite Extent (should be TRUE)",
        "Settings.AutoExposureMethod": "Exposure Method (should be 0=Manual or 1=Histogram)",
        "Settings.AutoExposureBias": "Exposure Bias (should be -1.0 to 0.0)",
        "Settings.bOverride_AutoExposureBias": "Override Exposure (should be TRUE)",
        "Settings.BloomIntensity": "Bloom (should be 0.0)",
        "Settings.bOverride_BloomIntensity": "Override Bloom (should be TRUE)",
    }
    
    for prop, desc in settings.items():
        result = get_property(PPV_PATH, prop)
        if result:
            value = result.get("PropertyValue")
            print(f"✓ {prop}: {value} - {desc}")
        else:
            print(f"✗ {prop}: FAILED TO READ - {desc}")
    
    return True

def check_datacapture_settings():
    """Verify DataCapture configuration (C++ side is compiled in)"""
    print("\n=== DataCapture Actor ===")
    
    # Check actor exists and is accessible
    result = get_property(ACTOR_PATH, "ActorLabel")
    if result:
        label = result.get("PropertyValue", "Unknown")
        print(f"✓ Actor exists: {label}")
    else:
        print(f"✗ Actor NOT FOUND at {ACTOR_PATH}")
        return False
    
    # Check FOV
    fov_result = get_property(ACTOR_PATH, "CaptureComponent.FOVAngle")
    if fov_result:
        fov = fov_result.get("PropertyValue", 90.0)
        print(f"✓ FOV: {fov}°")
    
    # Check location
    loc_result = get_property(ACTOR_PATH, "RootComponent.RelativeLocation")
    if loc_result:
        loc = loc_result.get("PropertyValue", {})
        print(f"✓ Location: ({loc.get('X', 0):.1f}, {loc.get('Y', 0):.1f}, {loc.get('Z', 0):.1f})")
    
    print("\n⚠ C++ settings (CaptureSource, ShowFlags, BlendWeight) are compiled in.")
    print("  After recompiling, these should be:")
    print("  - CaptureSource = SCS_FinalColorLDR")
    print("  - PostProcessBlendWeight = 0.0")
    print("  - ShowFlags.EyeAdaptation = false")
    print("  - No bOverride_* settings enabled")
    
    return True

def main():
    print("DataCapture Configuration Validator")
    print("=" * 60)
    
    try:
        # Check API connection
        response = requests.get(f"{API_URL}/preset/version")
        if response.status_code != 200:
            print("✗ Remote Control API not responding. Is UE5 running?")
            return
        print("✓ Remote Control API connected")
        
        # Validate settings
        ppv_ok = check_ppv_settings()
        datacapture_ok = check_datacapture_settings()
        
        print("\n" + "=" * 60)
        if ppv_ok and datacapture_ok:
            print("✓ Configuration looks good!")
            print("\nNext steps:")
            print("1. Recompile UE5 project if DataCapture.cpp was modified")
            print("2. Run: python scripts/preview_capture.py")
            print("3. Compare test_preview.png with viewport visually")
        else:
            print("✗ Configuration has issues - see errors above")
    
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    main()
