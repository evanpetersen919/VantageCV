#!/usr/bin/env python3
"""Search for ALL components on bus/truck/car actors."""

import requests

BASE_URL = "http://127.0.0.1:30010/remote"
LEVEL_PATH = "/Game/automobileV2.automobileV2"

session = requests.Session()

# Vehicle pool X coordinates
POOL_X = {
    0: "car",
    1000: "bus", 
    2000: "motorcycle",
    3000: "bicycle",
    4000: "truck"
}

print("Searching for cube components on vehicles...\n")

# Check a range of possible component names
POSSIBLE_CUBE_NAMES = [
    "Cube", "Cube0", "Cube1", "Cube2", "Cube3", "Cube4", "Cube5",
    "cube", "cube0", "cube1", "cube2", "cube3", "cube4",
    "Box", "Box0", "Box1", "Box2", "Box3", "Box4",
    "Boundary", "Boundary0", "Boundary1", "Boundary2",
    "Front", "Back", "Left", "Right",
    "FrontBoundary", "BackBoundary", "LeftBoundary", "RightBoundary",
    "Collision", "Collision0", "Collision1",
    "SM_Cube", "SM_Box",
    "StaticMeshComponent0", "StaticMeshComponent1", "StaticMeshComponent2",
]

for i in range(1, 100):
    name = f"StaticMeshActor_{i}"
    path = f"{LEVEL_PATH}:PersistentLevel.{name}"
    
    resp = session.put(
        f"{BASE_URL}/object/call",
        json={"objectPath": path, "functionName": "K2_GetActorLocation"},
        timeout=2.0
    )
    if resp.status_code != 200:
        continue
    
    loc = resp.json().get("ReturnValue", {})
    x = loc.get("X", -1)
    y = loc.get("Y", 0)
    
    # Check if this is a car, bus, or truck
    category = None
    for pool_x, cat in POOL_X.items():
        if abs(x - pool_x) < 1.0:
            category = cat
            break
    
    if category not in ["car", "bus", "truck"]:
        continue
    
    # Search for any cube-like components
    found_components = []
    for comp_name in POSSIBLE_CUBE_NAMES:
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
                found_components.append((comp_name, dx, dy))
    
    if found_components or category == "bus":  # Always print buses
        print(f"{name} ({category} at X={x:.0f}):")
        if found_components:
            for comp, dx, dy in found_components:
                print(f"  {comp}: offset ({dx:.0f}, {dy:.0f})")
        else:
            print("  NO COMPONENTS FOUND with tested names")
        print()
