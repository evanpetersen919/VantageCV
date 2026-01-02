#!/usr/bin/env python3
"""
VantageCV Research v2 - Dataset Generation Script

Entry point for generating research-grade synthetic vehicle datasets.

Usage:
    python scripts/generate_v2.py --num-images 100 --seed 42
    python scripts/generate_v2.py --config configs/research_v2.yaml
    python scripts/generate_v2.py --dry-run  # Validate config only
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from vantagecv.research_v2 import (
    ResearchConfig,
    DatasetOrchestrator,
    ResearchLogger,
    VehicleSpawner,
)
from vantagecv.research_v2.config import load_or_create_config, TimeOfDay
from vantagecv.ue5_bridge import UE5Bridge


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="VantageCV Research v2 - Synthetic Vehicle Dataset Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate 100 images with default config
    python scripts/generate_v2.py --num-images 100
    
    # Use specific config file
    python scripts/generate_v2.py --config configs/research_v2.yaml
    
    # Generate with specific seed for reproducibility
    python scripts/generate_v2.py --num-images 50 --seed 12345
    
    # Validate configuration without generating
    python scripts/generate_v2.py --dry-run
    
    # Generate night-time dataset
    python scripts/generate_v2.py --num-images 50 --time night
""",
    )
    
    # Basic options
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=None,
        help="Path to configuration YAML file",
    )
    
    parser.add_argument(
        "--num-images", "-n",
        type=int,
        default=None,
        help="Number of images to generate (overrides config)",
    )
    
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=None,
        help="Random seed for reproducibility (overrides config)",
    )
    
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output directory (overrides config)",
    )
    
    parser.add_argument(
        "--experiment", "-e",
        type=str,
        default=None,
        help="Experiment name (overrides config)",
    )
    
    # Scene options
    parser.add_argument(
        "--time",
        choices=["day", "night"],
        default=None,
        help="Time of day (day or night)",
    )
    
    # Execution options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without generating data",
    )
    
    parser.add_argument(
        "--simulation",
        action="store_true",
        default=False,
        help="Force simulation mode even with --ue5 flag",
    )
    
    parser.add_argument(
        "--ue5",
        action="store_true",
        help="Connect to UE5 for actual rendering (default is simulation mode)",
    )
    
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test UE5 connection and vehicle visibility controls",
    )
    
    parser.add_argument(
        "--ue5-port",
        type=int,
        default=30010,
        help="UE5 Remote Control API port (default: 30010)",
    )
    
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10,
        help="Log progress every N frames",
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    
    return parser.parse_args()


def test_ue5_connection(config: ResearchConfig, port: int) -> int:
    """
    Test UE5 connection and vehicle visibility controls.
    
    This will:
    1. Connect to UE5 Remote Control API
    2. Test hiding all vehicles
    3. Test showing/positioning a few vehicles
    4. Restore original state
    """
    import time
    
    print()
    print("=" * 60)
    print("UE5 CONNECTION TEST")
    print("=" * 60)
    print()
    
    # Step 1: Connect to UE5
    print(f"[1/5] Connecting to UE5 at localhost:{port}...")
    try:
        bridge = UE5Bridge(host="localhost", port=port)
        bridge.level_name = "automobile"
        print("      ✓ Connection successful!")
    except ConnectionError as e:
        print(f"      ✗ Connection FAILED: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Is UE5 running with automobile level open?")
        print("  2. Is the Remote Control API plugin enabled?")
        print("  3. Check Edit > Project Settings > Plugins > Remote Control")
        print(f"  4. Verify port {port} is correct")
        return 1
    
    # Step 2: Test hiding all vehicles
    print()
    print("[2/5] Hiding all vehicle actors...")
    vehicle_actors = config.vehicles.vehicle_actors
    total_actors = sum(len(actors) for actors in vehicle_actors.values())
    
    hidden_count = bridge.hide_all_vehicles(vehicle_actors)
    if hidden_count == total_actors:
        print(f"      ✓ Hidden {hidden_count}/{total_actors} actors")
    else:
        print(f"      ⚠ Hidden {hidden_count}/{total_actors} actors (some may have failed)")
    
    time.sleep(0.5)  # Let UE5 update
    
    # Step 3: Test spawning a few vehicles
    print()
    print("[3/5] Spawning test vehicles...")
    
    spawner = VehicleSpawner(config.vehicles, config.scene)
    spawner.set_seed(42)
    result = spawner.spawn_vehicles(count=3)
    
    if result.success:
        print(f"      Generated {len(result.vehicles)} vehicle positions:")
        for v in result.vehicles:
            print(f"        - {v.actor_name} ({v.vehicle_class.value}) at x={v.transform.x:.1f}m, y={v.transform.y:.1f}m")
    else:
        print("      ✗ Spawn generation failed")
        return 1
    
    # Step 4: Send commands to UE5
    print()
    print("[4/5] Sending visibility/transform commands to UE5...")
    
    commands = spawner.get_ue5_spawn_commands(result.vehicles)
    success_count = bridge.execute_spawn_commands(commands)
    
    print(f"      Executed {success_count}/{len(commands)} commands")
    
    if success_count == len(commands):
        print("      ✓ All commands successful!")
    else:
        print("      ⚠ Some commands failed - check actor paths")
    
    # Step 5: Summary
    print()
    print("[5/5] Test complete!")
    print()
    print("=" * 60)
    print("RESULT: ", end="")
    if success_count > 0:
        print("SUCCESS - UE5 integration is working!")
        print()
        print("You should see 3 vehicles positioned on the road in UE5.")
        print()
        
        # Test frame capture
        print("Testing frame capture...")
        import tempfile
        test_path = Path(tempfile.gettempdir()) / "vantagecv_test_capture.png"
        
        # Calculate camera position to see spawned vehicles
        # Compute centroid of all vehicles (in cm for UE5)
        vehicle_positions = [(v.transform.x * 100, v.transform.y * 100) for v in result.vehicles]
        centroid_x = sum(p[0] for p in vehicle_positions) / len(vehicle_positions)
        centroid_y = sum(p[1] for p in vehicle_positions) / len(vehicle_positions)
        
        # Position camera behind and above the vehicles, looking at centroid
        # Camera offset: behind (negative X), elevated, centered on Y
        camera_distance = 3000  # 30 meters behind centroid
        camera_height = config.camera.height * 100  # meters to cm
        
        camera_x = centroid_x - camera_distance  # Behind the centroid
        camera_y = centroid_y  # Centered on the vehicle spread
        camera_z = camera_height
        
        # Calculate pitch to look at ground-level centroid
        import math
        dx = centroid_x - camera_x
        dz = -camera_z  # Looking down at ground level
        pitch = math.degrees(math.atan2(dz, dx))  # Negative = looking down
        
        print(f"  Camera: ({camera_x/100:.1f}m, {camera_y/100:.1f}m, {camera_z/100:.1f}m) pitch={pitch:.1f}°")
        print(f"  Target: vehicle centroid at ({centroid_x/100:.1f}m, {centroid_y/100:.1f}m)")
        
        bridge.set_capture_camera(
            x=camera_x,
            y=camera_y,
            z=camera_z,
            pitch=pitch, yaw=0, roll=0,
            fov=config.camera.fov
        )
        
        if bridge.capture_frame(str(test_path), 1920, 1080):
            print(f"  ✓ Frame captured to: {test_path}")
        else:
            print("  ⚠ Frame capture failed (DataCapture actor may need setup)")
        
        # Test annotation generation
        print("Testing annotation generation...")
        annotations = bridge.generate_annotations()
        bbox_count = len(annotations.get("bounding_boxes", []))
        if bbox_count > 0:
            print(f"  ✓ Generated {bbox_count} bounding boxes")
            for bbox in annotations["bounding_boxes"][:3]:
                print(f"    - {bbox.get('class', '?')}: ({bbox.get('x_min', 0):.0f}, {bbox.get('y_min', 0):.0f}) to ({bbox.get('x_max', 0):.0f}, {bbox.get('y_max', 0):.0f})")
        else:
            print("  ⚠ No bounding boxes generated (may need visible vehicles)")
        
        # Automatic cleanup: hide all vehicles
        print()
        print("Cleaning up vehicles...")
        try:
            # Try authoritative cleanup first
            hidden, still_visible = bridge.authoritative_vehicle_cleanup(
                "/Game/automobile.automobile:PersistentLevel.DomainRandomization_1"
            )
            print(f"  ✓ Authoritative cleanup: {hidden} vehicles hidden, {still_visible} still visible")
        except Exception as e:
            # Fallback to simple hide
            bridge.hide_all_vehicles(vehicle_actors)
            print(f"  ✓ Vehicles hidden (fallback method)")
        
        print()
        print("Test complete!")
        return 0
    else:
        print("FAILED - Check UE5 setup")
        print()
        print("Possible issues:")
        print("  - Actor names don't match (Car_1 vs car_1)")
        print("  - Level path incorrect (/Game/automobile)")
        print("  - Remote Control not responding to calls")
        return 1


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    print("=" * 60)
    print("VantageCV Research v2 - Synthetic Vehicle Dataset Generator")
    print("=" * 60)
    
    # Load or create configuration
    if args.config and args.config.exists():
        print(f"Loading config from: {args.config}")
        config = ResearchConfig.load(args.config)
    else:
        print("Using default configuration")
        config = ResearchConfig()
    
    # Apply command line overrides
    if args.num_images is not None:
        config.num_images = args.num_images
        print(f"  num_images: {args.num_images}")
    
    if args.seed is not None:
        config.random_seed = args.seed
        print(f"  seed: {args.seed}")
    
    if args.output is not None:
        config.output.base_dir = args.output
        print(f"  output: {args.output}")
    
    if args.experiment is not None:
        config.experiment_name = args.experiment
        print(f"  experiment: {args.experiment}")
    
    if args.time is not None:
        config.scene.time_of_day = TimeOfDay(args.time)
        print(f"  time_of_day: {args.time}")
    
    print()
    print(f"Experiment: {config.experiment_name}")
    print(f"Output: {config.output.base_dir}")
    print(f"Images: {config.num_images}")
    print(f"Seed: {config.random_seed}")
    print()
    
    # Validate configuration
    issues = config.validate()
    if issues:
        print("Configuration validation FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    
    print("Configuration validated successfully")
    
    # Test connection mode
    if args.test_connection:
        return test_ue5_connection(config, args.ue5_port)
    
    if args.dry_run:
        print("\n[DRY RUN] Exiting without generating data")
        return 0
    
    # Create orchestrator
    ue5_connection = None
    if args.ue5 and not args.simulation:
        print("\nConnecting to UE5...")
        try:
            from vantagecv.ue5_bridge import UE5Bridge
            ue5_connection = UE5Bridge(port=args.ue5_port)
            
            # Test connection
            if not ue5_connection.test_connection():
                print("  WARNING: UE5 connection test failed - check that editor is running")
                print("  Falling back to simulation mode")
                ue5_connection = None
            else:
                print(f"  Connected to UE5 on port {args.ue5_port}")
        except Exception as e:
            print(f"  ERROR: Failed to connect to UE5: {e}")
            print("  Falling back to simulation mode")
            ue5_connection = None
    else:
        print("\nRunning in simulation mode (no UE5)")
    
    print()
    print("-" * 60)
    print("Starting dataset generation...")
    print("-" * 60)
    print()
    
    orchestrator = DatasetOrchestrator(
        config=config,
        ue5_connection=ue5_connection,
    )
    
    # Generate dataset
    try:
        stats = orchestrator.generate_dataset(
            progress_interval=args.progress_interval,
        )
        
        # Print final summary
        print()
        print("=" * 60)
        print("GENERATION COMPLETE")
        print("=" * 60)
        print()
        print(f"Images generated: {stats.images_generated}")
        print(f"Images failed: {stats.images_failed}")
        print(f"Total vehicles: {stats.total_vehicles}")
        print(f"Avg vehicles/image: {stats.total_vehicles / max(stats.images_generated, 1):.1f}")
        print()
        print("Class distribution:")
        for cls, count in stats.class_counts.items():
            pct = count / max(stats.total_vehicles, 1) * 100
            print(f"  {cls}: {count} ({pct:.1f}%)")
        print()
        print(f"Output directory: {config.output.base_dir}")
        print(f"  Images: {config.output.images_dir}")
        print(f"  Annotations: {config.output.annotations_dir}")
        print(f"  Logs: {config.output.logs_dir}")
        print(f"  Metadata: {config.output.metadata_dir}")
        
        if stats.images_failed > 0:
            print()
            print("Failures:")
            for reason, count in stats.failure_counts.items():
                print(f"  {reason}: {count}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nGeneration interrupted by user")
        return 130
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
