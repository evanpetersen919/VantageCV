"""Quick preview capture to see what DataCapture will output."""

import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:30010/remote"
DATACAPTURE = "/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1"

# Capture test image
output_path = str(Path("test_preview.png").resolve())

print("Capturing preview image...")
print(f"Output: {output_path}")

response = requests.put(
    f"{BASE_URL}/object/call",
    json={
        "objectPath": DATACAPTURE,
        "functionName": "CaptureFrame",
        "parameters": {
            "OutputPath": output_path,
            "Width": 1920,
            "Height": 1080
        }
    },
    timeout=10
)

if response.status_code == 200:
    result = response.json()
    if result.get("ReturnValue"):
        print(f"✓ Preview captured: {output_path}")
        print("\nOpening image...")
        import os
        os.system(f'start "{output_path}"')
    else:
        print("✗ Capture failed - check UE5 is running and level is loaded")
else:
    print(f"✗ API error: {response.status_code}")
