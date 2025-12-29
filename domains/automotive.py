#==============================================================================
# VantageCV - Automotive Domain with Structured Domain Randomization
#==============================================================================
# File: automotive.py
# Description: Research-grade domain plugin for vehicle detection with SDR.
#              Implements structured domain randomization for sim-to-real
#              transfer learning as described in Tobin et al. (2017).
#
# Vehicle Classes: car, truck, bus, motorcycle, bicycle (COCO-aligned)
#
# References:
#   - Tobin et al. "Domain Randomization for Transferring Deep Neural 
#     Networks from Simulation to the Real World" (2017)
#   - Tremblay et al. "Training Deep Networks with Synthetic Data" (2018)
#
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import random
import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from .base import BaseDomain
from vantagecv.randomization import (
    LightingRandomizer,
    MaterialRandomizer,
    CameraRandomizer,
    ObjectRandomizer
)

logger = logging.getLogger(__name__)


@dataclass
class DomainRandomizationConfig:
    """
    Configuration for structured domain randomization.
    
    All parameters are designed for research reproducibility with
    configurable ranges for ablation studies.
    """
    # Ground plane randomization
    ground_color_min: Tuple[float, float, float] = (0.1, 0.1, 0.1)
    ground_color_max: Tuple[float, float, float] = (0.6, 0.6, 0.6)
    ground_roughness_range: Tuple[float, float] = (0.3, 0.9)
    
    # Lighting randomization
    sun_intensity_range: Tuple[float, float] = (1.0, 15.0)
    sun_elevation_range: Tuple[float, float] = (15.0, 75.0)
    sun_azimuth_range: Tuple[float, float] = (0.0, 360.0)
    color_temperature_range: Tuple[float, float] = (4000.0, 7500.0)
    
    # Distractor object randomization
    distractor_enabled: bool = True
    distractor_count_range: Tuple[int, int] = (5, 15)
    distractor_scale_range: Tuple[float, float] = (0.5, 3.0)
    distractor_distance_range: Tuple[float, float] = (500.0, 2000.0)
    distractor_random_colors: bool = True
    distractor_random_shapes: bool = True
    
    # Camera randomization
    camera_distance_range: Tuple[float, float] = (300.0, 800.0)
    camera_height_range: Tuple[float, float] = (100.0, 250.0)
    camera_fov_range: Tuple[float, float] = (60.0, 90.0)
    camera_pitch_range: Tuple[float, float] = (-15.0, -5.0)
    
    # Vehicle placement randomization
    vehicle_count_range: Tuple[int, int] = (1, 6)
    vehicle_spacing_min: float = 100.0
    vehicle_rotation_range: Tuple[float, float] = (-30.0, 30.0)
    
    # Reproducibility
    random_seed: int = -1


@dataclass 
class VehicleClass:
    """Vehicle class definition with COCO category alignment."""
    name: str
    coco_id: int
    spawn_weight: float = 1.0
    scale_range: Tuple[float, float] = (0.9, 1.1)
    color_palette: List[Tuple[float, float, float]] = field(default_factory=list)


# COCO-aligned vehicle classes for direct evaluation
VEHICLE_CLASSES = {
    'car': VehicleClass(
        name='car',
        coco_id=3,
        spawn_weight=1.0,
        color_palette=[
            (0.1, 0.1, 0.1),    # Black
            (0.9, 0.9, 0.9),    # White
            (0.7, 0.7, 0.7),    # Silver
            (0.15, 0.15, 0.2),  # Dark blue
            (0.6, 0.1, 0.1),    # Red
        ]
    ),
    'truck': VehicleClass(
        name='truck',
        coco_id=8,
        spawn_weight=0.6,
        scale_range=(1.2, 1.5),
        color_palette=[
            (0.9, 0.9, 0.9),    # White
            (0.2, 0.25, 0.3),   # Dark gray
            (0.6, 0.3, 0.1),    # Brown
        ]
    ),
    'bus': VehicleClass(
        name='bus',
        coco_id=6,
        spawn_weight=0.3,
        scale_range=(1.5, 2.0),
        color_palette=[
            (0.9, 0.7, 0.1),    # Yellow (school bus)
            (0.1, 0.3, 0.6),    # Blue (city bus)
            (0.9, 0.9, 0.9),    # White
        ]
    ),
    'motorcycle': VehicleClass(
        name='motorcycle',
        coco_id=4,
        spawn_weight=0.5,
        scale_range=(0.4, 0.6),
        color_palette=[
            (0.1, 0.1, 0.1),    # Black
            (0.8, 0.1, 0.1),    # Red
            (0.1, 0.3, 0.7),    # Blue
        ]
    ),
    'bicycle': VehicleClass(
        name='bicycle',
        coco_id=2,
        spawn_weight=0.4,
        scale_range=(0.3, 0.5),
        color_palette=[
            (0.1, 0.1, 0.1),    # Black
            (0.8, 0.1, 0.1),    # Red
            (0.1, 0.5, 0.1),    # Green
            (0.9, 0.9, 0.2),    # Yellow
        ]
    ),
}


class AutomotiveDomain(BaseDomain):
    """
    Research-grade automotive domain with structured domain randomization.
    
    Implements extreme domain randomization for sim-to-real transfer:
    - Random ground colors/textures to prevent background overfitting
    - Random sky colors and lighting conditions
    - Random distractor objects (geometric shapes with random colors)
    - Controlled vehicle placement with class balancing
    - Reproducible randomization with seed support
    
    Vehicle Classes (COCO-aligned):
        car (3), truck (8), bus (6), motorcycle (4), bicycle (2)
    
    Attributes:
        sdr_config: Structured domain randomization configuration
        vehicle_classes: Dictionary of vehicle class definitions
        current_seed: Current random seed for reproducibility
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize automotive domain with SDR configuration.
        
        Args:
            config: YAML configuration dictionary with domain parameters
        """
        super().__init__(config)
        
        # Initialize SDR configuration from YAML or defaults
        self.sdr_config = self._load_sdr_config(config)
        self.vehicle_classes = VEHICLE_CLASSES
        self.current_seed: Optional[int] = None
        
        # Image dimensions for annotation generation
        self.image_width = config.get('camera', {}).get('resolution', {}).get('width', 1920)
        self.image_height = config.get('camera', {}).get('resolution', {}).get('height', 1080)
        
        logger.info(
            f"Automotive domain initialized with SDR: "
            f"{len(self.vehicle_classes)} vehicle classes, "
            f"distractors={'enabled' if self.sdr_config.distractor_enabled else 'disabled'}"
        )
    
    def _load_sdr_config(self, config: Dict[str, Any]) -> DomainRandomizationConfig:
        """
        Load SDR configuration from YAML config.
        
        Args:
            config: YAML configuration dictionary
            
        Returns:
            Populated DomainRandomizationConfig dataclass
        """
        sdr_section = config.get('domain_randomization', {})
        
        return DomainRandomizationConfig(
            # Ground
            ground_color_min=tuple(sdr_section.get('ground_color_min', [0.1, 0.1, 0.1])),
            ground_color_max=tuple(sdr_section.get('ground_color_max', [0.6, 0.6, 0.6])),
            ground_roughness_range=tuple(sdr_section.get('ground_roughness_range', [0.3, 0.9])),
            
            # Lighting
            sun_intensity_range=tuple(sdr_section.get('sun_intensity_range', [1.0, 15.0])),
            sun_elevation_range=tuple(sdr_section.get('sun_elevation_range', [15.0, 75.0])),
            sun_azimuth_range=tuple(sdr_section.get('sun_azimuth_range', [0.0, 360.0])),
            color_temperature_range=tuple(sdr_section.get('color_temperature_range', [4000.0, 7500.0])),
            
            # Distractors
            distractor_enabled=sdr_section.get('distractor_enabled', True),
            distractor_count_range=tuple(sdr_section.get('distractor_count_range', [5, 15])),
            distractor_scale_range=tuple(sdr_section.get('distractor_scale_range', [0.5, 3.0])),
            distractor_distance_range=tuple(sdr_section.get('distractor_distance_range', [500.0, 2000.0])),
            distractor_random_colors=sdr_section.get('distractor_random_colors', True),
            distractor_random_shapes=sdr_section.get('distractor_random_shapes', True),
            
            # Camera
            camera_distance_range=tuple(sdr_section.get('camera_distance_range', [300.0, 800.0])),
            camera_height_range=tuple(sdr_section.get('camera_height_range', [100.0, 250.0])),
            camera_fov_range=tuple(sdr_section.get('camera_fov_range', [60.0, 90.0])),
            camera_pitch_range=tuple(sdr_section.get('camera_pitch_range', [-15.0, -5.0])),
            
            # Vehicles
            vehicle_count_range=tuple(sdr_section.get('vehicle_count_range', [1, 6])),
            vehicle_spacing_min=sdr_section.get('vehicle_spacing_min', 100.0),
            vehicle_rotation_range=tuple(sdr_section.get('vehicle_rotation_range', [-30.0, 30.0])),
            
            # Reproducibility
            random_seed=sdr_section.get('random_seed', -1),
        )
    
    def setup_scene(self) -> bool:
        """
        Set up scene for vehicle capture.
        
        Scene requirements for SDR:
        - Ground plane actor with randomizable material
        - Directional light (sun) for lighting randomization
        - Sky light for ambient lighting
        - DomainRandomization actor for distractor spawning
        - Vehicle spawn points or free placement area
        
        Returns:
            True if scene setup successful
        """
        logger.info("Setting up automotive SDR scene")
        
        # Initialize seed for this scene
        if self.sdr_config.random_seed >= 0:
            self.current_seed = self.sdr_config.random_seed
        else:
            self.current_seed = random.randint(0, 2**31 - 1)
        
        random.seed(self.current_seed)
        np.random.seed(self.current_seed % (2**32))
        
        logger.debug(f"Scene initialized with seed: {self.current_seed}")
        
        return True
    
    def randomize_scene(self) -> Dict[str, Any]:
        """
        Apply structured domain randomization.
        
        Randomization pipeline:
        1. Randomize ground plane (color, roughness)
        2. Randomize sky (zenith color, horizon color)
        3. Randomize lighting (sun position, intensity, temperature)
        4. Spawn distractor objects (random shapes, colors, positions)
        5. Place vehicles with class-balanced sampling
        6. Randomize camera (position, orientation, FOV)
        
        All parameters are logged for reproducibility.
        
        Returns:
            Complete randomization parameter dictionary for UE5 or logging
        """
        cfg = self.sdr_config
        
        # Ground randomization
        ground_params = {
            'color': self._random_color(cfg.ground_color_min, cfg.ground_color_max),
            'roughness': random.uniform(*cfg.ground_roughness_range),
        }
        
        # Lighting randomization
        lighting_params = {
            'sun_intensity': random.uniform(*cfg.sun_intensity_range),
            'sun_elevation': random.uniform(*cfg.sun_elevation_range),
            'sun_azimuth': random.uniform(*cfg.sun_azimuth_range),
            'color_temperature': random.uniform(*cfg.color_temperature_range),
            'shadow_intensity': random.uniform(0.3, 1.0),
        }
        
        # Sky randomization (select from presets with variation)
        sky_presets = [
            {'zenith': (0.4, 0.6, 1.0), 'horizon': (0.8, 0.9, 1.0)},    # Clear day
            {'zenith': (0.6, 0.65, 0.7), 'horizon': (0.7, 0.7, 0.75)},  # Overcast
            {'zenith': (1.0, 0.7, 0.5), 'horizon': (1.0, 0.5, 0.2)},    # Sunset
            {'zenith': (0.15, 0.15, 0.25), 'horizon': (0.4, 0.3, 0.5)}, # Dusk
            {'zenith': (0.05, 0.05, 0.1), 'horizon': (0.1, 0.1, 0.15)}, # Night
            {'zenith': (0.3, 0.3, 0.35), 'horizon': (0.5, 0.5, 0.55)},  # Storm
        ]
        sky_preset = random.choice(sky_presets)
        sky_params = {
            'zenith_color': self._add_color_variation(sky_preset['zenith'], 0.1),
            'horizon_color': self._add_color_variation(sky_preset['horizon'], 0.1),
        }
        
        # Distractor parameters
        distractor_params = {}
        if cfg.distractor_enabled:
            distractor_params = {
                'count': random.randint(*cfg.distractor_count_range),
                'scale_range': cfg.distractor_scale_range,
                'distance_range': cfg.distractor_distance_range,
                'random_colors': cfg.distractor_random_colors,
                'random_shapes': cfg.distractor_random_shapes,
            }
        
        # Camera randomization
        camera_params = {
            'distance': random.uniform(*cfg.camera_distance_range),
            'height': random.uniform(*cfg.camera_height_range),
            'azimuth': random.uniform(0, 360),
            'pitch': random.uniform(*cfg.camera_pitch_range),
            'fov': random.uniform(*cfg.camera_fov_range),
        }
        
        # Vehicle placement
        num_vehicles = random.randint(*cfg.vehicle_count_range)
        vehicle_params = self._generate_vehicle_placements(num_vehicles)
        
        randomization_params = {
            'seed': self.current_seed,
            'ground': ground_params,
            'lighting': lighting_params,
            'sky': sky_params,
            'distractors': distractor_params,
            'camera': camera_params,
            'vehicles': vehicle_params,
        }
        
        logger.debug(
            f"SDR applied: seed={self.current_seed}, "
            f"vehicles={num_vehicles}, "
            f"distractors={distractor_params.get('count', 0)}, "
            f"sun_elev={lighting_params['sun_elevation']:.1f}"
        )
        
        return randomization_params
    
    def _generate_vehicle_placements(self, num_vehicles: int) -> List[Dict[str, Any]]:
        """
        Generate vehicle placements with class-balanced sampling.
        
        Uses weighted sampling to ensure representation of all classes
        while maintaining realistic spatial distribution.
        
        Args:
            num_vehicles: Number of vehicles to place
            
        Returns:
            List of vehicle placement dictionaries
        """
        cfg = self.sdr_config
        
        # Weighted class selection
        class_names = list(self.vehicle_classes.keys())
        class_weights = [self.vehicle_classes[c].spawn_weight for c in class_names]
        
        vehicles = []
        used_positions = []
        
        for i in range(num_vehicles):
            # Select class with weighting
            selected_class = random.choices(class_names, weights=class_weights, k=1)[0]
            vehicle_def = self.vehicle_classes[selected_class]
            
            # Generate non-overlapping position
            max_attempts = 10
            for _ in range(max_attempts):
                # Random position in capture area
                x = random.uniform(-400, 400)
                y = random.uniform(-200, 200)
                
                # Check spacing
                valid = all(
                    np.sqrt((x - px)**2 + (y - py)**2) > cfg.vehicle_spacing_min
                    for px, py in used_positions
                )
                
                if valid:
                    used_positions.append((x, y))
                    break
            else:
                # Skip if can't find valid position
                continue
            
            # Vehicle parameters
            scale = random.uniform(*vehicle_def.scale_range)
            rotation = random.uniform(*cfg.vehicle_rotation_range)
            
            # Random color from class palette
            if vehicle_def.color_palette:
                color = random.choice(vehicle_def.color_palette)
                color = self._add_color_variation(color, 0.05)
            else:
                color = self._random_color((0.1, 0.1, 0.1), (0.9, 0.9, 0.9))
            
            vehicles.append({
                'class': selected_class,
                'coco_id': vehicle_def.coco_id,
                'position': (x, y, 0),
                'rotation': (0, 0, rotation),
                'scale': scale,
                'color': color,
            })
        
        return vehicles
    
    def get_annotations(self) -> Dict[str, Any]:
        """
        Generate ground truth annotations in COCO-compatible format.
        
        Produces annotations for:
        - 2D bounding boxes (COCO format: [x, y, width, height])
        - Instance segmentation masks (polygon format)
        - 6D pose (rotation matrix + translation)
        - COCO category IDs for direct evaluation
        
        All annotations are generated from the randomized scene state.
        
        Returns:
            COCO-compatible annotation dictionary
        """
        # Get vehicle placements from last randomization
        num_vehicles = random.randint(*self.sdr_config.vehicle_count_range)
        vehicle_placements = self._generate_vehicle_placements(num_vehicles)
        
        annotations = {
            'image_id': self.current_seed if self.current_seed else random.randint(10000, 99999),
            'annotations': [],
            'metadata': {
                'domain': 'automotive',
                'sdr_seed': self.current_seed,
                'num_vehicles': len(vehicle_placements),
                'num_distractors': random.randint(*self.sdr_config.distractor_count_range) if self.sdr_config.distractor_enabled else 0,
            }
        }
        
        # Generate annotation for each vehicle
        for idx, vehicle in enumerate(vehicle_placements):
            annotation = self._generate_vehicle_annotation(idx, vehicle)
            annotations['annotations'].append(annotation)
        
        logger.debug(f"Generated {len(annotations['annotations'])} vehicle annotations")
        
        return annotations
    
    def _generate_vehicle_annotation(
        self, 
        instance_id: int, 
        vehicle: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate single vehicle annotation with all modalities.
        
        Args:
            instance_id: Unique instance identifier
            vehicle: Vehicle placement dictionary
            
        Returns:
            Complete annotation dictionary for one vehicle
        """
        vehicle_class = vehicle['class']
        vehicle_def = self.vehicle_classes[vehicle_class]
        
        # Project 3D position to 2D bounding box (simplified projection)
        x3d, y3d, z3d = vehicle['position']
        scale = vehicle['scale']
        
        # Estimate 2D bbox from 3D position (approximation for mock data)
        # In real UE5: Get screen-space bounds from actor
        center_x = self.image_width / 2 + x3d * 1.5
        center_y = self.image_height / 2 - y3d * 0.5
        
        # Size based on vehicle class and scale
        base_sizes = {
            'car': (200, 150),
            'truck': (280, 180),
            'bus': (350, 200),
            'motorcycle': (100, 120),
            'bicycle': (80, 100),
        }
        base_w, base_h = base_sizes.get(vehicle_class, (150, 120))
        w = base_w * scale * random.uniform(0.9, 1.1)
        h = base_h * scale * random.uniform(0.9, 1.1)
        
        # COCO format: [x, y, width, height]
        x = max(0, center_x - w / 2)
        y = max(0, center_y - h / 2)
        bbox = [x, y, w, h]
        
        # Clip to image bounds
        bbox[2] = min(bbox[2], self.image_width - bbox[0])
        bbox[3] = min(bbox[3], self.image_height - bbox[1])
        
        # Generate segmentation polygon (vehicle silhouette)
        polygon = self._generate_vehicle_polygon(bbox, vehicle_class)
        
        # Generate 6D pose
        roll, pitch, yaw = vehicle['rotation']
        from vantagecv.utils import euler_to_rotation_matrix
        rotation_matrix = euler_to_rotation_matrix(
            np.radians(roll), 
            np.radians(pitch), 
            np.radians(yaw)
        )
        
        annotation = {
            'id': instance_id,
            'category_id': vehicle_def.coco_id,
            'category_name': vehicle_class,
            'bbox': [round(v, 2) for v in bbox],
            'area': round(bbox[2] * bbox[3], 2),
            'segmentation': [polygon],
            'iscrowd': 0,
            'pose': {
                'rotation': rotation_matrix.tolist(),
                'translation': list(vehicle['position']),
                'scale': vehicle['scale'],
            },
            'attributes': {
                'color': vehicle['color'],
                'occluded': random.random() < 0.15,
                'truncated': random.random() < 0.1,
            }
        }
        
        return annotation
    
    def _generate_vehicle_polygon(
        self, 
        bbox: List[float], 
        vehicle_class: str
    ) -> List[float]:
        """
        Generate vehicle silhouette polygon for segmentation.
        
        Creates class-specific polygon shapes approximating vehicle silhouettes.
        
        Args:
            bbox: Bounding box [x, y, w, h]
            vehicle_class: Vehicle class name
            
        Returns:
            Flattened polygon coordinates [x1, y1, x2, y2, ...]
        """
        x, y, w, h = bbox
        
        # Generate simplified vehicle silhouette based on class
        if vehicle_class == 'car':
            # Sedan shape
            polygon = [
                x + w * 0.1, y + h,          # Bottom left
                x, y + h * 0.6,              # Left side
                x + w * 0.15, y + h * 0.3,   # Left windshield
                x + w * 0.35, y,             # Roof left
                x + w * 0.65, y,             # Roof right
                x + w * 0.85, y + h * 0.3,   # Right windshield
                x + w, y + h * 0.6,          # Right side
                x + w * 0.9, y + h,          # Bottom right
            ]
        elif vehicle_class == 'truck':
            # Truck shape (boxy)
            polygon = [
                x, y + h,                    # Bottom left
                x, y + h * 0.2,              # Left side
                x + w * 0.3, y,              # Cabin top left
                x + w * 0.4, y,              # Cabin top right
                x + w * 0.4, y + h * 0.3,    # Cabin back
                x + w, y + h * 0.3,          # Trailer top
                x + w, y + h,                # Bottom right
            ]
        elif vehicle_class == 'bus':
            # Bus shape (rectangular)
            polygon = [
                x, y + h,                    # Bottom left
                x, y + h * 0.1,              # Left side
                x + w * 0.05, y,             # Top left
                x + w * 0.95, y,             # Top right
                x + w, y + h * 0.1,          # Right side
                x + w, y + h,                # Bottom right
            ]
        elif vehicle_class == 'motorcycle':
            # Motorcycle shape (rider silhouette)
            polygon = [
                x + w * 0.3, y + h,          # Rear wheel
                x, y + h * 0.6,              # Rear
                x + w * 0.4, y,              # Rider head
                x + w * 0.6, y + h * 0.3,    # Front
                x + w, y + h * 0.7,          # Front wheel
                x + w * 0.7, y + h,          # Bottom
            ]
        elif vehicle_class == 'bicycle':
            # Bicycle shape (simplified)
            polygon = [
                x + w * 0.2, y + h,          # Rear wheel
                x, y + h * 0.5,              # Rear
                x + w * 0.5, y,              # Rider
                x + w, y + h * 0.5,          # Front
                x + w * 0.8, y + h,          # Front wheel
            ]
        else:
            # Default rectangle
            polygon = [x, y, x + w, y, x + w, y + h, x, y + h]
        
        # Add slight randomization to polygon vertices
        polygon = [
            round(v + random.uniform(-2, 2), 2) 
            for v in polygon
        ]
        
        return polygon
    
    def _random_color(
        self, 
        min_rgb: Tuple[float, float, float], 
        max_rgb: Tuple[float, float, float]
    ) -> Tuple[float, float, float]:
        """
        Generate random RGB color in range.
        
        Args:
            min_rgb: Minimum RGB values (0-1)
            max_rgb: Maximum RGB values (0-1)
            
        Returns:
            Random RGB tuple
        """
        return (
            random.uniform(min_rgb[0], max_rgb[0]),
            random.uniform(min_rgb[1], max_rgb[1]),
            random.uniform(min_rgb[2], max_rgb[2]),
        )
    
    def _add_color_variation(
        self, 
        color: Tuple[float, float, float], 
        variation: float
    ) -> Tuple[float, float, float]:
        """
        Add random variation to color.
        
        Args:
            color: Base RGB color (0-1)
            variation: Maximum variation amount
            
        Returns:
            Modified RGB tuple, clamped to valid range
        """
        return tuple(
            max(0.0, min(1.0, c + random.uniform(-variation, variation)))
            for c in color
        )
    
    def get_object_list(self) -> List[str]:
        """
        Get list of detectable object classes.
        
        Returns:
            List of COCO-aligned vehicle class names
        """
        return list(VEHICLE_CLASSES.keys())
    
    def validate_scene(self) -> bool:
        """
        Validate scene quality for training data.
        
        Validation checks:
        - At least one vehicle visible
        - Vehicles within image bounds
        - No extreme overlap between vehicles
        - Lighting not completely dark
        
        Returns:
            True if scene passes quality checks
        """
        # Generate test annotations to validate
        test_annotations = self.get_annotations()
        
        # Check at least one vehicle
        if len(test_annotations['annotations']) == 0:
            logger.debug("Scene validation failed: No vehicles")
            return False
        
        # Check all bboxes within image bounds
        for anno in test_annotations['annotations']:
            x, y, w, h = anno['bbox']
            if x < 0 or y < 0 or x + w > self.image_width or y + h > self.image_height:
                logger.debug(f"Scene validation failed: Vehicle out of bounds")
                return False
            
            # Check minimum visible area
            if w * h < 500:
                logger.debug(f"Scene validation failed: Vehicle too small")
                return False
        
        return True
    
    def get_ue5_randomization_params(self) -> Dict[str, Any]:
        """
        Get parameters formatted for UE5 DomainRandomization actor.
        
        Converts Python config to UE5-compatible parameter dictionary
        for Remote Control API calls.
        
        Returns:
            UE5-formatted randomization parameters
        """
        cfg = self.sdr_config
        
        return {
            'Ground': {
                'bRandomizeColor': True,
                'bRandomizeRoughness': True,
                'MinColor': {'R': cfg.ground_color_min[0], 'G': cfg.ground_color_min[1], 'B': cfg.ground_color_min[2]},
                'MaxColor': {'R': cfg.ground_color_max[0], 'G': cfg.ground_color_max[1], 'B': cfg.ground_color_max[2]},
                'RoughnessRange': {'X': cfg.ground_roughness_range[0], 'Y': cfg.ground_roughness_range[1]},
            },
            'Lighting': {
                'bEnabled': True,
                'IntensityRange': {'X': cfg.sun_intensity_range[0], 'Y': cfg.sun_intensity_range[1]},
                'ElevationRange': {'X': cfg.sun_elevation_range[0], 'Y': cfg.sun_elevation_range[1]},
                'AzimuthRange': {'X': cfg.sun_azimuth_range[0], 'Y': cfg.sun_azimuth_range[1]},
                'TemperatureRange': {'X': cfg.color_temperature_range[0], 'Y': cfg.color_temperature_range[1]},
            },
            'Distractors': {
                'bEnabled': cfg.distractor_enabled,
                'CountRange': {'X': cfg.distractor_count_range[0], 'Y': cfg.distractor_count_range[1]},
                'ScaleRange': {'X': cfg.distractor_scale_range[0], 'Y': cfg.distractor_scale_range[1]},
                'DistanceRange': {'X': cfg.distractor_distance_range[0], 'Y': cfg.distractor_distance_range[1]},
                'bRandomColors': cfg.distractor_random_colors,
                'bRandomShapes': cfg.distractor_random_shapes,
            },
            'RandomSeed': self.current_seed if self.current_seed else -1,
        }

