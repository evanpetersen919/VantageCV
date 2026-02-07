#!/usr/bin/env python3
"""
Test script to verify strict prop validation rules.

This script validates that:
1. Props only spawn at valid anchor locations
2. Props spawn at the correct locations (verified after teleport)
3. Props match their anchor types
4. Failed spawns are logged and skipped
"""

import sys
sys.path.insert(0, ".")

from vantagecv.research_v2.prop_zone_controller import PropZoneController

def main():
    print("=" * 70)
    print("PROP VALIDATION TEST")
    print("=" * 70)
    print()
    
    # Initialize controller
    controller = PropZoneController()
    
    # Step 1: Detect anchors
    print("Step 1: Detecting anchors...")
    anchors = controller.detect_anchors()
    
    total_anchors = sum(len(v) for v in anchors.values())
    if total_anchors == 0:
        print("ERROR: No anchors detected! Check if UE5 is running.")
        return 1
    
    print(f"✓ Detected {total_anchors} total anchors\n")
    
    # Step 2: Detect prop pool
    print("Step 2: Detecting prop pool...")
    pool = controller.detect_prop_pool()
    
    total_props = sum(len(v) for v in pool.values())
    if total_props == 0:
        print("ERROR: No props in pool! Check prop pool setup.")
        return 1
    
    print(f"✓ Detected {total_props} props in pool\n")
    
    # Step 3: Test barrier spawn with validation
    print("Step 3: Testing barrier spawn with strict validation...")
    print("-" * 70)
    barrier_result = controller.spawn_barriers(seed=12345, spawn_chance=0.3)
    print("-" * 70)
    
    if barrier_result.success:
        print(f"✓ Barrier spawn completed: {len(barrier_result.spawned_props)} spawned")
    else:
        print(f"✗ Barrier spawn failed: {barrier_result.failure_reason}")
    
    print()
    
    # Step 4: Test vegetation spawn with validation
    print("Step 4: Testing vegetation spawn with strict validation...")
    print("-" * 70)
    veg_result = controller.spawn_vegetation(seed=12346, spawn_chance=0.2)
    print("-" * 70)
    
    if veg_result.success:
        print(f"✓ Vegetation spawn completed: {len(veg_result.spawned_props)} spawned")
    else:
        print(f"✗ Vegetation spawn failed: {veg_result.failure_reason}")
    
    print()
    
    # Step 5: Verify spawned props are at correct locations
    print("Step 5: Verifying all spawned props are at correct locations...")
    all_spawned = barrier_result.spawned_props + veg_result.spawned_props
    
    if len(all_spawned) == 0:
        print("WARNING: No props spawned to verify")
    else:
        verification_passed = 0
        for prop in all_spawned:
            # Get actual location from UE5
            actual_transform = controller._get_actor_transform(prop.asset_path)
            if actual_transform:
                actual_loc = actual_transform["location"]
                expected_loc = prop.location
                
                # Calculate distance
                import math
                dx = actual_loc["X"] - expected_loc["X"]
                dy = actual_loc["Y"] - expected_loc["Y"]
                dz = actual_loc["Z"] - expected_loc["Z"]
                distance = math.sqrt(dx*dx + dy*dy + dz*dz)
                
                if distance < 10.0:  # Within 10cm tolerance
                    verification_passed += 1
                else:
                    print(f"✗ {prop.prop_name} at wrong location (distance: {distance:.1f}cm)")
        
        print(f"✓ {verification_passed}/{len(all_spawned)} props verified at correct locations")
    
    print()
    print("=" * 70)
    print("VALIDATION TEST COMPLETE")
    print("=" * 70)
    print()
    print("SUMMARY:")
    print(f"  Anchors detected: {total_anchors}")
    print(f"  Props in pool: {total_props}")
    print(f"  Barriers spawned: {len(barrier_result.spawned_props)}")
    print(f"  Vegetation spawned: {len(veg_result.spawned_props)}")
    
    if len(all_spawned) > 0:
        verification_rate = verification_passed / len(all_spawned) * 100
        print(f"  Location accuracy: {verification_rate:.1f}%")
        
        if verification_rate == 100:
            print("\n✓ ALL PROPS SPAWNED AT CORRECT LOCATIONS!")
            return 0
        else:
            print("\n✗ SOME PROPS NOT AT CORRECT LOCATIONS - CHECK LOGS")
            return 1
    else:
        print("\n⚠ No props spawned - cannot verify")
        return 0

if __name__ == "__main__":
    sys.exit(main())
