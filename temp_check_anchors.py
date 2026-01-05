#!/usr/bin/env python3
"""Check parking anchor rotations"""
import requests

parking_anchors = [
    "StaticMeshActor_15",
    "StaticMeshActor_14",
    "StaticMeshActor_16",
    "StaticMeshActor_17",
    "StaticMeshActor_21"
]

level_path = "/Game/automobileV2.automobileV2"

print("Parking anchor rotations:")
for name in parking_anchors:
    path = f"{level_path}:PersistentLevel.{name}"
    
    # Get location
    loc_resp = requests.put(
        "http://127.0.0.1:30010/remote/object/call",
        json={"objectPath": path, "functionName": "K2_GetActorLocation"}
    )
    loc = loc_resp.json().get("ReturnValue", {})
    
    # Get rotation
    rot_resp = requests.put(
        "http://127.0.0.1:30010/remote/object/call",
        json={"objectPath": path, "functionName": "K2_GetActorRotation"}
    )
    rot = rot_resp.json().get("ReturnValue", {})
    
    print(f"  {name}: Loc=({loc.get('X', 0):.0f}, {loc.get('Y', 0):.0f}) Yaw={rot.get('Yaw', 0):.1f}°")
