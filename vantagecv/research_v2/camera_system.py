"""
Research v2 - MODULE 3: Camera System

Responsibilities:
- Single forward-facing dashcam
- Fixed height and pitch
- Minor FOV jitter allowed

Camera parameters:
- Height: fixed (e.g., 1.5m)
- FOV: 90 ± small jitter
- Resolution: fixed

Logging (REQUIRED):
- Camera initialized
- Intrinsics
- Extrinsics
- Frame index
"""

from dataclasses import dataclass
from typing import Optional
import math
import random

from .logging_utils import ResearchLogger
from .config import CameraConfig


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters."""
    fx: float  # Focal length X (pixels)
    fy: float  # Focal length Y (pixels)
    cx: float  # Principal point X (pixels)
    cy: float  # Principal point Y (pixels)
    width: int
    height: int
    
    def to_dict(self) -> dict:
        return {
            "fx": self.fx,
            "fy": self.fy,
            "cx": self.cx,
            "cy": self.cy,
            "width": self.width,
            "height": self.height,
        }
    
    def to_matrix(self) -> list[list[float]]:
        """Return 3x3 intrinsic matrix K."""
        return [
            [self.fx, 0, self.cx],
            [0, self.fy, self.cy],
            [0, 0, 1],
        ]


@dataclass
class CameraExtrinsics:
    """Camera extrinsic parameters (pose in world)."""
    x: float       # Position X (meters)
    y: float       # Position Y (meters)
    z: float       # Position Z (meters) - height
    pitch: float   # Rotation around Y (degrees)
    yaw: float     # Rotation around Z (degrees)
    roll: float    # Rotation around X (degrees)
    
    def to_dict(self) -> dict:
        return {
            "position": {"x": self.x, "y": self.y, "z": self.z},
            "rotation": {"pitch": self.pitch, "yaw": self.yaw, "roll": self.roll},
        }


@dataclass
class CameraState:
    """Current camera state for a frame."""
    frame_index: int
    intrinsics: CameraIntrinsics
    extrinsics: CameraExtrinsics
    fov: float  # Actual FOV used (with jitter applied)
    
    def to_dict(self) -> dict:
        return {
            "frame_index": self.frame_index,
            "fov": self.fov,
            "intrinsics": self.intrinsics.to_dict(),
            "extrinsics": self.extrinsics.to_dict(),
        }


class CameraSystem:
    """
    MODULE 3 - Camera System
    
    Fixed forward-facing dashcam with minor randomization.
    """
    
    MODULE_NAME = "CameraSystem"
    
    def __init__(
        self,
        config: CameraConfig,
        logger: Optional[ResearchLogger] = None,
    ):
        """
        Initialize camera system.
        
        Args:
            config: Camera configuration
            logger: Optional logger
        """
        self.config = config
        self.logger = logger or ResearchLogger(self.MODULE_NAME)
        self._rng = random.Random()
        self._current_state: Optional[CameraState] = None
        
        # Compute base intrinsics
        self._base_intrinsics = self._compute_intrinsics(config.fov)
        
        self.logger.log_init(
            height=config.height,
            fov=config.fov,
            fov_jitter=config.fov_jitter,
            resolution=(config.width, config.height_px),
            base_intrinsics=self._base_intrinsics.to_dict(),
        )
    
    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)
        self.logger.debug("Random seed set", seed=seed)
    
    def _compute_intrinsics(self, fov: float) -> CameraIntrinsics:
        """
        Compute intrinsic parameters from FOV.
        
        Args:
            fov: Horizontal field of view in degrees
            
        Returns:
            CameraIntrinsics object
        """
        # Focal length from FOV: f = w / (2 * tan(fov/2))
        fov_rad = math.radians(fov)
        fx = self.config.width / (2 * math.tan(fov_rad / 2))
        fy = fx  # Square pixels assumed
        
        # Principal point at image center
        cx = self.config.width / 2
        cy = self.config.height_px / 2
        
        return CameraIntrinsics(
            fx=fx,
            fy=fy,
            cx=cx,
            cy=cy,
            width=self.config.width,
            height=self.config.height_px,
        )
    
    def _get_extrinsics(self) -> CameraExtrinsics:
        """Get camera extrinsics (fixed position)."""
        return CameraExtrinsics(
            x=self.config.x_position,
            y=self.config.y_position,
            z=self.config.height,
            pitch=self.config.pitch,
            yaw=self.config.yaw,
            roll=self.config.roll,
        )
    
    def setup_frame(self, frame_index: int, apply_jitter: bool = True) -> CameraState:
        """
        Set up camera for a specific frame.
        
        Args:
            frame_index: Current frame index
            apply_jitter: Whether to apply FOV jitter
            
        Returns:
            CameraState for this frame
        """
        # Apply FOV jitter if enabled
        if apply_jitter and self.config.fov_jitter > 0:
            jitter = self._rng.uniform(-self.config.fov_jitter, self.config.fov_jitter)
            actual_fov = self.config.fov + jitter
        else:
            actual_fov = self.config.fov
        
        # Compute intrinsics for this FOV
        intrinsics = self._compute_intrinsics(actual_fov)
        extrinsics = self._get_extrinsics()
        
        self._current_state = CameraState(
            frame_index=frame_index,
            intrinsics=intrinsics,
            extrinsics=extrinsics,
            fov=actual_fov,
        )
        
        self.logger.info(
            "Camera setup for frame",
            frame_index=frame_index,
            fov=actual_fov,
            intrinsics=intrinsics.to_dict(),
            extrinsics=extrinsics.to_dict(),
        )
        
        return self._current_state
    
    @property
    def state(self) -> Optional[CameraState]:
        """Get current camera state."""
        return self._current_state
    
    @property
    def intrinsics(self) -> CameraIntrinsics:
        """Get current intrinsics (base if no state)."""
        if self._current_state:
            return self._current_state.intrinsics
        return self._base_intrinsics
    
    def project_point_3d_to_2d(
        self,
        x: float,
        y: float,
        z: float,
    ) -> tuple[float, float, float]:
        """
        Project 3D world point to 2D image coordinates.
        
        Uses simple pinhole camera model.
        Camera is at origin looking down +X axis.
        
        Args:
            x: World X (forward from camera, meters)
            y: World Y (lateral, meters)
            z: World Z (height, meters)
            
        Returns:
            Tuple of (u, v, depth) where u,v are pixel coords
        """
        intrinsics = self.intrinsics
        extrinsics = self._get_extrinsics()
        
        # Transform to camera frame
        # Camera looks down +X, Y is left/right, Z is up
        cam_x = x - extrinsics.x
        cam_y = y - extrinsics.y
        cam_z = z - extrinsics.z
        
        # Depth is X distance
        depth = cam_x
        
        if depth <= 0:
            # Point is behind camera
            return -1, -1, depth
        
        # Project to image plane
        # u = fx * (-Y/X) + cx  (Y is inverted because image Y goes down)
        # v = fy * (-Z/X) + cy
        u = intrinsics.fx * (-cam_y / cam_x) + intrinsics.cx
        v = intrinsics.fy * (-cam_z / cam_x) + intrinsics.cy
        
        return u, v, depth
    
    def project_bbox_3d_to_2d(
        self,
        x: float,
        y: float,
        z: float,
        length: float,
        width: float,
        height: float,
    ) -> Optional[tuple[float, float, float, float]]:
        """
        Project 3D bounding box to 2D image bbox.
        
        Args:
            x, y, z: Center of 3D bbox (meters)
            length: Extent in X (meters)
            width: Extent in Y (meters)  
            height: Extent in Z (meters)
            
        Returns:
            Tuple of (x, y, w, h) in pixels, or None if not visible
        """
        # Get 8 corners of 3D bbox
        corners_3d = []
        for dx in [-length/2, length/2]:
            for dy in [-width/2, width/2]:
                for dz in [0, height]:  # Bottom at z, top at z+height
                    corners_3d.append((x + dx, y + dy, z + dz))
        
        # Project all corners
        corners_2d = []
        all_behind = True
        
        for cx, cy, cz in corners_3d:
            u, v, depth = self.project_point_3d_to_2d(cx, cy, cz)
            if depth > 0:
                all_behind = False
            corners_2d.append((u, v))
        
        if all_behind:
            self.logger.debug("Bbox fully behind camera", x=x, y=y, z=z)
            return None
        
        # Get bounding rectangle of projected corners
        us = [c[0] for c in corners_2d if c[0] >= 0]
        vs = [c[1] for c in corners_2d if c[1] >= 0]
        
        if not us or not vs:
            return None
        
        min_u, max_u = min(us), max(us)
        min_v, max_v = min(vs), max(vs)
        
        # Return as x, y, w, h
        return min_u, min_v, max_u - min_u, max_v - min_v
    
    def is_point_in_frame(self, u: float, v: float) -> bool:
        """Check if 2D point is within image bounds."""
        return (0 <= u < self.config.width and 
                0 <= v < self.config.height_px)
    
    def get_ue5_commands(self) -> list[dict]:
        """Get UE5 commands to set up camera."""
        extrinsics = self._get_extrinsics()
        
        return [{
            "type": "set_camera",
            "location": {
                "x": extrinsics.x * 100,  # meters to cm
                "y": extrinsics.y * 100,
                "z": extrinsics.z * 100,
            },
            "rotation": {
                "pitch": extrinsics.pitch,
                "yaw": extrinsics.yaw,
                "roll": extrinsics.roll,
            },
            "fov": self._current_state.fov if self._current_state else self.config.fov,
            "resolution": {
                "width": self.config.width,
                "height": self.config.height_px,
            },
        }]
    
    def validate(self) -> tuple[bool, list[str]]:
        """Validate camera configuration."""
        issues = []
        
        if self.config.fov < 30 or self.config.fov > 150:
            issues.append(f"FOV {self.config.fov} outside reasonable range [30, 150]")
        
        if self.config.width < 640 or self.config.height_px < 480:
            issues.append(f"Resolution {self.config.width}x{self.config.height_px} too low")
        
        if self.config.height < 0.5:
            issues.append(f"Camera height {self.config.height}m unrealistically low")
        
        is_valid = len(issues) == 0
        
        if is_valid:
            self.logger.info("Camera configuration validated successfully")
        else:
            for issue in issues:
                self.logger.warning("Camera validation issue", issue=issue)
        
        return is_valid, issues
