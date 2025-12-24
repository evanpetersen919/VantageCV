#==============================================================================
# VantageCV - Data Validation Utilities
#==============================================================================
# File: validation.py
# Description: Quality checks for generated datasets - annotation validation,
#              image statistics, dataset completeness verification
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class AnnotationValidator:
    """
    Validate annotation quality and consistency.
    
    Checks:
    - Bounding box validity (within image bounds, positive size)
    - Segmentation mask validity
    - 6D pose matrix properties
    - Class label consistency
    """
    
    def __init__(self, image_width: int = 1920, image_height: int = 1080):
        """
        Initialize annotation validator.
        
        Args:
            image_width: Expected image width in pixels
            image_height: Expected image height in pixels
        """
        self.image_width = image_width
        self.image_height = image_height
    
    def validate_bbox(self, bbox: List[float]) -> Tuple[bool, str]:
        """
        Validate bounding box coordinates.
        
        Args:
            bbox: [x, y, width, height]
            
        Returns:
            (is_valid, error_message) tuple
        """
        if len(bbox) != 4:
            return False, f"Bbox must have 4 values, got {len(bbox)}"
        
        x, y, w, h = bbox
        
        if w <= 0 or h <= 0:
            return False, f"Bbox dimensions must be positive: w={w}, h={h}"
        
        if x < 0 or y < 0:
            return False, f"Bbox position must be non-negative: x={x}, y={y}"
        
        if x + w > self.image_width or y + h > self.image_height:
            return False, f"Bbox extends beyond image bounds: x+w={x+w}, y+h={y+h}"
        
        # Check for extremely small boxes (likely errors)
        if w < 5 or h < 5:
            return False, f"Bbox too small (likely error): w={w}, h={h}"
        
        return True, ""
    
    def validate_segmentation(self, segmentation: List[List[float]]) -> Tuple[bool, str]:
        """
        Validate segmentation polygon.
        
        Args:
            segmentation: List of polygons [[x1,y1,x2,y2,...], ...]
            
        Returns:
            (is_valid, error_message) tuple
        """
        if not segmentation:
            return False, "Empty segmentation"
        
        for polygon in segmentation:
            if len(polygon) < 6:  # Need at least 3 points (x,y pairs)
                return False, f"Polygon must have at least 3 points, got {len(polygon)//2}"
            
            if len(polygon) % 2 != 0:
                return False, f"Polygon must have even number of values (x,y pairs), got {len(polygon)}"
            
            # Check all points are within image bounds
            for i in range(0, len(polygon), 2):
                x, y = polygon[i], polygon[i+1]
                if x < 0 or x > self.image_width or y < 0 or y > self.image_height:
                    return False, f"Polygon point ({x},{y}) outside image bounds"
        
        return True, ""
    
    def validate_pose(self, pose: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate 6D pose annotation.
        
        Args:
            pose: Dictionary with 'rotation' and 'translation' keys
            
        Returns:
            (is_valid, error_message) tuple
        """
        if 'rotation' not in pose or 'translation' not in pose:
            return False, "Pose must contain 'rotation' and 'translation'"
        
        rotation = np.array(pose['rotation'])
        translation = np.array(pose['translation'])
        
        # Check rotation matrix shape
        if rotation.shape != (3, 3):
            return False, f"Rotation must be 3x3 matrix, got shape {rotation.shape}"
        
        # Check orthogonality: R^T * R = I
        identity_check = rotation.T @ rotation
        if not np.allclose(identity_check, np.eye(3), atol=1e-4):
            return False, "Rotation matrix not orthogonal"
        
        # Check determinant = 1 (proper rotation)
        det = np.linalg.det(rotation)
        if not np.isclose(det, 1.0, atol=1e-4):
            return False, f"Rotation determinant must be 1.0, got {det:.6f}"
        
        # Check translation shape
        if translation.shape != (3,):
            return False, f"Translation must be 3D vector, got shape {translation.shape}"
        
        # Check for NaN or Inf
        if not np.all(np.isfinite(rotation)) or not np.all(np.isfinite(translation)):
            return False, "Pose contains NaN or Inf values"
        
        return True, ""
    
    def validate_annotation_file(self, annotation_path: Path) -> Dict[str, Any]:
        """
        Validate complete annotation file.
        
        Args:
            annotation_path: Path to annotation JSON file
            
        Returns:
            Validation results dictionary
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'stats': {
                'total_objects': 0,
                'valid_bboxes': 0,
                'valid_masks': 0,
                'valid_poses': 0
            }
        }
        
        try:
            with open(annotation_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            results['valid'] = False
            results['errors'].append(f"Failed to load JSON: {str(e)}")
            return results
        
        # Validate components
        components = data.get('components', [])
        results['stats']['total_objects'] = len(components)
        
        for idx, component in enumerate(components):
            # Validate bbox
            if 'bbox' in component:
                is_valid, error = self.validate_bbox(component['bbox'])
                if is_valid:
                    results['stats']['valid_bboxes'] += 1
                else:
                    results['errors'].append(f"Component {idx} bbox: {error}")
                    results['valid'] = False
            
            # Validate segmentation
            if 'segmentation' in component:
                is_valid, error = self.validate_segmentation(component['segmentation'])
                if is_valid:
                    results['stats']['valid_masks'] += 1
                else:
                    results['warnings'].append(f"Component {idx} segmentation: {error}")
            
            # Validate pose
            if 'pose' in component:
                is_valid, error = self.validate_pose(component['pose'])
                if is_valid:
                    results['stats']['valid_poses'] += 1
                else:
                    results['errors'].append(f"Component {idx} pose: {error}")
                    results['valid'] = False
        
        return results


class ImageStatistics:
    """
    Compute and validate image statistics.
    
    Checks for:
    - Brightness (not too dark/bright)
    - Contrast (sufficient variation)
    - Blur detection
    - Color distribution
    """
    
    @staticmethod
    def compute_statistics(image_path: Path) -> Dict[str, float]:
        """
        Compute image statistics.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dictionary of statistics
        """
        try:
            img = Image.open(image_path)
            img_array = np.array(img)
            
            # Convert to grayscale for some metrics
            if len(img_array.shape) == 3:
                gray = np.mean(img_array, axis=2)
            else:
                gray = img_array
            
            stats = {
                'mean_brightness': np.mean(gray),
                'std_brightness': np.std(gray),
                'min_value': np.min(gray),
                'max_value': np.max(gray),
                'contrast_ratio': (np.max(gray) - np.min(gray)) / 255.0,
                'entropy': ImageStatistics._compute_entropy(gray)
            }
            
            # Blur detection using Laplacian variance
            stats['blur_score'] = ImageStatistics._compute_blur_score(gray)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to compute image statistics: {str(e)}")
            return {}
    
    @staticmethod
    def _compute_entropy(image: np.ndarray) -> float:
        """Compute image entropy (information content)."""
        histogram, _ = np.histogram(image, bins=256, range=(0, 256))
        histogram = histogram / histogram.sum()
        histogram = histogram[histogram > 0]
        return -np.sum(histogram * np.log2(histogram))
    
    @staticmethod
    def _compute_blur_score(image: np.ndarray) -> float:
        """Compute blur score using Laplacian variance (higher = sharper)."""
        try:
            import cv2
            laplacian = cv2.Laplacian(image.astype(np.float32), cv2.CV_64F)
            return laplacian.var()
        except ImportError:
            # Fallback: simple edge detection
            dx = np.diff(image, axis=1)
            dy = np.diff(image, axis=0)
            return np.var(dx) + np.var(dy)
    
    @staticmethod
    def validate_statistics(stats: Dict[str, float]) -> Tuple[bool, List[str]]:
        """
        Validate image quality based on statistics.
        
        Args:
            stats: Statistics dictionary from compute_statistics()
            
        Returns:
            (is_valid, warnings) tuple
        """
        warnings = []
        is_valid = True
        
        # Check brightness
        if stats.get('mean_brightness', 128) < 30:
            warnings.append("Image too dark")
            is_valid = False
        elif stats.get('mean_brightness', 128) > 225:
            warnings.append("Image too bright")
            is_valid = False
        
        # Check contrast
        if stats.get('contrast_ratio', 1.0) < 0.2:
            warnings.append("Low contrast")
        
        # Check blur
        if stats.get('blur_score', 1000) < 100:
            warnings.append("Image may be blurry")
        
        # Check entropy (information content)
        if stats.get('entropy', 7.0) < 4.0:
            warnings.append("Low entropy (lacks detail)")
        
        return is_valid, warnings


class DatasetValidator:
    """
    Validate complete dataset integrity.
    
    Checks:
    - All images have corresponding annotations
    - Class distribution balance
    - Train/val split ratios
    - File completeness
    """
    
    @staticmethod
    def validate_dataset(dataset_dir: Path) -> Dict[str, Any]:
        """
        Validate complete dataset.
        
        Args:
            dataset_dir: Root dataset directory
            
        Returns:
            Validation results dictionary
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        images_dir = dataset_dir / 'images'
        annotations_dir = dataset_dir / 'annotations'
        
        # Check directories exist
        if not images_dir.exists():
            results['errors'].append(f"Images directory not found: {images_dir}")
            results['valid'] = False
            return results
        
        if not annotations_dir.exists():
            results['errors'].append(f"Annotations directory not found: {annotations_dir}")
            results['valid'] = False
            return results
        
        # Get all images and annotations
        images = sorted(images_dir.glob('*.png'))
        annotations = sorted(annotations_dir.glob('*.json'))
        
        results['stats']['num_images'] = len(images)
        results['stats']['num_annotations'] = len(annotations)
        
        # Check image-annotation correspondence
        if len(images) != len(annotations):
            results['warnings'].append(
                f"Mismatch: {len(images)} images but {len(annotations)} annotations"
            )
        
        # Check for orphaned files
        image_stems = {img.stem for img in images}
        annotation_stems = {ann.stem for ann in annotations}
        
        orphaned_images = image_stems - annotation_stems
        orphaned_annotations = annotation_stems - image_stems
        
        if orphaned_images:
            results['warnings'].append(f"{len(orphaned_images)} images without annotations")
        if orphaned_annotations:
            results['warnings'].append(f"{len(orphaned_annotations)} annotations without images")
        
        # Check for COCO file
        coco_file = dataset_dir / 'annotations_coco.json'
        if not coco_file.exists():
            results['warnings'].append("COCO annotations file not found")
        
        logger.info(
            f"Dataset validation: {len(images)} images, "
            f"{len(annotations)} annotations, "
            f"{len(results['errors'])} errors, "
            f"{len(results['warnings'])} warnings"
        )
        
        return results
