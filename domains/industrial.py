#==============================================================================
# VantageCV - Industrial Domain
#==============================================================================
# File: industrial.py
# Description: Domain plugin for PCB and electronics inspection scenarios
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import random
import numpy as np
from typing import Dict, Any, List
from .base import BaseDomain


class IndustrialDomain(BaseDomain):
    """
    Industrial domain for PCB and electronics quality inspection.
    
    Focus areas:
    - Circuit board defect detection (scratches, cracks, missing components)
    - Electronics assembly verification
    - Surface quality inspection
    - Component placement validation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize industrial domain with PCB-specific parameters."""
        super().__init__(config)
        self.defect_types = ['scratch', 'crack', 'discoloration', 'missing_component', 
                            'solder_bridge', 'lifted_pad']
        self.component_types = self.get_object_list()
        self.current_pcb = None
        
    def setup_scene(self) -> bool:
        """
        Set up PCB inspection environment in UE5.
        
        Scene setup:
        - Load inspection table with neutral background
        - Position overhead camera mount (30-60cm height)
        - Set up industrial LED lighting arrays
        - Load PCB mesh from CAD models
        - Spawn electronic components (ICs, resistors, capacitors)
        
        TODO: Replace with actual UE5 C++ plugin communication
        """
        print(f"[Industrial] Setting up PCB inspection scene")
        
        # TODO: UE5 plugin calls
        # self.ue5_bridge.load_map("PCB_InspectionLab")
        # self.ue5_bridge.spawn_actor("InspectionTable")
        # self.ue5_bridge.set_camera_mount_height(random.uniform(30, 60))
        
        # Mock: Simulate loading PCB
        pcb_types = ['single_layer', 'double_layer', 'multi_layer']
        self.current_pcb = random.choice(pcb_types)
        print(f"[Industrial] Loaded {self.current_pcb} PCB with {len(self.component_types)} component types")
        
        return True
    
    def randomize_scene(self) -> Dict[str, Any]:
        """
        Apply domain randomization for PCB inspection.
        
        Randomization includes:
        - Lighting: intensity, angle, color temperature (industrial LEDs)
        - Materials: PCB surface finish (matte/glossy), solder shine
        - Poses: PCB rotation (0-360°), slight tilt angles
        - Defects: inject realistic manufacturing defects
        - Camera: FOV, height, viewing angle variation
        """
        randomization_params = {
            'lighting': {
                'intensity': random.uniform(0.6, 1.8),  # Industrial LED range
                'color_temp': random.randint(4000, 6500),  # Cool white LEDs
                'num_sources': random.randint(2, 4),  # Multi-directional lighting
                'shadow_softness': random.uniform(0.3, 0.7)
            },
            'material': {
                'pcb_finish': random.choice(['matte_green', 'glossy_green', 'blue', 'black']),
                'solder_metallic': random.uniform(0.7, 0.95),
                'copper_oxidation': random.uniform(0.0, 0.2),  # Surface aging
                'silkscreen_clarity': random.uniform(0.85, 1.0)
            },
            'pose': {
                'rotation_z': random.uniform(0, 360),  # PCB can be any orientation
                'tilt_x': random.uniform(-5, 5),  # Slight manufacturing variations
                'tilt_y': random.uniform(-5, 5),
                'position_offset': [random.uniform(-3, 3), random.uniform(-3, 3)]
            },
            'defects': {
                'has_defect': random.random() < 0.30,  # 30% defect rate for training
                'defect_type': random.choice(self.defect_types) if random.random() < 0.30 else None,
                'defect_severity': random.uniform(0.2, 1.0) if random.random() < 0.30 else 0.0
            },
            'camera': {
                'fov': random.uniform(55, 75),  # Inspection camera range
                'height_cm': random.uniform(35, 55),
                'angle_deviation': random.uniform(-10, 10)  # From perpendicular
            }
        }
        
        # TODO: Apply to UE5 scene
        # self.ue5_bridge.set_light_params(randomization_params['lighting'])
        # self.ue5_bridge.set_material_properties(randomization_params['material'])
        # self.ue5_bridge.rotate_actor('PCB', randomization_params['pose'])
        # if randomization_params['defects']['has_defect']:
        #     self.ue5_bridge.inject_defect(randomization_params['defects'])
        
        print(f"[Industrial] Randomized - Defect: {randomization_params['defects']['defect_type']}")
        
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
        """
        # TODO: Implement actual validation via UE5
        # bounds_check = self.ue5_bridge.is_actor_in_frame('PCB')
        # exposure_check = self.ue5_bridge.check_exposure_levels()
        # component_count = len(self.ue5_bridge.get_visible_components())
        
        # Mock validation: randomly reject 8% of scenes
        is_valid = random.random() > 0.08
        
        if not is_valid:
            print("[Industrial] Scene validation failed - regenerating")
        
        return is_valid

