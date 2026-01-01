#!/usr/bin/env python3
"""
VantageCV - Direct Capture Test
================================
Simple test to verify UE5 capture is working with correct brightness.
Captures a single frame and displays brightness statistics.
"""

import requests
import time
from pathlib import Path

# UE5 Remote Control API settings
UE5_HOST = "http://localhost:30010"
OUTPUT_DIR = Path("data/synthetic/test")

def call_ue5(endpoint: str, body: dict = None):
    """Make a request to UE5 Remote Control API."""
    url = f"{UE5_HOST}{endpoint}"
    try:
        if body:
            resp = requests.put(url, json=body, timeout=10)
        else:
            resp = requests.get(url, timeout=10)
        return resp.status_code, resp.json() if resp.text else {}
    except Exception as e:
        return 0, {"error": str(e)}

def capture_test_image():
    """Capture a single test image and check brightness."""
    print("=" * 60)
    print("VantageCV Capture Test")
    print("=" * 60)
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Find DataCapture actor
    print("\n1. Finding DataCapture actor...")
    status, result = call_ue5("/remote/object/property", {
        "objectPath": "/Game/automobile.automobile:PersistentLevel.DataCapture_1",
        "propertyName": "RootComponent"
    })
    
    if status != 200:
        print(f"   ERROR: Could not find DataCapture actor (status {status})")
        print(f"   Response: {result}")
        return False
    
    print("   FOUND: DataCapture actor")
    
    # Set resolution
    print("\n2. Setting resolution to 1280x720...")
    status, result = call_ue5("/remote/object/call", {
        "objectPath": "/Game/automobile.automobile:PersistentLevel.DataCapture_1",
        "functionName": "SetResolution",
        "parameters": {
            "Width": 1280,
            "Height": 720
        }
    })
    print(f"   Status: {status}")
    
    # Capture frame
    output_path = str((OUTPUT_DIR / "brightness_test.png").absolute()).replace("\\", "/")
    print(f"\n3. Capturing frame to: {output_path}")
    
    status, result = call_ue5("/remote/object/call", {
        "objectPath": "/Game/automobile.automobile:PersistentLevel.DataCapture_1",
        "functionName": "CaptureFrame",
        "parameters": {
            "OutputPath": output_path,
            "Width": 1280,
            "Height": 720
        }
    })
    
    print(f"   Status: {status}")
    print(f"   Result: {result}")
    
    # Wait for file to be written
    time.sleep(1)
    
    # Check if file exists and analyze brightness
    output_file = OUTPUT_DIR / "brightness_test.png"
    if output_file.exists():
        file_size = output_file.stat().st_size
        print(f"\n4. Image saved successfully!")
        print(f"   File size: {file_size:,} bytes")
        
        # Try to analyze brightness with PIL
        try:
            from PIL import Image
            import numpy as np
            
            img = Image.open(output_file)
            img_array = np.array(img)
            
            # Calculate brightness statistics
            mean_brightness = img_array.mean()
            max_brightness = img_array.max()
            min_brightness = img_array.min()
            
            # Per-channel stats
            if len(img_array.shape) == 3:
                r_mean = img_array[:,:,0].mean()
                g_mean = img_array[:,:,1].mean()
                b_mean = img_array[:,:,2].mean()
                print(f"\n5. Brightness Analysis:")
                print(f"   Overall Mean: {mean_brightness:.1f} / 255")
                print(f"   Min: {min_brightness}, Max: {max_brightness}")
                print(f"   R: {r_mean:.1f}, G: {g_mean:.1f}, B: {b_mean:.1f}")
                
                # Brightness assessment
                if mean_brightness < 30:
                    print("\n   ❌ VERY DARK - Something is wrong!")
                elif mean_brightness < 60:
                    print("\n   ⚠️  DARK - May need exposure adjustment")
                elif mean_brightness < 180:
                    print("\n   ✅ GOOD - Normal brightness range")
                else:
                    print("\n   ⚠️  BRIGHT - May be overexposed")
            
        except ImportError:
            print("\n   (Install PIL for brightness analysis: pip install Pillow)")
        
        print(f"\n6. Opening image: {output_file}")
        import subprocess
        subprocess.run(["explorer", str(output_file)], shell=True)
        
        return True
    else:
        print(f"\n   ERROR: File was not created!")
        return False


if __name__ == "__main__":
    success = capture_test_image()
    print("\n" + "=" * 60)
    if success:
        print("Test completed. Check the opened image for brightness.")
    else:
        print("Test FAILED. Check UE5 is running with Remote Control enabled.")
    print("=" * 60)
