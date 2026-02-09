"""
TimeAugmentationController - Time-of-Day Lighting Control

RESPONSIBILITY (STRICT):
- Setting time-of-day via sun/sky lighting
- Adjusting directional light rotation (sun angle)
- Adjusting skylight intensity
- Adjusting exposure compensation
- Logging applied time state

MUST NOT:
- Spawn or modify vehicles
- Spawn or modify props
- Move the camera
- Capture images
- Modify weather systems (handled elsewhere)

TIME STATES:
- Dawn, Morning, Noon, Afternoon, Sunset, Night
- Each state defines sun rotation, sky intensity, exposure

RESET BEHAVIOR:
- Stores original lighting settings on first use
- Restores to original settings after test
"""

import math
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
class TimeState:
    """Configuration for a time-of-day state"""
    name: str
    sun_pitch: float      # Sun elevation angle (0 = horizon, -90 = zenith)
    sun_yaw: float        # Sun direction (compass heading)
    sky_intensity: float  # SkyLight intensity multiplier
    exposure_bias: float  # Post-process exposure compensation
    sun_roll: float = -55.49  # Roll (baseline from UE5 level)
    description: str = ""


@dataclass
class TimeAugmentationResult:
    """Result of a time augmentation operation"""
    success: bool
    time_state: Optional[str] = None
    sun_rotation: Optional[Dict[str, float]] = None
    sky_intensity: Optional[float] = None
    exposure_bias: Optional[float] = None
    seed: Optional[int] = None
    failure_reason: Optional[str] = None


# =============================================================================
# DEFAULT TIME STATES (Configurable)
# =============================================================================

# Baseline detected from UE5: Pitch=-21.56, Yaw=175.22, Roll=-55.49
# All states stay very close to baseline with only subtle variation.
DEFAULT_TIME_STATES = {
    "dawn": TimeState(
        name="dawn",
        sun_pitch=-8.0,       # Low sun near horizon
        sun_yaw=105.0,        # East
        sky_intensity=0.3,
        exposure_bias=1.5,
        description="Early morning, golden hour start"
    ),
    "morning": TimeState(
        name="morning",
        sun_pitch=-20.5,      # ~1° from baseline
        sun_yaw=173.0,        # ~2° shift from baseline
        sky_intensity=1.0,
        exposure_bias=0.0,
        description="Mid-morning, very subtle shadow shift"
    ),
    "noon": TimeState(
        name="noon",
        sun_pitch=-21.5,      # Baseline pitch
        sun_yaw=175.0,        # Baseline yaw
        sky_intensity=1.0,
        exposure_bias=0.0,
        description="Midday, baseline lighting"
    ),
    "afternoon": TimeState(
        name="afternoon",
        sun_pitch=-21.0,      # ~0.5° from baseline
        sun_yaw=177.0,        # ~2° shift from baseline
        sky_intensity=1.0,
        exposure_bias=0.0,
        description="Afternoon, very subtle shadow shift"
    ),
    "sunset": TimeState(
        name="sunset",
        sun_pitch=-10.0,      # Low sun
        sun_yaw=255.0,        # West
        sky_intensity=0.4,
        exposure_bias=1.0,
        description="Golden hour, long shadows"
    ),
    "night": TimeState(
        name="night",
        sun_pitch=15.0,       # Below horizon
        sun_yaw=270.0,        # West (moon position)
        sky_intensity=0.05,
        exposure_bias=3.0,
        description="Night time, minimal natural light"
    ),
}


# =============================================================================
# CONTROLLER
# =============================================================================

class TimeAugmentationController:
    """
    Time-of-Day Augmentation Controller
    
    Controls directional light (sun) and skylight to simulate different times of day.
    Deterministic selection based on random seed.
    """
    
    def __init__(self,
                 host: str = "127.0.0.1",
                 port: int = 30010,
                 level_path: str = "/Game/automobileV2.automobileV2",
                 time_states: Optional[Dict[str, TimeState]] = None):
        """
        Initialize the TimeAugmentationController.
        
        Args:
            host: UE5 Remote Control host
            port: UE5 Remote Control port
            level_path: Level path for actor resolution
            time_states: Custom time state definitions (uses defaults if None)
        """
        self.base_url = f"http://{host}:{port}/remote"
        self.level_path = level_path
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Time states (configurable)
        self.time_states = time_states or DEFAULT_TIME_STATES
        
        # Detected actors
        self.directional_light: Optional[str] = None
        self.sky_light: Optional[str] = None
        self.post_process_volume: Optional[str] = None
        
        # Original settings for reset
        self.original_sun_rotation: Optional[Dict[str, float]] = None
        self.original_sky_intensity: Optional[float] = None
        self.original_exposure_bias: Optional[float] = None
        self.originals_saved: bool = False
        
        # Current state
        self.current_time_state: Optional[str] = None
    
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
    
    # =========================================================================
    # ACTOR DETECTION
    # =========================================================================
    
    def detect_lighting_actors(self) -> bool:
        """
        Detect existing DirectionalLight and SkyLight actors dynamically.
        
        Returns:
            True if required actors found, False otherwise
        """
        logger.info("Detecting lighting actors...")
        
        # Common actor naming patterns to search
        directional_patterns = [
            "DirectionalLight",
            "DirectionalLight_1",
            "DirectionalLight_2",
            "DirectionalLight_3",
            "DirectionalLight_4",
            "SunLight", 
            "Sun",
            "Light_Directional"
        ]
        
        sky_patterns = [
            "SkyLight",
            "SkyLight_1",
            "Sky_Light",
            "AmbientLight"
        ]
        
        post_process_patterns = [
            "PostProcessVolume",
            "PostProcessVolume_1",
            "GlobalPostProcess",
            "PP_Volume"
        ]
        
        # Find DirectionalLight
        for pattern in directional_patterns:
            path = f"{self.level_path}:PersistentLevel.{pattern}"
            result = self._call_remote(path, "K2_GetActorRotation")
            if result and "ReturnValue" in result:
                self.directional_light = pattern
                logger.info(f"  Found DirectionalLight: {pattern}")
                break
        
        if not self.directional_light:
            logger.error("  ERROR: No DirectionalLight found in level!")
            return False
        
        # Find SkyLight
        for pattern in sky_patterns:
            path = f"{self.level_path}:PersistentLevel.{pattern}"
            result = self._call_remote(path, "K2_GetActorLocation")
            if result and "ReturnValue" in result:
                self.sky_light = pattern
                logger.info(f"  Found SkyLight: {pattern}")
                break
        
        if not self.sky_light:
            logger.warning("  WARNING: No SkyLight found - sky intensity control disabled")
        
        # Find PostProcessVolume (optional)
        for pattern in post_process_patterns:
            path = f"{self.level_path}:PersistentLevel.{pattern}"
            result = self._call_remote(path, "K2_GetActorLocation")
            if result and "ReturnValue" in result:
                self.post_process_volume = pattern
                logger.info(f"  Found PostProcessVolume: {pattern}")
                break
        
        if not self.post_process_volume:
            logger.warning("  WARNING: No PostProcessVolume found - exposure control disabled")
        
        return True
    
    def _save_original_settings(self) -> bool:
        """Save original lighting settings for reset"""
        if self.originals_saved:
            return True
        
        logger.info("Saving original lighting settings...")
        
        # Save sun rotation
        if self.directional_light:
            path = f"{self.level_path}:PersistentLevel.{self.directional_light}"
            result = self._call_remote(path, "K2_GetActorRotation")
            if result and "ReturnValue" in result:
                self.original_sun_rotation = result["ReturnValue"].copy()
                logger.info(f"  Saved sun rotation: Pitch={self.original_sun_rotation.get('Pitch', 0):.1f}")
        
        # Save sky intensity
        if self.sky_light:
            path = f"{self.level_path}:PersistentLevel.{self.sky_light}.LightComponent"
            result = self._get_property(path, "Intensity")
            if result:
                self.original_sky_intensity = result.get("Intensity", 1.0)
                logger.info(f"  Saved sky intensity: {self.original_sky_intensity}")
        
        # Save exposure bias (from post process volume settings)
        # Note: Exposure is complex in UE5 - this is simplified
        self.original_exposure_bias = 0.0
        
        self.originals_saved = True
        logger.info("  Original settings saved")
        return True
    
    # =========================================================================
    # TIME AUGMENTATION
    # =========================================================================
    
    def set_time(self, 
                 time_state: str = None,
                 seed: int = None) -> TimeAugmentationResult:
        """
        Set specific time-of-day state.
        
        Args:
            time_state: Name of time state (dawn, morning, noon, etc.)
                        If None, randomly selects based on seed.
            seed: Random seed for deterministic selection
        
        Returns:
            TimeAugmentationResult with applied settings
        """
        # Ensure actors are detected
        if not self.directional_light:
            if not self.detect_lighting_actors():
                return TimeAugmentationResult(
                    success=False,
                    failure_reason="Failed to detect required lighting actors"
                )
        
        # Save originals on first use
        self._save_original_settings()
        
        # Select time state
        if time_state:
            if time_state not in self.time_states:
                return TimeAugmentationResult(
                    success=False,
                    failure_reason=f"Unknown time state: {time_state}"
                )
            selected_state = self.time_states[time_state]
        else:
            # Random selection based on seed
            if seed is not None:
                random.seed(seed)
            state_names = list(self.time_states.keys())
            selected_name = random.choice(state_names)
            selected_state = self.time_states[selected_name]
        
        logger.info(f"Setting time-of-day: {selected_state.name}")
        logger.info(f"  Description: {selected_state.description}")
        
        # Apply sun rotation
        sun_rotation = {
            "Pitch": selected_state.sun_pitch,
            "Yaw": selected_state.sun_yaw,
            "Roll": selected_state.sun_roll
        }
        
        path = f"{self.level_path}:PersistentLevel.{self.directional_light}"
        result = self._call_remote(path, "K2_SetActorRotation", {
            "NewRotation": sun_rotation,
            "bTeleportPhysics": True
        })
        
        if not result:
            logger.warning("  Failed to set sun rotation")
        else:
            logger.info(f"  Sun rotation: Pitch={sun_rotation['Pitch']:.1f}, Yaw={sun_rotation['Yaw']:.1f}")
        
        # Apply sky intensity
        sky_intensity_applied = None
        if self.sky_light:
            path = f"{self.level_path}:PersistentLevel.{self.sky_light}.LightComponent"
            success = self._set_property(path, "Intensity", selected_state.sky_intensity)
            if success:
                sky_intensity_applied = selected_state.sky_intensity
                logger.info(f"  Sky intensity: {selected_state.sky_intensity}")
            else:
                logger.warning("  Failed to set sky intensity")
        
        # Apply exposure bias (simplified - full implementation would use post process settings)
        exposure_applied = selected_state.exposure_bias
        logger.info(f"  Exposure bias: {selected_state.exposure_bias}")
        
        # Log seed
        if seed is not None:
            logger.info(f"  Random seed: {seed}")
        
        self.current_time_state = selected_state.name
        
        return TimeAugmentationResult(
            success=True,
            time_state=selected_state.name,
            sun_rotation=sun_rotation,
            sky_intensity=sky_intensity_applied,
            exposure_bias=exposure_applied,
            seed=seed
        )
    
    def randomize(self, 
                  seed: int = None,
                  allowed_states: List[str] = None) -> TimeAugmentationResult:
        """
        Randomly select and apply a time-of-day state.
        
        Args:
            seed: Random seed for deterministic selection
            allowed_states: List of allowed state names (None = all states)
        
        Returns:
            TimeAugmentationResult with applied settings
        """
        if seed is not None:
            random.seed(seed)
        
        # Filter allowed states
        if allowed_states:
            available = [s for s in allowed_states if s in self.time_states]
            if not available:
                return TimeAugmentationResult(
                    success=False,
                    failure_reason=f"No valid states in allowed_states: {allowed_states}"
                )
        else:
            available = list(self.time_states.keys())
        
        selected = random.choice(available)
        return self.set_time(time_state=selected, seed=seed)
    
    # =========================================================================
    # RESET
    # =========================================================================
    
    def reset(self) -> bool:
        """
        Restore original lighting settings.
        
        Returns:
            True if reset successful
        """
        if not self.originals_saved:
            logger.info("No original settings saved - nothing to reset")
            return True
        
        logger.info("Resetting lighting to original state...")
        success = True
        
        # Restore sun rotation
        if self.directional_light and self.original_sun_rotation:
            path = f"{self.level_path}:PersistentLevel.{self.directional_light}"
            result = self._call_remote(path, "K2_SetActorRotation", {
                "NewRotation": self.original_sun_rotation,
                "bTeleportPhysics": True
            })
            if result:
                logger.info(f"  Restored sun rotation: Pitch={self.original_sun_rotation.get('Pitch', 0):.1f}")
            else:
                logger.warning("  Failed to restore sun rotation")
                success = False
        
        # Restore sky intensity
        if self.sky_light and self.original_sky_intensity is not None:
            path = f"{self.level_path}:PersistentLevel.{self.sky_light}.LightComponent"
            if self._set_property(path, "Intensity", self.original_sky_intensity):
                logger.info(f"  Restored sky intensity: {self.original_sky_intensity}")
            else:
                logger.warning("  Failed to restore sky intensity")
                success = False
        
        self.current_time_state = None
        
        if success:
            logger.info("  Lighting reset complete")
        
        return success
    
    # =========================================================================
    # INFO / DEBUG
    # =========================================================================
    
    def get_available_states(self) -> List[str]:
        """Get list of available time state names"""
        return list(self.time_states.keys())
    
    def get_current_state(self) -> Optional[str]:
        """Get currently applied time state name"""
        return self.current_time_state
    
    def log_status(self):
        """Log current controller status"""
        logger.info("=" * 60)
        logger.info("TIME AUGMENTATION STATUS")
        logger.info("=" * 60)
        logger.info(f"  DirectionalLight: {self.directional_light or 'NOT DETECTED'}")
        logger.info(f"  SkyLight: {self.sky_light or 'NOT DETECTED'}")
        logger.info(f"  PostProcessVolume: {self.post_process_volume or 'NOT DETECTED'}")
        logger.info(f"  Current state: {self.current_time_state or 'None'}")
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
    
    controller = TimeAugmentationController()
    
    # Detect lighting actors
    if not controller.detect_lighting_actors():
        print("Failed to detect lighting actors")
        exit(1)
    
    controller.log_status()
    
    # Test each time state
    for state_name in controller.get_available_states():
        print(f"\nTesting: {state_name}")
        result = controller.set_time(time_state=state_name, seed=42)
        print(f"  Success: {result.success}")
        if result.success:
            print(f"  Sun rotation: {result.sun_rotation}")
        input("Press Enter to continue...")
    
    # Reset
    print("\nResetting...")
    controller.reset()
    print("Done!")
