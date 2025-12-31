#==============================================================================
# VantageCV Research - Occlusion Analysis
#==============================================================================
# Compute and track occlusion metrics for research-grade annotations
# Critical for studying occlusion-aware perception performance
#==============================================================================

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OcclusionSource(Enum):
    """Source of occlusion for analysis."""
    NONE = "none"
    VEHICLE = "vehicle"           # Occluded by another vehicle
    INFRASTRUCTURE = "infrastructure"  # Occluded by poles, signs, etc.
    SELF = "self"                 # Self-occlusion (e.g., vehicle at angle)
    TRUNCATION = "truncation"     # Partially outside frame


@dataclass
class OcclusionMetrics:
    """
    Per-instance occlusion metrics.
    
    Attributes:
        occlusion_ratio: visible_pixels / full_projected_bbox_pixels
        is_occluded: True if occlusion_ratio < 1.0
        occlusion_source: Primary source of occlusion
        occluder_ids: List of instance IDs causing occlusion
        visible_area: Actual visible pixel count
        total_area: Full projected bounding box area
        is_truncated: True if extends beyond image boundary
        truncation_ratio: Portion of bbox outside image
    """
    occlusion_ratio: float
    is_occluded: bool
    occlusion_source: OcclusionSource
    occluder_ids: List[int]
    visible_area: int
    total_area: int
    is_truncated: bool
    truncation_ratio: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export."""
        return {
            'occlusion_ratio': round(self.occlusion_ratio, 4),
            'is_occluded': self.is_occluded,
            'occlusion_source': self.occlusion_source.value,
            'occluder_ids': self.occluder_ids,
            'visible_area': self.visible_area,
            'total_area': self.total_area,
            'is_truncated': self.is_truncated,
            'truncation_ratio': round(self.truncation_ratio, 4)
        }


@dataclass
class BoundingBox2D:
    """2D bounding box representation."""
    x: float  # Top-left x
    y: float  # Top-left y
    width: float
    height: float
    instance_id: int
    class_name: str
    depth: float = 0.0  # Distance from camera for occlusion ordering
    
    @property
    def x2(self) -> float:
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        return self.y + self.height
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)


class OcclusionAnalyzer:
    """
    Research-grade occlusion analysis system.
    
    Computes precise occlusion metrics for each vehicle instance,
    enabling occlusion-aware performance analysis and training.
    
    Key features:
    - Per-pixel occlusion computation (when instance masks available)
    - Bounding box overlap approximation (fallback)
    - Depth-ordered occlusion reasoning
    - Vehicle-vs-infrastructure occlusion classification
    - Truncation detection at image boundaries
    """
    
    def __init__(self, image_width: int, image_height: int,
                 min_occlusion_threshold: float = 0.3,
                 target_occluded_ratio: float = 0.35):
        """
        Initialize occlusion analyzer.
        
        Args:
            image_width: Image width in pixels
            image_height: Image height in pixels
            min_occlusion_threshold: Minimum overlap ratio to consider occluded
            target_occluded_ratio: Target percentage of images with occlusion (30-40%)
        """
        self.image_width = image_width
        self.image_height = image_height
        self.min_occlusion_threshold = min_occlusion_threshold
        self.target_occluded_ratio = target_occluded_ratio
    
    def compute_bbox_intersection(self, box1: BoundingBox2D, box2: BoundingBox2D) -> float:
        """
        Compute intersection area between two bounding boxes.
        
        Args:
            box1: First bounding box
            box2: Second bounding box
            
        Returns:
            Intersection area in pixels
        """
        x1 = max(box1.x, box2.x)
        y1 = max(box1.y, box2.y)
        x2 = min(box1.x2, box2.x2)
        y2 = min(box1.y2, box2.y2)
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        return (x2 - x1) * (y2 - y1)
    
    def compute_truncation(self, bbox: BoundingBox2D) -> Tuple[bool, float]:
        """
        Compute truncation metrics for a bounding box.
        
        Args:
            bbox: Bounding box to analyze
            
        Returns:
            Tuple of (is_truncated, truncation_ratio)
        """
        # Compute visible portion within image bounds
        visible_x1 = max(0, bbox.x)
        visible_y1 = max(0, bbox.y)
        visible_x2 = min(self.image_width, bbox.x2)
        visible_y2 = min(self.image_height, bbox.y2)
        
        if visible_x2 <= visible_x1 or visible_y2 <= visible_y1:
            return True, 1.0  # Completely outside
        
        visible_area = (visible_x2 - visible_x1) * (visible_y2 - visible_y1)
        total_area = bbox.area
        
        if total_area == 0:
            return False, 0.0
        
        truncation_ratio = 1.0 - (visible_area / total_area)
        is_truncated = truncation_ratio > 0.01  # 1% threshold
        
        return is_truncated, truncation_ratio
    
    def analyze_occlusions(self, 
                           bboxes: List[BoundingBox2D],
                           instance_masks: Optional[Dict[int, np.ndarray]] = None,
                           infrastructure_mask: Optional[np.ndarray] = None) -> Dict[int, OcclusionMetrics]:
        """
        Analyze occlusions for all instances in a frame.
        
        Args:
            bboxes: List of bounding boxes sorted by depth (near to far)
            instance_masks: Optional per-instance segmentation masks
            infrastructure_mask: Optional infrastructure occlusion mask
            
        Returns:
            Dict mapping instance_id to OcclusionMetrics
        """
        results = {}
        
        # Sort by depth (closer objects can occlude farther ones)
        sorted_bboxes = sorted(bboxes, key=lambda b: b.depth)
        
        for i, bbox in enumerate(sorted_bboxes):
            # Check truncation
            is_truncated, truncation_ratio = self.compute_truncation(bbox)
            
            # Initialize metrics
            total_occlusion_area = 0.0
            occluder_ids = []
            primary_source = OcclusionSource.NONE
            
            # Check occlusion by closer objects (lower indices in sorted list)
            for j in range(i):
                closer_bbox = sorted_bboxes[j]
                intersection = self.compute_bbox_intersection(bbox, closer_bbox)
                
                if intersection > 0:
                    total_occlusion_area += intersection
                    occluder_ids.append(closer_bbox.instance_id)
                    primary_source = OcclusionSource.VEHICLE
            
            # Add truncation to occlusion
            if is_truncated:
                truncation_area = bbox.area * truncation_ratio
                total_occlusion_area += truncation_area
                if primary_source == OcclusionSource.NONE:
                    primary_source = OcclusionSource.TRUNCATION
            
            # Compute final metrics
            total_area = max(1, int(bbox.area))
            visible_area = max(0, int(bbox.area - total_occlusion_area))
            occlusion_ratio = visible_area / total_area
            is_occluded = occlusion_ratio < (1.0 - self.min_occlusion_threshold)
            
            results[bbox.instance_id] = OcclusionMetrics(
                occlusion_ratio=occlusion_ratio,
                is_occluded=is_occluded,
                occlusion_source=primary_source,
                occluder_ids=occluder_ids,
                visible_area=visible_area,
                total_area=total_area,
                is_truncated=is_truncated,
                truncation_ratio=truncation_ratio
            )
        
        return results
    
    def analyze_with_masks(self,
                           instance_masks: Dict[int, np.ndarray],
                           depths: Dict[int, float],
                           class_names: Dict[int, str]) -> Dict[int, OcclusionMetrics]:
        """
        Precise pixel-level occlusion analysis using instance masks.
        
        This is the preferred method when instance segmentation is available.
        
        Args:
            instance_masks: Dict mapping instance_id to binary mask
            depths: Dict mapping instance_id to depth value
            class_names: Dict mapping instance_id to class name
            
        Returns:
            Dict mapping instance_id to OcclusionMetrics
        """
        results = {}
        
        # Sort instances by depth
        sorted_ids = sorted(depths.keys(), key=lambda x: depths[x])
        
        # Build cumulative occlusion mask
        occlusion_accumulator = np.zeros((self.image_height, self.image_width), dtype=bool)
        
        for instance_id in sorted_ids:
            mask = instance_masks[instance_id]
            
            # Compute visible pixels (not occluded by closer objects)
            visible_mask = mask & ~occlusion_accumulator
            visible_area = int(np.sum(visible_mask))
            total_area = int(np.sum(mask))
            
            # Compute truncation
            is_truncated = False
            truncation_ratio = 0.0
            
            # Check if mask touches image boundary
            if np.any(mask[0, :]) or np.any(mask[-1, :]) or \
               np.any(mask[:, 0]) or np.any(mask[:, -1]):
                is_truncated = True
                # Estimate truncation ratio based on boundary pixels
                boundary_pixels = (np.sum(mask[0, :]) + np.sum(mask[-1, :]) + 
                                   np.sum(mask[:, 0]) + np.sum(mask[:, -1]))
                truncation_ratio = min(0.5, boundary_pixels / max(1, total_area))
            
            # Determine occlusion source
            occluder_ids = []
            primary_source = OcclusionSource.NONE
            
            if visible_area < total_area:
                # Find which instances are causing occlusion
                for other_id in sorted_ids:
                    if depths[other_id] < depths[instance_id]:
                        other_mask = instance_masks[other_id]
                        overlap = np.sum(mask & other_mask)
                        if overlap > 0:
                            occluder_ids.append(other_id)
                
                if occluder_ids:
                    primary_source = OcclusionSource.VEHICLE
                elif is_truncated:
                    primary_source = OcclusionSource.TRUNCATION
            
            # Compute ratio
            occlusion_ratio = visible_area / max(1, total_area)
            is_occluded = occlusion_ratio < (1.0 - self.min_occlusion_threshold)
            
            results[instance_id] = OcclusionMetrics(
                occlusion_ratio=occlusion_ratio,
                is_occluded=is_occluded,
                occlusion_source=primary_source,
                occluder_ids=occluder_ids,
                visible_area=visible_area,
                total_area=total_area,
                is_truncated=is_truncated,
                truncation_ratio=truncation_ratio
            )
            
            # Add this instance to occlusion accumulator
            occlusion_accumulator |= mask
        
        return results
    
    def get_occlusion_statistics(self, 
                                 all_metrics: List[Dict[int, OcclusionMetrics]]) -> Dict:
        """
        Compute dataset-level occlusion statistics.
        
        Args:
            all_metrics: List of per-frame occlusion results
            
        Returns:
            Dict with dataset statistics
        """
        total_instances = 0
        occluded_instances = 0
        truncated_instances = 0
        occlusion_ratios = []
        source_counts = {s: 0 for s in OcclusionSource}
        
        for frame_metrics in all_metrics:
            for instance_id, metrics in frame_metrics.items():
                total_instances += 1
                occlusion_ratios.append(metrics.occlusion_ratio)
                source_counts[metrics.occlusion_source] += 1
                
                if metrics.is_occluded:
                    occluded_instances += 1
                if metrics.is_truncated:
                    truncated_instances += 1
        
        if total_instances == 0:
            return {'error': 'No instances to analyze'}
        
        return {
            'total_instances': total_instances,
            'occluded_instances': occluded_instances,
            'occluded_ratio': occluded_instances / total_instances,
            'truncated_instances': truncated_instances,
            'truncated_ratio': truncated_instances / total_instances,
            'mean_visibility': float(np.mean(occlusion_ratios)),
            'std_visibility': float(np.std(occlusion_ratios)),
            'occlusion_sources': {s.value: c for s, c in source_counts.items()}
        }


def generate_occlusion_scenario(analyzer: OcclusionAnalyzer,
                                 num_vehicles: int,
                                 target_occlusion_ratio: float = 0.4) -> List[BoundingBox2D]:
    """
    Generate vehicle placements that achieve target occlusion ratio.
    
    Used for explicit occlusion scenario generation (research requirement).
    
    Args:
        analyzer: OcclusionAnalyzer instance
        num_vehicles: Number of vehicles to place
        target_occlusion_ratio: Target percentage of vehicles to be occluded
        
    Returns:
        List of BoundingBox2D with placements achieving target occlusion
    """
    import random
    
    bboxes = []
    vehicle_classes = ['car', 'truck', 'bus', 'motorcycle', 'bicycle']
    
    # Size ranges by class (width, height in pixels at reference distance)
    size_ranges = {
        'car': ((80, 150), (50, 100)),
        'truck': ((120, 200), (80, 150)),
        'bus': ((150, 250), (100, 180)),
        'motorcycle': ((30, 60), (40, 80)),
        'bicycle': ((20, 40), (40, 70))
    }
    
    num_to_occlude = int(num_vehicles * target_occlusion_ratio)
    
    for i in range(num_vehicles):
        class_name = random.choice(vehicle_classes)
        w_range, h_range = size_ranges[class_name]
        
        width = random.uniform(*w_range)
        height = random.uniform(*h_range)
        depth = random.uniform(500, 5000)  # Distance from camera
        
        if i < num_to_occlude and len(bboxes) > 0:
            # Place overlapping with existing vehicle
            base_bbox = random.choice(bboxes)
            x = base_bbox.x + random.uniform(-width * 0.5, width * 0.5)
            y = base_bbox.y + random.uniform(-height * 0.3, height * 0.3)
            depth = base_bbox.depth + random.uniform(100, 500)  # Behind
        else:
            # Place randomly
            x = random.uniform(0, analyzer.image_width - width)
            y = random.uniform(analyzer.image_height * 0.3, 
                              analyzer.image_height - height)
        
        bboxes.append(BoundingBox2D(
            x=x, y=y, width=width, height=height,
            instance_id=i, class_name=class_name, depth=depth
        ))
    
    return bboxes
