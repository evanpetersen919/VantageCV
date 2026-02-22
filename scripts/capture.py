#!/usr/bin/env python3
"""
VantageCV - Capture Pipeline

Single entry point for spawning, validation, and smart camera capture.

Workflow:
1. VehicleSpawnController: Spawn vehicles from pool to anchors
2. SceneValidationController: Validate scene is ready
3. SmartCameraCaptureController: Position camera and capture
4. VehicleSpawnController: Reset vehicles to pool

Usage:
    # Validate scene only:
    python scripts/capture.py --validate-only

    # Single capture (spawns 3 cars by default):
    python scripts/capture.py --output output/frame_001.png --seed 42

    # Capture with specific vehicle count:
    python scripts/capture.py --output output/frame_001.png --seed 42 --vehicles 5

    # Batch capture:
    python scripts/capture.py --batch 10 --output-dir output/batch_001

Author: Evan Petersen
Date: January 2026
"""

import argparse
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.research_v2.vehicle_spawn_controller import VehicleSpawnController
from vantagecv.research_v2.scene_validation_controller import SceneValidationController
from vantagecv.research_v2.smart_camera_capture_controller import (
    SmartCameraCaptureController,
    CaptureStatus
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def validate_scene(args) -> int:
    """Run scene validation only"""
    print("\n" + "=" * 60)
    print("SCENE VALIDATION")
    print("=" * 60)
    
    controller = SceneValidationController(
        host=args.host,
        port=args.port,
        level_path=args.level
    )
    
    report = controller.validate(seed=args.seed)
    
    print("\n" + "=" * 60)
    print("VALIDATION RESULT")
    print("=" * 60)
    print(f"  SCENE_VALID:    {report.scene_valid}")
    print(f"  FAILURE_REASON: {report.failure_reason or 'None'}")
    print(f"  Pass: {report.pass_count}")
    print(f"  Fail: {report.fail_count}")
    print(f"  Warn: {report.warn_count}")
    
    if not report.scene_valid:
        print("\n❌ Scene validation FAILED")
        print(f"   Reason: {report.failure_reason}")
        return 1
    
    print("\n✅ Scene validation PASSED")
    return 0


def single_capture(args) -> int:
    """Capture a single frame with full spawn/capture/reset workflow"""
    print("\n" + "=" * 60)
    print("SMART CAMERA CAPTURE")
    print("=" * 60)
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize controllers
    spawner = VehicleSpawnController(
        host=args.host,
        port=args.port,
        level_path=args.level
    )
    
    capture_controller = SmartCameraCaptureController(
        host=args.host,
        port=args.port,
        level_path=args.level,
        data_capture_actor=args.data_capture
    )
    
    try:
        # Step 1: Hide ALL vehicles in pool (clean slate)
        print("\n--- Step 1: Reset Vehicle Pool ---")
        spawner.hide_all_vehicles()
        
        # Step 2: Spawn vehicles
        print(f"\n--- Step 2: Spawn {args.vehicles} Vehicles (parking_ratio={args.parking_ratio}) ---")
        spawn_result = spawner.spawn(
            seed=args.seed,
            count=args.vehicles,
            parking_ratio=args.parking_ratio,
            vehicle_types=args.vehicle_types.split(",") if args.vehicle_types else ["car"]
        )
        
        if not spawn_result.success:
            print(f"\n❌ Spawn failed: {spawn_result.failure_reason}")
            return 1
        
        print(f"   Spawned {len(spawn_result.spawned_vehicles)} vehicles")
        
        # Step 3: Capture
        print("\n--- Step 3: Camera Capture ---")
        result = capture_controller.capture(
            output_path=str(output_path),
            seed=args.seed,
            width=args.width,
            height=args.height,
            validate_scene=not args.skip_validation
        )
        
        print("\n" + "=" * 60)
        print("CAPTURE RESULT")
        print("=" * 60)
        print(f"  Status: {result.status.value}")
        print(f"  Image:  {result.image_path or 'Not captured'}")
        
        if result.camera_placement:
            loc = result.camera_placement.location
            rot = result.camera_placement.rotation
            print(f"  Camera: ({loc['X']:.1f}, {loc['Y']:.1f}, {loc['Z']:.1f}) "
                  f"Pitch={rot['Pitch']:.1f}° Yaw={rot['Yaw']:.1f}° FOV={result.camera_placement.fov:.1f}°")
        
        if result.visibility_results:
            print("\n  Visibility:")
            for v in result.visibility_results:
                status = "✓" if v.visible_percentage >= 30 else "✗"
                print(f"    {status} {v.vehicle_name}: {v.visible_percentage:.1f}%")
        
        if result.failure_reason:
            print(f"\n  Failure: {result.failure_reason}")
        
        if result.status == CaptureStatus.SUCCESS:
            print("\n✅ Capture SUCCESS")
            return 0
        else:
            print(f"\n❌ Capture FAILED: {result.status.value}")
            return 1
    
    finally:
        # Step 4: Always reset vehicles back to pool
        print("\n--- Step 4: Reset Vehicles to Pool ---")
        spawner.reset_all()


def batch_capture(args) -> int:
    """Capture multiple frames with spawn/capture/reset per frame"""
    print("\n" + "=" * 60)
    print(f"BATCH CAPTURE ({args.batch} frames)")
    print("=" * 60)
    
    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize controllers
    spawner = VehicleSpawnController(
        host=args.host,
        port=args.port,
        level_path=args.level
    )
    
    capture_controller = SmartCameraCaptureController(
        host=args.host,
        port=args.port,
        level_path=args.level,
        data_capture_actor=args.data_capture
    )
    
    # Pre-flight validation (without vehicles)
    if not args.skip_validation:
        print("\n--- Pre-flight Validation ---")
        validator = SceneValidationController(
            host=args.host,
            port=args.port,
            level_path=args.level
        )
        report = validator.validate(seed=args.seed)
        
        if not report.scene_valid:
            print(f"\n❌ Scene validation FAILED: {report.failure_reason}")
            return 1
        print("✓ Scene valid - proceeding with batch capture")
    
    # Capture frames
    success_count = 0
    fail_count = 0
    vehicle_types = args.vehicle_types.split(",") if args.vehicle_types else ["car"]
    
    for i in range(args.batch):
        frame_seed = args.seed + i
        output_path = output_dir / f"frame_{i:06d}.png"
        
        print(f"\n--- Frame {i + 1}/{args.batch} (seed={frame_seed}) ---")
        
        try:
            # Hide all and spawn fresh vehicles for each frame
            spawner.hide_all_vehicles()
            
            spawn_result = spawner.spawn(
                seed=frame_seed,
                count=args.vehicles,
                parking_ratio=args.parking_ratio,
                vehicle_types=vehicle_types
            )
            
            if not spawn_result.success:
                fail_count += 1
                print(f"  ✗ Spawn failed: {spawn_result.failure_reason}")
                continue
            
            result = capture_controller.capture(
                output_path=str(output_path),
                seed=frame_seed,
                width=args.width,
                height=args.height,
                validate_scene=False  # Skip validation for speed
            )
            
            if result.status == CaptureStatus.SUCCESS:
                success_count += 1
                print(f"  ✓ Captured: {output_path.name}")
            else:
                fail_count += 1
                print(f"  ✗ Failed: {result.failure_reason}")
        
        finally:
            spawner.reset_all()
    
    # Summary
    print("\n" + "=" * 60)
    print("BATCH CAPTURE COMPLETE")
    print("=" * 60)
    print(f"  Total:   {args.batch}")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {fail_count}")
    print(f"  Output:  {output_dir}")
    
    return 0 if fail_count == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="VantageCV Capture Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate scene:
  python scripts/capture.py --validate-only

  # Single capture with 3 cars (50% parking, 50% lanes):
  python scripts/capture.py --output output/frame_001.png --seed 42

  # Capture with 5 mixed vehicles, all in lanes:
  python scripts/capture.py --output output/frame_001.png --vehicles 5 --vehicle-types car,truck --parking-ratio 0.0

  # Capture with 4 vehicles, all in parking:
  python scripts/capture.py --output output/frame_001.png --vehicles 4 --parking-ratio 1.0

  # Batch capture:
  python scripts/capture.py --batch 10 --output-dir output/batch_001
        """
    )
    
    # Mode selection
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--validate-only", action="store_true",
                     help="Only validate scene, don't capture")
    mode.add_argument("--batch", type=int, metavar="N",
                     help="Batch capture N frames")
    
    # Output options
    parser.add_argument("--output", default="output/capture.png",
                       help="Output image path (single capture)")
    parser.add_argument("--output-dir", default="output/batch",
                       help="Output directory (batch capture)")
    
    # Vehicle spawning
    parser.add_argument("--vehicles", type=int, default=3,
                       help="Number of vehicles to spawn (default: 3)")
    parser.add_argument("--vehicle-types", dest="vehicle_types", default="car",
                       help="Comma-separated vehicle types: car,truck,bus,motorcycle,bicycle (default: car)")
    parser.add_argument("--parking-ratio", type=float, default=0.5,
                       help="Ratio of vehicles in parking vs lanes: 0.0=all lanes, 1.0=all parking (default: 0.5)")
    
    # Capture settings
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed (default: 42)")
    parser.add_argument("--width", type=int, default=1920,
                       help="Image width (default: 1920)")
    parser.add_argument("--height", type=int, default=1080,
                       help="Image height (default: 1080)")
    
    # Connection settings
    parser.add_argument("--host", default="127.0.0.1",
                       help="UE5 Remote Control host")
    parser.add_argument("--port", type=int, default=30010,
                       help="UE5 Remote Control port")
    parser.add_argument("--level", default="/Game/automobileV2.automobileV2",
                       help="Level path")
    parser.add_argument("--data-capture", default="DataCapture_2",
                       help="DataCapture actor name")
    
    # Flags
    parser.add_argument("--skip-validation", action="store_true",
                       help="Skip scene validation")
    
    args = parser.parse_args()
    
    # Route to appropriate handler
    if args.validate_only:
        return validate_scene(args)
    elif args.batch:
        return batch_capture(args)
    else:
        return single_capture(args)


if __name__ == "__main__":
    exit(main())
