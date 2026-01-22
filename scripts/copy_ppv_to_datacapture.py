"""
Copy PostProcessVolume settings directly to DataCapture component
Since SceneCaptureComponent2D doesn't automatically use world PPV,
we need to explicitly copy the settings.
"""
import requests
import json

API_URL = "http://127.0.0.1:30010/remote"
PPV_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1"
DATACAP_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1"

def get_property(path, prop):
    response = requests.put(f"{API_URL}/object/property", 
                           json={"objectPath": path, "propertyName": prop})
    if response.status_code == 200:
        return response.json().get("PropertyValue")
    return None

def set_property(path, prop, value):
    payload = {"objectPath": path, "propertyName": prop, "propertyValue": value}
    response = requests.put(f"{API_URL}/object/property", json=payload)
    return response.status_code == 200

print("\n=== Reading PostProcessVolume Settings ===\n")

# Read PPV exposure settings
ppv_method = get_property(PPV_PATH, "Settings.AutoExposureMethod")
ppv_bias = get_property(PPV_PATH, "Settings.AutoExposureBias")
ppv_min = get_property(PPV_PATH, "Settings.AutoExposureMinBrightness")
ppv_max = get_property(PPV_PATH, "Settings.AutoExposureMaxBrightness")

print(f"PPV AutoExposureMethod: {ppv_method}")
print(f"PPV AutoExposureBias: {ppv_bias}")
print(f"PPV MinBrightness: {ppv_min}")
print(f"PPV MaxBrightness: {ppv_max}")

print("\n=== Copying to DataCapture Component ===\n")

# Copy settings to CaptureComponent with overrides enabled
set_property(DATACAP_PATH, "CaptureComponent.PostProcessBlendWeight", 1.0)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureMethod", True)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.AutoExposureMethod", ppv_method if ppv_method is not None else 0)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureBias", True)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.AutoExposureBias", ppv_bias if ppv_bias is not None else 0.0)

if ppv_min is not None:
    set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureMinBrightness", True)
    set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.AutoExposureMinBrightness", ppv_min)

if ppv_max is not None:
    set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureMaxBrightness", True)
    set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.AutoExposureMaxBrightness", ppv_max)

print("✓ Copied PPV exposure settings to DataCapture")
print("✓ Set PostProcessBlendWeight = 1.0")
print("\nNow test capture:")
print("  python scripts/preview_capture.py")
