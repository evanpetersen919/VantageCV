"""
Prop Anchor Detection Script (Location-Scoped)

Detects prop anchors from UE5 level with location-based organization.
Same structure as zone detection (capture_zones.py) but for props.

Detection by scale:
- (0.2, 0.2, 0.2) → Barrier anchors
- (0.4, 0.4, 0.4) → Vegetation anchors
- (0.5, 0.5, 0.5) → Sign anchors
- (0.6, 0.6, 0.6) → Furniture anchors
- (0.7, 0.7, 0.7) → RoadTrash anchors

Author: Evan Petersen
Date: January 2026
"""

import argparse
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)


def main():
    parser = argparse.ArgumentParser(
        description="Detect prop anchors from UE5 level (location-scoped)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Detect all prop anchors with location breakdown:
  python scripts/capture_props.py
  
  # Custom level path:
  python scripts/capture_props.py --level /Game/MyLevel
"""
    )
    
    parser.add_argument(
        "--level",
        default="/Game/automobileV2",
        help="Level path (default: /Game/automobileV2)"
    )
    
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="UE5 Remote Control API host (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=30010,
        help="UE5 Remote Control API port (default: 30010)"
    )
    
    args = parser.parse_args()
    
    # Import here to avoid import errors if not using the script
    from vantagecv.research_v2.prop_zone_controller import PropZoneController
    
    print("\n" + "="*60)
    print("PROP ANCHOR DETECTION (LOCATION-SCOPED)")
    print("="*60)
    print(f"Level: {args.level}")
    print(f"API: http://{args.host}:{args.port}/remote")
    
    # Create controller
    controller = PropZoneController(
        level_path=args.level,
        host=args.host,
        port=args.port
    )
    
    # Detect anchors (location-scoped)
    print("\nDetecting prop anchors...")
    controller.detect_anchors()
    
    # Print location summary table
    print("\n" + "="*70)
    print("LOCATION SUMMARY TABLE")
    print("="*70)
    print(f"{'Location':<12} {'Barrier':<10} {'Vegetation':<12} {'Sign':<8} {'Furniture':<12} {'RoadTrash':<12} {'Total':<8}")
    print("-"*70)
    
    for loc_idx in range(1, 8):  # 7 locations
        location_data = controller.detected_anchors_by_location.get(loc_idx, {})
        
        barrier = len(location_data.get("barrier", []))
        vegetation = len(location_data.get("vegetation", []))
        sign = len(location_data.get("sign", []))
        furniture = len(location_data.get("furniture", []))
        roadtrash = len(location_data.get("roadtrash", []))
        total = barrier + vegetation + sign + furniture + roadtrash
        
        print(f"Location {loc_idx:<4} {barrier:<10} {vegetation:<12} {sign:<8} {furniture:<12} {roadtrash:<12} {total:<8}")
    
    # Global totals
    print("-"*70)
    total_barrier = len(controller.detected_anchors.get("barrier", []))
    total_vegetation = len(controller.detected_anchors.get("vegetation", []))
    total_sign = len(controller.detected_anchors.get("sign", []))
    total_furniture = len(controller.detected_anchors.get("furniture", []))
    total_roadtrash = len(controller.detected_anchors.get("roadtrash", []))
    grand_total = total_barrier + total_vegetation + total_sign + total_furniture + total_roadtrash
    
    print(f"{'TOTAL':<12} {total_barrier:<10} {total_vegetation:<12} {total_sign:<8} {total_furniture:<12} {total_roadtrash:<12} {grand_total:<8}")
    print("="*70)
    
    print("\n✓ Prop detection complete!")
    print(f"  Total anchors detected: {grand_total} across 7 locations\n")


if __name__ == "__main__":
    main()
