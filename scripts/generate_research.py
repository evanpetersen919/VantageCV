#!/usr/bin/env python
#==============================================================================
# VantageCV Research - Dataset Generation Script
#==============================================================================
# Academic-grade synthetic data generation for vehicle perception
# Designed for publication-quality datasets and ablation studies
#==============================================================================

import argparse
import sys
import yaml
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.research.generator import ResearchDataGenerator


def setup_logging(verbose: bool = False, log_file: str = None):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def load_config(config_path: str) -> dict:
    """Load YAML configuration file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    config['config_file'] = config_path
    return config


def main():
    parser = argparse.ArgumentParser(
        description='VantageCV Research - Academic-Grade Synthetic Data Generation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 1000 images with default research config
  python generate_research.py --num-images 1000
  
  # Generate with specific seed for reproducibility
  python generate_research.py --num-images 500 --seed 42
  
  # Generate to custom output directory
  python generate_research.py --num-images 1000 --output ./dataset_v1
  
  # Verbose output with logging
  python generate_research.py --num-images 100 --verbose --log-file generation.log
        """
    )
    
    parser.add_argument(
        '--num-images', '-n',
        type=int,
        default=1000,
        help='Number of images to generate (default: 1000)'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default='configs/research.yaml',
        help='Path to configuration file (default: configs/research.yaml)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output directory (default: data/synthetic/research_{timestamp})'
    )
    
    parser.add_argument(
        '--seed', '-s',
        type=int,
        default=None,
        help='Random seed for reproducibility'
    )
    
    parser.add_argument(
        '--ue5-host',
        type=str,
        default='localhost',
        help='UE5 Remote Control API host (default: localhost)'
    )
    
    parser.add_argument(
        '--ue5-port',
        type=int,
        default=30010,
        help='UE5 Remote Control API port (default: 30010)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        default=None,
        help='Log file path'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose, args.log_file)
    logger = logging.getLogger(__name__)
    
    # Load configuration
    try:
        config = load_config(args.config)
        logger.info(f"Loaded configuration from {args.config}")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    # Set output directory - use fixed "test" folder
    if args.output:
        output_dir = args.output
    else:
        output_dir = "data/synthetic/test"
    
    # Print banner
    print("\n" + "="*70)
    print("VantageCV Research - Academic-Grade Synthetic Data Generation")
    print("="*70)
    print(f"Config: {args.config}")
    print(f"Images: {args.num_images}")
    print(f"Output: {output_dir}")
    print(f"Seed: {args.seed if args.seed else 'random'}")
    print(f"UE5: {args.ue5_host}:{args.ue5_port}")
    print("="*70 + "\n")
    
    # Create generator
    try:
        generator = ResearchDataGenerator(
            config=config,
            output_dir=output_dir,
            ue5_host=args.ue5_host,
            ue5_port=args.ue5_port,
            seed=args.seed
        )
    except Exception as e:
        logger.error(f"Failed to initialize generator: {e}")
        print(f"\nError: {e}")
        print("Make sure UE5 is running with the automobile level loaded.")
        sys.exit(1)
    
    # Generate dataset
    try:
        results = generator.generate(args.num_images)
        
        print("\n" + "="*70)
        print("GENERATION COMPLETE")
        print("="*70)
        print(f"Images generated: {results['generated']}")
        print(f"Scenes rejected: {results['rejected']}")
        print(f"Output directory: {results['output_dir']}")
        print("\nExported annotations:")
        for format_name, path in results['annotation_paths'].items():
            print(f"  - {format_name}: {path}")
        print("="*70 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nGeneration interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
