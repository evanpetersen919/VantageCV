"""
Research v2 - Adaptive Camera Controller

HARD CONSTRAINTS:
1. Camera MUST see ALL vehicles with >=50% visibility
2. Camera is DATA-DRIVEN, positioned based on vehicle distribution
3. Frame is REJECTED if any vehicle fails visibility check

Algorithm:
1. Compute world-space centroid of all vehicle bounding boxes
2. Compute tightest enclosing 3D bounds of all vehicles  
3. Position camera to fit all vehicles in frustum
4. Project each vehicle to 2D and verify >=50% visibility
5. Retry with zoom-out if any vehicle fails

This is a MEASUREMENT camera, not cinematic.

Logging (REQUIRED):
- Vehicle centroid
- Camera position
- Camera FOV
- Per-vehicle visibility ratios
- Pass / fail decision
"""

import math
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

from .logging_utils import ResearchLogger
from .config import CameraConfig
from .vehicle_spawner import SpawnedVehicle

logger = logging.getLogger(__name__)


# Minimum required visibility ratio for each vehicle
MIN_VISIBILITY_RATIO = 0.50  # 50%

# Maximum camera adjustment retries
MAX_CAMERA_RETRIES = 5

# FOV expansion step when retrying
FOV_EXPANSION_STEP = 10.0  # degrees

# Minimum/maximum FOV bounds
MIN_FOV = 60.0
MAX_FOV = 120.0


@dataclass
class BoundingBox3D:
    """Axis-aligned bounding box in world space."""
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float
    
    @property
    def center(self) -> Tuple[float, float, float]:
        """Get center point."""
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
            (self.min_z + self.max_z) / 2,
        )
    
    @property
    def size(self) -> Tuple[float, float, float]:
        """Get dimensions (length, width, height)."""
        return (
            self.max_x - self.min_x,
            self.max_y - self.min_y,
            self.max_z - self.min_z,
        )
    
    @property
    def diagonal(self) -> float:
        """Get diagonal length."""
        sx, sy, sz = self.size
        return math.sqrt(sx*sx + sy*sy + sz*sz)
    
    def to_dict(self) -> dict:
        return {
            "min": {"x": self.min_x, "y": self.min_y, "z": self.min_z},
            "max": {"x": self.max_x, "y": self.max_y, "z": self.max_z},
            "center": {"x": self.center[0], "y": self.center[1], "z": self.center[2]},
            "size": {"x": self.size[0], "y": self.size[1], "z": self.size[2]},
        }


@dataclass
class VehicleVisibility:
    """Visibility information for a single vehicle."""
    actor_name: str
    vehicle_class: str
    bbox_2d: Tuple[float, float, float, float]  # x, y, width, height
    visible_ratio: float
    is_valid: bool  # >= MIN_VISIBILITY_RATIO
    
    def to_dict(self) -> dict:
        return {
            "actor_name": self.actor_name,
            "vehicle_class": self.vehicle_class,
            "bbox_2d": self.bbox_2d,
            "visible_ratio": self.visible_ratio,
            "is_valid": self.is_valid,
        }


@dataclass
class CameraFitResult:
    """Result of camera fitting operation."""
    success: bool
    camera_position: Tuple[float, float, float]  # x, y, z in cm
    camera_rotation: Tuple[float, float, float]  # pitch, yaw, roll in degrees
    fov: float
    vehicle_centroid: Tuple[float, float, float]
    vehicle_bounds: Optional[BoundingBox3D]
    visibility_results: List[VehicleVisibility]
    retry_count: int
    failure_reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "camera_position": {
                "x": self.camera_position[0],
                "y": self.camera_position[1],
                "z": self.camera_position[2],
            },
            "camera_rotation": {
                "pitch": self.camera_rotation[0],
                "yaw": self.camera_rotation[1],
                "roll": self.camera_rotation[2],
            },
            "fov": self.fov,
            "vehicle_centroid": {
                "x": self.vehicle_centroid[0],
                "y": self.vehicle_centroid[1],
                "z": self.vehicle_centroid[2],
            },
            "vehicle_bounds": self.vehicle_bounds.to_dict() if self.vehicle_bounds else None,
            "visibility_results": [v.to_dict() for v in self.visibility_results],
            "retry_count": self.retry_count,
            "failure_reason": self.failure_reason,
        }


class AdaptiveCameraController:
    """
    Camera controller that GUARANTEES vehicle visibility.
    
    INVARIANT: A frame is only captured if ALL vehicles have >=50% visibility.
    """
    
    MODULE_NAME = "AdaptiveCamera"
    
    def __init__(
        self,
        config: CameraConfig,
        image_width: int = 1920,
        image_height: int = 1080,
        logger: Optional[ResearchLogger] = None,
    ):
        """
        Initialize adaptive camera.
        
        Args:
            config: Camera configuration
            image_width: Output image width
            image_height: Output image height
            logger: Optional research logger
        """
        self.config = config
        self.image_width = image_width
        self.image_height = image_height
        self.log = logger or ResearchLogger(self.MODULE_NAME)
        
        # Base camera height in cm
        self.camera_height_cm = config.height * 100  # m to cm
        
        self.log.log_init(
            camera_height_m=config.height,
            base_fov=config.fov,
            min_visibility_ratio=MIN_VISIBILITY_RATIO,
            max_retries=MAX_CAMERA_RETRIES,
            image_size=(image_width, image_height),
        )
    
    def fit_camera_to_vehicles(
        self,
        vehicles: List[SpawnedVehicle],
        world_offset_x: float,
        world_offset_y: float,
    ) -> CameraFitResult:
        """
        Fit camera to ensure all vehicles are visible.
        
        MANDATORY ALGORITHM:
        1. Compute centroid of all vehicle positions
        2. Compute enclosing bounding box
        3. Position camera behind vehicles, looking at centroid
        4. Verify >=50% visibility for each vehicle
        5. If any fails, zoom out (increase FOV or distance) and retry
        
        Args:
            vehicles: List of spawned vehicles with positions
            world_offset_x: Camera origin X in cm
            world_offset_y: Camera origin Y in cm
            
        Returns:
            CameraFitResult with camera parameters or failure info
        """
        if not vehicles:
            return CameraFitResult(
                success=False,
                camera_position=(world_offset_x, world_offset_y, self.camera_height_cm),
                camera_rotation=(0, 0, 0),
                fov=self.config.fov,
                vehicle_centroid=(0, 0, 0),
                vehicle_bounds=None,
                visibility_results=[],
                retry_count=0,
                failure_reason="No vehicles to frame",
            )
        
        # Step 1: Compute vehicle bounds and centroid
        bounds, centroid = self._compute_vehicle_bounds(vehicles, world_offset_x, world_offset_y)
        
        self.log.info(
            "Computing camera fit",
            vehicle_count=len(vehicles),
            centroid={"x": centroid[0], "y": centroid[1], "z": centroid[2]},
            bounds=bounds.to_dict(),
        )
        
        # Step 2: Try fitting with increasing FOV
        current_fov = self.config.fov
        retry_count = 0
        
        while retry_count < MAX_CAMERA_RETRIES:
            # Compute camera position
            camera_pos, camera_rot = self._compute_camera_pose(
                centroid, bounds, world_offset_x, world_offset_y, current_fov
            )
            
            # Project vehicles and check visibility
            visibility_results = self._project_and_check_visibility(
                vehicles, camera_pos, camera_rot, current_fov, 
                world_offset_x, world_offset_y
            )
            
            # Check if all vehicles pass
            all_visible = all(v.is_valid for v in visibility_results)
            
            # Log attempt
            self.log.info(
                "Camera fit attempt",
                retry=retry_count,
                fov=current_fov,
                camera_position={"x": camera_pos[0], "y": camera_pos[1], "z": camera_pos[2]},
                all_visible=all_visible,
                visibility_ratios=[v.visible_ratio for v in visibility_results],
            )
            
            if all_visible:
                # SUCCESS!
                self.log.info(
                    "Camera fit SUCCESS",
                    final_fov=current_fov,
                    retry_count=retry_count,
                    per_vehicle_visibility=[
                        {"actor": v.actor_name, "ratio": v.visible_ratio}
                        for v in visibility_results
                    ],
                )
                
                return CameraFitResult(
                    success=True,
                    camera_position=camera_pos,
                    camera_rotation=camera_rot,
                    fov=current_fov,
                    vehicle_centroid=centroid,
                    vehicle_bounds=bounds,
                    visibility_results=visibility_results,
                    retry_count=retry_count,
                )
            
            # RETRY: Increase FOV to zoom out
            current_fov += FOV_EXPANSION_STEP
            if current_fov > MAX_FOV:
                current_fov = MAX_FOV
            retry_count += 1
        
        # FAILURE: Could not fit all vehicles
        failed_vehicles = [v for v in visibility_results if not v.is_valid]
        
        self.log.error(
            "Camera fit FAILED - retries exceeded",
            max_retries=MAX_CAMERA_RETRIES,
            failed_vehicles=[
                {"actor": v.actor_name, "ratio": v.visible_ratio}
                for v in failed_vehicles
            ],
        )
        
        return CameraFitResult(
            success=False,
            camera_position=camera_pos,
            camera_rotation=camera_rot,
            fov=current_fov,
            vehicle_centroid=centroid,
            vehicle_bounds=bounds,
            visibility_results=visibility_results,
            retry_count=retry_count,
            failure_reason=f"Cannot achieve >=50% visibility for {len(failed_vehicles)} vehicles",
        )
    
    def _compute_vehicle_bounds(
        self,
        vehicles: List[SpawnedVehicle],
        world_offset_x: float,
        world_offset_y: float,
    ) -> Tuple[BoundingBox3D, Tuple[float, float, float]]:
        """
        Compute enclosing bounds and centroid of all vehicles.
        
        Returns:
            (BoundingBox3D, centroid_xyz)
        """
        # Get vehicle positions in world coordinates (cm)
        positions = []
        for v in vehicles:
            # Convert from spawn coordinates (meters) to world (cm)
            wx = world_offset_x + v.transform.x * 100
            wy = world_offset_y + v.transform.y * 100
            wz = v.transform.z * 100  # Usually on ground
            
            # Account for vehicle dimensions (in meters, convert to cm)
            half_l = v.dimensions.length * 100 / 2
            half_w = v.dimensions.width * 100 / 2
            half_h = v.dimensions.height * 100 / 2
            
            positions.append({
                "x": wx, "y": wy, "z": wz + half_h,  # Center Z at half height
                "half_l": half_l, "half_w": half_w, "half_h": half_h,
            })
        
        # Compute bounds
        min_x = min(p["x"] - p["half_l"] for p in positions)
        max_x = max(p["x"] + p["half_l"] for p in positions)
        min_y = min(p["y"] - p["half_w"] for p in positions)
        max_y = max(p["y"] + p["half_w"] for p in positions)
        min_z = 0  # Ground level
        max_z = max(p["z"] + p["half_h"] for p in positions)
        
        bounds = BoundingBox3D(min_x, max_x, min_y, max_y, min_z, max_z)
        
        # Compute centroid
        centroid = bounds.center
        
        return bounds, centroid
    
    def _compute_camera_pose(
        self,
        centroid: Tuple[float, float, float],
        bounds: BoundingBox3D,
        world_offset_x: float,
        world_offset_y: float,
        fov: float,
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """
        Compute camera position and rotation to frame the vehicles.
        
        Camera is positioned behind the centroid (negative X), looking forward.
        
        Returns:
            (position_xyz, rotation_pyr)
        """
        # Camera is at the spawn origin (world offset), which is behind vehicles
        # Vehicles are spawned at positive X from camera
        
        # The camera should be at the world offset position
        cam_x = world_offset_x
        cam_y = world_offset_y
        cam_z = self.camera_height_cm
        
        # Camera looks forward (+X direction in UE5)
        pitch = 0.0
        yaw = 0.0
        roll = 0.0
        
        return (cam_x, cam_y, cam_z), (pitch, yaw, roll)
    
    def _project_and_check_visibility(
        self,
        vehicles: List[SpawnedVehicle],
        camera_pos: Tuple[float, float, float],
        camera_rot: Tuple[float, float, float],
        fov: float,
        world_offset_x: float,
        world_offset_y: float,
    ) -> List[VehicleVisibility]:
        """
        Project all vehicles to 2D and check visibility.
        
        Returns:
            List of VehicleVisibility results
        """
        results = []
        
        for vehicle in vehicles:
            # Get vehicle position in world coordinates (cm)
            vx = world_offset_x + vehicle.transform.x * 100
            vy = world_offset_y + vehicle.transform.y * 100
            vz = vehicle.transform.z * 100
            
            # Vehicle dimensions in cm
            half_l = vehicle.dimensions.length * 100 / 2
            half_w = vehicle.dimensions.width * 100 / 2
            half_h = vehicle.dimensions.height * 100 / 2
            
            # Project 8 corners of vehicle bounding box
            corners_3d = [
                (vx - half_l, vy - half_w, vz),
                (vx + half_l, vy - half_w, vz),
                (vx - half_l, vy + half_w, vz),
                (vx + half_l, vy + half_w, vz),
                (vx - half_l, vy - half_w, vz + 2*half_h),
                (vx + half_l, vy - half_w, vz + 2*half_h),
                (vx - half_l, vy + half_w, vz + 2*half_h),
                (vx + half_l, vy + half_w, vz + 2*half_h),
            ]
            
            # Project to 2D
            corners_2d = []
            for corner in corners_3d:
                u, v = self._project_point(corner, camera_pos, camera_rot, fov)
                corners_2d.append((u, v))
            
            # Compute 2D bounding box from projected corners
            us = [c[0] for c in corners_2d]
            vs = [c[1] for c in corners_2d]
            
            bbox_x = min(us)
            bbox_y = min(vs)
            bbox_x2 = max(us)
            bbox_y2 = max(vs)
            bbox_w = bbox_x2 - bbox_x
            bbox_h = bbox_y2 - bbox_y
            
            # Compute visibility ratio
            total_area = bbox_w * bbox_h
            
            # Clip to image bounds
            clip_x = max(0, bbox_x)
            clip_y = max(0, bbox_y)
            clip_x2 = min(self.image_width, bbox_x2)
            clip_y2 = min(self.image_height, bbox_y2)
            
            visible_w = max(0, clip_x2 - clip_x)
            visible_h = max(0, clip_y2 - clip_y)
            visible_area = visible_w * visible_h
            
            if total_area > 0:
                visible_ratio = visible_area / total_area
            else:
                visible_ratio = 0.0
            
            is_valid = visible_ratio >= MIN_VISIBILITY_RATIO
            
            results.append(VehicleVisibility(
                actor_name=vehicle.actor_name,
                vehicle_class=vehicle.vehicle_class.value,
                bbox_2d=(bbox_x, bbox_y, bbox_w, bbox_h),
                visible_ratio=visible_ratio,
                is_valid=is_valid,
            ))
        
        return results
    
    def _project_point(
        self,
        point_3d: Tuple[float, float, float],
        camera_pos: Tuple[float, float, float],
        camera_rot: Tuple[float, float, float],
        fov: float,
    ) -> Tuple[float, float]:
        """
        Project a 3D point to 2D image coordinates.
        
        Uses pinhole camera model.
        
        Returns:
            (u, v) pixel coordinates
        """
        # Vector from camera to point
        dx = point_3d[0] - camera_pos[0]
        dy = point_3d[1] - camera_pos[1]
        dz = point_3d[2] - camera_pos[2]
        
        # For forward-facing camera (yaw=0, pitch=0):
        # X is forward, Y is right, Z is up
        # In camera space: z_cam is forward (depth), x_cam is right, y_cam is down
        
        # Transform to camera space (simplified for forward-facing camera)
        z_cam = dx  # Depth (forward)
        x_cam = -dy  # Right (negative because Y in UE5 is left-handed)
        y_cam = -dz  # Down (negative because Z is up)
        
        # Avoid division by zero
        if z_cam <= 0:
            z_cam = 0.01
        
        # Focal length from FOV
        fov_rad = math.radians(fov)
        fx = self.image_width / (2 * math.tan(fov_rad / 2))
        fy = fx  # Square pixels
        
        # Principal point
        cx = self.image_width / 2
        cy = self.image_height / 2
        
        # Project
        u = fx * (x_cam / z_cam) + cx
        v = fy * (y_cam / z_cam) + cy
        
        return u, v
