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
)
from vantagecv.research_v2.config import load_or_create_config, TimeOfDay


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
        default=True,
        help="Run in simulation mode (no UE5 connection)",
    )
    
    parser.add_argument(
        "--ue5",
        action="store_true",
        help="Connect to UE5 for actual rendering",
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
    
    if args.dry_run:
        print("\n[DRY RUN] Exiting without generating data")
        return 0
    
    # Create orchestrator
    ue5_connection = None
    if args.ue5 and not args.simulation:
        print("\nConnecting to UE5...")
        # TODO: Implement actual UE5 connection
        # ue5_connection = UE5RemoteConnection(config.ue5_host, config.ue5_port)
        print("  [Not implemented - using simulation mode]")
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
