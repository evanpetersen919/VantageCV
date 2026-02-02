"""
Debug script to find boundary mesh actors in the UE5 level.
"""

import requests
import sys
import yaml

# Load vehicle config to get vehicle names
with open("configs/levels/automobileV2_vehicles.yaml", "r") as f:
    config = yaml.safe_load(f)

level_path = config["level"]["path"]
base_url = "http://127.0.0.1:30010/remote"
session = requests.Session()


def get_all_actors():
    """Get all actors in the level."""
    try:
        response = session.put(
            f"{base_url}/object/call",
            json={
                "objectPath": "/Script/Engine.GameplayStatics",
                "functionName": "GetAllActorsOfClass",
                "parameters": {
                    "WorldContextObject": level_path,
                    "ActorClass": "/Script/Engine.Actor"
                }
            },
            timeout=10.0
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("ReturnValue", [])
    except Exception as e:
        print(f"Error: {e}")
    
    return []


def get_actor_location(actor_name):
    """Get actor location."""
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


# Get all vehicle names from config
vehicles = []
for category, vehicle_list in config.get("vehicles", {}).items():
    for v in vehicle_list:
        vehicles.append((v["name"], category))

print("=" * 60)
print("BOUNDARY MESH DETECTION")
print("=" * 60)

# For each vehicle, try to find boundary actors
boundary_patterns = ["_Front", "_Back", "_Left", "_Right", "_front", "_back", "_left", "_right",
                     "Front", "Back", "Left", "Right", "_Boundary", "_Bound", "_Box"]

found_boundaries = {}

for vehicle_name, category in vehicles[:5]:  # Test first 5
    print(f"\n{vehicle_name} ({category}):")
    
    # Get vehicle location
    veh_loc = get_actor_location(vehicle_name)
    if veh_loc:
        print(f"  Vehicle at: ({veh_loc['X']:.0f}, {veh_loc['Y']:.0f}, {veh_loc['Z']:.0f})")
    
    # Try each pattern
    for pattern in boundary_patterns:
        test_name = f"{vehicle_name}{pattern}"
        loc = get_actor_location(test_name)
        if loc:
            print(f"  FOUND: {test_name} at ({loc['X']:.0f}, {loc['Y']:.0f}, {loc['Z']:.0f})")
            if vehicle_name not in found_boundaries:
                found_boundaries[vehicle_name] = []
            found_boundaries[vehicle_name].append((pattern, loc))

print("\n" + "=" * 60)
print("SEARCHING FOR ANY ACTORS WITH 'BOUND' OR 'FRONT' IN NAME")
print("=" * 60)

# Get all actors and search for boundary-related names
all_actors = get_all_actors()
print(f"\nTotal actors found: {len(all_actors)}")

boundary_actors = []
for actor_path in all_actors:
    # Extract actor name from path
    if "." in str(actor_path):
        actor_name = str(actor_path).split(".")[-1]
    else:
        actor_name = str(actor_path)
    
    # Check for boundary-related keywords
    keywords = ["bound", "front", "back", "left", "right", "box", "collision", "extent"]
    if any(kw in actor_name.lower() for kw in keywords):
        boundary_actors.append(actor_name)

if boundary_actors:
    print("\nBoundary-related actors found:")
    for name in boundary_actors[:50]:
        print(f"  {name}")
else:
    print("\nNo boundary-related actors found by name search.")

print("\n" + "=" * 60)
print("CHECKING VEHICLE COMPONENT STRUCTURE")
print("=" * 60)

# Try to get components of a vehicle
test_vehicle = vehicles[0][0] if vehicles else None
if test_vehicle:
    print(f"\nChecking components of {test_vehicle}...")
    
    path = f"{level_path}:PersistentLevel.{test_vehicle}"
    try:
        # Try GetComponents
        response = session.put(
            f"{base_url}/object/call",
            json={
                "objectPath": path,
                "functionName": "GetComponents",
                "parameters": {
                    "ComponentClass": "/Script/Engine.SceneComponent"
                }
            },
            timeout=2.0
        )
        if response.status_code == 200:
            result = response.json()
            components = result.get("ReturnValue", [])
            print(f"  Components found: {len(components)}")
            for comp in components[:10]:
                print(f"    {comp}")
    except Exception as e:
        print(f"  GetComponents failed: {e}")
    
    # Try to get attached actors
    try:
        response = session.put(
            f"{base_url}/object/call",
            json={
                "objectPath": path,
                "functionName": "GetAttachedActors",
                "parameters": {}
            },
            timeout=2.0
        )
        if response.status_code == 200:
            result = response.json()
            attached = result.get("ReturnValue", [])
            print(f"  Attached actors: {len(attached)}")
            for att in attached:
                print(f"    {att}")
    except Exception as e:
        print(f"  GetAttachedActors failed: {e}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
