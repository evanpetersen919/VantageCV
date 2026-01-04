"""
SmartCameraCaptureController - Intelligent Camera Positioning and Capture

DEPENDENCY:
- MUST run ONLY if SceneValidationController reports SCENE_VALID = true
- Aborts immediately otherwise

CAMERA RESPONSIBILITY:
- Read vehicle transforms (DO NOT modify them)
- Compute optimal camera position and rotation
- Capture images
- Reject invalid frames

VEHICLE ROTATION RULE:
- Vehicle rotation at capture time is FINAL
- Camera logic MUST NOT rotate vehicles
- Vehicles inherit orientation strictly from zone-based spawn logic

CAMERA INTELLIGENCE:
- 1 vehicle: Close-up, lower height, narrow FOV, emphasize detail
- 2-4 vehicles: Medium distance, moderate height, balanced FOV
- 5+ vehicles: Higher elevation, wider FOV, ensure full scene coverage

VISIBILITY VALIDATION:
- For EACH vehicle, compute projected screen area
- Require ≥30% visible
- If ANY vehicle fails → reject image

RETRY LOGIC:
- Attempt up to N camera placements
- Log every failure reason
- Abort cleanly if no valid capture found
"""

import math
import logging
import requests
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Import validation controller
from .scene_validation_controller import SceneValidationController, ValidationStatus

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Visibility thresholds
MIN_VISIBILITY_PERCENTAGE = 30.0  # Each vehicle must be at least 30% visible
MAX_CAMERA_RETRIES = 5  # Maximum camera placement attempts

# Camera presets by vehicle count
CAMERA_PRESETS = {
    "single": {  # 1 vehicle
        "distance_min": 500,   # cm
        "distance_max": 800,
        "height_min": 150,
        "height_max": 250,
        "fov_min": 50,
        "fov_max": 70,
        "pitch_min": -15,
        "pitch_max": -5,
    },
    "small_group": {  # 2-4 vehicles
        "distance_min": 800,
        "distance_max": 1500,
        "height_min": 200,
        "height_max": 400,
        "fov_min": 60,
        "fov_max": 80,
        "pitch_min": -25,
        "pitch_max": -10,
    },
    "large_group": {  # 5+ vehicles
        "distance_min": 1500,
        "distance_max": 2500,
        "height_min": 400,
        "height_max": 700,
        "fov_min": 75,
        "fov_max": 100,
        "pitch_min": -35,
        "pitch_max": -15,
    },
}


class CaptureStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    FAILED_VISIBILITY = "FAILED_VISIBILITY"
    FAILED_CAPTURE = "FAILED_CAPTURE"
    ABORTED = "ABORTED"


@dataclass
class VehicleInfo:
    """Vehicle information for camera computation"""
    name: str
    location: Dict[str, float]  # X, Y, Z in cm
    rotation: Dict[str, float]  # Pitch, Yaw, Roll in degrees
    bounds_extent: Optional[Dict[str, float]] = None  # Half-extents if available


@dataclass
class CameraPlacement:
    """Computed camera placement"""
    location: Dict[str, float]  # X, Y, Z in cm
    rotation: Dict[str, float]  # Pitch, Yaw, Roll in degrees
    fov: float  # Field of view in degrees
    target_centroid: Dict[str, float]  # Target point camera is looking at


@dataclass
class VisibilityResult:
    """Visibility check result for a single vehicle"""
    vehicle_name: str
    visible_percentage: float
    in_frame: bool
    reason: Optional[str] = None


@dataclass
class CaptureResult:
    """Complete capture result"""
    status: CaptureStatus
    image_path: Optional[str] = None
    camera_placement: Optional[CameraPlacement] = None
    visibility_results: List[VisibilityResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    failure_reason: Optional[str] = None
    retry_count: int = 0


class SmartCameraCaptureController:
    """
    Smart Camera Capture Controller
    
    Computes optimal camera positions based on vehicle layout and captures
    high-quality images with visibility validation.
    """
    
    def __init__(self,
                 host: str = "127.0.0.1",
                 port: int = 30010,
                 level_path: str = "/Game/automobileV2.automobileV2",
                 data_capture_actor: str = "DataCapture_1",
                 vehicle_config_path: str = "configs/levels/automobileV2_vehicles.yaml"):
        self.base_url = f"http://{host}:{port}/remote"
        self.level_path = level_path
        self.data_capture_actor = data_capture_actor
        self.vehicle_config_path = Path(vehicle_config_path)
        self.session = requests.Session()
        self.vehicle_config = None
        
        # Load vehicle pool configuration
        if self.vehicle_config_path.exists():
            with open(self.vehicle_config_path, 'r') as f:
                self.vehicle_config = yaml.safe_load(f)
        
        # Validation controller
        self.validator = SceneValidationController(host=host, port=port, level_path=level_path)
        
        # Random state for camera variation
        self._rng_state = 0
        
        logger.info("SmartCameraCaptureController initialized")
        logger.info(f"  Level: {level_path}")
        logger.info(f"  DataCapture: {data_capture_actor}")
        logger.info(f"  Vehicle Config: {vehicle_config_path}")
    
    def set_seed(self, seed: int):
        """Set random seed for deterministic camera placement"""
        self._rng_state = seed
        logger.info(f"Camera seed set to {seed}")
    
    def _random_float(self, min_val: float, max_val: float) -> float:
        """Get deterministic pseudo-random float"""
        # Simple LCG for determinism
        self._rng_state = (self._rng_state * 1103515245 + 12345) & 0x7FFFFFFF
        t = (self._rng_state / 0x7FFFFFFF)
        return min_val + t * (max_val - min_val)
    
    # ========================================================================
    # REMOTE CONTROL API
    # ========================================================================
    
    def _call_remote(self, object_path: str, function_name: str,
                     parameters: Dict = None) -> Optional[Dict]:
        """Call a UE5 function via Remote Control API"""
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
                timeout=10.0
            )
            
            if response.status_code == 200:
                return response.json()
            return None
                
        except Exception as e:
            logger.error(f"Remote call error: {e}")
            return None
    
    def _get_property(self, object_path: str, property_name: str) -> Optional[Any]:
        """Get a property from an actor"""
        try:
            response = self.session.put(
                f"{self.base_url}/object/property",
                json={
                    "objectPath": object_path,
                    "propertyName": property_name
                },
                timeout=5.0
            )
            if response.status_code == 200:
                return response.json().get(property_name)
            return None
        except Exception as e:
            logger.error(f"Get property error: {e}")
            return None
    
    # ========================================================================
    # VEHICLE DISCOVERY (READ ONLY)
    # ========================================================================
    
    def _get_vehicle_pool(self) -> List[str]:
        """Get all vehicle actor names from config"""
        if not self.vehicle_config:
            return []
        
        vehicles = self.vehicle_config.get("vehicles", {})
        actor_names = []
        
        for category in ["bicycle", "bus", "car", "motorcycle", "truck"]:
            for v in vehicles.get(category, []):
                actor_names.append(v["name"])
        
        return actor_names
    
    def _get_visible_vehicles(self) -> List[VehicleInfo]:
        """Get all visible vehicle actors with their transforms (READ ONLY)"""
        vehicles = []
        
        # Use vehicle pool from config
        actor_names = self._get_vehicle_pool()
        
        if not actor_names:
            # Fallback to scanning if no config
            for prefix in ["StaticMeshActor", "SkeletalMeshActor"]:
                for i in range(100):
                    actor_names.append(f"{prefix}_{i}")
        
        for actor_name in actor_names:
            path = f"{self.level_path}:PersistentLevel.{actor_name}"
            
            # Check visibility using bHidden property
            is_hidden = self._get_property(path, "bHidden")
            if is_hidden is None or is_hidden == True:
                continue  # Hidden or not found
            
            # Get location
            loc_result = self._call_remote(path, "K2_GetActorLocation")
            if not loc_result:
                continue
            
            # Get rotation
            rot_result = self._call_remote(path, "K2_GetActorRotation")
            if not rot_result:
                continue
            
            # Skip anchors (scale 0.5)
            scale_result = self._call_remote(path, "GetActorScale3D")
            if scale_result:
                sx = scale_result.get("ReturnValue", {}).get("X", 1)
                if abs(sx - 0.5) < 0.1:
                    continue
            
            location = loc_result.get("ReturnValue", {})
            rotation = rot_result.get("ReturnValue", {})
            
            vehicles.append(VehicleInfo(
                name=actor_name,
                location=location,
                rotation=rotation
            ))
        
        logger.info(f"Found {len(vehicles)} visible vehicles")
        return vehicles
    
    # ========================================================================
    # CAMERA COMPUTATION
    # ========================================================================
    
    def _compute_vehicle_centroid(self, vehicles: List[VehicleInfo]) -> Dict[str, float]:
        """Compute the centroid of all vehicle positions"""
        if not vehicles:
            return {"X": 0, "Y": 0, "Z": 0}
        
        sum_x = sum(v.location.get("X", 0) for v in vehicles)
        sum_y = sum(v.location.get("Y", 0) for v in vehicles)
        sum_z = sum(v.location.get("Z", 0) for v in vehicles)
        n = len(vehicles)
        
        return {
            "X": sum_x / n,
            "Y": sum_y / n,
            "Z": sum_z / n
        }
    
    def _compute_vehicle_spread(self, vehicles: List[VehicleInfo], centroid: Dict[str, float]) -> float:
        """Compute the maximum distance from centroid to any vehicle"""
        if not vehicles:
            return 0
        
        max_dist = 0
        for v in vehicles:
            dx = v.location.get("X", 0) - centroid["X"]
            dy = v.location.get("Y", 0) - centroid["Y"]
            dist = math.sqrt(dx * dx + dy * dy)
            max_dist = max(max_dist, dist)
        
        return max_dist
    
    def _get_camera_preset(self, vehicle_count: int) -> Dict[str, Any]:
        """Get camera preset based on vehicle count"""
        if vehicle_count <= 1:
            return CAMERA_PRESETS["single"]
        elif vehicle_count <= 4:
            return CAMERA_PRESETS["small_group"]
        else:
            return CAMERA_PRESETS["large_group"]
    
    def _compute_camera_placement(self, 
                                   vehicles: List[VehicleInfo],
                                   attempt: int = 0) -> CameraPlacement:
        """
        Compute optimal camera placement based on vehicle layout.
        
        Uses vehicle count to select camera preset, then applies
        deterministic randomization for variety.
        """
        centroid = self._compute_vehicle_centroid(vehicles)
        spread = self._compute_vehicle_spread(vehicles, centroid)
        preset = self._get_camera_preset(len(vehicles))
        
        # Adjust distance based on vehicle spread
        base_distance = preset["distance_min"] + spread
        distance = min(max(base_distance, preset["distance_min"]), preset["distance_max"])
        
        # Random angle around scene (deterministic based on seed + attempt)
        self._rng_state = (self._rng_state + attempt * 7919) & 0x7FFFFFFF
        angle = self._random_float(0, 360)
        angle_rad = math.radians(angle)
        
        # Random height within preset range
        height = self._random_float(preset["height_min"], preset["height_max"])
        
        # Random FOV within preset range
        fov = self._random_float(preset["fov_min"], preset["fov_max"])
        
        # Random pitch within preset range
        pitch = self._random_float(preset["pitch_min"], preset["pitch_max"])
        
        # Compute camera position (orbit around centroid)
        cam_x = centroid["X"] + distance * math.cos(angle_rad)
        cam_y = centroid["Y"] + distance * math.sin(angle_rad)
        cam_z = centroid["Z"] + height
        
        # Compute yaw to look at centroid
        dx = centroid["X"] - cam_x
        dy = centroid["Y"] - cam_y
        yaw = math.degrees(math.atan2(dy, dx))
        
        placement = CameraPlacement(
            location={"X": cam_x, "Y": cam_y, "Z": cam_z},
            rotation={"Pitch": pitch, "Yaw": yaw, "Roll": 0},
            fov=fov,
            target_centroid=centroid
        )
        
        logger.info(f"Camera placement (attempt {attempt + 1}):")
        logger.info(f"  Position: ({cam_x:.1f}, {cam_y:.1f}, {cam_z:.1f})")
        logger.info(f"  Rotation: Pitch={pitch:.1f}°, Yaw={yaw:.1f}°")
        logger.info(f"  FOV: {fov:.1f}°")
        logger.info(f"  Distance: {distance:.1f}cm, Spread: {spread:.1f}cm")
        
        return placement
    
    # ========================================================================
    # CAMERA CONTROL
    # ========================================================================
    
    def _set_camera_transform(self, placement: CameraPlacement) -> bool:
        """Set the DataCapture camera position and rotation"""
        path = f"{self.level_path}:PersistentLevel.{self.data_capture_actor}"
        
        # Set location
        loc_result = self._call_remote(path, "K2_SetActorLocation", {
            "NewLocation": placement.location,
            "bSweep": False,
            "bTeleport": True
        })
        
        if not loc_result:
            logger.error("Failed to set camera location")
            return False
        
        # Set rotation
        rot_result = self._call_remote(path, "K2_SetActorRotation", {
            "NewRotation": placement.rotation,
            "bTeleportPhysics": True
        })
        
        if not rot_result:
            logger.error("Failed to set camera rotation")
            return False
        
        return True
    
    # ========================================================================
    # VISIBILITY VALIDATION
    # ========================================================================
    
    def _validate_visibility(self, 
                              vehicles: List[VehicleInfo],
                              placement: CameraPlacement) -> List[VisibilityResult]:
        """
        Validate that all vehicles are sufficiently visible from camera position.
        
        Uses simplified frustum check and distance-based visibility estimation.
        """
        results = []
        cam_loc = placement.location
        cam_rot = placement.rotation
        fov = placement.fov
        
        for vehicle in vehicles:
            v_loc = vehicle.location
            
            # Vector from camera to vehicle
            dx = v_loc.get("X", 0) - cam_loc["X"]
            dy = v_loc.get("Y", 0) - cam_loc["Y"]
            dz = v_loc.get("Z", 0) - cam_loc["Z"]
            
            # Distance to vehicle
            distance = math.sqrt(dx * dx + dy * dy + dz * dz)
            
            # Angle to vehicle from camera forward vector
            yaw_rad = math.radians(cam_rot["Yaw"])
            cam_forward_x = math.cos(yaw_rad)
            cam_forward_y = math.sin(yaw_rad)
            
            # Normalize direction to vehicle (2D for yaw check)
            dir_len = math.sqrt(dx * dx + dy * dy)
            if dir_len > 0:
                dir_x = dx / dir_len
                dir_y = dy / dir_len
            else:
                dir_x, dir_y = 0, 0
            
            # Dot product to check if vehicle is in front of camera
            dot = cam_forward_x * dir_x + cam_forward_y * dir_y
            
            # Angle from camera forward
            angle_to_vehicle = math.degrees(math.acos(max(-1, min(1, dot))))
            
            # Check if within FOV cone
            half_fov = fov / 2
            in_fov = angle_to_vehicle <= half_fov
            
            # Estimate visibility percentage based on angle and distance
            if not in_fov:
                visibility = 0
                reason = f"Outside FOV (angle={angle_to_vehicle:.1f}°, max={half_fov:.1f}°)"
            elif distance > 3000:
                visibility = max(0, 100 - (distance - 3000) / 50)
                reason = f"Far away (dist={distance:.1f}cm)" if visibility < MIN_VISIBILITY_PERCENTAGE else None
            else:
                # Full visibility if in FOV and not too far
                visibility = 100 - (angle_to_vehicle / half_fov) * 30
                reason = None
            
            results.append(VisibilityResult(
                vehicle_name=vehicle.name,
                visible_percentage=visibility,
                in_frame=in_fov,
                reason=reason
            ))
            
            logger.info(f"  {vehicle.name}: {visibility:.1f}% visible, "
                       f"angle={angle_to_vehicle:.1f}°, dist={distance:.1f}cm"
                       + (f" - {reason}" if reason else ""))
        
        return results
    
    def _all_vehicles_visible(self, visibility_results: List[VisibilityResult]) -> Tuple[bool, str]:
        """Check if all vehicles meet minimum visibility threshold"""
        failed = []
        for r in visibility_results:
            if r.visible_percentage < MIN_VISIBILITY_PERCENTAGE:
                failed.append(f"{r.vehicle_name} ({r.visible_percentage:.1f}%)")
        
        if failed:
            return False, f"Vehicles below {MIN_VISIBILITY_PERCENTAGE}% visibility: " + ", ".join(failed)
        return True, ""
    
    # ========================================================================
    # IMAGE CAPTURE
    # ========================================================================
    
    def _capture_image(self, output_path: str, width: int = 1920, height: int = 1080) -> bool:
        """Capture image using DataCapture actor"""
        path = f"{self.level_path}:PersistentLevel.{self.data_capture_actor}"
        
        result = self._call_remote(path, "CaptureFrame", {
            "OutputPath": output_path,
            "Width": width,
            "Height": height
        })
        
        if result and result.get("ReturnValue", False):
            logger.info(f"Image captured: {output_path}")
            return True
        
        logger.error(f"Failed to capture image: {output_path}")
        return False
    
    # ========================================================================
    # MAIN CAPTURE WORKFLOW
    # ========================================================================
    
    def capture(self,
                output_path: str,
                seed: int = 42,
                width: int = 1920,
                height: int = 1080,
                validate_scene: bool = True) -> CaptureResult:
        """
        Main capture workflow.
        
        1. Validate scene (if enabled)
        2. Discover visible vehicles
        3. Compute camera placement
        4. Validate visibility
        5. Capture image
        6. Save metadata
        
        Args:
            output_path: Path to save the image
            seed: Random seed for deterministic camera placement
            width: Image width
            height: Image height
            validate_scene: Whether to run scene validation first
            
        Returns:
            CaptureResult with status and metadata
        """
        self.set_seed(seed)
        
        logger.info("=" * 60)
        logger.info("SMART CAMERA CAPTURE")
        logger.info("=" * 60)
        logger.info(f"Output: {output_path}")
        logger.info(f"Seed: {seed}")
        logger.info(f"Resolution: {width}x{height}")
        
        # ====================================================================
        # STEP 1: Scene Validation (REQUIRED DEPENDENCY)
        # ====================================================================
        if validate_scene:
            logger.info("\n--- Step 1: Scene Validation ---")
            validation_report = self.validator.validate(seed=seed)
            
            if not validation_report.scene_valid:
                logger.error(f"ABORT: Scene validation failed - {validation_report.failure_reason}")
                return CaptureResult(
                    status=CaptureStatus.FAILED_VALIDATION,
                    failure_reason=validation_report.failure_reason
                )
        
        # ====================================================================
        # STEP 2: Discover Vehicles (READ ONLY)
        # ====================================================================
        logger.info("\n--- Step 2: Vehicle Discovery ---")
        vehicles = self._get_visible_vehicles()
        
        if not vehicles:
            logger.warning("No visible vehicles found")
            return CaptureResult(
                status=CaptureStatus.FAILED_VISIBILITY,
                failure_reason="No visible vehicles in scene"
            )
        
        for v in vehicles:
            logger.info(f"  {v.name}: ({v.location['X']:.1f}, {v.location['Y']:.1f}, {v.location['Z']:.1f}) "
                       f"Yaw={v.rotation.get('Yaw', 0):.1f}°")
        
        # ====================================================================
        # STEP 3: Camera Placement with Retry
        # ====================================================================
        logger.info("\n--- Step 3: Camera Placement ---")
        
        best_placement = None
        best_visibility = None
        
        for attempt in range(MAX_CAMERA_RETRIES):
            # Compute camera placement
            placement = self._compute_camera_placement(vehicles, attempt=attempt)
            
            # Set camera transform
            if not self._set_camera_transform(placement):
                logger.warning(f"Attempt {attempt + 1}: Failed to set camera transform")
                continue
            
            # Validate visibility
            logger.info(f"\n  Visibility check (attempt {attempt + 1}):")
            visibility_results = self._validate_visibility(vehicles, placement)
            
            all_visible, reason = self._all_vehicles_visible(visibility_results)
            
            if all_visible:
                best_placement = placement
                best_visibility = visibility_results
                logger.info(f"  ✓ All vehicles visible - using this placement")
                break
            else:
                logger.warning(f"  ✗ Visibility check failed: {reason}")
                # Keep best so far
                if best_visibility is None or \
                   sum(v.visible_percentage for v in visibility_results) > \
                   sum(v.visible_percentage for v in best_visibility):
                    best_placement = placement
                    best_visibility = visibility_results
        
        if best_placement is None:
            return CaptureResult(
                status=CaptureStatus.FAILED_VISIBILITY,
                failure_reason="Could not find valid camera placement after all retries",
                retry_count=MAX_CAMERA_RETRIES
            )
        
        # Use best placement found
        self._set_camera_transform(best_placement)
        
        # Final visibility check
        all_visible, reason = self._all_vehicles_visible(best_visibility)
        if not all_visible:
            logger.error(f"REJECT: {reason}")
            return CaptureResult(
                status=CaptureStatus.FAILED_VISIBILITY,
                camera_placement=best_placement,
                visibility_results=best_visibility,
                failure_reason=reason,
                retry_count=MAX_CAMERA_RETRIES
            )
        
        # ====================================================================
        # STEP 4: Capture Image
        # ====================================================================
        logger.info("\n--- Step 4: Image Capture ---")
        
        if not self._capture_image(output_path, width, height):
            return CaptureResult(
                status=CaptureStatus.FAILED_CAPTURE,
                camera_placement=best_placement,
                visibility_results=best_visibility,
                failure_reason="Image capture failed"
            )
        
        # ====================================================================
        # STEP 5: Save Metadata
        # ====================================================================
        logger.info("\n--- Step 5: Metadata ---")
        
        metadata = {
            "seed": seed,
            "camera": {
                "location": best_placement.location,
                "rotation": best_placement.rotation,
                "fov": best_placement.fov
            },
            "vehicles": [
                {
                    "name": v.name,
                    "location": v.location,
                    "rotation": v.rotation,
                    "visibility_percentage": next(
                        (r.visible_percentage for r in best_visibility if r.vehicle_name == v.name),
                        0
                    )
                }
                for v in vehicles
            ],
            "image_path": output_path,
            "resolution": {"width": width, "height": height}
        }
        
        # Save metadata alongside image
        metadata_path = Path(output_path).with_suffix('.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Metadata saved: {metadata_path}")
        
        # ====================================================================
        # SUCCESS
        # ====================================================================
        logger.info("\n" + "=" * 60)
        logger.info("CAPTURE SUCCESS")
        logger.info("=" * 60)
        
        return CaptureResult(
            status=CaptureStatus.SUCCESS,
            image_path=output_path,
            camera_placement=best_placement,
            visibility_results=best_visibility,
            metadata=metadata
        )


# ============================================================================
# STANDALONE USAGE
# ============================================================================

def main():
    """Run smart camera capture from command line"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Smart camera capture")
    parser.add_argument("--output", default="output/capture.png", help="Output image path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--width", type=int, default=1920, help="Image width")
    parser.add_argument("--height", type=int, default=1080, help="Image height")
    parser.add_argument("--host", default="127.0.0.1", help="UE5 Remote Control host")
    parser.add_argument("--port", type=int, default=30010, help="UE5 Remote Control port")
    parser.add_argument("--skip-validation", action="store_true", help="Skip scene validation")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    
    # Run capture
    controller = SmartCameraCaptureController(
        host=args.host,
        port=args.port
    )
    
    result = controller.capture(
        output_path=args.output,
        seed=args.seed,
        width=args.width,
        height=args.height,
        validate_scene=not args.skip_validation
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("CAPTURE SUMMARY")
    print("=" * 60)
    print(f"  Status: {result.status.value}")
    print(f"  Image:  {result.image_path or 'None'}")
    print(f"  Reason: {result.failure_reason or 'None'}")
    
    if result.visibility_results:
        print("\n  Visibility:")
        for v in result.visibility_results:
            status = "✓" if v.visible_percentage >= MIN_VISIBILITY_PERCENTAGE else "✗"
            print(f"    {status} {v.vehicle_name}: {v.visible_percentage:.1f}%")
    
    return 0 if result.status == CaptureStatus.SUCCESS else 1


if __name__ == "__main__":
    exit(main())
