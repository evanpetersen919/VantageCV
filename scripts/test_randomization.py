#!/usr/bin/env python3
"""
Quick randomization test - cycle through 100 random captures for video recording
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.research_v2.vehicle_spawn_controller import VehicleSpawnController
from vantagecv.research_v2.smart_camera_capture_controller import SmartCameraCaptureController

def main():
    print("\n" + "=" * 60)
    print("RANDOMIZATION TEST - 100 Captures")
    print("=" * 60)
    print("\nInitializing controllers...")
    
    spawner = VehicleSpawnController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2"
    )
    
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
    
    for i in range(100):
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
        
        print(f"\n[{i+1}/100] Seed={seed}, Vehicles={vehicle_count}, Parking={parking_ratio:.0%}")
        
        try:
            # Reset and spawn
            spawner.hide_all_vehicles()
            
            spawn_result = spawner.spawn(
                seed=seed,
                count=vehicle_count,
                parking_ratio=parking_ratio,
                vehicle_types=["car"]
            )
            
            if not spawn_result.success:
                print(f"  ✗ Spawn failed")
                failed += 1
                continue
            
            # Capture
            result = capture_controller.capture(
                output_path=str(output_path),
                seed=seed,
                width=1920,
                height=1080,
                validate_scene=False  # Skip for speed
            )
            
            if result.status.value == "SUCCESS":
                print(f"  ✓ Captured")
                success += 1
            else:
                print(f"  ✗ {result.status.value}")
                failed += 1
        
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1
        
        finally:
            spawner.reset_all()
        
        # Brief pause to allow video recording
        time.sleep(0.1)
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"  Success: {success}/100")
    print(f"  Failed:  {failed}/100")
    print(f"  Output:  {output_dir}")

if __name__ == "__main__":
    main()
