"""
Adjust DataCapture exposure bias interactively
Run this, adjust the bias value, then test capture
"""
import requests
import json
import sys

API_URL = "http://127.0.0.1:30010/remote"
DATACAP_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1"

def set_property(prop, value):
    payload = {"objectPath": DATACAP_PATH, "propertyName": prop, "propertyValue": value}
    response = requests.put(f"{API_URL}/object/property", json=payload)
    return response.status_code == 200

if len(sys.argv) < 2:
    print("\nUsage: python adjust_exposure.py <bias>")
    print("\nExamples:")
    print("  python adjust_exposure.py -5.0  (darker)")
    print("  python adjust_exposure.py -10.0 (much darker)")
    print("  python adjust_exposure.py -15.0 (very dark)")
    print("\nCurrent: -3.0 (too bright)")
    print("\nStart with -7.0 and adjust from there.")
    sys.exit(1)

bias = float(sys.argv[1])

print(f"\nSetting AutoExposureBias = {bias}...")
set_property("CaptureComponent.PostProcessBlendWeight", 1.0)
set_property("CaptureComponent.PostProcessSettings.bOverride_AutoExposureBias", True)
set_property("CaptureComponent.PostProcessSettings.AutoExposureBias", bias)

print(f"✓ Set exposure bias to {bias}")
print("\nNow test: python scripts/preview_capture.py")
print("\nAdjust bias until capture matches viewport:")
print("  Too bright → more negative (-7, -10, -15)")
print("  Too dark → less negative (-2, -1, 0)")
