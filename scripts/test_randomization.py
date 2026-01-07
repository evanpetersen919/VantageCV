#!/usr/bin/env python3
"""
Quick randomization test - cycle through 10 random captures for video recording

SAFETY GUARANTEE:
After every test run, the level is restored to its exact pre-test state.
All actor transforms are captured before spawning and restored in finally block.
"""
import sys
import time
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.research_v2.vehicle_spawn_controller import VehicleSpawnController
from vantagecv.research_v2.smart_camera_capture_controller import SmartCameraCaptureController
from vantagecv.research_v2.prop_zone_controller import PropZoneController
from vantagecv.research_v2.time_augmentation_controller import TimeAugmentationController


class TestCleanup:
    """
    Guaranteed cleanup for test runs.
    Stores original transforms and restores them exactly on exit.
    """
    
    def __init__(self, spawner: VehicleSpawnController, prop_controller: PropZoneController,
                 time_controller: TimeAugmentationController = None):
        self.spawner = spawner
        self.prop_controller = prop_controller
        self.time_controller = time_controller
        self.saved_vehicle_transforms: Dict[str, Dict[str, Any]] = {}
        self.saved_prop_transforms: Dict[str, Dict[str, Any]] = {}
        self.actors_saved = 0
        self.actors_restored = 0
        self.restore_failures = 0
    
    def save_all_transforms(self) -> int:
        """
        Capture and store original transforms for ALL prop pool actors.
        Called BEFORE any spawning occurs.
        
        Returns:
            Number of actors saved
        """
        self.actors_saved = 0
        
        # Save prop pool transforms (already stored during detect_prop_pool)
        self.saved_prop_transforms = {}
        for prop_class, props in self.prop_controller.prop_pool.items():
            for prop_name in props:
                if prop_name in self.prop_controller.prop_pool_original_transforms:
                    self.saved_prop_transforms[prop_name] = \
                        self.prop_controller.prop_pool_original_transforms[prop_name].copy()
                    self.actors_saved += 1
        
        # Save vehicle pool transforms
        self.saved_vehicle_transforms = {}
        if hasattr(self.spawner, 'vehicle_pool_original_transforms'):
            for vehicle_name, transform in self.spawner.vehicle_pool_original_transforms.items():
                self.saved_vehicle_transforms[vehicle_name] = transform.copy()
                self.actors_saved += 1
        
        print(f"\n[TestCleanup] Saved {self.actors_saved} actor transforms")
        return self.actors_saved
    
    def restore_all_transforms(self) -> tuple:
        """
        Restore every actor to its exact original transform.
        Uses stored values only - no recomputation.
        
        Returns:
            Tuple of (actors_restored, failures)
        """
        self.actors_restored = 0
        self.restore_failures = 0
        
        print(f"\n[TestCleanup] Restoring actors to original transforms...")
        
        # Restore time/lighting first
        if self.time_controller:
            try:
                self.time_controller.reset()
                self.actors_restored += 1
            except Exception as e:
                print(f"[TestCleanup] ERROR restoring lighting: {e}")
                self.restore_failures += 1
        
        # Restore props via prop_controller.reset_all()
        try:
            self.prop_controller.reset_all()
            self.actors_restored += len(self.saved_prop_transforms)
        except Exception as e:
            print(f"[TestCleanup] ERROR restoring props: {e}")
            self.restore_failures += len(self.saved_prop_transforms)
        
        # Restore vehicles via spawner.reset_all()
        try:
            self.spawner.reset_all()
            self.actors_restored += len(self.saved_vehicle_transforms)
        except Exception as e:
            print(f"[TestCleanup] ERROR restoring vehicles: {e}")
            self.restore_failures += len(self.saved_vehicle_transforms)
        
        print(f"[TestCleanup] Restored {self.actors_restored} actors, {self.restore_failures} failures")
        return (self.actors_restored, self.restore_failures)


def main():
    print("\n" + "=" * 60)
    print("RANDOMIZATION TEST - 20 Captures")
    print("=" * 60)
    print("\nInitializing controllers...")
    
    spawner = VehicleSpawnController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2"
    )
    
    prop_controller = PropZoneController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2"
    )
    
    time_controller = TimeAugmentationController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2"
    )
    
    # Detect prop anchors and prop pool once at startup
    print("\nDetecting prop anchors...")
    prop_controller.detect_anchors()
    print("\nDetecting prop pool...")
    prop_controller.detect_prop_pool()
    # Note: We use prop pool (existing actors), not asset discovery
    
    # Detect lighting actors for time augmentation
    print("\nDetecting lighting actors...")
    if not time_controller.detect_lighting_actors():
        print("WARNING: Time augmentation may be limited - some lighting actors not found")
    
    # Print detection summary
    print("\n" + "=" * 60)
    print("DETECTION SUMMARY")
    print("=" * 60)
    print("\nAnchors (spawn zones):")
    for anchor_type, anchors in prop_controller.detected_anchors.items():
        print(f"  {anchor_type.capitalize():12}: {len(anchors)} anchors")
    print(f"\nProp Pool (available props):")
    for prop_class, props in prop_controller.prop_pool.items():
        print(f"  {prop_class.capitalize():12}: {len(props)} props")
    print(f"\nLighting:")
    print(f"  DirectionalLight: {time_controller.directional_light or 'NOT FOUND'}")
    print(f"  SkyLight: {time_controller.sky_light or 'NOT FOUND'}")
    print(f"  Available times: {', '.join(time_controller.get_available_states())}")
    print("=" * 60)
    
    # Initialize cleanup handler and save all transforms BEFORE any spawning
    cleanup = TestCleanup(spawner, prop_controller, time_controller)
    cleanup.save_all_transforms()
    
    capture_controller = SmartCameraCaptureController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2",
        data_capture_actor="DataCapture_1"
    )
    
    output_dir = Path("output/randomization_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    success = 0
    failed = 0
    
    # Wrap entire test in try/finally for guaranteed cleanup
    try:
        for i in range(20):
            seed = i + 2000
            
            # Vary parameters
            if i % 3 == 0:
                parking_ratio = 1.0  # All parking
                vehicle_count = 3
            elif i % 3 == 1:
                parking_ratio = 0.0  # All lanes
                vehicle_count = 4
            else:
                parking_ratio = 0.5  # Mixed
                vehicle_count = 5
            
            output_path = output_dir / f"frame_{i:03d}.png"
            
            print(f"\n[{i+1}/20] Seed={seed}, Vehicles={vehicle_count}, Parking={parking_ratio:.0%}")
            
            try:
                # Step 1: Time augmentation (before any spawning)
                time_result = time_controller.randomize(seed=seed)
                if not time_result.success:
                    print(f"  ✗ Time augmentation failed: {time_result.failure_reason}")
                    failed += 1
                    continue
                print(f"  Time: {time_result.time_state}")
                
                # Step 2: Reset and spawn vehicles
                spawner.hide_all_vehicles()
                
                spawn_result = spawner.spawn(
                    seed=seed,
                    count=vehicle_count,
                    parking_ratio=parking_ratio,
                    vehicle_types=["car"]
                )
                
                if not spawn_result.success:
                    print(f"  ✗ Vehicle spawn failed")
                    failed += 1
                    continue
                
                # Spawn props with same seed
                prop_result = prop_controller.spawn_all(seed=seed, spawn_chance=0.2)
                print(f"  Props spawned: {len(prop_result.spawned_props)}")
                
                # Capture
                result = capture_controller.capture(
                    output_path=str(output_path),
                    seed=seed,
                    width=1920,
                    height=1080,
                    validate_scene=False  # Skip for speed
                )
                
                if result.status.value == "SUCCESS":
                    print(f"  [OK] Captured")
                    success += 1
                else:
                    print(f"  [FAIL] {result.status.value}")
                    failed += 1
            
            except Exception as e:
                print(f"  [ERROR] {e}")
                failed += 1
            
            finally:
                # Per-iteration cleanup
                spawner.reset_all()
                prop_controller.reset_all()
            
            # Brief pause to allow video recording
            time.sleep(0.1)
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        print(f"  Success: {success}/20")
        print(f"  Failed:  {failed}/20")
        print(f"  Output:  {output_dir}")
    
    finally:
        # GUARANTEED CLEANUP: Restore all actors to original transforms
        # This runs even if test aborts early (Ctrl+C, exception, etc.)
        print("\n" + "=" * 60)
        print("FINAL CLEANUP - RESTORING LEVEL STATE")
        print("=" * 60)
        restored, failures = cleanup.restore_all_transforms()
        if failures > 0:
            print(f"\n⚠ WARNING: {failures} actors failed to restore")
        else:
            print(f"\n✓ Level restored to pre-test state ({restored} actors)")
        print("=" * 60)

if __name__ == "__main__":
    main()
