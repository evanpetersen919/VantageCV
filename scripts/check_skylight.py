"""
Check and adjust SkyLight intensity
SkyLight can cause meshes to be overbright even with correct DirectionalLight
"""
import requests

API_URL = "http://127.0.0.1:30010/remote"
SKYLIGHT_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.SkyLight"

def call_function(func_name, params={}):
    payload = {
        "objectPath": SKYLIGHT_PATH,
        "functionName": func_name,
        "parameters": params
    }
    response = requests.put(f"{API_URL}/object/call", json=payload)
    return response.status_code == 200

print("\n=== SkyLight Instructions ===\n")
print("In UE5:")
print("1. Find 'SkyLight' in World Outliner")
print("2. In Details panel, find 'Intensity'")
print("3. Current value is probably 1.0")
print("4. Try setting to 0.1 (10x dimmer)")
print("5. Check if meshes get darker")
print("\nAlso check:")
print("- Intensity Scale: should be 1.0")
print("- Light Color: should be white (1,1,1)")
print("\nThen test: python scripts/preview_capture.py")
