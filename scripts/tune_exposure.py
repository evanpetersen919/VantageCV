"""
Interactive exposure tuning - find the perfect manual exposure value
This gives deterministic, consistent captures
"""
import requests
import sys

API_URL = "http://127.0.0.1:30010/remote"
DATACAP_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1"

def set_property(path, prop, value):
    payload = {"objectPath": path, "propertyName": prop, "propertyValue": value}
    response = requests.put(f"{API_URL}/object/property", json=payload)
    return response.status_code == 200

if len(sys.argv) < 2:
    print("\n" + "="*60)
    print("INTERACTIVE EXPOSURE TUNING")
    print("="*60)
    print("\nUsage: python tune_exposure.py <bias>")
    print("\nStart with 0, then adjust:")
    print("  python tune_exposure.py 0")
    print("  python tune_exposure.py -2  (darker)")
    print("  python tune_exposure.py 2   (brighter)")
    print("\nKeep testing until test_preview.png looks perfect!")
    print("\nCurrent recommendation: Start with -1.0")
    sys.exit(0)

bias = float(sys.argv[1])

print(f"\nSetting Manual Exposure: Bias = {bias}")

# Switch to Manual Exposure (deterministic)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessBlendWeight", 1.0)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureMethod", True)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.AutoExposureMethod", 0)  # Manual

set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureBias", True)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.AutoExposureBias", bias)

# Clean effects
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_BloomIntensity", True)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.BloomIntensity", 0.0)

print(f"✓ Manual Exposure set to {bias}")
print("\nCapturing test image...")

import subprocess
subprocess.run(["python", "scripts/preview_capture.py"])

print("\n" + "="*60)
print(f"CHECK: test_preview.png with Bias={bias}")
print("="*60)
print("\nToo dark? Try higher: python tune_exposure.py", bias + 1)
print("Too bright? Try lower: python tune_exposure.py", bias - 1)
print("\nOnce it looks PERFECT, that's your final value!")
