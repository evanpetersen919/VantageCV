#==============================================================================
# VantageCV Research - Edge Case Scenarios
#==============================================================================
# Explicit scenario generators for long-tail robustness testing
# Each scenario tagged with unique ID for controlled ablation studies
#==============================================================================

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EdgeCaseType(Enum):
    """
    Edge case scenario types for robustness testing.
    
    Each scenario represents challenging conditions that perception
    models must handle for real-world deployment.
    """
    NIGHT_GLARE = "night_glare"           # Night + headlight glare
    BACKLIGHTING = "backlighting"          # Strong sun behind subjects
    TRAFFIC_JAM = "traffic_jam"            # High density, many occlusions
    EXTREME_PITCH = "extreme_pitch"        # Unusual camera angle
    MOTION_BLUR = "motion_blur"            # High-speed motion blur
    SEVERE_OCCLUSION = "severe_occlusion"  # Heavy occlusion clusters
    FOG_LOW_VISIBILITY = "fog_low_visibility"  # Dense fog
    RAIN_REFLECTIONS = "rain_reflections"   # Wet roads with reflections
    DUSK_SHADOWS = "dusk_shadows"          # Long shadows, mixed lighting
    SMALL_OBJECTS = "small_objects"        # Distant motorcycles/bicycles


@dataclass
class ScenarioConfig:
    """Configuration for a specific edge case scenario."""
    scenario_type: EdgeCaseType
    scenario_id: str
    description: str
    parameters: Dict
    target_percentage: float  # Percentage of dataset for this scenario
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for export."""
        return {
            'scenario_type': self.scenario_type.value,
            'scenario_id': self.scenario_id,
            'description': self.description,
            'parameters': self.parameters,
            'target_percentage': self.target_percentage
        }


class ScenarioGenerator:
    """
    Research-grade edge case scenario generator.
    
    Generates controlled challenging scenarios for:
    - Long-tail robustness evaluation
    - Failure mode analysis
    - Targeted data augmentation
    
    Each scenario is tagged with a unique ID for tracking and analysis.
    """
    
    # Default scenario configurations with research-informed parameters
    SCENARIO_CONFIGS = {
        EdgeCaseType.NIGHT_GLARE: ScenarioConfig(
            scenario_type=EdgeCaseType.NIGHT_GLARE,
            scenario_id="EC001",
            description="Night scene with vehicle headlight glare",
            parameters={
                'time_of_day': 'night',
                'headlight_intensity': (0.8, 1.0),
                'glare_bloom_strength': (0.5, 0.9),
                'ambient_light': (0.02, 0.1),
                'headlight_count': (2, 8)
            },
            target_percentage=0.05
        ),
        
        EdgeCaseType.BACKLIGHTING: ScenarioConfig(
            scenario_type=EdgeCaseType.BACKLIGHTING,
            scenario_id="EC002",
            description="Strong backlighting with sun behind subjects",
            parameters={
                'time_of_day': 'dawn',  # or dusk
                'sun_elevation': (5.0, 15.0),
                'sun_in_frame': True,
                'exposure_compensation': (-2.0, -1.0),
                'silhouette_strength': (0.4, 0.8)
            },
            target_percentage=0.04
        ),
        
        EdgeCaseType.TRAFFIC_JAM: ScenarioConfig(
            scenario_type=EdgeCaseType.TRAFFIC_JAM,
            scenario_id="EC003",
            description="High vehicle density traffic jam scenario",
            parameters={
                'vehicle_count': (15, 23),  # Max available
                'vehicle_spacing': (100.0, 300.0),  # Very close
                'vehicle_speed': (0.0, 5.0),  # Near stationary
                'lane_discipline': False,  # Vehicles overlap lanes
                'occlusion_target': 0.6
            },
            target_percentage=0.05
        ),
        
        EdgeCaseType.EXTREME_PITCH: ScenarioConfig(
            scenario_type=EdgeCaseType.EXTREME_PITCH,
            scenario_id="EC004",
            description="Unusual camera pitch angle",
            parameters={
                'camera_pitch': (-25.0, -15.0),  # or (15.0, 25.0)
                'fov_adjustment': (0.8, 1.0),  # Slight FOV change
                'horizon_offset': True
            },
            target_percentage=0.03
        ),
        
        EdgeCaseType.MOTION_BLUR: ScenarioConfig(
            scenario_type=EdgeCaseType.MOTION_BLUR,
            scenario_id="EC005",
            description="High-speed motion blur effects",
            parameters={
                'vehicle_speed': (80.0, 150.0),
                'shutter_speed': (1/30, 1/15),  # Slow shutter
                'blur_direction': 'horizontal',
                'blur_strength': (0.3, 0.7)
            },
            target_percentage=0.04
        ),
        
        EdgeCaseType.SEVERE_OCCLUSION: ScenarioConfig(
            scenario_type=EdgeCaseType.SEVERE_OCCLUSION,
            scenario_id="EC006",
            description="Heavy vehicle-on-vehicle occlusion clusters",
            parameters={
                'vehicle_count': (8, 15),
                'occlusion_target': 0.7,  # 70% of vehicles occluded
                'cluster_count': (2, 4),
                'min_visibility': 0.2  # Heavily occluded but visible
            },
            target_percentage=0.05
        ),
        
        EdgeCaseType.FOG_LOW_VISIBILITY: ScenarioConfig(
            scenario_type=EdgeCaseType.FOG_LOW_VISIBILITY,
            scenario_id="EC007",
            description="Dense fog with very low visibility",
            parameters={
                'weather': 'fog',
                'visibility_range': (20.0, 80.0),  # meters
                'fog_density': (0.6, 0.9),
                'color_desaturation': (0.3, 0.6)
            },
            target_percentage=0.04
        ),
        
        EdgeCaseType.RAIN_REFLECTIONS: ScenarioConfig(
            scenario_type=EdgeCaseType.RAIN_REFLECTIONS,
            scenario_id="EC008",
            description="Rain with wet road reflections",
            parameters={
                'weather': 'rain',
                'rain_intensity': (0.5, 1.0),
                'road_wetness': (0.6, 1.0),
                'reflection_strength': (0.4, 0.8),
                'spray_from_vehicles': True
            },
            target_percentage=0.04
        ),
        
        EdgeCaseType.DUSK_SHADOWS: ScenarioConfig(
            scenario_type=EdgeCaseType.DUSK_SHADOWS,
            scenario_id="EC009",
            description="Dusk with long shadows and mixed lighting",
            parameters={
                'time_of_day': 'dusk',
                'sun_elevation': (5.0, 15.0),
                'shadow_length_multiplier': (3.0, 6.0),
                'artificial_lights_on': True,
                'mixed_color_temp': True
            },
            target_percentage=0.04
        ),
        
        EdgeCaseType.SMALL_OBJECTS: ScenarioConfig(
            scenario_type=EdgeCaseType.SMALL_OBJECTS,
            scenario_id="EC010",
            description="Distant small objects (motorcycles, bicycles)",
            parameters={
                'primary_classes': ['motorcycle', 'bicycle'],
                'distance_range': (5000.0, 10000.0),  # Far away
                'min_pixel_height': 20,
                'max_pixel_height': 60,
                'count': (3, 8)
            },
            target_percentage=0.03
        )
    }
    
    def __init__(self, 
                 enabled_scenarios: Optional[List[EdgeCaseType]] = None,
                 custom_configs: Optional[Dict[EdgeCaseType, ScenarioConfig]] = None):
        """
        Initialize scenario generator.
        
        Args:
            enabled_scenarios: List of scenarios to enable (all by default)
            custom_configs: Custom scenario configurations to override defaults
        """
        self.scenarios = dict(self.SCENARIO_CONFIGS)
        
        # Apply custom configs
        if custom_configs:
            for scenario_type, config in custom_configs.items():
                self.scenarios[scenario_type] = config
        
        # Filter to enabled scenarios
        if enabled_scenarios:
            self.scenarios = {k: v for k, v in self.scenarios.items() 
                             if k in enabled_scenarios}
        
        # Track generation counts for distribution balancing
        self.generation_counts = {s: 0 for s in self.scenarios}
        self.total_generated = 0
    
    def should_generate_edge_case(self) -> Tuple[bool, Optional[EdgeCaseType]]:
        """
        Determine if next image should be an edge case.
        
        Uses weighted sampling based on target percentages and
        current generation counts to maintain distribution.
        
        Returns:
            Tuple of (should_generate, scenario_type)
        """
        if not self.scenarios:
            return False, None
        
        # Calculate total target percentage
        total_target = sum(s.target_percentage for s in self.scenarios.values())
        
        # Random chance of generating edge case
        if random.random() > total_target:
            return False, None
        
        # Weight by under-representation
        weights = []
        types = []
        
        for scenario_type, config in self.scenarios.items():
            if self.total_generated == 0:
                actual_ratio = 0
            else:
                actual_ratio = self.generation_counts[scenario_type] / self.total_generated
            
            target_ratio = config.target_percentage
            weight = max(0.1, target_ratio - actual_ratio + 0.5)
            weights.append(weight)
            types.append(scenario_type)
        
        # Weighted random selection
        selected = random.choices(types, weights=weights, k=1)[0]
        return True, selected
    
    def generate_scenario(self, scenario_type: EdgeCaseType) -> Dict:
        """
        Generate parameters for a specific scenario.
        
        Args:
            scenario_type: Type of edge case scenario
            
        Returns:
            Dict with all scene parameters for this scenario
        """
        config = self.scenarios.get(scenario_type)
        if not config:
            logger.warning(f"Unknown scenario type: {scenario_type}")
            return {}
        
        # Update tracking
        self.generation_counts[scenario_type] += 1
        self.total_generated += 1
        
        # Generate parameters by sampling from ranges
        params = {'scenario_id': config.scenario_id, 
                  'scenario_type': config.scenario_type.value}
        
        for key, value in config.parameters.items():
            if isinstance(value, tuple) and len(value) == 2:
                if isinstance(value[0], float):
                    params[key] = random.uniform(value[0], value[1])
                elif isinstance(value[0], int):
                    params[key] = random.randint(value[0], value[1])
                else:
                    params[key] = value
            else:
                params[key] = value
        
        return params
    
    def get_scenario_config(self, scenario_type: EdgeCaseType) -> ScenarioConfig:
        """Get configuration for a scenario type."""
        return self.scenarios.get(scenario_type)
    
    def get_distribution_stats(self) -> Dict:
        """
        Get current distribution statistics.
        
        Returns:
            Dict with per-scenario generation counts and ratios
        """
        stats = {
            'total_generated': self.total_generated,
            'edge_cases_generated': sum(self.generation_counts.values()),
            'scenarios': {}
        }
        
        for scenario_type, count in self.generation_counts.items():
            config = self.scenarios[scenario_type]
            actual_ratio = count / max(1, self.total_generated)
            stats['scenarios'][scenario_type.value] = {
                'scenario_id': config.scenario_id,
                'count': count,
                'actual_ratio': round(actual_ratio, 4),
                'target_ratio': config.target_percentage,
                'deviation': round(actual_ratio - config.target_percentage, 4)
            }
        
        return stats
    
    def reset_counts(self):
        """Reset generation counts for a new dataset."""
        self.generation_counts = {s: 0 for s in self.scenarios}
        self.total_generated = 0


def apply_night_glare_params(base_params: Dict, scenario_params: Dict) -> Dict:
    """Apply night glare scenario modifications."""
    result = dict(base_params)
    result['lighting']['time_of_day'] = 'night'
    result['lighting']['sun_elevation'] = -20.0
    result['post_process'] = {
        'bloom_intensity': scenario_params.get('glare_bloom_strength', 0.7),
        'exposure': scenario_params.get('ambient_light', 0.05)
    }
    return result


def apply_traffic_jam_params(base_params: Dict, scenario_params: Dict) -> Dict:
    """Apply traffic jam scenario modifications."""
    result = dict(base_params)
    result['vehicle_count'] = scenario_params.get('vehicle_count', 18)
    result['vehicle_spacing_override'] = scenario_params.get('vehicle_spacing', 200.0)
    result['occlusion_target'] = scenario_params.get('occlusion_target', 0.6)
    return result


def apply_fog_params(base_params: Dict, scenario_params: Dict) -> Dict:
    """Apply fog scenario modifications."""
    result = dict(base_params)
    result['weather'] = {
        'condition': 'fog',
        'visibility': scenario_params.get('visibility_range', 50.0),
        'density': scenario_params.get('fog_density', 0.7)
    }
    return result


# Scenario application function map
SCENARIO_APPLICATORS = {
    EdgeCaseType.NIGHT_GLARE: apply_night_glare_params,
    EdgeCaseType.TRAFFIC_JAM: apply_traffic_jam_params,
    EdgeCaseType.FOG_LOW_VISIBILITY: apply_fog_params,
    # Add more as needed
}
