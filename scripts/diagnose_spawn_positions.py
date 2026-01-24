"""
Diagnostic script to verify actual UE5 actor positions match expected centerline.
Spawns vehicles and queries their actual transforms from UE5.
"""

import sys
import random
sys.path.insert(0, r"F:\vscode\VantageCV")

from vantagecv.research_v2.vehicle_spawn_controller import VehicleSpawnController

def main():
    print("=" * 60)
    print("SPAWN POSITION DIAGNOSTIC")
    print("=" * 60)
    
    controller = VehicleSpawnController()
    
    # Get lanes from loaded config
    lanes = controller.anchor_config.get("lanes", {}).get("definitions", [])
    if not lanes:
        print("No lanes found in config!")
        return
    
    lane_1 = [l for l in lanes if l["id"] == "lane_1"]
    if not lane_1:
        print(f"lane_1 not found. Available: {[l['id'] for l in lanes]}")
        return
    lane_1 = lane_1[0]
    
    print(f"\nTarget Lane: {lane_1['id']}")
    print(f"  Start: {lane_1['start_position']}")
    print(f"  End: {lane_1['end_position']}")
    
    # Expected midpoint
    expected_x = (lane_1['start_position'][0] + lane_1['end_position'][0]) / 2
    expected_y = (lane_1['start_position'][1] + lane_1['end_position'][1]) / 2
    expected_z = (lane_1['start_position'][2] + lane_1['end_position'][2]) / 2
    
    print(f"\nExpected centerline midpoint (t=0.5):")
    print(f"  X={expected_x}, Y={expected_y}, Z={expected_z}")
    
    # Compute transform using the spawn logic
    transform = controller._compute_lane_transform(lane_1, 0.5)
    computed_loc = transform["location"]
    
    print(f"\nComputed spawn location:")
    print(f"  X={computed_loc['X']}, Y={computed_loc['Y']}, Z={computed_loc['Z']}")
    
    # Find first available car
    vehicles = controller.vehicle_config.get("vehicles", [])
    cars = [v for v in vehicles if v.get("category") == "car"]
    
    if not cars:
        print("\nNo cars in vehicle config!")
        return
    
    vehicle_name = cars[0]["name"]
    print(f"\nSpawning: {vehicle_name}")
    
    # Teleport vehicle
    rotation = {"Pitch": 0, "Yaw": 0, "Roll": 0}
    success = controller._teleport_actor(vehicle_name, computed_loc, rotation)
    
    if not success:
        print("  FAILED to teleport")
        return
    
    # Unhide
    controller._set_actor_hidden(vehicle_name, False)
    
    # Query actual position from UE5
    actual = controller._call_remote(vehicle_name, "K2_GetActorLocation")
    if not actual or "ReturnValue" not in actual:
        print("  FAILED to query actual position")
        return
    
    actual_loc = actual["ReturnValue"]
    print(f"\nActual UE5 position (queried back):")
    print(f"  X={actual_loc['X']}, Y={actual_loc['Y']}, Z={actual_loc['Z']}")
    
    # Calculate deviation
    dx = actual_loc['X'] - computed_loc['X']
    dy = actual_loc['Y'] - computed_loc['Y']
    dz = actual_loc['Z'] - computed_loc['Z']
    
    import math
    distance_cm = math.sqrt(dx*dx + dy*dy + dz*dz)
    
    print(f"\nDeviation from commanded position:")
    print(f"  ΔX={dx:.2f}, ΔY={dy:.2f}, ΔZ={dz:.2f}")
    print(f"  Distance: {distance_cm:.2f} cm")
    
    if distance_cm < 1.0:
        print("\n✅ Vehicle is AT the commanded position (< 1cm error)")
        print("   If vehicle looks offset, it's the mesh pivot point, not spawn logic!")
    else:
        print(f"\n⚠️ Vehicle moved {distance_cm:.2f}cm from commanded position")
        print("   This suggests UE5 teleport issue or collision correction")
    
    print(f"\nVehicle '{vehicle_name}' left spawned for visual inspection.")
    print("Check if the vehicle's CENTER sits on lane_1 centerline (Y=8845)")

if __name__ == "__main__":
    main()
