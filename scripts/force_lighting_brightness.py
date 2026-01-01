"""Force DirectionalLight to maximum brightness via Component API."""
import requests

UE5_URL = "http://localhost:30010"

# Force DirectionalLight_4 to EXTREME brightness
light_path = "/Game/automobile.automobile:PersistentLevel.DirectionalLight_4"

print("Forcing DirectionalLight_4 to MAXIMUM brightness...")
print("=" * 60)

# Call SetIntensity on the DirectionalLightComponent
resp = requests.put(
    f"{UE5_URL}/remote/object/call",
    json={
        "objectPath": light_path,
        "functionName": "SetIntensity",
        "parameters": {
            "NewIntensity": 100.0  # EXTREME - 10x normal max
        }
    }
)
print(f"SetIntensity(100.0): {resp.status_code} - {resp.json()}")

# Set pure white color
resp = requests.put(
    f"{UE5_URL}/remote/object/call",
    json={
        "objectPath": light_path,
        "functionName": "SetLightColor",
        "parameters": {
            "NewLightColor": {"R": 255, "G": 255, "B": 255, "A": 255}
        }
    }
)
print(f"SetLightColor(White): {resp.status_code} - {resp.json()}")

print("=" * 60)
print("DirectionalLight forced to intensity 100.0 (extreme)")
print("Now test capture to see if this fixes the darkness.")
