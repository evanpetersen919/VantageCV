#==============================================================================
# VantageCV Research - Annotation Exporters
#==============================================================================
# Multi-format annotation export for research compatibility
# Supports COCO, KITTI, and custom research formats
#==============================================================================

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class BoundingBox2D:
    """2D bounding box annotation."""
    x: float
    y: float
    width: float
    height: float
    
    def to_coco(self) -> List[float]:
        """COCO format: [x, y, width, height]"""
        return [self.x, self.y, self.width, self.height]
    
    def to_yolo(self, img_width: int, img_height: int) -> Tuple[float, float, float, float]:
        """YOLO format: (cx, cy, w, h) normalized"""
        cx = (self.x + self.width / 2) / img_width
        cy = (self.y + self.height / 2) / img_height
        w = self.width / img_width
        h = self.height / img_height
        return (cx, cy, w, h)
    
    def to_kitti(self) -> Tuple[float, float, float, float]:
        """KITTI format: (x1, y1, x2, y2)"""
        return (self.x, self.y, self.x + self.width, self.y + self.height)


@dataclass
class BoundingBox3D:
    """3D bounding box annotation in camera coordinates."""
    x: float  # Center x in camera coordinates
    y: float  # Center y  
    z: float  # Center z (depth)
    width: float   # Object width
    height: float  # Object height
    length: float  # Object length
    rotation_y: float  # Yaw rotation
    
    def to_kitti(self) -> Dict:
        """KITTI 3D format."""
        return {
            'location': [self.x, self.y, self.z],
            'dimensions': [self.height, self.width, self.length],
            'rotation_y': self.rotation_y
        }


@dataclass
class InstanceAnnotation:
    """
    Complete per-instance annotation.
    
    Comprehensive annotation for research-grade datasets including
    all required fields for detection, segmentation, and tracking tasks.
    """
    instance_id: int
    class_name: str
    class_id: int
    bbox_2d: BoundingBox2D
    bbox_3d: Optional[BoundingBox3D] = None
    segmentation: Optional[List[List[float]]] = None  # Polygon points
    
    # Occlusion and visibility
    occlusion_ratio: float = 1.0
    is_occluded: bool = False
    is_truncated: bool = False
    truncation_ratio: float = 0.0
    occlusion_source: str = "none"
    
    # Motion (for tracking)
    velocity: Optional[Tuple[float, float, float]] = None
    is_moving: bool = False
    
    # Tracking
    track_id: Optional[int] = None  # Persistent across frames
    
    # Area metrics
    area: float = 0.0
    visible_area: float = 0.0
    
    def to_coco_annotation(self, image_id: int, annotation_id: int) -> Dict:
        """Convert to COCO annotation format."""
        return {
            'id': annotation_id,
            'image_id': image_id,
            'category_id': self.class_id,
            'bbox': self.bbox_2d.to_coco(),
            'area': self.area if self.area > 0 else self.bbox_2d.width * self.bbox_2d.height,
            'iscrowd': 0,
            'segmentation': self.segmentation if self.segmentation else [],
            'attributes': {
                'occlusion_ratio': self.occlusion_ratio,
                'is_occluded': self.is_occluded,
                'is_truncated': self.is_truncated,
                'truncation_ratio': self.truncation_ratio,
                'occlusion_source': self.occlusion_source,
                'instance_id': self.instance_id,
                'track_id': self.track_id,
                'is_moving': self.is_moving
            }
        }


@dataclass
class FrameAnnotation:
    """
    Complete annotation for a single frame.
    
    Contains all instances plus frame-level metadata for
    research reproducibility and analysis.
    """
    frame_id: int
    image_filename: str
    image_width: int
    image_height: int
    instances: List[InstanceAnnotation] = field(default_factory=list)
    
    # Scene parameters
    scene_params: Dict = field(default_factory=dict)
    
    # Camera intrinsics/extrinsics
    camera_matrix: Optional[List[List[float]]] = None
    camera_extrinsics: Optional[Dict] = None
    
    # Scenario information
    scenario_id: Optional[str] = None
    scenario_type: Optional[str] = None
    
    # Sequence information
    sequence_id: Optional[int] = None
    frame_in_sequence: Optional[int] = None
    
    # Statistics
    vehicle_count: int = 0
    occluded_count: int = 0
    truncated_count: int = 0
    
    def compute_statistics(self):
        """Compute frame statistics from instances."""
        self.vehicle_count = len(self.instances)
        self.occluded_count = sum(1 for i in self.instances if i.is_occluded)
        self.truncated_count = sum(1 for i in self.instances if i.is_truncated)


class AnnotationExporter:
    """
    Base class for annotation export.
    
    Provides common functionality for multi-format export.
    """
    
    def __init__(self, output_dir: str, class_names: List[str]):
        """
        Initialize exporter.
        
        Args:
            output_dir: Output directory path
            class_names: List of class names in order of class_id
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.class_names = class_names
        self.class_to_id = {name: i for i, name in enumerate(class_names)}
    
    def export(self, annotations: List[FrameAnnotation]) -> str:
        """Export annotations. Override in subclass."""
        raise NotImplementedError


class COCOExporter(AnnotationExporter):
    """
    Export annotations in COCO format.
    
    Full COCO format with:
    - Detection annotations (bboxes)
    - Segmentation annotations (when available)
    - Extended attributes for research (occlusion, truncation, etc.)
    """
    
    def __init__(self, output_dir: str, class_names: List[str],
                 dataset_name: str = "VantageCV Synthetic Dataset",
                 include_segmentation: bool = True):
        """
        Initialize COCO exporter.
        
        Args:
            output_dir: Output directory path
            class_names: List of class names
            dataset_name: Name for the dataset
            include_segmentation: Whether to include segmentation masks
        """
        super().__init__(output_dir, class_names)
        self.dataset_name = dataset_name
        self.include_segmentation = include_segmentation
    
    def _build_categories(self) -> List[Dict]:
        """Build COCO categories list."""
        categories = []
        for class_id, class_name in enumerate(self.class_names):
            categories.append({
                'id': class_id,
                'name': class_name,
                'supercategory': 'vehicle'
            })
        return categories
    
    def _build_info(self) -> Dict:
        """Build COCO info section."""
        return {
            'description': self.dataset_name,
            'url': 'https://github.com/evanpetersen919/VantageCV',
            'version': '1.0',
            'year': 2025,
            'contributor': 'VantageCV Research',
            'date_created': datetime.now().isoformat()
        }
    
    def export(self, annotations: List[FrameAnnotation], 
               output_filename: str = "annotations_coco.json") -> str:
        """
        Export annotations to COCO format.
        
        Args:
            annotations: List of FrameAnnotation objects
            output_filename: Output filename
            
        Returns:
            Path to exported file
        """
        coco_data = {
            'info': self._build_info(),
            'licenses': [{'id': 1, 'name': 'Research Use', 'url': ''}],
            'categories': self._build_categories(),
            'images': [],
            'annotations': []
        }
        
        annotation_id = 1
        
        for frame in annotations:
            # Add image entry
            coco_data['images'].append({
                'id': frame.frame_id,
                'file_name': frame.image_filename,
                'width': frame.image_width,
                'height': frame.image_height,
                'date_captured': datetime.now().isoformat(),
                'license': 1,
                # Extended metadata
                'scene_params': frame.scene_params,
                'scenario_id': frame.scenario_id,
                'scenario_type': frame.scenario_type,
                'sequence_id': frame.sequence_id,
                'frame_in_sequence': frame.frame_in_sequence
            })
            
            # Add annotations
            for instance in frame.instances:
                ann = instance.to_coco_annotation(frame.frame_id, annotation_id)
                
                # Optionally exclude segmentation
                if not self.include_segmentation:
                    ann['segmentation'] = []
                
                coco_data['annotations'].append(ann)
                annotation_id += 1
        
        # Write to file
        output_path = self.output_dir / output_filename
        with open(output_path, 'w') as f:
            json.dump(coco_data, f, indent=2)
        
        logger.info(f"Exported {len(annotations)} frames, "
                   f"{annotation_id - 1} annotations to {output_path}")
        
        return str(output_path)
    
    def export_split(self, annotations: List[FrameAnnotation],
                     train_ratio: float = 0.8,
                     val_ratio: float = 0.1,
                     test_ratio: float = 0.1) -> Dict[str, str]:
        """
        Export with train/val/test split.
        
        Args:
            annotations: List of FrameAnnotation objects
            train_ratio: Fraction for training set
            val_ratio: Fraction for validation set
            test_ratio: Fraction for test set
            
        Returns:
            Dict mapping split name to file path
        """
        import random
        
        # Shuffle and split
        shuffled = list(annotations)
        random.shuffle(shuffled)
        
        n = len(shuffled)
        train_end = int(n * train_ratio)
        val_end = train_end + int(n * val_ratio)
        
        splits = {
            'train': shuffled[:train_end],
            'val': shuffled[train_end:val_end],
            'test': shuffled[val_end:]
        }
        
        paths = {}
        for split_name, split_data in splits.items():
            filename = f"annotations_{split_name}.json"
            paths[split_name] = self.export(split_data, filename)
        
        return paths


class KITTIExporter(AnnotationExporter):
    """
    Export annotations in KITTI format.
    
    KITTI format includes:
    - Per-image label files
    - 2D bounding boxes
    - 3D bounding boxes (when available)
    - Occlusion and truncation levels
    """
    
    # KITTI occlusion levels
    OCCLUSION_LEVELS = {
        (0.8, 1.0): 0,   # Fully visible
        (0.5, 0.8): 1,   # Partly occluded
        (0.0, 0.5): 2,   # Largely occluded
        (-1.0, 0.0): 3   # Unknown
    }
    
    def _get_occlusion_level(self, visibility_ratio: float) -> int:
        """Convert visibility ratio to KITTI occlusion level."""
        for (low, high), level in self.OCCLUSION_LEVELS.items():
            if low <= visibility_ratio <= high:
                return level
        return 3  # Unknown
    
    def _format_annotation_line(self, instance: InstanceAnnotation) -> str:
        """
        Format single annotation in KITTI format.
        
        Format: type truncated occluded alpha bbox_2d dimensions location rotation_y score
        """
        x1, y1, x2, y2 = instance.bbox_2d.to_kitti()
        
        # Occlusion level (0-3)
        occlusion = self._get_occlusion_level(instance.occlusion_ratio)
        
        # Truncation (0.0-1.0)
        truncation = instance.truncation_ratio
        
        # Alpha (observation angle) - placeholder
        alpha = 0.0
        
        # 3D info (use defaults if not available)
        if instance.bbox_3d:
            h, w, l = instance.bbox_3d.height, instance.bbox_3d.width, instance.bbox_3d.length
            x, y, z = instance.bbox_3d.x, instance.bbox_3d.y, instance.bbox_3d.z
            ry = instance.bbox_3d.rotation_y
        else:
            h, w, l = -1, -1, -1
            x, y, z = -1000, -1000, -1000
            ry = 0.0
        
        # Format: type truncated occluded alpha x1 y1 x2 y2 h w l x y z ry
        return (f"{instance.class_name} {truncation:.2f} {occlusion} {alpha:.2f} "
                f"{x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f} "
                f"{h:.2f} {w:.2f} {l:.2f} {x:.2f} {y:.2f} {z:.2f} {ry:.2f}")
    
    def export(self, annotations: List[FrameAnnotation],
               labels_subdir: str = "label_2") -> str:
        """
        Export annotations to KITTI format.
        
        Creates per-image label files in labels_subdir.
        
        Args:
            annotations: List of FrameAnnotation objects
            labels_subdir: Subdirectory for label files
            
        Returns:
            Path to labels directory
        """
        labels_dir = self.output_dir / labels_subdir
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        for frame in annotations:
            # Label filename matches image filename with .txt extension
            label_filename = Path(frame.image_filename).stem + ".txt"
            label_path = labels_dir / label_filename
            
            lines = []
            for instance in frame.instances:
                line = self._format_annotation_line(instance)
                lines.append(line)
            
            with open(label_path, 'w') as f:
                f.write('\n'.join(lines))
        
        logger.info(f"Exported {len(annotations)} KITTI label files to {labels_dir}")
        
        return str(labels_dir)


class YOLOExporter(AnnotationExporter):
    """Export annotations in YOLO format."""
    
    def export(self, annotations: List[FrameAnnotation],
               labels_subdir: str = "labels") -> str:
        """
        Export annotations to YOLO format.
        
        Creates per-image label files with normalized coordinates.
        
        Args:
            annotations: List of FrameAnnotation objects
            labels_subdir: Subdirectory for label files
            
        Returns:
            Path to labels directory
        """
        labels_dir = self.output_dir / labels_subdir
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        for frame in annotations:
            label_filename = Path(frame.image_filename).stem + ".txt"
            label_path = labels_dir / label_filename
            
            lines = []
            for instance in frame.instances:
                cx, cy, w, h = instance.bbox_2d.to_yolo(
                    frame.image_width, frame.image_height
                )
                lines.append(f"{instance.class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            
            with open(label_path, 'w') as f:
                f.write('\n'.join(lines))
        
        # Write classes file
        classes_path = self.output_dir / "classes.txt"
        with open(classes_path, 'w') as f:
            f.write('\n'.join(self.class_names))
        
        logger.info(f"Exported {len(annotations)} YOLO label files to {labels_dir}")
        
        return str(labels_dir)


class ResearchExporter:
    """
    Unified exporter for all formats.
    
    Convenience class that exports to multiple formats simultaneously.
    """
    
    def __init__(self, output_dir: str, class_names: List[str],
                 formats: List[str] = None):
        """
        Initialize multi-format exporter.
        
        Args:
            output_dir: Output directory path
            class_names: List of class names
            formats: List of format names to export ('coco', 'kitti', 'yolo')
        """
        self.output_dir = Path(output_dir)
        self.class_names = class_names
        self.formats = formats or ['coco', 'yolo']
        
        self.exporters = {}
        if 'coco' in self.formats:
            self.exporters['coco'] = COCOExporter(output_dir, class_names)
        if 'kitti' in self.formats:
            self.exporters['kitti'] = KITTIExporter(output_dir, class_names)
        if 'yolo' in self.formats:
            self.exporters['yolo'] = YOLOExporter(output_dir, class_names)
    
    def export_all(self, annotations: List[FrameAnnotation]) -> Dict[str, str]:
        """
        Export to all configured formats.
        
        Args:
            annotations: List of FrameAnnotation objects
            
        Returns:
            Dict mapping format name to output path
        """
        results = {}
        for format_name, exporter in self.exporters.items():
            results[format_name] = exporter.export(annotations)
        return results
