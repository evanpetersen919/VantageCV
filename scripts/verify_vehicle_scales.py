#!/usr/bin/env python3
"""Verify vehicle scales and sizes after normalization."""

import requests
import sys
sys.path.insert(0, "f:/vscode/VantageCV")

from vantagecv.research_v2.config import ResearchConfig

UE5_URL = "http://localhost:30010/remote/object/call"

def get_actor_scale(actor_name: str) -> tuple:
    """Get current scale of an actor."""
    actor_path = f"/Game/automobile.automobile:PersistentLevel.{actor_name}"
    
    payload = {
        "objectPath": actor_path,
        "functionName": "GetActorScale3D",
        "parameters": {},
        "generateTransaction": False
    }
    
    resp = requests.put(UE5_URL, json=payload, timeout=5)
    if resp.ok:
        result = resp.json()
        scale = result.get("ReturnValue", {})
        return scale.get("X", 1), scale.get("Y", 1), scale.get("Z", 1)
    return (1, 1, 1)

def get_actor_bounds(actor_name: str) -> tuple:
    """Get actual bounds of an actor in centimeters."""
    actor_path = f"/Game/automobile.automobile:PersistentLevel.{actor_name}"
    
    payload = {
        "objectPath": actor_path,
        "functionName": "GetActorBounds",
        "parameters": {"bOnlyCollidingComponents": False},
        "generateTransaction": False
    }
    
    resp = requests.put(UE5_URL, json=payload, timeout=5)
    if resp.ok:
        result = resp.json()
        extent = result.get("BoxExtent", {})
        # Extent is half-size, so multiply by 2
        return (
            extent.get("X", 0) * 2,
            extent.get("Y", 0) * 2,
            extent.get("Z", 0) * 2
        )
    return (0, 0, 0)

def main():
    config = ResearchConfig()
    
    print("=" * 80)
    print("VEHICLE SCALE AND SIZE VERIFICATION")
    print("=" * 80)
    print()
    
    # Expected realistic sizes per class (in meters)
    expected_sizes = {
        "car": (4.5, 1.8, 1.5),
        "truck": (7.0, 2.5, 3.0),
        "bus": (12.0, 2.5, 3.2),
        "motorcycle": (2.2, 0.8, 1.1),
        "bicycle": (1.8, 0.6, 1.0)
    }
    
    results = []
    
    for class_name, actors in config.vehicles.vehicle_actors.items():
        expected = expected_sizes.get(class_name, (5.0, 2.0, 2.0))
        
        for actor_name in actors:
            scale = get_actor_scale(actor_name)
            bounds = get_actor_bounds(actor_name)
            
            # Convert bounds to meters
            length_m = bounds[0] / 100
            width_m = bounds[1] / 100
            height_m = bounds[2] / 100
            
            # Check if within reasonable range (50% to 150% of expected)
            length_ok = expected[0] * 0.5 <= length_m <= expected[0] * 1.5
            width_ok = expected[1] * 0.5 <= width_m <= expected[1] * 1.5
            height_ok = expected[2] * 0.5 <= height_m <= expected[2] * 1.5
            
            status = "✓" if (length_ok and width_ok and height_ok) else "✗"
            
            results.append({
                "class": class_name,
                "actor": actor_name,
                "scale": scale,
                "size_m": (length_m, width_m, height_m),
                "expected": expected,
                "status": status
            })
    
    # Print results grouped by class
    current_class = None
    good_count = 0
    total_count = 0
    
    for r in results:
        if r["class"] != current_class:
            current_class = r["class"]
            exp = expected_sizes.get(current_class, (5.0, 2.0, 2.0))
            print(f"\n{current_class.upper()} (expected ~{exp[0]:.1f}m x {exp[1]:.1f}m x {exp[2]:.1f}m):")
            print("-" * 70)
        
        total_count += 1
        if r["status"] == "✓":
            good_count += 1
        
        print(f"  {r['status']} {r['actor']}")
        print(f"      Scale: ({r['scale'][0]:.3f}, {r['scale'][1]:.3f}, {r['scale'][2]:.3f})")
        print(f"      Actual: {r['size_m'][0]:.2f}m x {r['size_m'][1]:.2f}m x {r['size_m'][2]:.2f}m")
    
    print()
    print("=" * 80)
    print(f"SUMMARY: {good_count}/{total_count} vehicles within expected size range")
    print("=" * 80)

if __name__ == "__main__":
    main()
