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
import logging
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class SyntheticDataGenerator:
    """
    Main orchestrator for synthetic data generation.
    
    Coordinates the entire pipeline:
    1. Load domain-specific configuration
    2. Initialize domain plugin (industrial, automotive, etc.)
    3. Setup UE5 scene
    4. Generate loop: randomize → validate → capture → annotate
    5. Export annotations in multiple formats
    
    Supports both UE5 rendering and mock data generation for development.
    """
    
    def __init__(self, domain, config, annotator, use_ue5: bool = False, 
                 ue5_host: str = "localhost", ue5_port: int = 30010,
                 ue5_screenshot_path: Optional[str] = None):
        """
        Initialize generator with domain and config.
        
        Args:
            domain: Domain instance (IndustrialDomain, AutomotiveDomain, etc.)
            config: Config object with settings
            annotator: Annotator instance for export
            use_ue5: If True, connect to UE5; if False, use mock data
            ue5_host: UE5 Remote Control API hostname
            ue5_port: UE5 Remote Control API port
            ue5_screenshot_path: Path where UE5 saves screenshots (default: auto-detect from UE5 project)
        """
        self.domain = domain
        self.config = config
        self.annotator = annotator
        self.use_ue5 = use_ue5
        self.ue5_bridge = None
        self.ue5_screenshot_path = Path(ue5_screenshot_path) if ue5_screenshot_path else None
        
        # Connect to UE5 if requested
        if use_ue5:
            try:
                from .ue5_bridge import UE5Bridge
                self.ue5_bridge = UE5Bridge(host=ue5_host, port=ue5_port)
                logger.info("Connected to UE5 rendering engine")
                
                # Pass UE5 bridge to domain for scene randomization
                if hasattr(domain, 'ue5_bridge'):
                    domain.ue5_bridge = self.ue5_bridge
            except Exception as e:
                logger.warning(f"Failed to connect to UE5: {e}. Falling back to mock data.")
                self.use_ue5 = False
                self.ue5_bridge = None
        
        self.stats = {
            'generated': 0,
            'rejected': 0,
            'start_time': None,
            'end_time': None,
            'mode': 'ue5' if self.use_ue5 else 'mock'
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
        
        # Check for existing images and start from next index (append mode)
        existing_images = sorted(images_dir.glob('image_*.png'))
        start_index = 0
        if existing_images:
            # Extract highest index from existing files
            last_file = existing_images[-1].stem  # e.g., "image_000004"
            start_index = int(last_file.split('_')[-1]) + 1
            logger.info(f"Found {len(existing_images)} existing images, starting from index {start_index}")
        
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
        print("Scene setup complete\n")
        
        self.stats['start_time'] = datetime.now()
        generated_count = start_index
        attempts = 0
        target_count = start_index + num_images
        max_attempts = num_images * 3  # Allow up to 3x attempts for rejections
        
        print("[2/4] Generating images...")
        while generated_count < target_count and attempts < max_attempts:
            attempts += 1
            
            # Randomize scene
            randomization_metadata = self.domain.randomize_scene()
            
            # Validate scene quality
            if not self.domain.validate_scene():
                self.stats['rejected'] += 1
                continue
            
            # Capture image (mock data for now, UE5 rendering when connected)
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
            self.stats['generated'] = generated_count - start_index
            
            # Progress update
            if (generated_count - start_index) % 10 == 0 or generated_count == target_count:
                elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
                images_generated = generated_count - start_index
                rate = images_generated / elapsed if elapsed > 0 else 0
                eta = (target_count - generated_count) / rate if rate > 0 else 0
                print(f"  Progress: {generated_count - start_index}/{num_images} | "
                      f"Rate: {rate:.1f} img/s | "
                      f"Rejected: {self.stats['rejected']} | "
                      f"ETA: {eta:.0f}s")
        
        self.stats['end_time'] = datetime.now()
        
        print("\nImage generation complete\n")
        
        # Export annotations to standard formats
        print("[3/4] Exporting annotations...")
        self._export_annotations(output_path, annotations_dir)
        print("Annotations exported\n")
        
        # Save generation metadata
        print("[4/4] Saving metadata...")
        self._save_metadata(output_path)
        print("Metadata saved\n")
        
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
        Capture image from UE5 rendering engine or generate mock data.
        
        If connected to UE5, uses the Remote Control API to call VantageCVSubsystem.
        Otherwise, generates placeholder images for development and testing.
        
        Args:
            output_path: Filesystem path where the captured image will be saved
            
        Raises:
            ValueError: If resolution configuration is invalid
            IOError: If image cannot be saved to output_path
            RuntimeError: If UE5 capture fails
        """
        if self.use_ue5 and self.ue5_bridge:
            # Use actual UE5 rendering via VantageCVSubsystem
            try:
                success = self.ue5_bridge.capture_frame(str(output_path))
                if not success:
                    raise RuntimeError("VantageCVSubsystem.CaptureFrame() returned false")
                
                # UE5 saves to its own Screenshots directory, copy to our output location
                import shutil
                
                # Auto-detect screenshot path if not configured
                if self.ue5_screenshot_path is None:
                    # Default UE5 screenshot location
                    ue5_capture_path = Path.home() / "Documents" / "Unreal Projects" / "VantageCV_Project" / "Saved" / "Screenshots" / "test_capture.png"
                    # Also try alternate common locations
                    if not ue5_capture_path.exists():
                        for candidate in [
                            Path("F:/Unreal Editor/VantageCV_Project/Saved/Screenshots/test_capture.png"),
                            Path.home() / "AppData" / "Local" / "UnrealEngine" / "VantageCV_Project" / "Saved" / "Screenshots" / "test_capture.png"
                        ]:
                            if candidate.exists():
                                ue5_capture_path = candidate
                                self.ue5_screenshot_path = candidate
                                break
                else:
                    ue5_capture_path = self.ue5_screenshot_path
                
                if ue5_capture_path.exists():
                    shutil.copy2(ue5_capture_path, output_path)
                else:
                    raise RuntimeError(f"UE5 capture file not found at {ue5_capture_path}. Set ue5_screenshot_path in constructor.")
                    
                return
            except Exception as e:
                raise RuntimeError(f"UE5 frame capture failed: {str(e)}") from e
        
        # Mock data generation (for development without UE5)
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
        """
        Export annotations to COCO and YOLO formats.
        
        Converts domain-specific annotation format to standardized formats:
        - COCO JSON: detection, segmentation, and 6D pose
        - YOLO TXT: detection only
        - Poses JSON: dedicated 6D pose file
        """
        # Load all annotation JSONs
        annotation_files = sorted(annotations_dir.glob("*.json"))
        annotations_list = []
        
        for ann_file in annotation_files:
            with open(ann_file, 'r') as f:
                ann_data = json.load(f)
                
                # Convert domain-specific format to unified COCO-compatible format
                unified_ann = self._convert_to_coco_format(ann_data)
                annotations_list.append(unified_ann)
        
        # Get image size from config
        resolution = self.config.get('camera.resolution', [1920, 1080])
        image_size = tuple(resolution) if isinstance(resolution, list) else (1920, 1080)
        
        # Export to different formats
        self.annotator.export_coco(
            annotations_list, 
            output_path / 'annotations_coco.json', 
            image_size
        )
        self.annotator.export_yolo(
            annotations_list, 
            output_path / 'annotations_yolo', 
            image_size
        )
        self.annotator.export_poses(
            annotations_list,
            output_path / 'annotations_poses.json'
        )
        
    def _convert_to_coco_format(self, domain_annotations: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert domain-specific annotation format to unified COCO-compatible format.
        
        Handles different domain formats (industrial, automotive) and normalizes
        them to a consistent structure.
        
        Args:
            domain_annotations: Raw annotations from domain.get_annotations()
            
        Returns:
            Unified annotation dict compatible with COCO exporter
        """
        unified = {
            'image_filename': domain_annotations.get('image_filename', ''),
            'timestamp': domain_annotations.get('timestamp', ''),
            'components': [],
            'defects': []
        }
        
        # Industrial domain: has 'components' and 'defects' directly
        if 'components' in domain_annotations:
            unified['components'] = domain_annotations['components']
            unified['defects'] = domain_annotations.get('defects', [])
        
        # Automotive domain: has 'vehicles' and 'pedestrians'
        elif 'vehicles' in domain_annotations:
            # Convert vehicles to components
            for vehicle in domain_annotations.get('vehicles', []):
                component = {
                    'class': vehicle['class'],
                    'bbox': vehicle['bbox'],
                    'segmentation': vehicle.get('segmentation', []),
                    'pose': vehicle.get('pose')
                }
                unified['components'].append(component)
            
            # Convert pedestrians to components
            for pedestrian in domain_annotations.get('pedestrians', []):
                component = {
                    'class': pedestrian['class'],
                    'bbox': pedestrian['bbox'],
                    'segmentation': pedestrian.get('segmentation', [])
                }
                unified['components'].append(component)
        
        return unified
        
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

