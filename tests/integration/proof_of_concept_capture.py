"""
Proof-of-Concept: Capture screenshot from UE5 via VantageCV C++ Plugin
Uses Remote Control API to call VantageCVSubsystem (research-grade approach)
"""

import requests
import time
from pathlib import Path

# Configuration
UE5_HOST = "localhost"
UE5_PORT = 30010
OUTPUT_FILE = "F:/Unreal Editor/VantageCV_Project/Saved/Screenshots/test_capture.png"

def call_subsystem_function(function_name: str):
    """Call a function on the VantageCV Engine Subsystem via Remote Control API."""
    url = f"http://{UE5_HOST}:{UE5_PORT}/remote/object/call"
    
    # Engine Subsystems are accessible via this path
    payload = {
        "objectPath": "/Script/VantageCV.Default__VantageCVSubsystem",
        "functionName": function_name,
        "parameters": {},
        "generateTransaction": False
    }
    
    print(f"Calling {function_name}() on VantageCVSubsystem...")
    
    try:
        response = requests.put(url, json=payload, timeout=10)
        print(f"Status: {response.status_code}")
        if response.text:
            print(f"Response: {response.text[:500]}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def capture_frame():
    """Capture frame using VantageCV Engine Subsystem."""
    print("=" * 60)
    print("VantageCV - Research-Grade Screenshot Capture")
    print("Using Engine Subsystem + Remote Control API")
    print("=" * 60)
    
    print(f"\n1. Architecture:")
    print(f"   Python → Remote Control API → Engine Subsystem → DataCapture Actor")
    print(f"   This is production-grade synthetic data generation")
    
    print(f"\n2. Output Location:")
    print(f"   {OUTPUT_FILE}")
    
    print(f"\n3. Calling CaptureFrame() on VantageCVSubsystem...")
    success = call_subsystem_function("CaptureFrame")
    
    if success:
        print("\n   ✓ CaptureFrame() executed!")
        print("\n   C++ Pipeline:")
        print("     1. Subsystem locates DataCapture actor (TActorIterator)")
        print("     2. Calls DataCapture.CaptureFrame()")
        print("     3. Renders scene to texture (USceneCaptureComponent2D)")
        print("     4. Async PNG compression (IImageWrapper)")
        print("     5. Saves to disk (background thread)")
        print(f"\n   Check output: {OUTPUT_FILE}")
        print("\n   Check UE5 Output Log for 'LogVantageCVSubsystem' messages")
    else:
        print("\n   Note: Plugin needs to be recompiled with VantageCVSubsystem")
        print("   Close UE5, reopen, allow rebuild")
    
    print("\n" + "=" * 60)
    print("This architecture enables:")
    print("  • Batch dataset generation")
    print("  • Domain randomization")
    print("  • Automated annotation")
    print("  • Production ML pipelines")
    print("=" * 60)
    
    return success

if __name__ == "__main__":
    capture_frame()
