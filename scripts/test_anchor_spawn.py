"""
Test Anchor Spawn System

Verifies that all anchor actors exist and captures their transforms.
Run this to validate your level setup before generating data.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.research_v2.anchor_spawn_controller import (
    load_config,
    AnchorSpawnController,
    VehicleConfig
)
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def test_config_loading(config_path: str):
    """Test that configuration loads correctly"""
    print("\n" + "="*60)
    print("TEST: Configuration Loading")
    print("="*60)
    
    try:
        config = load_config(config_path)
        print(f"✓ Config loaded: {config_path}")
        print(f"  Level: {config.level_name}")
        print(f"  Path: {config.level_path}")
        print(f"  Parking anchors: {config.parking_anchors}")
        print(f"  Lanes: {[l.lane_id for l in config.lanes]}")
        print(f"  Locked actors: {config.locked_actors}")
        return config
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return None


def test_anchor_verification(controller: AnchorSpawnController):
    """Test that all anchors exist in the level"""
    print("\n" + "="*60)
    print("TEST: Anchor Verification")
    print("="*60)
    
    results = controller.verify_anchors()
    
    found = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nSummary: {found}/{total} anchors found")
    
    if found < total:
        print("\n⚠️  Missing anchors:")
        for name, exists in results.items():
            if not exists:
                print(f"    - {name}")
        return False
    
    return True


def test_parking_transform_capture(controller: AnchorSpawnController):
    """Test capturing parking anchor transforms"""
    print("\n" + "="*60)
    print("TEST: Parking Transform Capture")
    print("="*60)
    
    for anchor in controller.config.parking_anchors:
        transform = controller.get_anchor_transform(anchor)
        if transform:
            loc = transform['location']
            rot = transform['rotation']
            print(f"✓ {anchor}:")
            print(f"    Location: ({loc['x']:.1f}, {loc['y']:.1f}, {loc['z']:.1f})")
            print(f"    Rotation: Yaw={rot['yaw']:.1f}°")
        else:
            print(f"✗ {anchor}: FAILED")


def test_lane_configuration(controller: AnchorSpawnController):
    """Test lane anchor resolution"""
    print("\n" + "="*60)
    print("TEST: Lane Configuration")
    print("="*60)
    
    for lane in controller.config.lanes:
        start = controller.get_anchor_transform(lane.start_anchor)
        end = controller.get_anchor_transform(lane.end_anchor)
        
        if start and end:
            # Compute lane vector
            dx = end['location']['x'] - start['location']['x']
            dy = end['location']['y'] - start['location']['y']
            length = (dx**2 + dy**2)**0.5
            
            import math
            direction = math.degrees(math.atan2(dy, dx))
            
            print(f"✓ {lane.lane_id}:")
            print(f"    Start: ({start['location']['x']:.0f}, {start['location']['y']:.0f})")
            print(f"    End: ({end['location']['x']:.0f}, {end['location']['y']:.0f})")
            print(f"    Length: {length:.0f} cm")
            print(f"    Direction: {direction:.1f}°")
        else:
            print(f"✗ {lane.lane_id}: Missing anchors")


def test_spawn_simulation(controller: AnchorSpawnController):
    """Test spawning logic (without actually spawning)"""
    print("\n" + "="*60)
    print("TEST: Spawn Simulation")
    print("="*60)
    
    # Initialize with a seed
    controller.initialize(seed=42)
    
    # Simulate parking spawn
    vehicles = [
        VehicleConfig(asset_path="/Game/Vehicles/Sedan", vehicle_class="sedan"),
        VehicleConfig(asset_path="/Game/Vehicles/SUV", vehicle_class="suv"),
    ]
    
    print("\nSimulating parking spawn...")
    results = controller.spawn_parking_vehicles(vehicles, max_vehicles=3)
    print(f"  Would spawn {len([r for r in results if r['success']])} vehicles")
    
    print("\nSimulating lane spawn...")
    lane_results = controller.spawn_lane_vehicles(vehicles, vehicles_per_lane=2)
    print(f"  Would spawn {len(lane_results)} vehicles across lanes")
    
    # Summary
    summary = controller.get_spawn_summary()
    print(f"\nSpawn summary:")
    print(f"  Seed: {summary['seed']}")
    print(f"  Total instances: {summary['spawned_count']}")


def main():
    parser = argparse.ArgumentParser(description="Test anchor spawn system")
    parser.add_argument("--config", default="configs/levels/automobileV2_anchors.yaml",
                       help="Path to anchor configuration YAML")
    parser.add_argument("--verify-only", action="store_true",
                       help="Only verify anchors exist, don't simulate spawning")
    parser.add_argument("--host", default="127.0.0.1",
                       help="UE5 Remote Control host")
    parser.add_argument("--port", type=int, default=30010,
                       help="UE5 Remote Control port")
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("ANCHOR SPAWN SYSTEM TEST")
    print("="*60)
    
    # Test 1: Load config
    config = test_config_loading(args.config)
    if not config:
        print("\n❌ Config loading failed. Exiting.")
        return 1
    
    # Create controller
    controller = AnchorSpawnController(
        config=config,
        host=args.host,
        port=args.port
    )
    
    # Test 2: Verify anchors
    anchors_ok = test_anchor_verification(controller)
    
    if args.verify_only:
        if anchors_ok:
            print("\n✅ All anchors verified!")
            return 0
        else:
            print("\n❌ Some anchors missing. Check UE5 level.")
            return 1
    
    # Test 3: Capture parking transforms
    test_parking_transform_capture(controller)
    
    # Test 4: Lane configuration
    test_lane_configuration(controller)
    
    # Test 5: Spawn simulation
    test_spawn_simulation(controller)
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    exit(main())
