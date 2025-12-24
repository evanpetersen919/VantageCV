#==============================================================================
# VantageCV - Synthetic Data Generator
#==============================================================================
# File: generator.py
# Description: Main orchestrator for synthetic data generation pipeline
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import numpy as np
from PIL import Image


class SyntheticDataGenerator:
    """
    Main orchestrator for synthetic data generation.
    
    Coordinates the entire pipeline:
    1. Load domain-specific configuration
    2. Initialize domain plugin (industrial, automotive, etc.)
    3. Setup UE5 scene
    4. Generate loop: randomize → validate → capture → annotate
    5. Export annotations in multiple formats
    """
    
    def __init__(self, domain, config, annotator):
        """
        Initialize generator with domain and config.
        
        Args:
            domain: Domain instance (IndustrialDomain, AutomotiveDomain, etc.)
            config: Config object with settings
            annotator: Annotator instance for export
        """
        self.domain = domain
        self.config = config
        self.annotator = annotator
        self.stats = {
            'generated': 0,
            'rejected': 0,
            'start_time': None,
            'end_time': None
        }
        
    def generate_dataset(self, num_images: int, output_dir: str) -> Dict[str, Any]:
        """
        Generate synthetic dataset with N images.
        
        Pipeline for each image:
        1. Randomize scene parameters
        2. Validate scene quality
        3. Capture image (from UE5)
        4. Extract annotations
        5. Save image and metadata
        
        Args:
            num_images: Number of images to generate
            output_dir: Directory to save images and annotations
            
        Returns:
            Generation statistics and metadata
        """
        output_path = Path(output_dir)
        images_dir = output_path / 'images'
        annotations_dir = output_path / 'annotations'
        
        # Create output directories
        images_dir.mkdir(parents=True, exist_ok=True)
        annotations_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"VantageCV Synthetic Data Generation")
        print(f"{'='*60}")
        print(f"Domain: {self.domain.domain_name}")
        print(f"Target images: {num_images}")
        print(f"Output: {output_path}")
        print(f"{'='*60}\n")
        
        # Setup scene once
        print("[1/4] Setting up scene...")
        if not self.domain.setup_scene():
            raise RuntimeError("Failed to setup scene")
        print("✓ Scene setup complete\n")
        
        self.stats['start_time'] = datetime.now()
        generated_count = 0
        attempts = 0
        max_attempts = num_images * 3  # Allow up to 3x attempts for rejections
        
        print("[2/4] Generating images...")
        while generated_count < num_images and attempts < max_attempts:
            attempts += 1
            
            # Randomize scene
            randomization_metadata = self.domain.randomize_scene()
            
            # Validate scene quality
            if not self.domain.validate_scene():
                self.stats['rejected'] += 1
                continue
            
            # Capture image (TODO: Replace with actual UE5 capture)
            image_filename = f"image_{generated_count:06d}.png"
            image_path = images_dir / image_filename
            self._capture_image(image_path)
            
            # Extract ground truth annotations
            annotations = self.domain.get_annotations()
            annotations['image_filename'] = image_filename
            annotations['randomization'] = randomization_metadata
            annotations['timestamp'] = datetime.now().isoformat()
            
            # Save annotation metadata
            annotation_file = annotations_dir / f"image_{generated_count:06d}.json"
            with open(annotation_file, 'w') as f:
                json.dump(annotations, f, indent=2)
            
            generated_count += 1
            self.stats['generated'] = generated_count
            
            # Progress update
            if generated_count % 10 == 0 or generated_count == num_images:
                elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
                rate = generated_count / elapsed if elapsed > 0 else 0
                eta = (num_images - generated_count) / rate if rate > 0 else 0
                print(f"  Progress: {generated_count}/{num_images} | "
                      f"Rate: {rate:.1f} img/s | "
                      f"Rejected: {self.stats['rejected']} | "
                      f"ETA: {eta:.0f}s")
        
        self.stats['end_time'] = datetime.now()
        
        print(f"\n✓ Image generation complete\n")
        
        # Export annotations to standard formats
        print("[3/4] Exporting annotations...")
        self._export_annotations(output_path, annotations_dir)
        print("✓ Annotations exported\n")
        
        # Save generation metadata
        print("[4/4] Saving metadata...")
        self._save_metadata(output_path)
        print("✓ Metadata saved\n")
        
        # Print summary
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        print(f"{'='*60}")
        print(f"Generation Complete!")
        print(f"{'='*60}")
        print(f"Images generated: {self.stats['generated']}")
        print(f"Scenes rejected: {self.stats['rejected']}")
        print(f"Total duration: {duration:.1f}s")
        print(f"Average rate: {self.stats['generated']/duration:.2f} img/s")
        print(f"{'='*60}\n")
        
        return self.stats
    
    def _capture_image(self, output_path: Path) -> None:
        """
        Capture image from UE5 rendering engine.
        
        Currently generates placeholder images for development and testing.
        Will be replaced with actual UE5 C++ plugin communication.
        
        Args:
            output_path: Filesystem path where the captured image will be saved
            
        Raises:
            ValueError: If resolution configuration is invalid
            IOError: If image cannot be saved to output_path
        
        TODO: Implement UE5 bridge: self.ue5_bridge.capture_frame(str(output_path))
        """
        # Parse resolution from config (supports both list and dict formats)
        resolution = self.config.get('camera.resolution', [1920, 1080])
        
        if isinstance(resolution, dict):
            width = resolution.get('width', 1920)
            height = resolution.get('height', 1080)
        elif isinstance(resolution, (list, tuple)) and len(resolution) == 2:
            width, height = resolution[0], resolution[1]
        else:
            raise ValueError(
                f"Invalid resolution format: {resolution}. "
                f"Expected list [width, height] or dict {{width: X, height: Y}}"
            )
        
        # Validate resolution values
        if not (isinstance(width, int) and isinstance(height, int)):
            raise ValueError(f"Resolution dimensions must be integers: width={width}, height={height}")
        if width <= 0 or height <= 0:
            raise ValueError(f"Resolution dimensions must be positive: width={width}, height={height}")
        
        # Generate placeholder image (RGB, 8-bit per channel)
        try:
            dummy_image = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            Image.fromarray(dummy_image).save(output_path)
        except Exception as e:
            raise IOError(f"Failed to save image to {output_path}: {str(e)}") from e
    
    def _export_annotations(self, output_path: Path, annotations_dir: Path) -> None:
        """Export annotations to COCO and YOLO formats."""
        # Load all annotation JSONs
        annotation_files = sorted(annotations_dir.glob("*.json"))
        annotations_list = []
        
        for ann_file in annotation_files:
            with open(ann_file, 'r') as f:
                annotations_list.append(json.load(f))
        
        # Get image size from config
        resolution = self.config.get('camera.resolution', [1920, 1080])
        image_size = tuple(resolution) if isinstance(resolution, list) else (1920, 1080)
        
        # Export to different formats
        self.annotator.export_coco(annotations_list, output_path / 'annotations_coco.json', image_size)
        self.annotator.export_yolo(annotations_list, output_path / 'annotations_yolo', image_size)
        
    def _save_metadata(self, output_path: Path) -> None:
        """Save generation metadata and configuration."""
        metadata = {
            'domain': self.domain.domain_name,
            'config': self.config.data,
            'stats': {
                'generated': self.stats['generated'],
                'rejected': self.stats['rejected'],
                'start_time': self.stats['start_time'].isoformat(),
                'end_time': self.stats['end_time'].isoformat(),
                'duration_seconds': (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            },
            'version': 'VantageCV v0.1.0'
        }
        
        with open(output_path / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)

