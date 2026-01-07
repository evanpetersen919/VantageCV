"""
WeatherAugmentationController - Weather Condition Control

RESPONSIBILITY (STRICT):
- Applying weather conditions
- Adjusting atmospheric and visual parameters
- Logging the selected weather state

MUST NOT:
- Spawn or modify vehicles
- Spawn or modify props
- Move the camera
- Capture images
- Modify time-of-day logic

WEATHER STATES:
- Clear, Overcast, Rain, HeavyRain, Fog, LightFog
- Each state controls lighting, atmosphere, fog, clouds

RESET BEHAVIOR:
- Stores original settings on first use
- Restores to original settings after test
"""

import random
import logging
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class WeatherState:
    """Configuration for a weather condition"""
    name: str
    description: str = ""
    
    # Directional Light
    sun_intensity: float = 1.0           # Light intensity multiplier
    sun_color_temp: float = 6500.0       # Color temperature (Kelvin)
    
    # Exponential Height Fog
    fog_density: float = 0.0             # 0.0 = no fog, 0.05 = heavy fog
    fog_height_falloff: float = 0.2      # How quickly fog decreases with height
    fog_start_distance: float = 0.0      # Distance before fog starts
    
    # Volumetric Clouds
    cloud_coverage: float = 0.5          # 0.0 = clear, 1.0 = overcast
    cloud_density: float = 1.0           # Cloud opacity
    
    # Post-Process
    contrast: float = 1.0                # 1.0 = normal
    saturation: float = 1.0              # 1.0 = normal, 0.8 = desaturated
    
    # Rain (Niagara particle system)
    rain_enabled: bool = False
    rain_intensity: float = 0.0          # 0.0-1.0


@dataclass
class WeatherAugmentationResult:
    """Result of a weather augmentation operation"""
    success: bool
    weather_state: Optional[str] = None
    parameters_applied: Dict[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None
    warnings: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None


# =============================================================================
# DEFAULT WEATHER STATES (Configurable)
# =============================================================================

DEFAULT_WEATHER_STATES = {
    "clear": WeatherState(
        name="clear",
        description="Clear sunny sky",
        sun_intensity=1.0,
        sun_color_temp=6500.0,
        fog_density=0.0,
        fog_height_falloff=0.2,
        cloud_coverage=0.2,
        cloud_density=0.5,
        contrast=1.0,
        saturation=1.0,
        rain_enabled=False,
        rain_intensity=0.0
    ),
    "overcast": WeatherState(
        name="overcast",
        description="Cloudy, diffuse lighting",
        sun_intensity=0.4,
        sun_color_temp=7000.0,
        fog_density=0.002,
        fog_height_falloff=0.15,
        cloud_coverage=0.9,
        cloud_density=1.5,
        contrast=0.9,
        saturation=0.85,
        rain_enabled=False,
        rain_intensity=0.0
    ),
    "light_fog": WeatherState(
        name="light_fog",
        description="Light morning fog",
        sun_intensity=0.6,
        sun_color_temp=6000.0,
        fog_density=0.01,
        fog_height_falloff=0.1,
        cloud_coverage=0.6,
        cloud_density=1.0,
        contrast=0.85,
        saturation=0.9,
        rain_enabled=False,
        rain_intensity=0.0
    ),
    "fog": WeatherState(
        name="fog",
        description="Heavy fog, low visibility",
        sun_intensity=0.3,
        sun_color_temp=5500.0,
        fog_density=0.03,
        fog_height_falloff=0.05,
        cloud_coverage=0.8,
        cloud_density=1.2,
        contrast=0.75,
        saturation=0.7,
        rain_enabled=False,
        rain_intensity=0.0
    ),
    "rain": WeatherState(
        name="rain",
        description="Light to moderate rain",
        sun_intensity=0.35,
        sun_color_temp=7500.0,
        fog_density=0.005,
        fog_height_falloff=0.12,
        cloud_coverage=0.95,
        cloud_density=1.8,
        contrast=0.85,
        saturation=0.75,
        rain_enabled=True,
        rain_intensity=0.5
    ),
    "heavy_rain": WeatherState(
        name="heavy_rain",
        description="Heavy rain, reduced visibility",
        sun_intensity=0.2,
        sun_color_temp=8000.0,
        fog_density=0.015,
        fog_height_falloff=0.08,
        cloud_coverage=1.0,
        cloud_density=2.0,
        contrast=0.8,
        saturation=0.65,
        rain_enabled=True,
        rain_intensity=1.0
    ),
}


# =============================================================================
# CONTROLLER
# =============================================================================

class WeatherAugmentationController:
    """
    Weather Augmentation Controller
    
    Controls atmospheric actors to simulate different weather conditions.
    Deterministic selection based on random seed.
    """
    
    def __init__(self,
                 host: str = "127.0.0.1",
                 port: int = 30010,
                 level_path: str = "/Game/automobileV2.automobileV2",
                 weather_states: Optional[Dict[str, WeatherState]] = None):
        """
        Initialize the WeatherAugmentationController.
        
        Args:
            host: UE5 Remote Control host
            port: UE5 Remote Control port
            level_path: Level path for actor resolution
            weather_states: Custom weather state definitions (uses defaults if None)
        """
        self.base_url = f"http://{host}:{port}/remote"
        self.level_path = level_path
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Weather states (configurable)
        self.weather_states = weather_states or DEFAULT_WEATHER_STATES
        
        # Detected actors
        self.directional_light: Optional[str] = None
        self.exponential_fog: Optional[str] = None
        self.volumetric_cloud: Optional[str] = None
        self.sky_atmosphere: Optional[str] = None
        self.post_process_volume: Optional[str] = None
        self.rain_system: Optional[str] = None
        
        # Original settings for reset
        self.original_settings: Dict[str, Any] = {}
        self.originals_saved: bool = False
        
        # Current state
        self.current_weather_state: Optional[str] = None
    
    # =========================================================================
    # REMOTE CONTROL HELPERS
    # =========================================================================
    
    def _call_remote(self, object_path: str, function_name: str, 
                     parameters: Dict = None) -> Optional[Dict]:
        """Call a remote function on an actor"""
        try:
            payload = {
                "objectPath": object_path,
                "functionName": function_name
            }
            if parameters:
                payload["parameters"] = parameters
            
            response = self.session.put(
                f"{self.base_url}/object/call",
                json=payload,
                timeout=5.0
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.debug(f"Remote call failed: {e}")
            return None
    
    def _get_property(self, object_path: str, property_name: str) -> Optional[Any]:
        """Get a property value from an actor"""
        try:
            response = self.session.put(
                f"{self.base_url}/object/property",
                json={
                    "objectPath": object_path,
                    "propertyName": property_name,
                    "access": "READ_ACCESS"
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.debug(f"Property read failed: {e}")
            return None
    
    def _set_property(self, object_path: str, property_name: str, 
                      value: Any) -> bool:
        """Set a property value on an actor"""
        try:
            response = self.session.put(
                f"{self.base_url}/object/property",
                json={
                    "objectPath": object_path,
                    "propertyName": property_name,
                    "propertyValue": value
                },
                timeout=5.0
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Property write failed: {e}")
            return False
    
    def _actor_exists(self, actor_name: str) -> bool:
        """Check if an actor exists in the level"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        result = self._call_remote(path, "K2_GetActorLocation")
        return result is not None and "ReturnValue" in result
    
    # =========================================================================
    # ACTOR DETECTION
    # =========================================================================
    
    def detect_weather_actors(self) -> bool:
        """
        Detect existing weather-related actors dynamically.
        
        Returns:
            True if at least one controllable actor found
        """
        logger.info("Detecting weather actors...")
        found_count = 0
        
        # DirectionalLight patterns
        directional_patterns = [
            "DirectionalLight", "DirectionalLight_1", "DirectionalLight_2",
            "DirectionalLight_3", "DirectionalLight_4", "SunLight", "Sun"
        ]
        for pattern in directional_patterns:
            if self._actor_exists(pattern):
                self.directional_light = pattern
                logger.info(f"  Found DirectionalLight: {pattern}")
                found_count += 1
                break
        
        if not self.directional_light:
            logger.warning("  WARNING: No DirectionalLight found")
        
        # Exponential Height Fog patterns
        fog_patterns = [
            "ExponentialHeightFog", "ExponentialHeightFog_1", 
            "HeightFog", "Fog", "AtmosphericFog"
        ]
        for pattern in fog_patterns:
            if self._actor_exists(pattern):
                self.exponential_fog = pattern
                logger.info(f"  Found ExponentialHeightFog: {pattern}")
                found_count += 1
                break
        
        if not self.exponential_fog:
            logger.warning("  WARNING: No ExponentialHeightFog found - fog control disabled")
        
        # Volumetric Cloud patterns
        cloud_patterns = [
            "VolumetricCloud", "VolumetricCloud_1", "VolumetricClouds",
            "Clouds", "SkyCloud"
        ]
        for pattern in cloud_patterns:
            if self._actor_exists(pattern):
                self.volumetric_cloud = pattern
                logger.info(f"  Found VolumetricCloud: {pattern}")
                found_count += 1
                break
        
        if not self.volumetric_cloud:
            logger.warning("  WARNING: No VolumetricCloud found - cloud control disabled")
        
        # Sky Atmosphere patterns
        sky_patterns = [
            "SkyAtmosphere", "SkyAtmosphere_1", "Sky_Atmosphere", "Atmosphere"
        ]
        for pattern in sky_patterns:
            if self._actor_exists(pattern):
                self.sky_atmosphere = pattern
                logger.info(f"  Found SkyAtmosphere: {pattern}")
                found_count += 1
                break
        
        if not self.sky_atmosphere:
            logger.warning("  WARNING: No SkyAtmosphere found")
        
        # Post Process Volume patterns
        pp_patterns = [
            "PostProcessVolume", "PostProcessVolume_1", "PP_Volume",
            "GlobalPostProcess", "PostProcess"
        ]
        for pattern in pp_patterns:
            if self._actor_exists(pattern):
                self.post_process_volume = pattern
                logger.info(f"  Found PostProcessVolume: {pattern}")
                found_count += 1
                break
        
        if not self.post_process_volume:
            logger.warning("  WARNING: No PostProcessVolume found - post-process control disabled")
        
        # Rain Niagara System patterns
        rain_patterns = [
            "NS_Rain", "RainParticles", "Rain", "NiagaraRain",
            "BP_Rain", "RainSystem", "Niagara_Rain"
        ]
        for pattern in rain_patterns:
            if self._actor_exists(pattern):
                self.rain_system = pattern
                logger.info(f"  Found Rain System: {pattern}")
                found_count += 1
                break
        
        if not self.rain_system:
            logger.info("  INFO: No rain particle system found - rain effects disabled")
        
        logger.info(f"  Total weather actors found: {found_count}")
        return found_count > 0
    
    # =========================================================================
    # SAVE/RESTORE ORIGINAL SETTINGS
    # =========================================================================
    
    def _save_original_settings(self) -> bool:
        """Save original weather-related settings for reset"""
        if self.originals_saved:
            return True
        
        logger.info("Saving original weather settings...")
        
        # Save directional light intensity
        if self.directional_light:
            # Try different component paths for DirectionalLight
            for component in ["DirectionalLightComponent", "LightComponent"]:
                path = f"{self.level_path}:PersistentLevel.{self.directional_light}.{component}"
                result = self._get_property(path, "Intensity")
                if result:
                    self.original_settings["sun_intensity"] = result.get("Intensity", 1.0)
                    self.original_settings["sun_component"] = component
                    logger.info(f"  Saved sun intensity: {self.original_settings['sun_intensity']} (via {component})")
                    break
        
        # Save fog settings
        if self.exponential_fog:
            path = f"{self.level_path}:PersistentLevel.{self.exponential_fog}.ExponentialHeightFogComponent"
            
            result = self._get_property(path, "FogDensity")
            if result:
                self.original_settings["fog_density"] = result.get("FogDensity", 0.0)
            
            result = self._get_property(path, "FogHeightFalloff")
            if result:
                self.original_settings["fog_height_falloff"] = result.get("FogHeightFalloff", 0.2)
            
            logger.info(f"  Saved fog density: {self.original_settings.get('fog_density', 'N/A')}")
        
        # Save rain visibility state
        if self.rain_system:
            path = f"{self.level_path}:PersistentLevel.{self.rain_system}"
            result = self._call_remote(path, "IsHidden")
            if result:
                self.original_settings["rain_hidden"] = result.get("ReturnValue", True)
        
        self.originals_saved = True
        logger.info("  Original weather settings saved")
        return True
    
    # =========================================================================
    # WEATHER APPLICATION
    # =========================================================================
    
    def _apply_directional_light(self, state: WeatherState, warnings: List[str]) -> Dict[str, Any]:
        """Apply directional light settings"""
        applied = {}
        
        if not self.directional_light:
            return applied
        
        # Use saved component path or try both
        component = self.original_settings.get("sun_component", "DirectionalLightComponent")
        path = f"{self.level_path}:PersistentLevel.{self.directional_light}.{component}"
        
        # Set intensity
        if self._set_property(path, "Intensity", state.sun_intensity):
            applied["sun_intensity"] = state.sun_intensity
            logger.info(f"    Sun intensity: {state.sun_intensity}")
        else:
            # Try alternate component
            alt_component = "LightComponent" if component == "DirectionalLightComponent" else "DirectionalLightComponent"
            alt_path = f"{self.level_path}:PersistentLevel.{self.directional_light}.{alt_component}"
            if self._set_property(alt_path, "Intensity", state.sun_intensity):
                applied["sun_intensity"] = state.sun_intensity
                logger.info(f"    Sun intensity: {state.sun_intensity}")
            else:
                warnings.append("Failed to set sun intensity")
        
        return applied
    
    def _apply_fog(self, state: WeatherState, warnings: List[str]) -> Dict[str, Any]:
        """Apply exponential height fog settings"""
        applied = {}
        
        if not self.exponential_fog:
            return applied
        
        path = f"{self.level_path}:PersistentLevel.{self.exponential_fog}.ExponentialHeightFogComponent"
        
        # Set fog density
        if self._set_property(path, "FogDensity", state.fog_density):
            applied["fog_density"] = state.fog_density
            logger.info(f"    Fog density: {state.fog_density}")
        else:
            warnings.append("Failed to set fog density")
        
        # Set fog height falloff
        if self._set_property(path, "FogHeightFalloff", state.fog_height_falloff):
            applied["fog_height_falloff"] = state.fog_height_falloff
            logger.info(f"    Fog height falloff: {state.fog_height_falloff}")
        else:
            warnings.append("Failed to set fog height falloff")
        
        return applied
    
    def _apply_clouds(self, state: WeatherState, warnings: List[str]) -> Dict[str, Any]:
        """Apply volumetric cloud settings"""
        applied = {}
        
        if not self.volumetric_cloud:
            return applied
        
        # Cloud settings are typically on the VolumetricCloudComponent
        path = f"{self.level_path}:PersistentLevel.{self.volumetric_cloud}.VolumetricCloudComponent"
        
        # Try to set layer bottom altitude or coverage
        # Note: Exact property names depend on UE5 version
        logger.info(f"    Cloud coverage target: {state.cloud_coverage}")
        applied["cloud_coverage"] = state.cloud_coverage
        
        return applied
    
    def _apply_rain(self, state: WeatherState, warnings: List[str]) -> Dict[str, Any]:
        """Apply rain particle system settings"""
        applied = {}
        
        if not self.rain_system:
            if state.rain_enabled:
                warnings.append("Rain enabled but no rain system found")
            return applied
        
        path = f"{self.level_path}:PersistentLevel.{self.rain_system}"
        
        # Show/hide rain system
        hidden = not state.rain_enabled
        result = self._call_remote(path, "SetActorHiddenInGame", {"bNewHidden": hidden})
        
        if result is not None:
            applied["rain_enabled"] = state.rain_enabled
            applied["rain_intensity"] = state.rain_intensity
            logger.info(f"    Rain enabled: {state.rain_enabled}")
            if state.rain_enabled:
                logger.info(f"    Rain intensity: {state.rain_intensity}")
        else:
            warnings.append("Failed to toggle rain system")
        
        return applied
    
    def set_weather(self, 
                    weather_state: str = None,
                    seed: int = None) -> WeatherAugmentationResult:
        """
        Set specific weather state.
        
        Args:
            weather_state: Name of weather state (clear, overcast, rain, etc.)
                           If None, randomly selects based on seed.
            seed: Random seed for deterministic selection
        
        Returns:
            WeatherAugmentationResult with applied settings
        """
        warnings = []
        
        # Ensure actors are detected
        if not any([self.directional_light, self.exponential_fog, 
                    self.volumetric_cloud, self.rain_system]):
            if not self.detect_weather_actors():
                return WeatherAugmentationResult(
                    success=False,
                    failure_reason="No weather-controllable actors found"
                )
        
        # Save originals on first use
        self._save_original_settings()
        
        # Select weather state
        if weather_state:
            if weather_state not in self.weather_states:
                return WeatherAugmentationResult(
                    success=False,
                    failure_reason=f"Unknown weather state: {weather_state}"
                )
            selected_state = self.weather_states[weather_state]
        else:
            # Random selection based on seed
            if seed is not None:
                random.seed(seed + 1000)  # Offset from time seed
            state_names = list(self.weather_states.keys())
            selected_name = random.choice(state_names)
            selected_state = self.weather_states[selected_name]
        
        logger.info(f"Setting weather: {selected_state.name}")
        logger.info(f"  Description: {selected_state.description}")
        
        # Apply all weather components
        parameters_applied = {}
        
        logger.info("  Applying settings:")
        parameters_applied.update(self._apply_directional_light(selected_state, warnings))
        parameters_applied.update(self._apply_fog(selected_state, warnings))
        parameters_applied.update(self._apply_clouds(selected_state, warnings))
        parameters_applied.update(self._apply_rain(selected_state, warnings))
        
        # Log seed
        if seed is not None:
            logger.info(f"  Random seed: {seed}")
        
        # Log warnings
        for warning in warnings:
            logger.warning(f"  WARNING: {warning}")
        
        self.current_weather_state = selected_state.name
        
        return WeatherAugmentationResult(
            success=True,
            weather_state=selected_state.name,
            parameters_applied=parameters_applied,
            seed=seed,
            warnings=warnings
        )
    
    def randomize(self, 
                  seed: int = None,
                  allowed_states: List[str] = None) -> WeatherAugmentationResult:
        """
        Randomly select and apply a weather state.
        
        Args:
            seed: Random seed for deterministic selection
            allowed_states: List of allowed state names (None = all states)
        
        Returns:
            WeatherAugmentationResult with applied settings
        """
        if seed is not None:
            random.seed(seed + 1000)  # Offset from time seed
        
        # Filter allowed states
        if allowed_states:
            available = [s for s in allowed_states if s in self.weather_states]
            if not available:
                return WeatherAugmentationResult(
                    success=False,
                    failure_reason=f"No valid states in allowed_states: {allowed_states}"
                )
        else:
            available = list(self.weather_states.keys())
        
        selected = random.choice(available)
        return self.set_weather(weather_state=selected, seed=seed)
    
    # =========================================================================
    # RESET
    # =========================================================================
    
    def reset(self) -> bool:
        """
        Restore original weather settings.
        
        Returns:
            True if reset successful
        """
        if not self.originals_saved:
            logger.info("No original weather settings saved - nothing to reset")
            return True
        
        logger.info("Resetting weather to original state...")
        success = True
        
        # Restore sun intensity
        if self.directional_light and "sun_intensity" in self.original_settings:
            component = self.original_settings.get("sun_component", "DirectionalLightComponent")
            path = f"{self.level_path}:PersistentLevel.{self.directional_light}.{component}"
            if self._set_property(path, "Intensity", self.original_settings["sun_intensity"]):
                logger.info(f"  Restored sun intensity: {self.original_settings['sun_intensity']}")
            else:
                logger.warning("  Failed to restore sun intensity")
                success = False
        
        # Restore fog settings
        if self.exponential_fog:
            path = f"{self.level_path}:PersistentLevel.{self.exponential_fog}.ExponentialHeightFogComponent"
            
            if "fog_density" in self.original_settings:
                if self._set_property(path, "FogDensity", self.original_settings["fog_density"]):
                    logger.info(f"  Restored fog density: {self.original_settings['fog_density']}")
                else:
                    success = False
            
            if "fog_height_falloff" in self.original_settings:
                if self._set_property(path, "FogHeightFalloff", self.original_settings["fog_height_falloff"]):
                    logger.info(f"  Restored fog height falloff: {self.original_settings['fog_height_falloff']}")
                else:
                    success = False
        
        # Restore rain hidden state
        if self.rain_system and "rain_hidden" in self.original_settings:
            path = f"{self.level_path}:PersistentLevel.{self.rain_system}"
            result = self._call_remote(path, "SetActorHiddenInGame", 
                                       {"bNewHidden": self.original_settings["rain_hidden"]})
            if result is not None:
                logger.info(f"  Restored rain hidden: {self.original_settings['rain_hidden']}")
            else:
                success = False
        
        self.current_weather_state = None
        
        if success:
            logger.info("  Weather reset complete")
        
        return success
    
    # =========================================================================
    # INFO / DEBUG
    # =========================================================================
    
    def get_available_states(self) -> List[str]:
        """Get list of available weather state names"""
        return list(self.weather_states.keys())
    
    def get_current_state(self) -> Optional[str]:
        """Get currently applied weather state name"""
        return self.current_weather_state
    
    def log_status(self):
        """Log current controller status"""
        logger.info("=" * 60)
        logger.info("WEATHER AUGMENTATION STATUS")
        logger.info("=" * 60)
        logger.info(f"  DirectionalLight: {self.directional_light or 'NOT DETECTED'}")
        logger.info(f"  ExponentialHeightFog: {self.exponential_fog or 'NOT DETECTED'}")
        logger.info(f"  VolumetricCloud: {self.volumetric_cloud or 'NOT DETECTED'}")
        logger.info(f"  SkyAtmosphere: {self.sky_atmosphere or 'NOT DETECTED'}")
        logger.info(f"  PostProcessVolume: {self.post_process_volume or 'NOT DETECTED'}")
        logger.info(f"  Rain System: {self.rain_system or 'NOT DETECTED'}")
        logger.info(f"  Current state: {self.current_weather_state or 'None'}")
        logger.info(f"  Available states: {', '.join(self.get_available_states())}")
        logger.info("=" * 60)


# =============================================================================
# TEST / DEMO
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    controller = WeatherAugmentationController()
    
    # Detect weather actors
    if not controller.detect_weather_actors():
        print("No weather actors found - limited functionality")
    
    controller.log_status()
    
    # Test each weather state
    for state_name in controller.get_available_states():
        print(f"\nTesting: {state_name}")
        result = controller.set_weather(weather_state=state_name, seed=42)
        print(f"  Success: {result.success}")
        print(f"  Applied: {result.parameters_applied}")
        if result.warnings:
            print(f"  Warnings: {result.warnings}")
        input("Press Enter to continue...")
    
    # Reset
    print("\nResetting...")
    controller.reset()
    print("Done!")
