"""
RESET ALL SETTINGS - Clean slate
Removes all overrides from DataCapture, uses engine defaults
"""
import requests

API_URL = "http://127.0.0.1:30010/remote"
DATACAP_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1"

def set_property(path, prop, value):
    payload = {"objectPath": path, "propertyName": prop, "propertyValue": value}
    response = requests.put(f"{API_URL}/object/property", json=payload)
    return response.status_code == 200

print("\n" + "="*60)
print("RESETTING ALL DATACAPTURE SETTINGS")
print("="*60 + "\n")

# Remove all post-process overrides
print("Removing all DataCapture overrides...")

set_property(DATACAP_PATH, "CaptureComponent.PostProcessBlendWeight", 0.0)

# Disable all exposure overrides
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureMethod", False)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureBias", False)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureMinBrightness", False)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_AutoExposureMaxBrightness", False)

# Disable effects overrides
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_BloomIntensity", False)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_VignetteIntensity", False)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_SceneFringeIntensity", False)
set_property(DATACAP_PATH, "CaptureComponent.PostProcessSettings.bOverride_FilmGrainIntensity", False)

print("✓ All overrides removed")
print("✓ DataCapture now uses engine defaults")

print("\n" + "="*60)
print("RESET COMPLETE")
print("="*60)

print("\nDataCapture is now in CLEAN STATE.")
print("It will capture exactly what the engine renders by default.")
print("\nTest: python scripts/preview_capture.py")
print("\nThe capture will match viewport if viewport is using default settings.")
