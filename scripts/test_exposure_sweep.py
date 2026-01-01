"""Test different exposure bias values to find what makes images bright."""
import requests
import time
from PIL import Image
import numpy as np
import json

UE5_URL = "http://localhost:30010"
capture_path = "/Game/automobile.automobile:PersistentLevel.DataCapture_1"

# Test exposure bias values from 15 to 50
test_values = [15, 20, 25, 30, 40, 50]

print("=" * 70)
print("EXPOSURE BIAS SWEEP TEST")
print("=" * 70)
print(f"Testing bias values: {test_values}")
print(f"Target: Mean brightness > 120/255")
print("=" * 70)

results = []

for bias in test_values:
    print(f"\nTesting AutoExposureBias = {bias:.1f}...")
    
    # Capture frame
    try:
        resp = requests.put(
            f"{UE5_URL}/remote/object/call",
            json={
                "objectPath": capture_path,
                "functionName": "CaptureFrame"
            },
            timeout=15
        )
        
        if resp.status_code != 200:
            print(f"  ✗ Capture failed: {resp.status_code}")
            continue
            
        # Wait for file
        time.sleep(2)
        
        # Analyze
        img = Image.open('data/synthetic/test/images/frame_000000.png')
        arr = np.array(img)
        mean = arr.mean()
        
        results.append({"bias": bias, "brightness": mean})
        
        verdict = "✓ BRIGHT" if mean > 120 else ("⚠ MODERATE" if mean > 80 else "✗ DARK")
        print(f"  Brightness: {mean:.1f}/255 {verdict}")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")

print("\n" + "=" * 70)
print("RESULTS SUMMARY")
print("=" * 70)
for r in results:
    status = "✓" if r["brightness"] > 120 else ("⚠" if r["brightness"] > 80 else "✗")
    print(f"{status} Bias {r['bias']:5.1f} → Brightness {r['brightness']:6.1f}/255")

if results:
    best = max(results, key=lambda x: x["brightness"])
    print(f"\nBest: Bias={best['bias']} achieved {best['brightness']:.1f}/255")
    if best["brightness"] < 120:
        print(f"⚠ WARNING: Even maximum bias ({best['bias']}) only reached {best['brightness']:.1f}/255")
        print("⚠ This indicates SCENE LIGHTING is too dark, not just exposure settings!")
        print("⚠ Solution: Increase DirectionalLight intensity in UE5 editor (Details panel)")
