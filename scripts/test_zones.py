#!/usr/bin/env python3
"""
Zone System Test Script

Tests the zone-based spatial placement system.

Usage:
    python scripts/test_zones.py
    python scripts/test_zones.py --visualize
    python scripts/test_zones.py --spawn 5
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from vantagecv.research_v2.zones import (
    ZoneRegistry,
    ZoneBasedSpawner,
    ZoneVisualizer,
    ZoneConfig,
    ZoneType,
    create_test_zones,
)
from vantagecv.research_v2.config import VehicleSpawnerConfig, SceneConfig, VehicleClass
from vantagecv.research_v2.logging_utils import ResearchLogger


def test_zone_loading():
    """Test loading zones from manifest."""
    print("\n" + "=" * 60)
    print("TEST: Zone Loading")
    print("=" * 60)
    
    registry = ZoneRegistry()
    
    # Load from manifest
    manifest_path = project_root / "configs" / "zones" / "automobile.zones.yaml"
    if not manifest_path.exists():
        print(f"✗ Manifest not found: {manifest_path}")
        return False
    
    success = registry.load_from_manifest(manifest_path)
    if not success:
        print("✗ Failed to load manifest")
        return False
    
    print(f"✓ Loaded {registry.zone_count} zones")
    print(f"  - Road zones: {registry.road_zone_count}")
    print(f"  - Parking zones: {registry.parking_zone_count}")
    print(f"  - Exclusion zones: {registry.exclusion_zone_count}")
    
    # List zones
    for zone in registry:
        print(f"\n  [{zone.zone_type.value.upper()}] {zone.zone_id}")
        print(f"    Asset: {zone.asset_id}")
        print(f"    Enabled: {zone.enabled}")
        print(f"    Classes: {[c.value for c in zone.allowed_classes]}")
    
    return True


def test_zone_validation():
    """Test zone validation."""
    print("\n" + "=" * 60)
    print("TEST: Zone Validation")
    print("=" * 60)
    
    registry = ZoneRegistry()
    manifest_path = project_root / "configs" / "zones" / "automobile.zones.yaml"
    registry.load_from_manifest(manifest_path)
    
    valid, errors = registry.validate()
    
    if valid:
        print("✓ All zones valid")
    else:
        print(f"✗ Validation failed with {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
    
    return valid


def test_zone_spawning(count: int = 3):
    """Test zone-based vehicle spawning."""
    print("\n" + "=" * 60)
    print(f"TEST: Zone Spawning ({count} vehicles)")
    print("=" * 60)
    
    # Load zones
    registry = ZoneRegistry()
    manifest_path = project_root / "configs" / "zones" / "automobile.zones.yaml"
    registry.load_from_manifest(manifest_path)
    
    # Create spawner
    config = VehicleSpawnerConfig()
    scene_config = SceneConfig()
    spawner = ZoneBasedSpawner(registry, config, scene_config)
    spawner.set_seed(42)
    
    # Validate
    if not spawner.validate_config():
        print("✗ Spawner validation failed")
        return False
    
    print("✓ Spawner validated")
    
    # Spawn vehicles
    result = spawner.spawn_vehicles(count=count)
    
    if result.success:
        print(f"✓ Spawned {result.actual_count}/{result.requested_count} vehicles")
        
        for vehicle in result.vehicles:
            print(f"\n  Vehicle: {vehicle.instance_id}")
            print(f"    Class: {vehicle.vehicle_class.value}")
            print(f"    Actor: {vehicle.actor_name}")
            print(f"    Zone: {vehicle.zone_id} ({vehicle.zone_type.value})")
            if vehicle.slot_id:
                print(f"    Slot: {vehicle.slot_id}")
            pos = vehicle.transform.position
            print(f"    Position: ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f})")
    else:
        print(f"✗ Spawning failed: {result.actual_count}/{result.requested_count}")
        for failure in result.failures:
            print(f"  - {failure}")
    
    return result.success


def test_parking_slots():
    """Test parking slot allocation."""
    print("\n" + "=" * 60)
    print("TEST: Parking Slot Allocation")
    print("=" * 60)
    
    # Load zones
    registry = ZoneRegistry()
    manifest_path = project_root / "configs" / "zones" / "automobile.zones.yaml"
    registry.load_from_manifest(manifest_path)
    
    # Find parking zones
    parking_zones = registry.get_zones_by_type(ZoneType.PARKING)
    print(f"Found {len(parking_zones)} parking zones")
    
    for zone in parking_zones:
        from vantagecv.research_v2.zones.zone_data import ParkingZone
        if isinstance(zone, ParkingZone):
            print(f"\n  Zone: {zone.zone_id}")
            print(f"    Total slots: {len(zone.slots)}")
            
            # Allocate slots
            allocated = 0
            for i in range(3):
                slot = zone.allocate_slot(VehicleClass.CAR, f"test_vehicle_{i}")
                if slot:
                    print(f"    ✓ Allocated slot {slot.slot_id}")
                    allocated += 1
                else:
                    print(f"    ✗ No slot available")
                    break
            
            # Check remaining
            available = zone.get_available_slots(VehicleClass.CAR)
            print(f"    Remaining slots: {len(available)}")
            
            # Release all
            released = zone.release_all()
            print(f"    Released {released} slots")
    
    return True


def test_exclusion_zones():
    """Test exclusion zone behavior."""
    print("\n" + "=" * 60)
    print("TEST: Exclusion Zones")
    print("=" * 60)
    
    # Load zones
    registry = ZoneRegistry()
    manifest_path = project_root / "configs" / "zones" / "automobile.zones.yaml"
    registry.load_from_manifest(manifest_path)
    
    from vantagecv.research_v2.zones.zone_data import Vector3
    
    # Test points
    test_points = [
        Vector3(0, 0, 0),      # Should be in exclusion (camera area)
        Vector3(50, 0, 0),     # Should be in road zone
        Vector3(30, -8, 0),    # Should be in parking zone
        Vector3(50, 20, 0),    # Should be in exclusion (road edge)
    ]
    
    for point in test_points:
        in_exclusion = registry.is_point_in_exclusion(point)
        zone = registry.get_zone_at_point(point)
        
        status = "EXCLUDED" if in_exclusion else "OK"
        zone_name = zone.zone_id if zone else "None"
        
        print(f"  Point ({point.x}, {point.y}, {point.z}): {status}")
        print(f"    Zone: {zone_name}")
    
    return True


def test_visualization():
    """Test debug visualization generation."""
    print("\n" + "=" * 60)
    print("TEST: Debug Visualization")
    print("=" * 60)
    
    # Create test zones
    registry = create_test_zones()
    print(f"Created {registry.zone_count} test zones")
    
    # Generate visualization
    visualizer = ZoneVisualizer(registry)
    commands = visualizer.generate_debug_commands()
    
    print(f"Generated {len(commands)} debug draw commands")
    
    # Print summary
    summary = visualizer.generate_summary()
    print("\n" + summary)
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Test zone system")
    parser.add_argument("--spawn", type=int, default=3, help="Number of vehicles to spawn")
    parser.add_argument("--visualize", action="store_true", help="Test visualization")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    args = parser.parse_args()
    
    print("=" * 60)
    print("VantageCV Zone System Tests")
    print("=" * 60)
    
    results = {}
    
    # Run tests
    results["loading"] = test_zone_loading()
    results["validation"] = test_zone_validation()
    results["spawning"] = test_zone_spawning(args.spawn)
    results["parking"] = test_parking_slots()
    results["exclusion"] = test_exclusion_zones()
    
    if args.visualize or args.all:
        results["visualization"] = test_visualization()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
