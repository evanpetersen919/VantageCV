"""
Scan All Anchors - Extended Range

Scans StaticMeshActor_1 through StaticMeshActor_500 to find all prop anchors.

Usage:
    python scripts/scan_all_anchors.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from vantagecv.research_v2.prop_zone_controller import PropZoneController

logging.basicConfig(
    level=logging.WARNING,  # Suppress info logs for cleaner output
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Scan for all prop anchors with extended range"""
    controller = PropZoneController()
    
    print("=" * 80)
    print("SCANNING StaticMeshActor_1 to StaticMeshActor_500 for prop anchors")
    print("=" * 80)
    print("\nScanning in progress...")
    
    # Manually scan with extended range
    from vantagecv.research_v2.prop_zone_controller import ANCHOR_SCALES
    
    detected = {k: [] for k in ANCHOR_SCALES.keys()}
    
    for i in range(1, 501):
        if i % 100 == 0:
            print(f"  Scanned {i} actors...")
        
        actor_name = f"StaticMeshActor_{i}"
        transform = controller._get_actor_transform(actor_name)
        
        if not transform:
            continue
        
        scale = transform["scale"]
        
        # Check which anchor type this matches
        for anchor_type, target_scale in ANCHOR_SCALES.items():
            if controller._scale_matches(scale, target_scale):
                location = transform["location"]
                detected[anchor_type].append({
                    "name": actor_name,
                    "y": location.get("Y", 0),
                    "x": location.get("X", 0),
                    "z": location.get("Z", 0)
                })
                break
    
    print("\n" + "=" * 80)
    print("RESULTS: All detected anchors by Y-coordinate")
    print("=" * 80)
    
    # Collect all anchors and sort by Y
    all_anchors = []
    for anchor_type, anchors in detected.items():
        for anchor in anchors:
            all_anchors.append({
                "type": anchor_type,
                "name": anchor["name"],
                "y": anchor["y"],
                "x": anchor["x"],
                "z": anchor["z"]
            })
    
    all_anchors.sort(key=lambda a: a["y"])
    
    # Print all anchors
    current_range = None
    for anchor in all_anchors:
        y = anchor["y"]
        
        # Determine which location this falls in
        if y < 19600:
            loc = 1
        elif y < 39600:
            loc = 2
        elif y < 59600:
            loc = 3
        elif y < 79600:
            loc = 4
        elif y < 97600:
            loc = 5
        elif y < 117600:
            loc = 6
        elif y < 137600:
            loc = 7
        else:
            loc = "Unknown"
        
        if current_range != loc:
            print(f"\n--- LOCATION {loc} ---")
            current_range = loc
        
        print(f"  {anchor['name']:25} {anchor['type']:12} Y={y:10.1f}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY BY LOCATION")
    print("=" * 80)
    
    location_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
    
    for anchor in all_anchors:
        y = anchor["y"]
        if y < 19600:
            location_counts[1] += 1
        elif y < 39600:
            location_counts[2] += 1
        elif y < 59600:
            location_counts[3] += 1
        elif y < 79600:
            location_counts[4] += 1
        elif y < 97600:
            location_counts[5] += 1
        elif y < 117600:
            location_counts[6] += 1
        elif y < 137600:
            location_counts[7] += 1
    
    for loc in range(1, 8):
        count = location_counts[loc]
        status = "✓" if count > 0 else "✗"
        print(f"  Location {loc}: {count:3} anchors {status}")
    
    print(f"\nTotal anchors found: {len(all_anchors)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
