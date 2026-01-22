"""
Disable auto-exposure and eye adaptation permanently
Sets PostProcessVolume to Manual exposure with fixed EV
"""
import requests
import json

API_URL = "http://127.0.0.1:30010/remote"
PPV_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1"
DATACAP_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1"

def set_property(path, prop, value):
    payload = {"objectPath": path, "propertyName": prop, "propertyValue": value}
    response = requests.put(f"{API_URL}/object/property", json=payload)
    return response.status_code == 200

print("\n=== Disabling Auto-Exposure Permanently ===\n")

# PostProcessVolume: Manual exposure, negative bias to darken
print("Setting PostProcessVolume...")
set_property(PPV_PATH, "Settings.bOverride_AutoExposureMethod", True)
set_property(PPV_PATH, "Settings.AutoExposureMethod", 0)  # 0 = Manual
set_property(PPV_PATH, "Settings.bOverride_AutoExposureBias", True)
set_property(PPV_PATH, "Settings.AutoExposureBias", -3.0)  # Darker exposure
set_property(PPV_PATH, "Settings.bOverride_BloomIntensity", True)
set_property(PPV_PATH, "Settings.BloomIntensity", 0.0)  # No bloom

print("✓ PPV: Manual exposure, Bias=-3.0, Bloom=OFF")

# DataCapture: Copy settings with BlendWeight=1.0
print("\nSetting DataCapture component...")
set_property(DATACAP_PATH, "CaptureComponent.PostProcessBlendWeight", 1.0)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureMethod", True)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.AutoExposureMethod", 0)  # Manual
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureBias", True)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.AutoExposureBias", -3.0)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_BloomIntensity", True)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.BloomIntensity", 0.0)

print("✓ DataCapture: BlendWeight=1.0, Manual exposure, Bias=-3.0")

print("\n=== DONE ===")
print("Auto-exposure DISABLED, Manual exposure with EV=-3.0")
print("\nCheck viewport - it should be darker now.")
print("Test capture: python scripts/preview_capture.py")
print("\nIf still too bright/dark, adjust bias:")
print("  -1.0 = slightly darker")
print("  -3.0 = much darker")
print("  -5.0 = very dark")
