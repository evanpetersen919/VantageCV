#==============================================================================
# VantageCV - Domain Randomization Utilities
#==============================================================================
# File: randomization.py
# Description: Helper functions for scene randomization (lighting, materials,
#              camera poses, object placement) for domain randomization
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import random
import logging
from typing import Dict, Any, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class LightingRandomizer:
    """
    Randomize lighting parameters for photorealistic rendering.
    
    Handles different lighting scenarios:
    - Industrial: Overhead LED arrays, task lighting
    - Automotive: Sun position, ambient occlusion, HDR skybox
    - General: Point lights, spotlights, area lights
    """
    
    @staticmethod
    def randomize_industrial_lighting() -> Dict[str, Any]:
        """
        Generate randomized industrial lighting parameters.
        
        Industrial settings typically use:
        - Overhead LED panels (4000-6500K color temperature)
        - Multiple light sources for even illumination
        - Minimal shadows (high ambient + fill lights)
        
        Returns:
            Dictionary with lighting parameters
        """
        return {
            'type': 'industrial_led',
            'intensity': random.uniform(0.7, 1.5),  # Lumens multiplier
            'color_temperature': random.randint(4000, 6500),  # Kelvin
            'num_sources': random.randint(2, 4),  # Multi-directional
            'shadow_softness': random.uniform(0.4, 0.8),  # Soft shadows
            'ambient_occlusion': random.uniform(0.3, 0.6),
            'indirect_intensity': random.uniform(0.5, 0.9)
        }
    
    @staticmethod
    def randomize_automotive_lighting(time_of_day: str = None) -> Dict[str, Any]:
        """
        Generate randomized automotive/outdoor lighting.
        
        Automotive scenarios have dynamic lighting:
        - Sun position varies by time of day
        - Weather affects ambient intensity
        - HDR skybox for realistic reflections
        
        Args:
            time_of_day: Optional time ('dawn', 'day', 'dusk', 'night')
            
        Returns:
            Dictionary with lighting parameters
        """
        if time_of_day is None:
            time_of_day = random.choice(['dawn', 'day', 'dusk', 'night'])
        
        # Sun angle and intensity based on time
        sun_angles = {
            'dawn': (5, 20),     # Low angle, soft light
            'day': (40, 80),     # High angle, bright
            'dusk': (5, 20),     # Low angle, warm
            'night': (-10, 0)    # Below horizon
        }
        
        sun_intensities = {
            'dawn': (0.4, 0.7),
            'day': (0.9, 1.2),
            'dusk': (0.3, 0.6),
            'night': (0.0, 0.1)
        }
        
        angle_range = sun_angles[time_of_day]
        intensity_range = sun_intensities[time_of_day]
        
        return {
            'type': 'outdoor_sun',
            'time_of_day': time_of_day,
            'sun_angle': random.uniform(*angle_range),
            'sun_intensity': random.uniform(*intensity_range),
            'ambient_intensity': random.uniform(0.3, 0.7),
            'shadow_intensity': random.uniform(0.5, 0.95),
            'sky_brightness': random.uniform(0.6, 1.0),
            'cloud_coverage': random.uniform(0.0, 0.8)
        }


class MaterialRandomizer:
    """
    Randomize material properties for visual diversity.
    
    Varies:
    - Albedo/diffuse color
    - Roughness/glossiness
    - Metallic properties
    - Normal map intensity
    """
    
    @staticmethod
    def randomize_pcb_materials() -> Dict[str, Any]:
        """
        Randomize PCB surface materials.
        
        PCBs have characteristic green solder mask with varying:
        - Surface finish (glossy to matte)
        - Copper exposure (oxidation)
        - Solder shine
        
        Returns:
            Material parameter dictionary
        """
        return {
            'pcb_finish': random.choice(['glossy', 'semi_gloss', 'matte']),
            'pcb_color_variation': random.uniform(0.9, 1.1),  # Green hue shift
            'roughness': random.uniform(0.3, 0.7),
            'copper_oxidation': random.uniform(0.0, 0.3),
            'solder_metallic': random.uniform(0.7, 0.95),
            'component_wear': random.uniform(0.0, 0.2)
        }
    
    @staticmethod
    def randomize_vehicle_materials() -> Dict[str, Any]:
        """
        Randomize vehicle paint and materials.
        
        Vehicles have:
        - Various paint colors and finishes
        - Weathering/dirt accumulation
        - Window tint variations
        
        Returns:
            Material parameter dictionary
        """
        paint_colors = [
            (0.1, 0.1, 0.1),  # Black
            (0.9, 0.9, 0.9),  # White
            (0.5, 0.5, 0.5),  # Silver
            (0.7, 0.1, 0.1),  # Red
            (0.1, 0.2, 0.5),  # Blue
        ]
        
        return {
            'paint_color': random.choice(paint_colors),
            'paint_metallic': random.uniform(0.3, 0.9),
            'paint_roughness': random.uniform(0.1, 0.4),
            'dirt_amount': random.uniform(0.0, 0.5),
            'window_tint': random.uniform(0.1, 0.6),
            'tire_wear': random.uniform(0.0, 0.4)
        }


class CameraRandomizer:
    """
    Randomize camera parameters for viewpoint diversity.
    
    Varies:
    - Position (X, Y, Z)
    - Rotation (pitch, yaw, roll)
    - Field of view
    - Focus distance
    """
    
    @staticmethod
    def randomize_inspection_camera(
        height_range: Tuple[float, float] = (30, 60),
        angle_deviation: float = 10.0
    ) -> Dict[str, Any]:
        """
        Randomize overhead inspection camera.
        
        Inspection cameras are typically:
        - Overhead (looking down)
        - Fixed height range
        - Slight angle variations
        
        Args:
            height_range: Min/max height in cm
            angle_deviation: Max deviation from perpendicular (degrees)
            
        Returns:
            Camera parameter dictionary
        """
        return {
            'type': 'inspection',
            'height_cm': random.uniform(*height_range),
            'pitch': -90 + random.uniform(-angle_deviation, angle_deviation),
            'yaw': random.uniform(0, 360),
            'roll': random.uniform(-5, 5),
            'fov': random.uniform(55, 75),
            'position_offset_xy': (random.uniform(-3, 3), random.uniform(-3, 3))
        }
    
    @staticmethod
    def randomize_vehicle_camera(
        height_range: Tuple[float, float] = (1.2, 1.8),
        tilt_range: Tuple[float, float] = (-5, 5)
    ) -> Dict[str, Any]:
        """
        Randomize vehicle-mounted camera.
        
        Vehicle cameras:
        - Forward-facing
        - Mounted at realistic heights
        - Slight tilt variations
        
        Args:
            height_range: Camera height in meters
            tilt_range: Pitch angle range in degrees
            
        Returns:
            Camera parameter dictionary
        """
        return {
            'type': 'vehicle_mounted',
            'height_m': random.uniform(*height_range),
            'pitch': random.uniform(*tilt_range),
            'yaw': random.uniform(-2, 2),  # Mostly forward
            'roll': random.uniform(-1, 1),
            'fov': random.uniform(70, 90),  # Wide FOV for driving
            'lateral_offset_m': random.uniform(-0.3, 0.3)
        }


class ObjectRandomizer:
    """
    Randomize object placement and poses.
    
    Handles:
    - Position (X, Y, Z)
    - Rotation (Euler angles or quaternions)
    - Scale variations
    - Occlusion management
    """
    
    @staticmethod
    def randomize_component_placement(
        num_components: int,
        bounds: Tuple[float, float, float, float]
    ) -> List[Dict[str, Any]]:
        """
        Generate random component placements on PCB.
        
        Args:
            num_components: Number of components to place
            bounds: (min_x, min_y, max_x, max_y) in pixels
            
        Returns:
            List of component placement dictionaries
        """
        min_x, min_y, max_x, max_y = bounds
        placements = []
        
        for _ in range(num_components):
            placement = {
                'position': (
                    random.uniform(min_x, max_x),
                    random.uniform(min_y, max_y)
                ),
                'rotation_z': random.uniform(0, 360),  # Flat on PCB
                'rotation_xy': random.uniform(-2, 2),  # Slight tilt
                'scale': random.uniform(0.9, 1.1)
            }
            placements.append(placement)
        
        return placements
    
    @staticmethod
    def randomize_vehicle_placement(
        lane_position: str = 'center',
        distance_range: Tuple[float, float] = (5, 50)
    ) -> Dict[str, Any]:
        """
        Generate random vehicle placement in traffic scene.
        
        Args:
            lane_position: 'left', 'center', 'right'
            distance_range: Forward distance range in meters
            
        Returns:
            Vehicle placement dictionary
        """
        lane_offsets = {
            'left': -3.5,
            'center': 0.0,
            'right': 3.5
        }
        
        return {
            'distance_m': random.uniform(*distance_range),
            'lateral_offset_m': lane_offsets.get(lane_position, 0.0) + random.uniform(-0.5, 0.5),
            'rotation_y': random.uniform(-5, 5),  # Slight angle
            'speed_kmh': random.uniform(20, 80)
        }


def validate_randomization_params(params: Dict[str, Any], param_type: str) -> bool:
    """
    Validate randomization parameters are within acceptable ranges.
    
    Args:
        params: Randomization parameter dictionary
        param_type: Type of parameters ('lighting', 'material', 'camera', 'object')
        
    Returns:
        True if parameters are valid
        
    Raises:
        ValueError: If parameters are invalid
    """
    if param_type == 'lighting':
        if 'intensity' in params and not (0.0 <= params['intensity'] <= 10.0):
            raise ValueError(f"Lighting intensity must be 0-10, got {params['intensity']}")
    
    elif param_type == 'camera':
        if 'fov' in params and not (10.0 <= params['fov'] <= 120.0):
            raise ValueError(f"Camera FOV must be 10-120 degrees, got {params['fov']}")
    
    elif param_type == 'material':
        if 'roughness' in params and not (0.0 <= params['roughness'] <= 1.0):
            raise ValueError(f"Material roughness must be 0-1, got {params['roughness']}")
    
    return True
