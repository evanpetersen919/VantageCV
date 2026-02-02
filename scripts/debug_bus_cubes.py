#!/usr/bin/env python3
"""Debug script to check bus cube components."""

import requests

BASE_URL = "http://127.0.0.1:30010/remote"
LEVEL_PATH = "/Game/automobileV2.automobileV2"

def main():
    session = requests.Session()
    
    # Get all actors
    response = session.put(
        f"{BASE_URL}/object/call",
        json={
            "objectPath": LEVEL_PATH,
            "functionName": "K2_GetActorOfClass",
            "parameters": {"ActorClass": "/Script/Engine.StaticMeshActor"}
        },
        timeout=5.0
    )
    
    # Get actors
    actors_resp = session.get(
        f"{BASE_URL}/preset/automobileV2/property/GetAllRegisteredActors",
        timeout=5.0
    )
    
    if actors_resp.status_code != 200:
        print("Failed to get actors")
        return
    
    actors = [a.get("DisplayName", "") for a in actors_resp.json().get("PropertyValues", [])]
    
    # Find buses
    bus_actors = []
    for name in actors:
        path = f"{LEVEL_PATH}:PersistentLevel.{name}"
        try:
            resp = session.put(
                f"{BASE_URL}/object/property",
                json={"objectPath": path, "propertyName": "StaticMeshComponent.StaticMesh"},
                timeout=2.0
            )
            if resp.status_code == 200:
                mesh = resp.json().get("StaticMeshComponent", {}).get("StaticMesh", "")
                if "bus" in mesh.lower():
                    bus_actors.append((name, mesh))
        except:
            continue
    
    print(f"Found {len(bus_actors)} buses:")
    for name, mesh in bus_actors:
        print(f"\n=== {name} ===")
        print(f"  Mesh: {mesh}")
        
        # Get location and rotation
        path = f"{LEVEL_PATH}:PersistentLevel.{name}"
        
        loc_resp = session.put(
            f"{BASE_URL}/object/call",
            json={"objectPath": path, "functionName": "K2_GetActorLocation"},
            timeout=2.0
        )
        rot_resp = session.put(
            f"{BASE_URL}/object/call",
            json={"objectPath": path, "functionName": "K2_GetActorRotation"},
            timeout=2.0
        )
        
        loc = loc_resp.json().get("ReturnValue", {}) if loc_resp.status_code == 200 else {}
        rot = rot_resp.json().get("ReturnValue", {}) if rot_resp.status_code == 200 else {}
        
        print(f"  Location: ({loc.get('X', 0):.0f}, {loc.get('Y', 0):.0f}, {loc.get('Z', 0):.0f})")
        print(f"  Rotation: Yaw={rot.get('Yaw', 0):.1f}°")
        
        # Check for cube components
        cube_names = ["Cube", "Cube0", "Cube1", "Cube2", "Cube3", "Cube4", "Cube5"]
        found_cubes = []
        
        for cube_name in cube_names:
            comp_path = f"{LEVEL_PATH}:PersistentLevel.{name}.{cube_name}"
            try:
                resp = session.put(
                    f"{BASE_URL}/object/call",
                    json={"objectPath": comp_path, "functionName": "K2_GetComponentLocation"},
                    timeout=2.0
                )
                if resp.status_code == 200:
                    cube_loc = resp.json().get("ReturnValue")
                    if cube_loc:
                        found_cubes.append((cube_name, cube_loc))
            except:
                continue
        
        if found_cubes:
            print(f"  Found {len(found_cubes)} cube components:")
            for cname, cloc in found_cubes:
                offset_x = cloc["X"] - loc.get("X", 0)
                offset_y = cloc["Y"] - loc.get("Y", 0)
                offset_z = cloc["Z"] - loc.get("Z", 0)
                print(f"    {cname}: offset ({offset_x:.0f}, {offset_y:.0f}, {offset_z:.0f})")
        else:
            print("  NO CUBE COMPONENTS FOUND!")
            
            # Try to get actor bounds as fallback info
            bounds_resp = session.put(
                f"{BASE_URL}/object/call",
                json={"objectPath": path, "functionName": "GetActorBounds", "parameters": {"bOnlyCollidingComponents": False}},
                timeout=2.0
            )
            if bounds_resp.status_code == 200:
                result = bounds_resp.json().get("ReturnValue", {})
                origin = result.get("Origin", {})
                extent = result.get("BoxExtent", {})
                print(f"  GetActorBounds:")
                print(f"    Origin: ({origin.get('X', 0):.0f}, {origin.get('Y', 0):.0f}, {origin.get('Z', 0):.0f})")
                print(f"    Extent: ({extent.get('X', 0):.0f}, {extent.get('Y', 0):.0f}, {extent.get('Z', 0):.0f})")

if __name__ == "__main__":
    main()
