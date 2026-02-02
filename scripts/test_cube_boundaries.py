"""
Investigate Cube components as potential boundary markers.
"""

import requests
import yaml

# Load config
with open("configs/levels/automobileV2_vehicles.yaml", "r") as f:
    config = yaml.safe_load(f)

level_path = config["level"]["path"]
base_url = "http://127.0.0.1:30010/remote"
session = requests.Session()


def get_component_location(component_path):
    """Get component world location."""
    try:
        response = session.put(
            f"{base_url}/object/call",
            json={
                "objectPath": component_path,
                "functionName": "K2_GetComponentLocation"
            },
            timeout=2.0
        )
        if response.status_code == 200:
            return response.json().get("ReturnValue")
    except:
        pass
    return None


def get_component_relative_location(component_path):
    """Get component relative location (to parent)."""
    try:
        response = session.put(
            f"{base_url}/object/call",
            json={
                "objectPath": component_path,
                "functionName": "GetRelativeLocation"
            },
            timeout=2.0
        )
        if response.status_code == 200:
            return response.json().get("ReturnValue")
    except:
        pass
    return None


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


# Get vehicles
vehicles = []
for category, vehicle_list in config.get("vehicles", {}).items():
    for v in vehicle_list:
        vehicles.append((v["name"], category))

print("=" * 70)
print("CUBE COMPONENT INVESTIGATION")
print("=" * 70)

# Check first 5 vehicles for cube components
for vehicle_name, category in vehicles[:8]:
    print(f"\n{vehicle_name} ({category}):")
    
    # Get vehicle location
    veh_loc = get_actor_location(vehicle_name)
    if veh_loc:
        print(f"  Vehicle Location: ({veh_loc['X']:.0f}, {veh_loc['Y']:.0f}, {veh_loc['Z']:.0f})")
    
    # Check for Cube components
    cube_names = ["Cube", "Cube0", "Cube1", "Cube2", "Cube3", "Cube4",
                  "Front", "Back", "Left", "Right"]
    
    for cube_name in cube_names:
        comp_path = f"{level_path}:PersistentLevel.{vehicle_name}.{cube_name}"
        
        # Try getting world location
        world_loc = get_component_location(comp_path)
        rel_loc = get_component_relative_location(comp_path)
        
        if world_loc or rel_loc:
            print(f"\n  Found: {cube_name}")
            if world_loc:
                print(f"    World: ({world_loc['X']:.0f}, {world_loc['Y']:.0f}, {world_loc['Z']:.0f})")
            if rel_loc:
                print(f"    Relative: ({rel_loc['X']:.0f}, {rel_loc['Y']:.0f}, {rel_loc['Z']:.0f})")
            
            # Calculate offset from vehicle
            if world_loc and veh_loc:
                dx = world_loc['X'] - veh_loc['X']
                dy = world_loc['Y'] - veh_loc['Y']
                dz = world_loc['Z'] - veh_loc['Z']
                print(f"    Offset: ({dx:.0f}, {dy:.0f}, {dz:.0f})")

print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)
print("\nIf Cube0-3 are boundary markers, they should have:")
print("  - Front: Positive X offset (front of vehicle)")
print("  - Back: Negative X offset (rear of vehicle)")
print("  - Left: Negative Y offset (left side)")
print("  - Right: Positive Y offset (right side)")
