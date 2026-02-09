"""
Dashcam Camera Placement & Spatial Validation

GUARDRAILS ONLY — does not redesign the simulation.
Adds dashcam-like camera behavior on top of existing spawn + capture logic.

Rules enforced:
  1. Camera placed IN a valid road lane at windshield height
  2. Camera faces lane forward direction (like a dashcam)
  3. Camera must not overlap any vehicle
  4. No vehicles behind the camera
  5. No vehicles directly left/right (adjacent lane, same forward position)
  6. At most ONE vehicle in the same lane as camera, must be ahead
  7. Vehicles in adjacent lanes must be slightly ahead, not parallel
"""

import math
import random
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Dashcam is at windshield height above the road surface (cm)
DASHCAM_HEIGHT_CM = 150.0  # ~1.5 m
DASHCAM_HEIGHT_JITTER_CM = 200.0  # Random extra height [0, 200] cm

# Typical dashcam FOV (degrees)
DASHCAM_FOV = 90.0

# Slight downward pitch to mimic real dashcam mount
DASHCAM_PITCH = -3.0

# Default lane width when not specified (cm)
DEFAULT_LANE_WIDTH_CM = 400.0  # 4 m

# Minimum forward distance for "ahead" classification (cm)
MIN_AHEAD_DISTANCE_CM = 200.0  # 2 m — vehicles must be at least this far ahead

# Minimum clearance between camera point and any vehicle centre (cm)
MIN_CAMERA_VEHICLE_CLEARANCE_CM = 300.0

# Maximum number of vehicles allowed in the same lane as the camera
MAX_SAME_LANE_VEHICLES = 1


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DashcamPlacement:
    """Computed dashcam camera placement."""
    location: Dict[str, float]       # {"X", "Y", "Z"} in cm
    rotation: Dict[str, float]       # {"Pitch", "Yaw", "Roll"} in degrees
    fov: float                       # Field of view in degrees
    lane_id: str                     # Which lane the camera sits in
    lane_forward: Tuple[float, float]  # Normalised 2-D forward vector
    lane_right: Tuple[float, float]    # Normalised 2-D right vector
    lane_width_cm: float             # Physical lane width used for checks

    def to_camera_placement(self):
        """Convert to CameraPlacement for SmartCameraCaptureController."""
        from .smart_camera_capture_controller import CameraPlacement
        # Target centroid is a point ~20 m ahead of the camera
        fx, fy = self.lane_forward
        return CameraPlacement(
            location=dict(self.location),
            rotation=dict(self.rotation),
            fov=self.fov,
            target_centroid={
                "X": self.location["X"] + fx * 2000,
                "Y": self.location["Y"] + fy * 2000,
                "Z": self.location["Z"],
            },
        )


@dataclass
class VehicleSpatialInfo:
    """Spatial classification of a spawned vehicle relative to the dashcam."""
    name: str
    category: str
    forward_dist: float   # cm, positive = ahead
    lateral_dist: float   # cm, positive = right of camera
    same_lane: bool       # True if vehicle's spawn lane_id == camera lane_id
    adjacent_lane: bool
    spawn_lane_id: Optional[str] = None  # Lane ID the vehicle was spawned in
    rule_violated: Optional[str] = None  # None ⇒ passes all rules


@dataclass
class DashcamFilterResult:
    """Result of spatial filtering."""
    kept_vehicles: List[str]           # Vehicle names that pass all rules
    hidden_vehicles: List[str]         # Vehicle names that were hidden
    spatial_info: List[VehicleSpatialInfo]
    dashcam_placement: DashcamPlacement


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def compute_dashcam_placement(
    spawner,       # VehicleSpawnController — we use its lane helpers
    seed: int,
    lane_width_cm: float = DEFAULT_LANE_WIDTH_CM,
) -> Optional[DashcamPlacement]:
    """
    Pick a random valid lane and compute a dashcam placement in it.

    The camera position is a random point along the lane centreline
    (t ∈ [0.25, 0.75] to avoid endpoints) at DASHCAM_HEIGHT_CM above
    the road surface.

    Args:
        spawner:  VehicleSpawnController instance (provides lane data)
        seed:     Random seed for determinism
        lane_width_cm: Physical lane width for spatial checks

    Returns:
        DashcamPlacement or None if no lanes available
    """
    rng = random.Random(seed)

    lanes = spawner._get_lane_definitions()
    if not lanes:
        logger.warning("No lane definitions — cannot compute dashcam placement")
        return None

    # Shuffle lanes so the choice is random (deterministic via seed)
    lanes_copy = list(lanes)
    rng.shuffle(lanes_copy)

    for lane in lanes_copy:
        segments = spawner._discover_lane_segments(lane)
        if not segments:
            continue

        segment = rng.choice(segments)

        # Place camera well behind the lane start so all vehicles are
        # comfortably ahead.  Negative t extends behind the lane origin;
        # the lane direction vector is still used so the camera faces
        # the correct way.  Range [-0.5, 0.0] = 0–50% of lane length
        # behind the start anchor.
        t = rng.uniform(-0.5, 0.0)
        transform = spawner._compute_lane_transform_with_offset(segment, t, lateral_offset=0.0)
        if not transform:
            continue

        loc = transform["location"]
        lane_yaw = transform["rotation"]["Yaw"]
        yaw_rad = math.radians(lane_yaw)

        # Forward and right unit vectors
        fx = math.cos(yaw_rad)
        fy = math.sin(yaw_rad)
        rx = math.sin(yaw_rad)
        ry = -math.cos(yaw_rad)

        # Randomize height: base + [0, DASHCAM_HEIGHT_JITTER_CM]
        cam_height = DASHCAM_HEIGHT_CM + rng.uniform(0, DASHCAM_HEIGHT_JITTER_CM)

        placement = DashcamPlacement(
            location={"X": loc["X"], "Y": loc["Y"], "Z": loc["Z"] + cam_height},
            rotation={"Pitch": DASHCAM_PITCH, "Yaw": lane_yaw, "Roll": 0.0},
            fov=DASHCAM_FOV,
            lane_id=lane.get("id", "unknown"),
            lane_forward=(fx, fy),
            lane_right=(rx, ry),
            lane_width_cm=lane_width_cm,
        )

        logger.info(
            f"Dashcam placement: lane={placement.lane_id}, "
            f"pos=({loc['X']:.0f}, {loc['Y']:.0f}, {loc['Z'] + DASHCAM_HEIGHT_CM:.0f}), "
            f"yaw={lane_yaw:.1f}°"
        )
        return placement

    logger.warning("Could not find any valid lane for dashcam placement")
    return None


# ---------------------------------------------------------------------------
# Spatial classification
# ---------------------------------------------------------------------------

def _classify_vehicle(
    placement: DashcamPlacement,
    vehicle_name: str,
    vehicle_category: str,
    vehicle_location: Dict[str, float],
    spawn_lane_id: Optional[str] = None,
) -> VehicleSpatialInfo:
    """
    Classify a single vehicle relative to the dashcam.

    same_lane is determined by matching the vehicle's spawn lane ID
    against the camera's lane ID (exact match).  Falls back to
    lateral-distance heuristic only when lane ID is unavailable.
    """
    cam = placement.location
    fx, fy = placement.lane_forward
    rx, ry = placement.lane_right
    lw = placement.lane_width_cm

    # Relative position of vehicle w.r.t. camera (2-D, ignore Z)
    rel_x = vehicle_location.get("X", 0) - cam["X"]
    rel_y = vehicle_location.get("Y", 0) - cam["Y"]

    forward_dist = rel_x * fx + rel_y * fy
    lateral_dist = rel_x * rx + rel_y * ry

    abs_lateral = abs(lateral_dist)

    # Primary: lane-ID match (reliable even when camera is extrapolated)
    if spawn_lane_id is not None:
        same_lane = (spawn_lane_id == placement.lane_id)
    else:
        # Fallback for parking/sidewalk vehicles: use lateral distance
        same_lane = abs_lateral < (lw / 2)

    adjacent_lane = (not same_lane) and abs_lateral < (1.5 * lw)

    return VehicleSpatialInfo(
        name=vehicle_name,
        category=vehicle_category,
        forward_dist=forward_dist,
        lateral_dist=lateral_dist,
        same_lane=same_lane,
        adjacent_lane=adjacent_lane,
        spawn_lane_id=spawn_lane_id,
    )


def _apply_rules(info: VehicleSpatialInfo) -> VehicleSpatialInfo:
    """Check all dashcam spatial rules and set `rule_violated` if any fail."""

    # Rule 1: No vehicles behind the camera
    if info.forward_dist < 0:
        info.rule_violated = f"behind camera (fwd={info.forward_dist:.0f}cm)"
        return info

    # Rule 2: No vehicles directly beside the camera
    #   "directly beside" = within 1.5 lane widths AND not sufficiently ahead
    if info.adjacent_lane and info.forward_dist < MIN_AHEAD_DISTANCE_CM:
        info.rule_violated = (
            f"beside camera (fwd={info.forward_dist:.0f}cm, lat={info.lateral_dist:.0f}cm)"
        )
        return info

    # Rule 3: Same-lane vehicle must be ahead (handled in batch below)
    #   We just flag it here if it's in the same lane but not ahead enough.
    if info.same_lane and info.forward_dist < MIN_AHEAD_DISTANCE_CM:
        info.rule_violated = (
            f"same lane but not ahead (fwd={info.forward_dist:.0f}cm)"
        )
        return info

    # Rule 4: Adjacent-lane vehicles must be slightly ahead
    if info.adjacent_lane and info.forward_dist < MIN_AHEAD_DISTANCE_CM:
        info.rule_violated = (
            f"adjacent lane not ahead (fwd={info.forward_dist:.0f}cm)"
        )
        return info

    return info


# ---------------------------------------------------------------------------
# Main filter
# ---------------------------------------------------------------------------

def filter_vehicles_for_dashcam(
    placement: DashcamPlacement,
    spawned_vehicles: List[Any],
    spawner,  # VehicleSpawnController — used to hide actors
) -> DashcamFilterResult:
    """
    Evaluate every spawned vehicle against dashcam spatial rules.
    Vehicles that violate any rule are hidden in the scene.

    Args:
        placement:        DashcamPlacement computed earlier
        spawned_vehicles: List of VehicleInstance (has .name, .category,
                          .spawn_location)
        spawner:          VehicleSpawnController (for _set_actor_hidden)

    Returns:
        DashcamFilterResult with kept / hidden lists and diagnostics
    """
    spatial: List[VehicleSpatialInfo] = []
    kept: List[str] = []
    hidden: List[str] = []

    # First pass: classify and apply per-vehicle rules
    for v in spawned_vehicles:
        loc = v.spawn_location
        # anchor_name stores the lane_id for lane-spawned vehicles
        spawn_lane_id = getattr(v, 'anchor_name', None)
        # Only treat it as a lane ID if it starts with "lane_"
        if spawn_lane_id and not spawn_lane_id.startswith("lane_"):
            spawn_lane_id = None
        info = _classify_vehicle(placement, v.name, v.category, loc, spawn_lane_id)
        info = _apply_rules(info)
        spatial.append(info)

    # Second pass: enforce max-one-same-lane rule
    same_lane_ok = [s for s in spatial if s.same_lane and s.rule_violated is None]
    if len(same_lane_ok) > MAX_SAME_LANE_VEHICLES:
        # Keep only the closest same-lane vehicle that is ahead
        same_lane_ok.sort(key=lambda s: s.forward_dist)
        for extra in same_lane_ok[MAX_SAME_LANE_VEHICLES:]:
            extra.rule_violated = (
                f"excess same-lane vehicle (only {MAX_SAME_LANE_VEHICLES} allowed)"
            )

    # Third pass: also check camera-vehicle clearance
    cam = placement.location
    for info in spatial:
        if info.rule_violated is not None:
            continue
        v_match = next((v for v in spawned_vehicles if v.name == info.name), None)
        if v_match:
            vloc = v_match.spawn_location
            dx = vloc.get("X", 0) - cam["X"]
            dy = vloc.get("Y", 0) - cam["Y"]
            dz = vloc.get("Z", 0) - cam["Z"]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist < MIN_CAMERA_VEHICLE_CLEARANCE_CM:
                info.rule_violated = f"too close to camera ({dist:.0f}cm < {MIN_CAMERA_VEHICLE_CLEARANCE_CM}cm)"

    # Apply: hide violators, keep the rest
    for info in spatial:
        if info.rule_violated:
            hidden.append(info.name)
            spawner._set_actor_hidden(info.name, True)
            logger.info(f"  [DASHCAM HIDE] {info.name}: {info.rule_violated}")
        else:
            kept.append(info.name)
            logger.info(
                f"  [DASHCAM KEEP] {info.name}: fwd={info.forward_dist:.0f}cm, "
                f"lat={info.lateral_dist:.0f}cm, same_lane={info.same_lane}"
            )

    # Summary
    print(f"  Dashcam filter: {len(kept)} kept, {len(hidden)} hidden")
    for info in spatial:
        tag = "KEEP" if info.rule_violated is None else "HIDE"
        reason = info.rule_violated or "OK"
        print(
            f"    [{tag}] {info.name} ({info.category}): "
            f"fwd={info.forward_dist:.0f}cm, lat={info.lateral_dist:.0f}cm — {reason}"
        )

    return DashcamFilterResult(
        kept_vehicles=kept,
        hidden_vehicles=hidden,
        spatial_info=spatial,
        dashcam_placement=placement,
    )
