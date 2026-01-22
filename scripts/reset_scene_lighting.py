"""
Reset PostProcess, DirectionalLight, SkyLight, and Atmosphere to UE5 defaults
Removes all custom settings from these scene actors
"""
import requests

API_URL = "http://127.0.0.1:30010/remote"

def call_function(path, func_name):
    payload = {"objectPath": path, "functionName": func_name}
    response = requests.put(f"{API_URL}/object/call", json=payload)
    return response.status_code == 200

print("\n" + "="*60)
print("RESETTING SCENE LIGHTING TO UE5 DEFAULTS")
print("="*60 + "\n")

actors_to_reset = [
    "/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1",
    "/Game/automobileV2.automobileV2:PersistentLevel.DirectionalLight_4",
    "/Game/automobileV2.automobileV2:PersistentLevel.SkyLight_2",
    "/Game/automobileV2.automobileV2:PersistentLevel.SkyAtmosphere"
]

print("These actors will be reset to default settings:")
for actor in actors_to_reset:
    print(f"  - {actor.split('.')[-1]}")

print("\n⚠ WARNING: This will delete all custom lighting settings!")
print("You'll need to reconfigure lighting manually in UE5 after this.\n")

response = input("Type 'yes' to proceed: ")
if response.lower() != 'yes':
    print("Cancelled.")
    exit(0)

print("\nIn UE5, manually do this:")
print("\n1. Select PostProcessVolume_1 in World Outliner")
print("2. In Details, click the small arrow next to each overridden property")
print("3. Select 'Reset to Default'")
print("\n4. Select DirectionalLight_4")
print("5. Set Intensity to default (3.14159 or similar)")
print("\n6. Select SkyLight_2") 
print("7. Reset all overridden properties to default")
print("\n8. Select SkyAtmosphere")
print("9. Reset all overridden properties to default")

print("\n" + "="*60)
print("Manual reset required - no API available for this")
print("="*60)
print("\nAlternatively, you can delete these actors and re-add them:")
print("1. Delete the actors in UE5")
print("2. Add new default ones from Place Actors panel")
print("   - Lights > Directional Light")
print("   - Lights > Sky Light")
print("   - Visual Effects > Sky Atmosphere")
print("   - Volumes > Post Process Volume")
