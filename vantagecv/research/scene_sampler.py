#==============================================================================
# VantageCV Research - Scene Sampler
#==============================================================================
# Distributional sampling for vehicle counts and scene parameters
# Designed for controlled ablation studies and dataset distribution shaping
#==============================================================================

import random
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EnvironmentType(Enum):
    """Scene environment types."""
    URBAN = "urban"
    SUBURBAN = "suburban"
    HIGHWAY = "highway"


class TimeOfDay(Enum):
    """Time of day categories with sun parameters."""
    DAWN = "dawn"
    NOON = "noon"
    DUSK = "dusk"
    NIGHT = "night"


class WeatherCondition(Enum):
    """Weather conditions with visual effects."""
    CLEAR = "clear"
    RAIN = "rain"
    FOG = "fog"
    SNOW = "snow"


class RoadGeometry(Enum):
    """Road layout types."""
    STRAIGHT = "straight"
    CURVED = "curved"
    INTERSECTION = "intersection"


@dataclass
class VehicleDistribution:
    """
    Research-grade vehicle count distribution.
    
    Based on empirical traffic density distributions for training
    robust perception models across sparse-to-dense scenarios.
    
    Distribution rationale:
    - Single vehicle (15-20%): Pure class/pose/scale learning
    - Medium density (40-50%): Realistic traffic patterns
    - High density (20-25%): Occlusion and stress testing
    - Very high density (5-10%): Edge case robustness
    """
    # Distribution buckets: (min_count, max_count, probability)
    buckets: List[Tuple[int, int, float]] = field(default_factory=lambda: [
        (1, 1, 0.175),     # 15-20% single vehicle
        (2, 4, 0.45),      # 40-50% medium density
        (5, 10, 0.225),    # 20-25% high density  
        (11, 23, 0.075),   # 5-10% very high density (max 23 vehicles available)
    ])
    
    def sample(self) -> int:
        """Sample vehicle count from distribution."""
        r = random.random()
        cumulative = 0.0
        
        for min_count, max_count, prob in self.buckets:
            cumulative += prob
            if r <= cumulative:
                return random.randint(min_count, max_count)
        
        # Fallback to last bucket
        min_count, max_count, _ = self.buckets[-1]
        return random.randint(min_count, max_count)
    
    def get_bucket_label(self, count: int) -> str:
        """Get human-readable bucket label for a count."""
        if count == 1:
            return "single"
        elif 2 <= count <= 4:
            return "medium"
        elif 5 <= count <= 10:
            return "high"
        else:
            return "very_high"


@dataclass
class CameraConfig:
    """Dashcam-style camera configuration with research-grade jitter."""
    height_range: Tuple[float, float] = (120.0, 180.0)  # cm, typical dashcam
    fov_range: Tuple[float, float] = (60.0, 120.0)       # degrees
    pitch_jitter: Tuple[float, float] = (-5.0, 5.0)      # degrees
    roll_jitter: Tuple[float, float] = (-2.0, 2.0)       # degrees
    translation_jitter: Tuple[float, float] = (-10.0, 10.0)  # cm lateral
    
    def sample(self) -> Dict:
        """Sample camera configuration."""
        return {
            'height': random.uniform(*self.height_range),
            'fov': random.uniform(*self.fov_range),
            'pitch': random.uniform(*self.pitch_jitter),
            'roll': random.uniform(*self.roll_jitter),
            'lateral_offset': random.uniform(*self.translation_jitter)
        }


@dataclass
class LightingConfig:
    """Time-of-day and lighting configuration."""
    
    # Sun elevation ranges by time of day (degrees)
    sun_elevation_ranges: Dict[TimeOfDay, Tuple[float, float]] = field(default_factory=lambda: {
        TimeOfDay.DAWN: (5.0, 20.0),
        TimeOfDay.NOON: (60.0, 90.0),
        TimeOfDay.DUSK: (5.0, 20.0),
        TimeOfDay.NIGHT: (-30.0, -5.0),
    })
    
    # Sun azimuth (full 360 for variety)
    azimuth_range: Tuple[float, float] = (0.0, 360.0)
    
    # Shadow intensity by time of day
    shadow_intensity: Dict[TimeOfDay, Tuple[float, float]] = field(default_factory=lambda: {
        TimeOfDay.DAWN: (0.3, 0.6),
        TimeOfDay.NOON: (0.8, 1.0),
        TimeOfDay.DUSK: (0.3, 0.6),
        TimeOfDay.NIGHT: (0.0, 0.2),
    })
    
    def sample(self, time_of_day: TimeOfDay) -> Dict:
        """Sample lighting parameters for given time of day."""
        return {
            'time_of_day': time_of_day.value,
            'sun_elevation': random.uniform(*self.sun_elevation_ranges[time_of_day]),
            'sun_azimuth': random.uniform(*self.azimuth_range),
            'shadow_intensity': random.uniform(*self.shadow_intensity[time_of_day])
        }


@dataclass
class WeatherConfig:
    """Weather condition configuration with visual parameters."""
    
    # Visibility range in meters for fog
    fog_visibility_range: Tuple[float, float] = (50.0, 500.0)
    
    # Rain intensity (0-1)
    rain_intensity_range: Tuple[float, float] = (0.2, 1.0)
    
    # Wet road reflectivity for rain
    wet_road_reflectivity: Tuple[float, float] = (0.3, 0.8)
    
    def sample(self, condition: WeatherCondition) -> Dict:
        """Sample weather parameters."""
        params = {'condition': condition.value}
        
        if condition == WeatherCondition.FOG:
            params['visibility'] = random.uniform(*self.fog_visibility_range)
        elif condition == WeatherCondition.RAIN:
            params['intensity'] = random.uniform(*self.rain_intensity_range)
            params['road_wetness'] = random.uniform(*self.wet_road_reflectivity)
        elif condition == WeatherCondition.SNOW:
            params['intensity'] = random.uniform(0.1, 0.8)
            
        return params


class SceneSampler:
    """
    Research-grade scene parameter sampler.
    
    Provides controlled, reproducible sampling of all scene parameters
    with support for:
    - Distributional vehicle counts
    - Environment/weather/lighting diversity
    - Camera configuration jitter
    - Seed-based reproducibility for ablation studies
    """
    
    def __init__(self, 
                 vehicle_distribution: Optional[VehicleDistribution] = None,
                 camera_config: Optional[CameraConfig] = None,
                 lighting_config: Optional[LightingConfig] = None,
                 weather_config: Optional[WeatherConfig] = None,
                 seed: Optional[int] = None):
        """
        Initialize sampler with configuration.
        
        Args:
            vehicle_distribution: Vehicle count distribution
            camera_config: Camera parameter ranges
            lighting_config: Lighting parameter ranges
            weather_config: Weather parameter ranges
            seed: Random seed for reproducibility
        """
        self.vehicle_dist = vehicle_distribution or VehicleDistribution()
        self.camera_config = camera_config or CameraConfig()
        self.lighting_config = lighting_config or LightingConfig()
        self.weather_config = weather_config or WeatherConfig()
        
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            
        # Distribution weights for categorical variables
        self.environment_weights = {
            EnvironmentType.URBAN: 0.5,
            EnvironmentType.SUBURBAN: 0.3,
            EnvironmentType.HIGHWAY: 0.2
        }
        
        self.time_weights = {
            TimeOfDay.NOON: 1.0,      # Force NOON only for bright images
            TimeOfDay.DAWN: 0.0,
            TimeOfDay.DUSK: 0.0,
            TimeOfDay.NIGHT: 0.0
        }
        
        self.weather_weights = {
            WeatherCondition.CLEAR: 0.6,
            WeatherCondition.RAIN: 0.2,
            WeatherCondition.FOG: 0.15,
            WeatherCondition.SNOW: 0.05
        }
        
        self.road_geometry_weights = {
            RoadGeometry.STRAIGHT: 0.5,
            RoadGeometry.CURVED: 0.3,
            RoadGeometry.INTERSECTION: 0.2
        }
    
    def _weighted_choice(self, weights: Dict) -> any:
        """Sample from weighted categorical distribution."""
        items = list(weights.keys())
        probs = list(weights.values())
        return random.choices(items, weights=probs, k=1)[0]
    
    def sample_scene(self) -> Dict:
        """
        Sample complete scene configuration.
        
        Returns:
            Dict containing all scene parameters for one frame
        """
        # Sample categorical variables
        environment = self._weighted_choice(self.environment_weights)
        time_of_day = self._weighted_choice(self.time_weights)
        weather = self._weighted_choice(self.weather_weights)
        road_geometry = self._weighted_choice(self.road_geometry_weights)
        
        # Sample vehicle count from distribution
        vehicle_count = self.vehicle_dist.sample()
        vehicle_bucket = self.vehicle_dist.get_bucket_label(vehicle_count)
        
        # Sample continuous parameters
        camera = self.camera_config.sample()
        lighting = self.lighting_config.sample(time_of_day)
        weather_params = self.weather_config.sample(weather)
        
        # Lane count based on environment
        if environment == EnvironmentType.HIGHWAY:
            lane_count = random.randint(2, 6)
        elif environment == EnvironmentType.URBAN:
            lane_count = random.randint(2, 4)
        else:
            lane_count = random.randint(1, 3)
        
        return {
            'vehicle_count': vehicle_count,
            'vehicle_bucket': vehicle_bucket,
            'environment': environment.value,
            'road_geometry': road_geometry.value,
            'lane_count': lane_count,
            'time_of_day': time_of_day.value,
            'lighting': lighting,
            'weather': weather_params,
            'camera': camera
        }
    
    def sample_vehicle_appearance(self) -> Dict:
        """
        Sample individual vehicle appearance parameters.
        
        Returns:
            Dict with vehicle-level randomization parameters
        """
        return {
            'color_hue': random.uniform(0.0, 1.0),
            'color_saturation': random.uniform(0.3, 1.0),
            'color_value': random.uniform(0.2, 1.0),
            'roughness': random.uniform(0.1, 0.8),
            'dirt_level': random.uniform(0.0, 0.5),
            'wear_level': random.uniform(0.0, 0.3),
            'scale_jitter': random.uniform(0.95, 1.05),  # ±5%
        }
    
    def sample_vehicle_placement(self, camera_distance_range: Tuple[float, float] = (1000.0, 8000.0)) -> Dict:
        """
        Sample vehicle placement parameters.
        
        Args:
            camera_distance_range: Min/max distance from camera in cm
            
        Returns:
            Dict with placement parameters
        """
        return {
            'distance_from_camera': random.uniform(*camera_distance_range),
            'lane_offset_noise': random.uniform(-50.0, 50.0),  # cm lateral
            'is_truncated': random.random() < 0.15,  # 15% chance of truncation
            'truncation_side': random.choice(['left', 'right', 'top', 'bottom']) if random.random() < 0.15 else None
        }
    
    def sample_vehicle_motion(self, environment: str) -> Dict:
        """
        Sample vehicle motion parameters based on environment.
        
        Args:
            environment: Scene environment type
            
        Returns:
            Dict with motion parameters
        """
        # Speed distributions by environment (km/h)
        speed_ranges = {
            'highway': (60.0, 130.0),
            'urban': (0.0, 50.0),
            'suburban': (20.0, 70.0)
        }
        
        speed_range = speed_ranges.get(environment, (0.0, 50.0))
        
        return {
            'is_moving': random.random() < 0.7,  # 70% moving
            'speed': random.uniform(*speed_range),
            'trajectory': random.choice(['straight', 'turning']) if random.random() < 0.8 else 'straight'
        }


def create_sampler_from_config(config: Dict, seed: Optional[int] = None) -> SceneSampler:
    """
    Create SceneSampler from configuration dictionary.
    
    Args:
        config: Configuration dictionary with sampling parameters
        seed: Random seed for reproducibility
        
    Returns:
        Configured SceneSampler instance
    """
    scene_config = config.get('scene_sampling', {})
    
    # Build vehicle distribution from config
    vehicle_buckets = scene_config.get('vehicle_distribution', {})
    if vehicle_buckets:
        buckets = [
            (1, 1, vehicle_buckets.get('single', 0.175)),
            (2, 4, vehicle_buckets.get('medium', 0.45)),
            (5, 10, vehicle_buckets.get('high', 0.225)),
            (11, 23, vehicle_buckets.get('very_high', 0.075)),
        ]
        vehicle_dist = VehicleDistribution(buckets=buckets)
    else:
        vehicle_dist = VehicleDistribution()
    
    # Build camera config
    camera_params = scene_config.get('camera', {})
    camera_config = CameraConfig(
        height_range=tuple(camera_params.get('height_range', [120.0, 180.0])),
        fov_range=tuple(camera_params.get('fov_range', [60.0, 120.0])),
        pitch_jitter=tuple(camera_params.get('pitch_jitter', [-5.0, 5.0])),
        roll_jitter=tuple(camera_params.get('roll_jitter', [-2.0, 2.0]))
    )
    
    return SceneSampler(
        vehicle_distribution=vehicle_dist,
        camera_config=camera_config,
        seed=seed
    )
