#!/usr/bin/env python3
"""
Move an anchor to camera location so we can see it
"""
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

def move_to_camera():
    base_url = "http://127.0.0.1:30010/remote"
    level_path = "/Game/automobileV2.automobileV2"
    
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Get camera location
    camera_path = f"{level_path}:PersistentLevel.DataCapture_1"
    
    print("Getting camera location...")
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": camera_path,
            "functionName": "K2_GetActorLocation"
        },
        timeout=5.0
    )
    
    cam_loc = response.json().get("ReturnValue", {})
    print(f"Camera at: {cam_loc}")
    
    # Move anchor 200 units in front of camera
    test_loc = {
        "X": cam_loc.get("X", 0) + 200,
        "Y": cam_loc.get("Y", 0),
        "Z": cam_loc.get("Z", 0)
    }
    
    # Test with StaticMeshActor_4
    test_actor = "StaticMeshActor_4"
    actor_path = f"{level_path}:PersistentLevel.{test_actor}"
    
    print(f"\nMoving {test_actor} to: {test_loc}")
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": actor_path,
            "functionName": "K2_SetActorLocation",
            "parameters": {
                "NewLocation": test_loc,
                "bSweep": False,
                "bTeleport": True
            }
        },
        timeout=5.0
    )
    print(f"Status: {response.status_code}")
    
    # Make sure it's visible
    print(f"\nMaking {test_actor} visible...")
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": actor_path,
            "functionName": "SetActorHiddenInGame",
            "parameters": {"bNewHidden": False}
        },
        timeout=5.0
    )
    print(f"Status: {response.status_code}")
    
    # Scale it up so it's easier to see
    print(f"\nScaling up to 2.0...")
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": actor_path,
            "functionName": "SetActorScale3D",
            "parameters": {"NewScale3D": {"X": 2.0, "Y": 2.0, "Z": 2.0}}
        },
        timeout=5.0
    )
    print(f"Status: {response.status_code}")
    
    print("\n" + "=" * 60)
    print("Check UE5 viewport - should see a large sphere in front of camera!")
    input("Press Enter to reset...")
    
    # Reset scale
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": actor_path,
            "functionName": "SetActorScale3D",
            "parameters": {"NewScale3D": {"X": 0.2, "Y": 0.2, "Z": 0.2}}
        },
        timeout=5.0
    )

if __name__ == "__main__":
    move_to_camera()
