#!/usr/bin/env python3
"""Test spawning a vehicle to verify scale is preserved."""

import requests
import sys
import time
sys.path.insert(0, "f:/vscode/VantageCV")

UE5_BASE = "http://localhost:30010"

def call_function(actor_path: str, function: str, params: dict = None):
    """Call a function on a UE5 actor."""
    payload = {
        "objectPath": actor_path,
        "functionName": function,
        "parameters": params or {},
        "generateTransaction": False
    }
    resp = requests.put(f"{UE5_BASE}/remote/object/call", json=payload, timeout=5)
    return resp.json() if resp.ok else None

def get_actor_scale(actor_name: str) -> tuple:
    """Get current scale of an actor."""
    actor_path = f"/Game/automobile.automobile:PersistentLevel.{actor_name}"
    result = call_function(actor_path, "GetActorScale3D")
    if result:
        scale = result.get("ReturnValue", {})
        return scale.get("X", 1), scale.get("Y", 1), scale.get("Z", 1)
    return (1, 1, 1)

def set_visibility(actor_name: str, visible: bool):
    """Set actor visibility."""
    actor_path = f"/Game/automobile.automobile:PersistentLevel.{actor_name}"
    # Use SetActorHiddenInGame - note: True = hidden, False = visible
    call_function(actor_path, "SetActorHiddenInGame", {"bNewHidden": not visible})

def set_location(actor_name: str, x: float, y: float, z: float):
    """Set actor location."""
    actor_path = f"/Game/automobile.automobile:PersistentLevel.{actor_name}"
    call_function(actor_path, "K2_SetActorLocation", {
        "NewLocation": {"X": x, "Y": y, "Z": z},
        "bSweep": False,
        "bTeleport": True
    })

def main():
    # Test with a car
    test_actor = "StaticMeshActor_25"  # The truck with 0.035 scale
    
    print(f"Testing spawn cycle for {test_actor}")
    print("=" * 50)
    
    # Check initial scale
    scale_before = get_actor_scale(test_actor)
    print(f"Scale before: {scale_before}")
    
    # Simulate spawn sequence: show, move, then hide
    print("\nShowing actor...")
    set_visibility(test_actor, True)
    time.sleep(0.5)
    
    print("Moving actor to camera position...")
    # Position in front of DataCapture_1 (8047, 7926, 150) facing Yaw=0
    set_location(test_actor, 8047 + 1500, 7926, 150)  # 15m in front
    time.sleep(0.5)
    
    scale_during = get_actor_scale(test_actor)
    print(f"Scale after move: {scale_during}")
    
    print("\nHiding actor...")
    set_visibility(test_actor, False)
    time.sleep(0.5)
    
    scale_after = get_actor_scale(test_actor)
    print(f"Scale after hide: {scale_after}")
    
    # Check if scale was preserved
    print("\n" + "=" * 50)
    if abs(scale_before[0] - scale_after[0]) < 0.001:
        print("✓ Scale preserved throughout spawn cycle!")
    else:
        print("✗ Scale changed!")
        print(f"  Before: {scale_before}")
        print(f"  After:  {scale_after}")

if __name__ == "__main__":
    main()
