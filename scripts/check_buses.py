#!/usr/bin/env python3
"""Check bus cube components."""

import requests

BASE_URL = "http://127.0.0.1:30010/remote"
LEVEL_PATH = "/Game/automobileV2.automobileV2"

session = requests.Session()

# Known bus actors from pool detection - check all actors with "bus" in mesh
# First let's get all registered actors from the preset
# We'll check actors we know are buses from previous runs

# Actually, let's search for buses by checking mesh names
# From pool detection, buses have X > 3000 in pool area

# Test with known StaticMeshActor names - iterate through a range
for i in range(1, 100):
    name = f"StaticMeshActor_{i}"
    path = f"{LEVEL_PATH}:PersistentLevel.{name}"
    
    # Get mesh
    resp = session.put(
        f"{BASE_URL}/object/property",
        json={"objectPath": path, "propertyName": "StaticMeshComponent.StaticMesh"},
        timeout=2.0
    )
    if resp.status_code != 200:
        continue
    
    mesh = resp.json().get("StaticMeshComponent", {}).get("StaticMesh", "")
    if "bus" not in mesh.lower():
        continue
    
    print(f"\n=== {name} ===")
    print(f"  Mesh: {mesh}")
    
    # Get location/rotation
    loc_r = session.put(f"{BASE_URL}/object/call", json={"objectPath": path, "functionName": "K2_GetActorLocation"}, timeout=2.0)
    rot_r = session.put(f"{BASE_URL}/object/call", json={"objectPath": path, "functionName": "K2_GetActorRotation"}, timeout=2.0)
    loc = loc_r.json().get("ReturnValue", {})
    rot = rot_r.json().get("ReturnValue", {})
    print(f"  Location: ({loc.get('X', 0):.0f}, {loc.get('Y', 0):.0f})")
    print(f"  Rotation: Yaw={rot.get('Yaw', 0):.1f}")
    
    # Try cubes
    cubes = ["Cube", "Cube0", "Cube1", "Cube2", "Cube3", "Cube4"]
    found = []
    for c in cubes:
        cp = f"{LEVEL_PATH}:PersistentLevel.{name}.{c}"
        r = session.put(f"{BASE_URL}/object/call", json={"objectPath": cp, "functionName": "K2_GetComponentLocation"}, timeout=2.0)
        if r.status_code == 200:
            cl = r.json().get("ReturnValue")
            if cl:
                dx = cl["X"] - loc.get("X", 0)
                dy = cl["Y"] - loc.get("Y", 0)
                found.append((c, dx, dy))
    
    if found:
        print(f"  Found {len(found)} cube components:")
        for c, dx, dy in found:
            print(f"    {c}: world offset ({dx:.0f}, {dy:.0f})")
    else:
        print("  NO CUBE COMPONENTS!")
        # Get actor bounds for reference
        br = session.put(
            f"{BASE_URL}/object/call", 
            json={"objectPath": path, "functionName": "GetActorBounds", "parameters": {"bOnlyCollidingComponents": False}}, 
            timeout=2.0
        )
        if br.status_code == 200:
            res = br.json().get("ReturnValue", {})
            ext = res.get("BoxExtent", {})
            print(f"  GetActorBounds extent: X={ext.get('X', 0):.0f}, Y={ext.get('Y', 0):.0f}, Z={ext.get('Z', 0):.0f}")
