"""Check and fix PostProcessVolume exposure settings"""
import requests
import json

API_URL = "http://127.0.0.1:30010/remote"
PPV_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1"

def get_property(prop):
    response = requests.put(f"{API_URL}/object/property", 
                           json={"objectPath": PPV_PATH, "propertyName": prop})
    if response.status_code == 200:
        return response.json().get("PropertyValue")
    return None

def set_property(prop, value):
    payload = {
        "objectPath": PPV_PATH,
        "propertyName": prop,
        "propertyValue": value
    }
    response = requests.put(f"{API_URL}/object/property", json=payload)
    return response.status_code == 200

print("\n=== Current PostProcessVolume Exposure ===\n")
method = get_property("Settings.AutoExposureMethod")
bias = get_property("Settings.AutoExposureBias")
override_method = get_property("Settings.bOverride_AutoExposureMethod")
override_bias = get_property("Settings.bOverride_AutoExposureBias")

print(f"AutoExposureMethod: {method} (0=Manual, 1=Auto Histogram)")
print(f"AutoExposureBias: {bias}")
print(f"Override Method: {override_method}")
print(f"Override Bias: {override_bias}")

print("\n=== Setting Manual Exposure (EV100 = 0) ===\n")

# Set to Manual exposure with no bias
set_property("Settings.bOverride_AutoExposureMethod", True)
set_property("Settings.AutoExposureMethod", 0)  # Manual
set_property("Settings.bOverride_AutoExposureBias", True)
set_property("Settings.AutoExposureBias", 0.0)  # No bias

print("✓ Set PostProcessVolume to Manual Exposure, EV100=0")
print("\nNow test capture again:")
print("  python scripts/preview_capture.py")
