#!/usr/bin/env python3
"""Check ALL cars, trucks, and buses have front and back boundaries."""

import sys
sys.path.insert(0, ".")

import requests

BASE_URL = "http://127.0.0.1:30010/remote"
LEVEL_PATH = "/Game/automobileV2.automobileV2"

# Vehicle pool X coordinates
POOL_X = {
    0: "car",
    1000: "bus", 
    4000: "truck"
}

session = requests.Session()

from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker
checker = VehicleSpacingChecker()

print("Checking ALL cars, trucks, and buses for front/back boundaries...\n")

vehicles_by_category = {"car": [], "bus": [], "truck": []}
missing_boundaries = []

# Find all vehicles in pool
for i in range(1, 300):
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
    
    # Check if this is a car, bus, or truck
    category = None
    for pool_x, cat in POOL_X.items():
        if abs(x - pool_x) < 1.0:
            category = cat
            break
    
    if category:
        vehicles_by_category[category].append(name)

# Check each vehicle for boundaries
all_good = True

for category in ["car", "bus", "truck"]:
    vehicles = vehicles_by_category[category]
    print(f"=== {category.upper()} ({len(vehicles)} vehicles) ===")
    
    for actor in vehicles:
        offsets = checker._get_cube_component_offsets(actor)
        
        # Check if we have front and back (positive and negative X offsets)
        has_front = False
        has_back = False
        front_val = 0
        back_val = 0
        
        for name, off in offsets.items():
            if off["X"] > 50:  # Front (positive X)
                has_front = True
                front_val = off["X"]
            elif off["X"] < -50:  # Back (negative X)
                has_back = True
                back_val = off["X"]
        
        if has_front and has_back:
            length = front_val - back_val
            print(f"  ✓ {actor}: front={front_val:.0f}cm, back={back_val:.0f}cm (length={length:.0f}cm)")
        else:
            all_good = False
            issue = []
            if not has_front:
                issue.append("NO FRONT")
            if not has_back:
                issue.append("NO BACK")
            print(f"  ✗ {actor}: {', '.join(issue)} - found offsets: {offsets}")
            missing_boundaries.append((category, actor))
    
    print()

print("=" * 60)
if all_good:
    print("✓ ALL VEHICLES HAVE FRONT AND BACK BOUNDARIES - READY TO TEST!")
else:
    print(f"✗ {len(missing_boundaries)} VEHICLES MISSING BOUNDARIES:")
    for cat, actor in missing_boundaries:
        print(f"  - {actor} ({cat})")
    print("\nNOT READY TO TEST - Fix missing boundaries first!")
