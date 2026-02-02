#!/usr/bin/env python3
"""Deep search for cube components on a specific bus actor."""

import requests

BASE_URL = "http://127.0.0.1:30010/remote"
LEVEL_PATH = "/Game/automobileV2.automobileV2"
session = requests.Session()

# Check a bus actor
name = "StaticMeshActor_7"  # A bus at X=1000
path = f"{LEVEL_PATH}:PersistentLevel.{name}"

loc_r = session.put(f"{BASE_URL}/object/call", json={"objectPath": path, "functionName": "K2_GetActorLocation"}, timeout=2.0)
loc = loc_r.json().get("ReturnValue", {})
x, y = loc.get("X", 0), loc.get("Y", 0)
print(f"{name} (bus) at ({x:.0f}, {y:.0f})")
print()

# Try many different component name patterns
prefixes = ["Cube", "cube", "Box", "box", "Bound", "bound", "Collision", "collision", "SM_Cube", "SM_Box"]
found_any = False

for prefix in prefixes:
    # Try base name and numbered variants
    for n in range(-1, 30):
        if n == -1:
            comp_name = prefix
        else:
            comp_name = f"{prefix}{n}"
        
        cp = f"{LEVEL_PATH}:PersistentLevel.{name}.{comp_name}"
        r = session.put(
            f"{BASE_URL}/object/call",
            json={"objectPath": cp, "functionName": "K2_GetComponentLocation"},
            timeout=1.0
        )
        if r.status_code == 200:
            cl = r.json().get("ReturnValue")
            if cl:
                dx = cl["X"] - x
                dy = cl["Y"] - y
                print(f"  FOUND: {comp_name} at offset ({dx:.0f}, {dy:.0f})")
                found_any = True

if not found_any:
    print("  No cube/box components found on this bus!")
    print()
    print("Let me try to get all components...")
    
    # Try GetComponentsByClass
    r = session.put(
        f"{BASE_URL}/object/call",
        json={
            "objectPath": path,
            "functionName": "GetComponentsByClass",
            "parameters": {"ComponentClass": "/Script/Engine.StaticMeshComponent"}
        },
        timeout=2.0
    )
    if r.status_code == 200:
        result = r.json()
        print(f"GetComponentsByClass result: {result}")
