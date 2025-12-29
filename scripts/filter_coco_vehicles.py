"""
VantageCV - COCO Vehicle Subset Filter

File: filter_coco_vehicles.py
Description: Extract vehicle-only subset from COCO for automotive domain evaluation
Author: Evan Petersen
Date: December 2025
"""

import json
from pathlib import Path
from typing import Dict, List, Set
import shutil
from collections import defaultdict


VEHICLE_CLASSES = {
    'bicycle': 2,
    'car': 3,
    'motorcycle': 4,
    'bus': 6,
    'truck': 8
}


def filter_coco_vehicles(
    coco_dir: Path,
    output_dir: Path,
    split: str = 'val2017'
) -> None:
    """
    Filter COCO dataset to only vehicle classes.
    
    Args:
        coco_dir: Path to COCO dataset root
        output_dir: Path to save filtered dataset
        split: Dataset split to filter (train2017, val2017, test2017)
    """
    coco_dir = Path(coco_dir)
    output_dir = Path(output_dir)
    
    # Load annotations
    anno_file = coco_dir / 'annotations' / f'instances_{split}.json'
    print(f"Loading {anno_file}...")
    
    with open(anno_file, 'r') as f:
        coco_data = json.load(f)
    
    # Get vehicle category IDs
    vehicle_cat_ids = set(VEHICLE_CLASSES.values())
    
    # Filter categories
    filtered_categories = [
        cat for cat in coco_data['categories']
        if cat['id'] in vehicle_cat_ids
    ]
    
    # Filter annotations
    print(f"Filtering annotations for {len(vehicle_cat_ids)} vehicle classes...")
    filtered_annotations = [
        anno for anno in coco_data['annotations']
        if anno['category_id'] in vehicle_cat_ids
    ]
    
    # Get image IDs that contain vehicles
    vehicle_image_ids = set(anno['image_id'] for anno in filtered_annotations)
    
    # Filter images
    filtered_images = [
        img for img in coco_data['images']
        if img['id'] in vehicle_image_ids
    ]
    
    print(f"\nFiltering results:")
    print(f"  Categories: {len(coco_data['categories'])} -> {len(filtered_categories)}")
    print(f"  Annotations: {len(coco_data['annotations'])} -> {len(filtered_annotations)}")
    print(f"  Images: {len(coco_data['images'])} -> {len(filtered_images)}")
    
    # Count annotations per class
    class_counts = defaultdict(int)
    for anno in filtered_annotations:
        cat_id = anno['category_id']
        cat_name = next(c['name'] for c in filtered_categories if c['id'] == cat_id)
        class_counts[cat_name] += 1
    
    print(f"\nAnnotations per class:")
    for class_name in sorted(VEHICLE_CLASSES.keys()):
        print(f"  {class_name}: {class_counts[class_name]}")
    
    # Create filtered annotation file
    filtered_data = {
        'info': coco_data['info'],
        'licenses': coco_data['licenses'],
        'categories': filtered_categories,
        'images': filtered_images,
        'annotations': filtered_annotations
    }
    
    # Save filtered annotations
    output_anno_dir = output_dir / 'annotations'
    output_anno_dir.mkdir(parents=True, exist_ok=True)
    
    output_anno_file = output_anno_dir / f'instances_vehicles_{split}.json'
    print(f"\nSaving filtered annotations to {output_anno_file}...")
    
    with open(output_anno_file, 'w') as f:
        json.dump(filtered_data, f)
    
    # Copy image files
    output_images_dir = output_dir / f'{split}_vehicles'
    output_images_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nCopying {len(filtered_images)} images to {output_images_dir}...")
    
    source_images_dir = coco_dir / split
    copied_count = 0
    
    for img_info in filtered_images:
        source_path = source_images_dir / img_info['file_name']
        dest_path = output_images_dir / img_info['file_name']
        
        if source_path.exists():
            shutil.copy2(source_path, dest_path)
            copied_count += 1
            
            if copied_count % 100 == 0:
                print(f"  Copied {copied_count}/{len(filtered_images)} images...", end='\r')
    
    print(f"\nCopied {copied_count} images successfully")
    
    # Create summary file
    summary = {
        'dataset': 'COCO Vehicles Subset',
        'split': split,
        'vehicle_classes': VEHICLE_CLASSES,
        'total_categories': len(filtered_categories),
        'total_images': len(filtered_images),
        'total_annotations': len(filtered_annotations),
        'annotations_per_class': dict(class_counts),
        'output_structure': {
            'annotations': str(output_anno_file),
            'images': str(output_images_dir)
        }
    }
    
    summary_file = output_dir / f'summary_{split}_vehicles.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nSummary saved to {summary_file}")
    print("\n" + "="*60)
    print("COCO Vehicles filtering complete!")
    print("="*60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Filter COCO dataset to vehicle classes only")
    parser.add_argument(
        '--coco-dir',
        type=str,
        default='data/coco',
        help='Path to COCO dataset root'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/coco_vehicles',
        help='Path to save filtered dataset'
    )
    parser.add_argument(
        '--split',
        type=str,
        default='val2017',
        choices=['train2017', 'val2017', 'test2017'],
        help='Dataset split to filter'
    )
    
    args = parser.parse_args()
    
    filter_coco_vehicles(
        coco_dir=Path(args.coco_dir),
        output_dir=Path(args.output_dir),
        split=args.split
    )
