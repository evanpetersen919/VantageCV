"""
Debug Location 3 - Diagnostic Script

Investigates why no props are spawning at location 3.

Usage:
    python scripts/debug_location_3.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from vantagecv.research_v2.prop_zone_controller import PropZoneController

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Location 3 boundaries
LOCATION_3_Y_MIN = 39600
LOCATION_3_Y_MAX = 59600


def main():
    """Debug location 3 prop spawning"""
    controller = PropZoneController()
    
    # Detect all anchors
    logger.info("=" * 80)
    logger.info("STEP 1: Detecting ALL anchors in level")
    logger.info("=" * 80)
    controller.detect_anchors()
    
    # Show all anchor locations
    logger.info("\n" + "=" * 80)
    logger.info("ALL DETECTED ANCHORS BY TYPE")
    logger.info("=" * 80)
    
    total_anchors = 0
    for anchor_type, anchors in controller.detected_anchors.items():
        logger.info(f"\n{anchor_type.upper()}: {len(anchors)} anchors")
        for anchor in anchors:
            y_pos = anchor.location["Y"]
            logger.info(f"  - {anchor.name}: Y={y_pos:.1f}")
            total_anchors += 1
    
    logger.info(f"\nTotal anchors detected: {total_anchors}")
    
    # Filter for location 3
    logger.info("\n" + "=" * 80)
    logger.info(f"STEP 2: Filtering for Location 3 (Y ∈ [{LOCATION_3_Y_MIN}, {LOCATION_3_Y_MAX}))")
    logger.info("=" * 80)
    
    filtered_anchors = {anchor_type: [] for anchor_type in controller.detected_anchors.keys()}
    
    for anchor_type, anchors in controller.detected_anchors.items():
        for anchor in anchors:
            y_pos = anchor.location["Y"]
            if LOCATION_3_Y_MIN <= y_pos < LOCATION_3_Y_MAX:
                filtered_anchors[anchor_type].append(anchor)
    
    # Show filtered results
    total_filtered = 0
    for anchor_type, anchors in filtered_anchors.items():
        if anchors:
            logger.info(f"\n{anchor_type.upper()}: {len(anchors)} anchors in range")
            for anchor in anchors:
                y_pos = anchor.location["Y"]
                logger.info(f"  - {anchor.name}: Y={y_pos:.1f}")
                total_filtered += 1
        else:
            logger.info(f"\n{anchor_type.upper()}: 0 anchors in range")
    
    logger.info(f"\nTotal anchors in Location 3: {total_filtered}")
    
    # Detect prop pool
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Detecting prop pool")
    logger.info("=" * 80)
    controller.detect_prop_pool()
    
    total_props = sum(len(props) for props in controller.prop_pool.values())
    logger.info(f"\nTotal props in pool: {total_props}")
    
    # Try spawning with location boundaries
    if total_filtered > 0:
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Attempting to spawn props with location boundaries")
        logger.info("=" * 80)
        
        # Set location boundaries
        controller.set_location_boundaries(LOCATION_3_Y_MIN, LOCATION_3_Y_MAX)
        
        # Update detected anchors to filtered set
        controller.detected_anchors = filtered_anchors
        
        # Try spawning
        result = controller.spawn_all(seed=42, spawn_chance=0.5)
        
        logger.info(f"\n\nSPAWN RESULT:")
        logger.info(f"  Success: {result.success}")
        logger.info(f"  Props spawned: {len(result.spawned_props)}")
        
        if result.spawned_props:
            logger.info("\n  Spawned:")
            for prop in result.spawned_props:
                logger.info(f"    - {prop.prop_name}: Y={prop.location['Y']:.1f}")
        else:
            logger.warning("\n  NO PROPS SPAWNED!")
            logger.warning("  Possible reasons:")
            logger.warning("    1. Spawn chance rolls failed (try increasing spawn_chance)")
            logger.warning("    2. No props available in pool")
            logger.warning("    3. Validation failures (check logs above)")
    else:
        logger.warning("\n" + "=" * 80)
        logger.warning("RESULT: No anchors found in Location 3 Y-range")
        logger.warning("=" * 80)
        logger.warning(f"\nLocation 3 is defined as Y ∈ [{LOCATION_3_Y_MIN}, {LOCATION_3_Y_MAX})")
        logger.warning("But no prop anchors were detected in this range.")
        logger.warning("\nPossible reasons:")
        logger.warning("  1. No prop anchors placed in level at this Y-range")
        logger.warning("  2. Anchors exist but have wrong scale values")
        logger.warning("  3. Y-range definition is incorrect for this level")
        logger.warning("\nCheck your level editor to confirm anchor placement.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
