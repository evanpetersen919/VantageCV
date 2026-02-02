#!/usr/bin/env python3
"""Verify boundary detection on all vehicle types."""

import sys
sys.path.insert(0, ".")

from vantagecv.research_v2.vehicle_spacing import VehicleSpacingChecker

checker = VehicleSpacingChecker()

# Test each vehicle category
test_vehicles = {
    "bus": ["StaticMeshActor_7", "StaticMeshActor_9", "StaticMeshActor_11"],
    "car": ["StaticMeshActor_19", "StaticMeshActor_26"],
    "truck": ["StaticMeshActor_27", "StaticMeshActor_25"],
}

for category, actors in test_vehicles.items():
    print(f"\n=== {category.upper()} ===")
    for actor in actors:
        offsets = checker._get_cube_component_offsets(actor)
        if offsets:
            print(f"{actor}: {len(offsets)} boundary components")
            for name, off in offsets.items():
                print(f"  {name}: local offset ({off['X']:.0f}, {off['Y']:.0f})")
        else:
            print(f"{actor}: NO BOUNDARIES FOUND")
        
        # Also test the full cache
        success = checker._cache_boundary_offsets(actor, category)
        if success and actor in checker.boundary_offsets:
            bo = checker.boundary_offsets[actor]
            print(f"  Cached: front={bo.front is not None}, back={bo.back is not None}")
            if bo.front:
                print(f"    Front: ({bo.front['X']:.0f}, {bo.front['Y']:.0f})")
            if bo.back:
                print(f"    Back: ({bo.back['X']:.0f}, {bo.back['Y']:.0f})")
