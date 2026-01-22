"""Check viewport camera exposure settings"""
import requests
import json

API_URL = "http://127.0.0.1:30010/remote"

# Try to find PlayerCameraManager or viewport camera
cameras = [
    "/Game/automobileV2.automobileV2:PersistentLevel.CameraActor_0",
    "/Game/automobileV2.automobileV2:PersistentLevel.PlayerCameraManager",
]

def get_property(path, prop):
    response = requests.put(f"{API_URL}/object/property", 
                           json={"objectPath": path, "propertyName": prop})
    if response.status_code == 200:
        return response.json().get("PropertyValue")
    return None

print("\n=== Checking Scene ===\n")

# Check DataCapture camera
datacap_fov = get_property("/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1", "CaptureComponent.FOVAngle")
print(f"DataCapture FOV: {datacap_fov}")

# Check if there's exposure compensation in the scene
ppv_exposure_comp = get_property("/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1", "Settings.AutoExposureExposureCompensation")
print(f"PPV ExposureCompensation: {ppv_exposure_comp}")

# Check DirectionalLight intensity
light_intensity = get_property("/Game/automobileV2.automobileV2:PersistentLevel.DirectionalLight", "Intensity")
print(f"DirectionalLight Intensity: {light_intensity}")

print("\n=== DIAGNOSIS ===")
print("If viewport looks GOOD but capture is WHITE:")
print("  → Viewport is using different exposure than DataCapture")
print("  → Check: Window > Developer Tools > Show Flags")
print("  → Look for 'Eye Adaptation' or 'Auto Exposure' enabled in viewport")
print("\nIf BOTH viewport and capture are WHITE:")
print("  → Scene lighting is too bright")
print("  → Lower DirectionalLight intensity")
print("  → Or add negative exposure bias to PPV")
