#==============================================================================
# VantageCV - Data Generation Script
#==============================================================================
# File: generate.py
# Description: Generate synthetic datasets using UE5
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

"""Generate synthetic training data using VantageCV."""

import argparse
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv import load_config, SyntheticDataGenerator
from vantagecv.utils import setup_logging
import logging


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate synthetic training data with VantageCV'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to domain configuration YAML file'
    )
    
    parser.add_argument(
        '--num-images',
        type=int,
        default=1000,
        help='Number of images to generate (default: 1000)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/synthetic',
        help='Output directory for generated data'
    )
    
    parser.add_argument(
        '--ue5-host',
        type=str,
        default='localhost',
        help='UE5 Remote Control API host'
    )
    
    parser.add_argument(
        '--ue5-port',
        type=int,
        default=30010,
        help='UE5 Remote Control API port'
    )
    
    parser.add_argument(
        '--format',
        type=str,
        choices=['coco', 'yolo'],
        default='coco',
        help='Annotation format'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    return parser.parse_args()


def main():
    """Main data generation function."""
    args = parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("VantageCV Data Generation")
    logger.info("=" * 60)
    
    # Load configuration
    logger.info(f"Loading config from {args.config}")
    config = load_config(args.config)
    
    # Create generator
    generator = SyntheticDataGenerator(
        config=config,
        output_dir=Path(args.output_dir)
    )
    
    # Connect to UE5
    logger.info(f"Connecting to UE5 at {args.ue5_host}:{args.ue5_port}")
    if not generator.connect_to_ue5(args.ue5_host, args.ue5_port):
        logger.error("Failed to connect to UE5")
        return 1
    
    # Generate dataset
    logger.info(f"Generating {args.num_images} images...")
    try:
        generator.generate_dataset(
            num_images=args.num_images,
            annotation_format=args.format
        )
        logger.info("\n" + "=" * 60)
        logger.info("Generation complete!")
        logger.info(f"Output saved to: {args.output_dir}")
        logger.info("=" * 60)
        return 0
        
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

