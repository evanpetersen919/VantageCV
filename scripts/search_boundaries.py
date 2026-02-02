"""
Comprehensive search for boundary-related actors in UE5 level.
Tries multiple patterns to find any boundary actors.
"""

import requests
import yaml

# Load config
with open("configs/levels/automobileV2_vehicles.yaml", "r") as f:
    config = yaml.safe_load(f)

level_path = config["level"]["path"]
base_url = "http://127.0.0.1:30010/remote"
session = requests.Session()


def get_actor_location(actor_name):
    """Get actor location - returns None if actor doesn't exist."""
    path = f"{level_path}:PersistentLevel.{actor_name}"
    try:
        response = session.put(
            f"{base_url}/object/call",
            json={
                "objectPath": path,
                "functionName": "K2_GetActorLocation"
            },
            timeout=2.0
        )
        if response.status_code == 200:
            return response.json().get("ReturnValue")
    except:
        pass
    return None


# Get all vehicles from config
vehicles = []
for category, vehicle_list in config.get("vehicles", {}).items():
    for v in vehicle_list:
        vehicles.append((v["name"], category))

print("=" * 70)
print("COMPREHENSIVE BOUNDARY ACTOR SEARCH")
print("=" * 70)

# Extended patterns to try
prefixes = ["", "BP_", "SM_"]
suffixes = [
    "_Front", "_Back", "_Left", "_Right",  # Standard
    "_front", "_back", "_left", "_right",  # Lowercase
    "Front", "Back", "Left", "Right",      # No underscore
    "_FrontBound", "_BackBound",           # With Bound
    "_F", "_B", "_L", "_R",                # Abbreviated
    "_Bounds", "_Boundary",                # Singular
    "_Box", "_Collision",                  # Collision-related
    "_1", "_2", "_3", "_4",                # Numbered
]

found = {}

for vehicle_name, category in vehicles:
    print(f"\n{vehicle_name} ({category}):")
    
    for prefix in prefixes:
        for suffix in suffixes:
            test_name = f"{prefix}{vehicle_name}{suffix}"
            loc = get_actor_location(test_name)
            if loc:
                print(f"  FOUND: {test_name}")
                print(f"         Location: ({loc['X']:.0f}, {loc['Y']:.0f}, {loc['Z']:.0f})")
                if vehicle_name not in found:
                    found[vehicle_name] = []
                found[vehicle_name].append(test_name)

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if found:
    print("\nBoundary actors found:")
    for veh, actors in found.items():
        print(f"  {veh}: {actors}")
else:
    print("\nNo boundary actors found with any tested pattern.")
    print("\nTo fix this, you can either:")
    print("1. Add boundary marker actors to vehicles in UE5")
    print("2. Store boundary offsets in a YAML config file")
    print("3. Use GetActorBounds to calculate boundaries dynamically")

print("\n" + "=" * 70)
print("ALTERNATIVE: Check for child components")
print("=" * 70)

# Try to get components/children for a vehicle
test_vehicle = vehicles[0][0]
path = f"{level_path}:PersistentLevel.{test_vehicle}"

print(f"\nQuerying components of {test_vehicle}...")

# Try GetComponentsByClass
try:
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": path,
            "functionName": "GetComponentsByClass",
            "parameters": {
                "ComponentClass": "/Script/Engine.StaticMeshComponent"
            }
        },
        timeout=2.0
    )
    if response.status_code == 200:
        result = response.json()
        components = result.get("ReturnValue", [])
        print(f"  StaticMeshComponents: {len(components)}")
        for comp in components[:5]:
            print(f"    {comp}")
except Exception as e:
    print(f"  GetComponentsByClass failed: {e}")

# Try to read actor labels/tags
try:
    # Get actor tags which might indicate boundary info
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": path,
            "functionName": "GetActorTags",
            "parameters": {}
        },
        timeout=2.0
    )
    if response.status_code == 200:
        result = response.json()
        tags = result.get("ReturnValue", [])
        print(f"  Actor Tags: {tags}")
except Exception as e:
    print(f"  GetActorTags: {e}")
