"""Check actual runtime settings on DataCapture component"""
import requests
import json

API_URL = "http://127.0.0.1:30010/remote"
DATACAP_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1"

def get_property(prop):
    response = requests.put(f"{API_URL}/object/property", 
                           json={"objectPath": DATACAP_PATH, "propertyName": prop})
    if response.status_code == 200:
        return response.json().get("PropertyValue")
    return None

print("\n=== DataCapture Component Runtime Settings ===\n")

blend = get_property("CaptureComponent.PostProcessBlendWeight")
method_override = get_property("CaptureComponent.PostProcessSettings.bOverride_AutoExposureMethod")
method = get_property("CaptureComponent.PostProcessSettings.AutoExposureMethod")
bias_override = get_property("CaptureComponent.PostProcessSettings.bOverride_AutoExposureBias")
bias = get_property("CaptureComponent.PostProcessSettings.AutoExposureBias")

print(f"PostProcessBlendWeight: {blend}")
print(f"bOverride_AutoExposureMethod: {method_override}")
print(f"AutoExposureMethod: {method}")
print(f"bOverride_AutoExposureBias: {bias_override}")
print(f"AutoExposureBias: {bias}")

print("\n=== DIAGNOSIS ===")
if blend == 1.0 and method_override and bias is not None:
    print(f"✓ C++ settings applied: Manual exposure, Bias={bias}")
    if bias > -1.0:
        print("⚠ Bias too high (not dark enough), should be -3.0 or lower")
else:
    print("✗ C++ settings NOT applied - Python API may be overriding")
    print("  BlendWeight should be 1.0")
    print("  bOverride_AutoExposureMethod should be True")
