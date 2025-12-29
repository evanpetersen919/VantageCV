#==============================================================================
# VantageCV - Industrial Domain
#==============================================================================
# File: industrial.py
# Description: Domain plugin for PCB and electronics inspection scenarios
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import random
import logging
import numpy as np
from typing import Dict, Any, List
from .base import BaseDomain
from vantagecv.randomization import (
    LightingRandomizer,
    MaterialRandomizer,
    CameraRandomizer,
    ObjectRandomizer
)

logger = logging.getLogger(__name__)


class IndustrialDomain(BaseDomain):
    """
    Industrial domain for PCB and electronics quality inspection.
    
    Focus areas:
    - Circuit board defect detection (scratches, cracks, missing components)
    - Electronics assembly verification
    - Surface quality inspection
    - Component placement validation
    """
    
    def __init__(self, config: Dict[str, Any], ue5_bridge=None):
        """Initialize industrial domain with PCB-specific parameters."""
        super().__init__(config)
        self.defect_types = ['scratch', 'crack', 'discoloration', 'missing_component', 
                            'solder_bridge', 'lifted_pad']
        self.component_types = self.get_object_list()
        self.current_pcb = None
        self.ue5_bridge = ue5_bridge
        
    def setup_scene(self) -> bool:
        """
        Set up PCB inspection environment in UE5.
        
        Scene setup:
        - Load inspection table with neutral background
        - Position overhead camera mount (30-60cm height)
        - Set up industrial LED lighting arrays
        - Load PCB mesh from CAD models
        - Spawn electronic components (ICs, resistors, capacitors)
        
        Scene randomization is handled by UE5Bridge and VantageCVSubsystem.
        This method validates and prepares scene parameters.
        """
        logger.info(f"Setting up PCB inspection scene")
        
        # Scene setup delegated to UE5 via Remote Control API
        # Future enhancements:
        # - self.ue5_bridge.load_map("PCB_InspectionLab")
        # - self.ue5_bridge.spawn_actor("InspectionTable")
        # - self.ue5_bridge.set_camera_mount_height(random.uniform(30, 60))
        
        # Mock: Simulate loading PCB
        pcb_types = ['single_layer', 'double_layer', 'multi_layer']
        self.current_pcb = random.choice(pcb_types)
        logger.info(f"Loaded {self.current_pcb} PCB with {len(self.component_types)} component types")
        
        return True
    
    def randomize_scene(self) -> Dict[str, Any]:
        """
        Apply domain randomization for PCB inspection.
        
        Uses structured randomization utilities for:
        - Lighting: Industrial LED arrays with realistic parameters
        - Materials: PCB surface finish variations
        - Camera: Inspection camera positioning
        - Objects: Component placement on PCB
        - Defects: Manufacturing defect injection (30% rate)
        
        Returns:
            Complete randomization parameter dictionary
        """
        # Apply UE5 lighting randomization if bridge is available
        if self.ue5_bridge:
            lighting_config = self.config.get('industrial.lighting', {})
            intensity_range = lighting_config.get('intensity_range', [300, 800])
            color_temp_range = lighting_config.get('color_temp_range', [4000, 6500])
            
            self.ue5_bridge.randomize_lighting(
                intensity_range=tuple(intensity_range),
                color_temp_range=tuple(color_temp_range)
            )
            
            # Apply material randomization via C++ SceneController
            # Use actor pattern from config
            actor_pattern = self.config.get('industrial.ue5.target_actor_pattern', 'StaticMeshActor')
            self.ue5_bridge.randomize_materials(object_types=[actor_pattern])
            
            # Randomize camera position for variety
            camera_config = self.config.get('camera', {})
            height_range = camera_config.get('height_range', [30, 60])
            distance_range = (height_range[0], height_range[1])
            fov = camera_config.get('fov', 65)
            fov_range = (fov - 5, fov + 5)
            
            self.ue5_bridge.randomize_camera(
                distance_range=distance_range,
                fov_range=fov_range
            )
        
        # Use randomization utilities for consistent, realistic parameters
        lighting_params = LightingRandomizer.randomize_industrial_lighting()
        material_params = MaterialRandomizer.randomize_pcb_materials()
        camera_params = CameraRandomizer.randomize_inspection_camera(
            height_range=(35, 55),
            angle_deviation=10.0
        )
        
        # PCB pose randomization
        pose_params = {
            'rotation_z': random.uniform(0, 360),
            'tilt_x': random.uniform(-5, 5),
            'tilt_y': random.uniform(-5, 5),
            'position_offset': camera_params['position_offset_xy']
        }
        
        # Defect injection (30% defect rate for training)
        has_defect = random.random() < 0.30
        defect_params = {
            'has_defect': has_defect,
            'defect_type': random.choice(self.defect_types) if has_defect else None,
            'defect_severity': random.uniform(0.2, 1.0) if has_defect else 0.0
        }
        
        randomization_params = {
            'lighting': lighting_params,
            'material': material_params,
            'camera': camera_params,
            'pose': pose_params,
            'defects': defect_params
        }
        
        logger.debug(
            f"Industrial randomization: "
            f"lighting_intensity={lighting_params['intensity']:.2f}, "
            f"camera_height={camera_params['height_cm']:.1f}cm, "
            f"defect={defect_params['defect_type']}"
        )
        
        return randomization_params
    
    def get_annotations(self) -> Dict[str, Any]:
        """
        Extract ground truth annotations for PCB inspection.
        
        Annotations include:
        - Object detection: bounding boxes for components and defects
        - Instance segmentation: pixel-level polygon masks for each component
        - 6D pose: rotation matrix + translation for component placement
        - Quality labels: pass/fail classification
        
        Returns:
            Dictionary with comprehensive multi-modal annotations
        """
        annotations = {
            'image_id': random.randint(10000, 99999),
            'pcb_type': self.current_pcb,
            'components': [],
            'defects': [],
            'quality_label': 'pass',
            'metadata': {
                'domain': 'industrial',
                'scene_type': 'pcb_inspection'
            }
        }
        
        # Generate component annotations with realistic mock data
        num_components = random.randint(5, 15)
        for i in range(num_components):
            bbox = [
                random.randint(50, 1800), 
                random.randint(50, 1000), 
                random.randint(20, 100), 
                random.randint(20, 100)
            ]
            
            # Generate polygon segmentation mask from bbox with slight variation
            x, y, w, h = bbox
            polygon = [
                x + random.uniform(0, 2), y + random.uniform(0, 2),
                x + w - random.uniform(0, 2), y + random.uniform(0, 2),
                x + w - random.uniform(0, 2), y + h - random.uniform(0, 2),
                x + random.uniform(0, 2), y + h - random.uniform(0, 2)
            ]
            
            # Generate realistic 6D pose (rotation matrix + translation)
            roll = np.radians(random.uniform(-5, 5))  # Small rotation variations
            pitch = np.radians(random.uniform(-5, 5))
            yaw = np.radians(random.uniform(-180, 180))  # Full rotation around Z
            
            # Import rotation conversion from utils
            from vantagecv.utils import euler_to_rotation_matrix
            rotation_matrix = euler_to_rotation_matrix(roll, pitch, yaw)
            
            # Translation relative to camera (in cm)
            translation = [
                random.uniform(-15, 15),  # X position
                random.uniform(-10, 10),   # Y position  
                random.uniform(35, 55)     # Z depth (camera height)
            ]
            
            component = {
                'class': random.choice(self.component_types),
                'bbox': bbox,
                'segmentation': [polygon],  # COCO polygon format
                'pose': {
                    'rotation': rotation_matrix.tolist(),  # 3x3 matrix
                    'translation': translation,
                    'unit': 'centimeters',
                    'confidence': random.uniform(0.95, 1.0)
                }
            }
            annotations['components'].append(component)
        
        # Add defect annotation if present
        if random.random() < 0.30:
            defect_bbox = [
                random.randint(100, 1700), 
                random.randint(100, 900), 
                random.randint(30, 120), 
                random.randint(30, 120)
            ]
            
            # Generate defect mask polygon
            dx, dy, dw, dh = defect_bbox
            defect_polygon = [
                dx, dy,
                dx + dw, dy,
                dx + dw, dy + dh,
                dx, dy + dh
            ]
            
            defect = {
                'type': random.choice(self.defect_types),
                'bbox': defect_bbox,
                'severity': random.uniform(0.3, 1.0),
                'segmentation': [defect_polygon]
            }
            annotations['defects'].append(defect)
            annotations['quality_label'] = 'fail'
        
        return annotations
    
    def validate_scene(self) -> bool:
        """
        Validate PCB inspection scene quality.
        
        Validation checks:
        - PCB fully visible in frame (not clipped)
        - Components clearly visible (not over/underexposed)
        - At least 3 components present
        - Camera in focus range
        - No extreme occlusions
        
        Currently uses statistical quality control (random rejection).
        Future: integrate UE5 render quality metrics.
        """
        # Future enhancements for UE5 validation:
        # - bounds_check = self.ue5_bridge.is_actor_in_frame('PCB')
        # - exposure_check = self.ue5_bridge.check_exposure_levels()
        # - component_count = len(self.ue5_bridge.get_visible_components())
        
        # Mock validation: randomly reject 8% of scenes
        is_valid = random.random() > 0.08
        
        if not is_valid:
            logger.debug("Scene validation failed - regenerating")
        
        return is_valid

