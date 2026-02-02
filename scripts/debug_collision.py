#!/usr/bin/env python3
"""Debug collision detection between bus and car."""

import sys
import math
sys.path.insert(0, ".")

from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker, VehicleBounds

checker = VehicleSpacingChecker()

# Simulate a bus at a lane position
bus_name = "StaticMeshActor_7"  # Bus with front=833, back=-837
bus_category = "bus"

# Cache the bus offsets first
checker._cache_boundary_offsets(bus_name, bus_category)
bus_offsets = checker.boundary_offsets[bus_name]
print(f"Bus offsets: front=({bus_offsets.front['X']:.0f}, {bus_offsets.front['Y']:.0f}), back=({bus_offsets.back['X']:.0f}, {bus_offsets.back['Y']:.0f})")

# Simulate bus spawned at a lane position facing Y+ direction (yaw=90)
bus_loc = {"X": 13145, "Y": 8500, "Z": 10}
bus_rot = {"Pitch": 0, "Yaw": 90, "Roll": 0}

bus_bounds = checker.get_vehicle_bounds(bus_name, bus_category, bus_loc, bus_rot, False)

print(f"\nBus at ({bus_loc['X']}, {bus_loc['Y']}) facing yaw={bus_rot['Yaw']}°:")
print(f"  Front boundary (world): ({bus_bounds.front_boundary['X']:.0f}, {bus_bounds.front_boundary['Y']:.0f})")
print(f"  Back boundary (world): ({bus_bounds.back_boundary['X']:.0f}, {bus_bounds.back_boundary['Y']:.0f})")

bus_corners = checker._get_vehicle_corners(bus_bounds)
print(f"  Corners: {[(int(x), int(y)) for x, y in bus_corners]}")

# Now simulate a car trying to spawn INSIDE the bus
car_name = "StaticMeshActor_19"  # Car with front=331, back=-339
car_category = "car"
checker._cache_boundary_offsets(car_name, car_category)

# Try spawning the car at the bus's center (should collide)
car_loc = {"X": 13145, "Y": 8500, "Z": 10}  # SAME as bus center!
car_rot = {"Pitch": 0, "Yaw": 90, "Roll": 0}

car_bounds = checker.get_vehicle_bounds(car_name, car_category, car_loc, car_rot, False)

print(f"\nCar at ({car_loc['X']}, {car_loc['Y']}) facing yaw={car_rot['Yaw']}° (INSIDE BUS):")
print(f"  Front boundary (world): ({car_bounds.front_boundary['X']:.0f}, {car_bounds.front_boundary['Y']:.0f})")
print(f"  Back boundary (world): ({car_bounds.back_boundary['X']:.0f}, {car_bounds.back_boundary['Y']:.0f})")

car_corners = checker._get_vehicle_corners(car_bounds)
print(f"  Corners: {[(int(x), int(y)) for x, y in car_corners]}")

# Check collision
collision = checker._check_collision(car_bounds, bus_bounds)
print(f"\n*** COLLISION DETECTED: {collision} ***")

if not collision:
    print("\nERROR: Car inside bus but NO collision detected!")
    print("Debugging SAT algorithm...")
    
    # Debug SAT
    axes = []
    
    # Car axes
    dx = car_bounds.front_boundary["X"] - car_bounds.back_boundary["X"]
    dy = car_bounds.front_boundary["Y"] - car_bounds.back_boundary["Y"]
    length = math.sqrt(dx*dx + dy*dy)
    if length > 0.01:
        axes.append(("car_fwd", dx/length, dy/length))
        axes.append(("car_side", -dy/length, dx/length))
    
    # Bus axes
    dx = bus_bounds.front_boundary["X"] - bus_bounds.back_boundary["X"]
    dy = bus_bounds.front_boundary["Y"] - bus_bounds.back_boundary["Y"]
    length = math.sqrt(dx*dx + dy*dy)
    if length > 0.01:
        axes.append(("bus_fwd", dx/length, dy/length))
        axes.append(("bus_side", -dy/length, dx/length))
    
    for name, ax, ay in axes:
        car_projs = [cx * ax + cy * ay for cx, cy in car_corners]
        bus_projs = [bx * ax + by * ay for bx, by in bus_corners]
        
        car_min, car_max = min(car_projs), max(car_projs)
        bus_min, bus_max = min(bus_projs), max(bus_projs)
        
        # Add margin
        car_min -= 50
        car_max += 50
        
        separated = car_max < bus_min or bus_max < car_min
        
        print(f"  Axis {name} ({ax:.2f}, {ay:.2f}):")
        print(f"    Car projection: [{car_min:.0f}, {car_max:.0f}]")
        print(f"    Bus projection: [{bus_min:.0f}, {bus_max:.0f}]")
        print(f"    Separated: {separated}")
else:
    print("\n✓ Collision correctly detected!")

# Also test with car offset by 200cm in Y (still inside bus)
print("\n" + "="*60)
print("Test 2: Car at Y+200 (still inside bus)")
car_loc2 = {"X": 13145, "Y": 8700, "Z": 10}  # 200cm offset
car_bounds2 = checker.get_vehicle_bounds(car_name, car_category, car_loc2, car_rot, False)
collision2 = checker._check_collision(car_bounds2, bus_bounds)
print(f"Car at Y=8700 (bus at Y=8500): Collision={collision2}")

# Test with car OUTSIDE bus
print("\n" + "="*60)
print("Test 3: Car at Y+1500 (should be OUTSIDE bus)")
car_loc3 = {"X": 13145, "Y": 10000, "Z": 10}  # 1500cm offset - outside!
car_bounds3 = checker.get_vehicle_bounds(car_name, car_category, car_loc3, car_rot, False)
collision3 = checker._check_collision(car_bounds3, bus_bounds)
print(f"Car at Y=10000 (bus at Y=8500): Collision={collision3}")
if collision3:
    print("  (Should NOT collide - bus ends at ~8500+833=9333)")
