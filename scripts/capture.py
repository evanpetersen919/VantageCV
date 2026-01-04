#!/usr/bin/env python3
"""
VantageCV - Capture Pipeline

Single entry point for scene validation and smart camera capture.
Uses SceneValidationController and SmartCameraCaptureController.

Usage:
    # Validate scene only:
    python scripts/capture.py --validate-only

    # Single capture:
    python scripts/capture.py --output output/frame_001.png --seed 42

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
    """Capture a single frame"""
    print("\n" + "=" * 60)
    print("SMART CAMERA CAPTURE")
    print("=" * 60)
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    controller = SmartCameraCaptureController(
        host=args.host,
        port=args.port,
        level_path=args.level,
        data_capture_actor=args.data_capture
    )
    
    result = controller.capture(
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


def batch_capture(args) -> int:
    """Capture multiple frames"""
    print("\n" + "=" * 60)
    print(f"BATCH CAPTURE ({args.batch} frames)")
    print("=" * 60)
    
    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    controller = SmartCameraCaptureController(
        host=args.host,
        port=args.port,
        level_path=args.level,
        data_capture_actor=args.data_capture
    )
    
    # First, validate scene once
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
    
    for i in range(args.batch):
        frame_seed = args.seed + i
        output_path = output_dir / f"frame_{i:06d}.png"
        
        print(f"\n--- Frame {i + 1}/{args.batch} (seed={frame_seed}) ---")
        
        result = controller.capture(
            output_path=str(output_path),
            seed=frame_seed,
            width=args.width,
            height=args.height,
            validate_scene=False  # Already validated
        )
        
        if result.status == CaptureStatus.SUCCESS:
            success_count += 1
            print(f"  ✓ Captured: {output_path.name}")
        else:
            fail_count += 1
            print(f"  ✗ Failed: {result.failure_reason}")
    
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

  # Single capture:
  python scripts/capture.py --output output/frame_001.png --seed 42

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
    parser.add_argument("--data-capture", default="DataCapture_1",
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
