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
import re
import sys
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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

# Location boundaries (Y-coordinate ranges), matching the same 7 capture
# locations defined in scripts/test_randomization.py and
# scripts/interactive_spawn_test.py.
LOCATION_BOUNDARIES = {
    1: (400, 19600),
    2: (19600, 39600),
    3: (39600, 59600),
    4: (59600, 79600),
    5: (79600, 97600),
    6: (97600, 117600),
    7: (117600, 137600),
}


def overlay_vehicle_info(image_path: str, vehicles, seed: int = 0):
    """Overlay spawned vehicle info as white text on the top-left corner of
    a captured image (in-place -- overwrites image_path). Identical format
    to test_randomization.py's overlay_vehicle_info(), so output from both
    scripts looks the same.
    """
    try:
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("consola.ttf", 18)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("cour.ttf", 18)
            except (OSError, IOError):
                font = ImageFont.load_default()

        lines = [f"Seed: {seed}  |  Vehicles: {len(vehicles)}"]
        for v in vehicles:
            loc = v.spawn_location
            lines.append(
                f"  {v.category:10} {v.name:25} "
                f"({loc['X']:.0f}, {loc['Y']:.0f})  {v.anchor_name or ''}"
            )

        x, y = 10, 10
        for line in lines:
            for ox, oy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                draw.text((x + ox, y + oy), line, fill="black", font=font)
            draw.text((x, y), line, fill="white", font=font)
            y += 22

        img.save(image_path)
    except Exception as e:
        print(f"  [WARN] Could not overlay vehicle info: {e}")


def make_location_filter(location: int):
    """Build a position_filter(location_dict) -> bool constraining spawns to
    the given capture location's Y-coordinate range."""
    if location not in LOCATION_BOUNDARIES:
        raise ValueError(
            f"Unknown --location {location}; valid values are {sorted(LOCATION_BOUNDARIES)}"
        )
    y_min, y_max = LOCATION_BOUNDARIES[location]

    def _filter(loc: dict) -> bool:
        return y_min <= loc.get("Y", 0) <= y_max

    return _filter


def next_numbered_dir(base_dir: Path, prefix: str = "test_") -> Path:
    """Find the next available <prefix><NNN> directory under base_dir (e.g.
    test_001, test_002, ...), without creating it."""
    base_dir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    existing = [
        int(m.group(1))
        for p in base_dir.iterdir() if p.is_dir()
        for m in [pattern.match(p.name)] if m
    ]
    next_n = max(existing, default=0) + 1
    return base_dir / f"{prefix}{next_n:03d}"


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
    spawner.detect_vehicle_pool()  # required: populates vehicle_pool_original_transforms,
                                    # which reset_all() needs (see finally block below)

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
            vehicle_types=args.vehicle_types.split(",") if args.vehicle_types else ["car"],
            position_filter=make_location_filter(args.location) if args.location else None
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
            overlay_vehicle_info(str(output_path), spawn_result.spawned_vehicles, seed=args.seed)
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
    
    # Ensure output directory exists. If --output-dir wasn't explicitly
    # given, auto-create the next numbered folder (output/test_001,
    # test_002, ...) instead of reusing/overwriting a fixed default.
    if args.output_dir is None:
        output_dir = next_numbered_dir(Path("output"))
    else:
        output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Optional: constrain spawning to a single capture location
    position_filter = make_location_filter(args.location) if args.location else None
    if args.location:
        print(f"Restricting spawns to location {args.location} (Y in {LOCATION_BOUNDARIES[args.location]})")

    # Initialize controllers
    spawner = VehicleSpawnController(
        host=args.host,
        port=args.port,
        level_path=args.level
    )
    spawner.detect_vehicle_pool()  # required: populates vehicle_pool_original_transforms,
                                    # which reset_all() needs (see finally block below)

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
                vehicle_types=vehicle_types,
                position_filter=position_filter
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
                overlay_vehicle_info(str(output_path), spawn_result.spawned_vehicles, seed=frame_seed)
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

  # Batch capture (auto-numbered output/test_001, test_002, ...):
  python scripts/capture.py --batch 10

  # Batch capture restricted to location 1, auto-numbered folder:
  python scripts/capture.py --batch 10 --location 1

  # Batch capture with an explicit output folder (disables auto-numbering):
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
    parser.add_argument("--output-dir", default=None,
                       help="Output directory (batch capture). If not given, "
                            "auto-creates the next output/test_NNN folder.")

    # Vehicle spawning
    parser.add_argument("--location", type=int, choices=sorted(LOCATION_BOUNDARIES),
                       help="Restrict spawning to one of the 7 capture locations (1-7)")
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
