#!/usr/bin/env python3
"""Find buses in pool and check their cube components."""

import requests

BASE_URL = "http://127.0.0.1:30010/remote"
LEVEL_PATH = "/Game/automobileV2.automobileV2"

session = requests.Session()

print("Looking for buses (X=1000 in pool)...")

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
    y = loc.get("Y", 0)
    
    # Bus at X=1000
    if abs(x - 1000) < 1.0:
        print(f"\n{name} (bus):")
        
        rot_r = session.put(
            f"{BASE_URL}/object/call",
            json={"objectPath": path, "functionName": "K2_GetActorRotation"},
            timeout=2.0
        )
        rot = rot_r.json().get("ReturnValue", {})
        yaw = rot.get("Yaw", 0)
        print(f"  Location: ({x:.0f}, {y:.0f}), Yaw={yaw:.1f}")
        
        # Check for cubes
        cubes = ["Cube", "Cube0", "Cube1", "Cube2", "Cube3", "Cube4"]
        found = []
        for c in cubes:
            cp = f"{LEVEL_PATH}:PersistentLevel.{name}.{c}"
            r = session.put(
                f"{BASE_URL}/object/call",
                json={"objectPath": cp, "functionName": "K2_GetComponentLocation"},
                timeout=2.0
            )
            if r.status_code == 200:
                cl = r.json().get("ReturnValue")
                if cl:
                    dx = cl["X"] - x
                    dy = cl["Y"] - y
                    found.append((c, dx, dy))
        
        if found:
            print(f"  Has {len(found)} cubes:")
            for c, dx, dy in found:
                print(f"    {c}: offset ({dx:.0f}, {dy:.0f})")
        else:
            print("  NO CUBES - uses default 1200cm length, 150cm half-width")
            # Show actual bounds
            br = session.put(
                f"{BASE_URL}/object/call",
                json={"objectPath": path, "functionName": "GetActorBounds", "parameters": {"bOnlyCollidingComponents": False}},
                timeout=2.0
            )
            if br.status_code == 200:
                res = br.json().get("ReturnValue", {})
                ext = res.get("BoxExtent", {})
                ex = ext.get("X", 0)
                ey = ext.get("Y", 0)
                print(f"  ActorBounds: length~{ex*2:.0f}cm, width~{ey*2:.0f}cm")
