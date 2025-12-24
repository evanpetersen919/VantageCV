#==============================================================================
# VantageCV - Data Generation Script
#==============================================================================
# File: generate.py
# Description: Command-line script to generate synthetic datasets
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import argparse
import sys
import importlib
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.config import Config
from vantagecv.generator import SyntheticDataGenerator
from vantagecv.annotator import AnnotationExporter


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='VantageCV: Generate synthetic computer vision datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 1000 industrial PCB images
  python scripts/generate.py --config configs/industrial.yaml --num-images 1000
  
  # Generate automotive dataset with YOLO format
  python scripts/generate.py --config configs/automotive.yaml --format yolo --num-images 5000
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to domain configuration YAML file (e.g., configs/industrial.yaml)'
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
        default=None,
        help='Output directory (default: data/synthetic/<domain_name>)'
    )
    
    parser.add_argument(
        '--format',
        type=str,
        choices=['coco', 'yolo', 'both'],
        default='both',
        help='Annotation export format (default: both)'
    )
    
    parser.add_argument(
        '--use-ue5',
        action='store_true',
        help='Use Unreal Engine 5 for rendering (requires UE5 running with Remote Control API)'
    )
    
    parser.add_argument(
        '--ue5-host',
        type=str,
        default='localhost',
        help='UE5 Remote Control API hostname (default: localhost)'
    )
    
    parser.add_argument(
        '--ue5-port',
        type=int,
        default=30010,
        help='UE5 Remote Control API port (default: 30010)'
    )
    
    return parser.parse_args()


def main():
    """Main data generation pipeline."""
    args = parse_args()
    
    print("\n" + "="*60)
    print("VantageCV Synthetic Data Generation")
    print("="*60 + "\n")
    
    # Load configuration
    print(f"Loading configuration: {args.config}")
    config = Config(args.config)
    domain_name = config.get('domain.name', 'unknown')
    print(f"Domain: {domain_name}\n")
    
    # Determine output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = f"data/synthetic/{domain_name}"
    
    # Initialize domain dynamically based on config
    print(f"Initializing {domain_name} domain...")
    domain_module = importlib.import_module(f'domains.{domain_name}')
    domain_class_name = ''.join(word.capitalize() for word in domain_name.split('_')) + 'Domain'
    domain_class = getattr(domain_module, domain_class_name)
    domain = domain_class(config.data)
    
    # Initialize annotation exporter
    class_names = domain.get_object_list()
    annotator = AnnotationExporter(class_names)
    
    # Initialize generator
    generator = SyntheticDataGenerator(
        domain=domain,
        config=config,
        annotator=annotator,
        use_ue5=args.use_ue5,
        ue5_host=args.ue5_host,
        ue5_port=args.ue5_port
    )
    
    # Show rendering mode
    if args.use_ue5:
        print(f"Rendering mode: Unreal Engine 5 ({args.ue5_host}:{args.ue5_port})")
    else:
        print("Rendering mode: Mock data (for development)")
    
    # Generate dataset
    try:
        stats = generator.generate_dataset(
            num_images=args.num_images,
            output_dir=output_dir
        )
        
        print(f"\n{'='*60}")
        print("Dataset generation successful!")
        print(f"{'='*60}")
        print(f"Location: {output_dir}/")
        print(f"  - images/           : {stats['generated']} images")
        print(f"  - annotations/      : JSON metadata files")
        print(f"  - annotations_coco.json")
        print(f"  - annotations_yolo/ : YOLO format labels")
        print(f"  - metadata.json     : Generation statistics")
        print(f"{'='*60}\n")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nGeneration interrupted by user.")
        return 1
        
    except Exception as e:
        print(f"\n\nError during generation: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

