"""
Check Prop Locations - Diagnostic Script

Verifies that spawned props are at their expected anchor locations.
Run this after prop spawning to diagnose location issues.

Usage:
    python scripts/check_prop_locations.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from vantagecv.research_v2.prop_zone_controller import PropZoneController
import math

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def compute_distance(loc1, loc2):
    """Compute Euclidean distance between two locations"""
    dx = loc1["X"] - loc2["X"]
    dy = loc1["Y"] - loc2["Y"]
    dz = loc1["Z"] - loc2["Z"]
    return math.sqrt(dx*dx + dy*dy + dz*dz)


def check_spawned_locations(controller: PropZoneController):
    """
    Check if spawned props are at their expected locations.
    
    For each spawned prop:
    1. Get its current actual location from UE5
    2. Compare to the expected location (stored in spawned_props)
    3. Report any discrepancies
    """
    logger.info("=" * 80)
    logger.info("PROP LOCATION VERIFICATION")
    logger.info("=" * 80)
    
    if not controller.spawned_props:
        logger.info("No spawned props found. Run spawn_all() first.")
        return
    
    logger.info(f"Checking {len(controller.spawned_props)} spawned props...")
    logger.info("")
    
    issues = []
    max_distance = 0.0
    
    for i, prop in enumerate(controller.spawned_props, 1):
        # Extract actual actor name from asset_path (e.g., "StaticMeshActor_123")
        actor_name = prop.asset_path
        
        # Get current transform from UE5
        actual_transform = controller._get_actor_transform(actor_name)
        
        if not actual_transform:
            logger.error(f"[{i}] ✗ {prop.prop_name}")
            logger.error(f"    Cannot get transform for {actor_name}")
            issues.append({
                "prop": prop.prop_name,
                "issue": "Cannot read transform",
                "actor": actor_name
            })
            continue
        
        actual_loc = actual_transform["location"]
        expected_loc = prop.location
        
        # Compute distance
        distance = compute_distance(actual_loc, expected_loc)
        max_distance = max(max_distance, distance)
        
        # Report
        if distance > 10.0:  # More than 10cm tolerance
            logger.warning(f"[{i}] ⚠ {prop.prop_name} - LOCATION MISMATCH")
            logger.warning(f"    Expected: ({expected_loc['X']:.1f}, {expected_loc['Y']:.1f}, {expected_loc['Z']:.1f})")
            logger.warning(f"    Actual:   ({actual_loc['X']:.1f}, {actual_loc['Y']:.1f}, {actual_loc['Z']:.1f})")
            logger.warning(f"    Distance: {distance:.1f} cm")
            logger.warning(f"    Anchor:   {prop.anchor_name}")
            logger.warning(f"    Type:     {prop.prop_type}")
            issues.append({
                "prop": prop.prop_name,
                "issue": "Location mismatch",
                "distance": distance,
                "expected": expected_loc,
                "actual": actual_loc,
                "anchor": prop.anchor_name,
                "type": prop.prop_type
            })
        else:
            logger.info(f"[{i}] ✓ {prop.prop_name} - OK (distance: {distance:.1f} cm)")
    
    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total props checked: {len(controller.spawned_props)}")
    logger.info(f"Props with issues: {len(issues)}")
    logger.info(f"Maximum distance: {max_distance:.1f} cm")
    
    if issues:
        logger.warning("")
        logger.warning("ISSUES FOUND:")
        for issue in issues:
            logger.warning(f"  - {issue['prop']}: {issue['issue']}")
            if "distance" in issue:
                logger.warning(f"    Distance: {issue['distance']:.1f} cm")
                logger.warning(f"    Type: {issue['type']}, Anchor: {issue['anchor']}")
    else:
        logger.info("")
        logger.info("✓ All props are at correct locations!")
    
    return issues


def main():
    """Run prop location check"""
    controller = PropZoneController()
    
    # Detect anchors and prop pool
    logger.info("Detecting anchors...")
    controller.detect_anchors()
    
    logger.info("")
    logger.info("Detecting prop pool...")
    controller.detect_prop_pool()
    
    logger.info("")
    logger.info("Spawning props...")
    result = controller.spawn_all(seed=42, spawn_chance=0.3)
    
    if not result.success:
        logger.error("Prop spawning failed!")
        return 1
    
    logger.info("")
    logger.info(f"Spawned {len(result.spawned_props)} props successfully")
    
    # Wait a moment for UE5 to settle
    import time
    logger.info("")
    logger.info("Waiting 1 second for UE5 to settle...")
    time.sleep(1.0)
    
    # Check locations
    logger.info("")
    issues = check_spawned_locations(controller)
    
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
