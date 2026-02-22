#!/usr/bin/env python3
"""
Quick randomization test - cycle through 20 random captures for video recording

SAFETY GUARANTEE:
After every test run, the level is restored to its exact pre-test state.
All actor transforms are captured before spawning and restored in finally block.

VEHICLE CATEGORY CONSTRAINTS:
- Bikes: Parking slots OR sidewalks
- Motorcycles: Parking slots only
- Buses: Road lanes only
- Cars: Parking slots OR road lanes
- Trucks: Parking slots OR road lanes
"""
import sys
import math
import time
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.research_v2.vehicle_spawn_controller import VehicleSpawnController
from vantagecv.research_v2.smart_camera_capture_controller import SmartCameraCaptureController
from vantagecv.research_v2.prop_zone_controller import PropZoneController
from vantagecv.research_v2.time_augmentation_controller import TimeAugmentationController
from vantagecv.research_v2.weather_augmentation_controller import WeatherAugmentationController
from vantagecv.research_v2.dashcam_camera import (
    DashcamPlacement,
    compute_dashcam_placement,
    filter_vehicles_for_dashcam,
)


# =============================================================================
# LOCATION BOUNDARIES
# =============================================================================

# Location boundaries (Y-coordinate ranges)
LOCATION_BOUNDARIES = {
    1: (400, 19600),
    2: (19600, 39600),
    3: (39600, 59600),
    4: (59600, 79600),
    5: (79600, 97600),
    6: (97600, 117600),
    7: (117600, 137600),
}


# =============================================================================
# VEHICLE ZONE CONSTRAINTS
# =============================================================================

# Define which zone types are allowed for each vehicle category
VEHICLE_ZONE_CONSTRAINTS = {
    "bicycle": ["sidewalk"],             # Bikes: sidewalk only
    "motorcycle": ["parking"],           # Motorcycles: parking only
    "bus": ["lane"],                     # Buses: lanes only
    "car": ["parking", "lane"],          # Cars: parking or lanes
    "truck": ["parking", "lane"],        # Trucks: parking or lanes
}

# All vehicle categories to spawn
ALL_VEHICLE_CATEGORIES = ["bicycle", "motorcycle", "bus", "car", "truck"]


# =============================================================================
# SPAWN STATISTICS TRACKER
# =============================================================================

@dataclass
class SpawnStats:
    """Track spawn attempts and results per category"""
    attempts: Dict[str, int] = field(default_factory=lambda: {cat: 0 for cat in ALL_VEHICLE_CATEGORIES})
    successes: Dict[str, int] = field(default_factory=lambda: {cat: 0 for cat in ALL_VEHICLE_CATEGORIES})
    skipped_no_zone: Dict[str, int] = field(default_factory=lambda: {cat: 0 for cat in ALL_VEHICLE_CATEGORIES})
    skipped_constraint: Dict[str, int] = field(default_factory=lambda: {cat: 0 for cat in ALL_VEHICLE_CATEGORIES})
    collision_removed: int = 0
    
    def log_attempt(self, category: str, zone_type: str):
        """Log a spawn attempt"""
        self.attempts[category] = self.attempts.get(category, 0) + 1
    
    def log_success(self, category: str, vehicle_name: str, zone_name: str):
        """Log a successful spawn"""
        self.successes[category] = self.successes.get(category, 0) + 1
    
    def log_skip_no_zone(self, category: str):
        """Log a skip due to no available zones"""
        self.skipped_no_zone[category] = self.skipped_no_zone.get(category, 0) + 1
        print(f"    [SKIP] {category}: No valid zones available")
    
    def log_skip_constraint(self, category: str, zone_type: str):
        """Log a skip due to zone constraint violation"""
        self.skipped_constraint[category] = self.skipped_constraint.get(category, 0) + 1
        allowed = VEHICLE_ZONE_CONSTRAINTS.get(category, [])
        print(f"    [SKIP] {category}: Zone '{zone_type}' not allowed (allowed: {allowed})")
    
    def log_collision(self, actor1: str, actor2: str, resolution: str):
        """Log a collision detection and resolution"""
        self.collision_removed += 1
        print(f"    [COLLISION] {actor1} ↔ {actor2} → {resolution}")
    
    def print_summary(self):
        """Print final spawn statistics"""
        print("\n  Spawn Summary by Category:")
        total_spawned = 0
        total_skipped = 0
        for cat in ALL_VEHICLE_CATEGORIES:
            spawned = self.successes.get(cat, 0)
            no_zone = self.skipped_no_zone.get(cat, 0)
            constraint = self.skipped_constraint.get(cat, 0)
            total_spawned += spawned
            total_skipped += no_zone + constraint
            skip_info = []
            if no_zone > 0:
                skip_info.append(f"no-zone:{no_zone}")
            if constraint > 0:
                skip_info.append(f"constraint:{constraint}")
            skip_str = f" (skipped: {', '.join(skip_info)})" if skip_info else ""
            print(f"    {cat:12}: {spawned} spawned{skip_str}")
        
        print(f"  Total: {total_spawned} spawned, {total_skipped} skipped")
        if self.collision_removed > 0:
            print(f"  Collisions resolved: {self.collision_removed}")


# =============================================================================
# TEST CLEANUP
# =============================================================================

class TestCleanup:
    """
    Guaranteed cleanup for test runs.
    Stores original transforms and restores them exactly on exit.
    """
    
    def __init__(self, spawner: VehicleSpawnController, prop_controller: PropZoneController,
                 time_controller: TimeAugmentationController = None,
                 weather_controller: WeatherAugmentationController = None):
        self.spawner = spawner
        self.prop_controller = prop_controller
        self.time_controller = time_controller
        self.weather_controller = weather_controller
        self.saved_vehicle_transforms: Dict[str, Dict[str, Any]] = {}
        self.saved_prop_transforms: Dict[str, Dict[str, Any]] = {}
        self.actors_saved = 0
        self.actors_restored = 0
        self.restore_failures = 0
        self.baseline_set = False
    
    def reset_to_baseline(self) -> bool:
        """
        Set environment to deterministic baseline state BEFORE testing.
        Baseline: Noon lighting, clear weather, no fog, no rain.
        Called once at test start for clean initial conditions.
        
        Returns:
            True if baseline set successfully
        """
        if self.baseline_set:
            return True  # Already set, don't repeat
        
        print("\n[TestCleanup] Setting baseline environment (noon, clear)...")
        success = True
        
        # Set time to noon
        if self.time_controller:
            result = self.time_controller.set_time(time_state="noon")
            if result.success:
                print("  [OK] Time: noon")
            else:
                print(f"  [FAIL] Time: {result.failure_reason}")
                success = False
        
        # Set weather to clear AND manually clear fog/rain
        if self.weather_controller:
            # First, explicitly disable fog and rain
            print("  Clearing fog and rain...")
            
            # Clear fog density
            if self.weather_controller.exponential_fog:
                fog_path = f"{self.weather_controller.level_path}:PersistentLevel.{self.weather_controller.exponential_fog}.HeightFogComponent0"
                if self.weather_controller._set_property(fog_path, "FogDensity", 0.0):
                    print("    [OK] Fog density: 0.0")
                else:
                    print("    [FAIL] Could not clear fog density")
                    success = False
            
            # Disable ALL rain actors across all locations
            print("  Disabling all rain actors...")
            self.weather_controller._hide_all_rain_actors()
            print("    [OK] All rain actors hidden")
            
            # Now set weather to clear (for other settings)
            result = self.weather_controller.set_weather(weather_state="clear")
            if result.success:
                print("  [OK] Weather: clear (no fog, no rain)")
            else:
                print(f"  [FAIL] Weather: {result.failure_reason}")
                success = False
        
        self.baseline_set = success
        return success
    
    def save_all_transforms(self) -> int:
        """
        Capture and store original transforms for ALL prop pool actors.
        Called BEFORE any spawning occurs.
        
        Returns:
            Number of actors saved
        """
        self.actors_saved = 0
        
        # Save prop pool transforms (already stored during detect_prop_pool)
        self.saved_prop_transforms = {}
        for prop_class, props in self.prop_controller.prop_pool.items():
            for prop_name in props:
                if prop_name in self.prop_controller.prop_pool_original_transforms:
                    self.saved_prop_transforms[prop_name] = \
                        self.prop_controller.prop_pool_original_transforms[prop_name].copy()
                    self.actors_saved += 1
        
        # Save vehicle pool transforms
        self.saved_vehicle_transforms = {}
        if hasattr(self.spawner, 'vehicle_pool_original_transforms'):
            for vehicle_name, transform in self.spawner.vehicle_pool_original_transforms.items():
                self.saved_vehicle_transforms[vehicle_name] = transform.copy()
                self.actors_saved += 1
        
        print(f"\n[TestCleanup] Saved {self.actors_saved} actor transforms")
        return self.actors_saved
    
    def restore_all_transforms(self) -> tuple:
        """
        Restore every actor to its exact original transform.
        Uses stored values only - no recomputation.
        
        Returns:
            Tuple of (actors_restored, failures)
        """
        self.actors_restored = 0
        self.restore_failures = 0
        
        print(f"\n[TestCleanup] Restoring actors to original transforms...")
        
        # Restore time/lighting first
        if self.time_controller:
            try:
                self.time_controller.reset()
                self.actors_restored += 1
            except Exception as e:
                print(f"[TestCleanup] ERROR restoring lighting: {e}")
                self.restore_failures += 1
        
        # Restore weather
        if self.weather_controller:
            try:
                self.weather_controller.reset()
                self.actors_restored += 1
            except Exception as e:
                print(f"[TestCleanup] ERROR restoring weather: {e}")
                self.restore_failures += 1
        
        # Restore props via prop_controller.reset_all()
        try:
            self.prop_controller.reset_all()
            self.actors_restored += len(self.saved_prop_transforms)
        except Exception as e:
            print(f"[TestCleanup] ERROR restoring props: {e}")
            self.restore_failures += len(self.saved_prop_transforms)
        
        # Restore vehicles via spawner.reset_all()
        try:
            self.spawner.reset_all()
            self.actors_restored += len(self.saved_vehicle_transforms)
        except Exception as e:
            print(f"[TestCleanup] ERROR restoring vehicles: {e}")
            self.restore_failures += len(self.saved_vehicle_transforms)
        
        print(f"[TestCleanup] Restored {self.actors_restored} actors, {self.restore_failures} failures")
        return (self.actors_restored, self.restore_failures)


# =============================================================================
# LOCATION FILTERING HELPERS
# =============================================================================

def filter_anchor_config_by_location(spawner, location: int) -> Dict:
    """Filter anchor config to only zones within a specific location's Y boundaries.
    
    This fetches actor positions from UE5 since the YAML only stores actor names.
    """
    if not spawner.anchor_config or location not in LOCATION_BOUNDARIES:
        return spawner.anchor_config
    
    y_min, y_max = LOCATION_BOUNDARIES[location]
    filtered_config = {}
    
    # Filter parking anchors (list of dicts with name/position/yaw or old format strings)
    if 'parking' in spawner.anchor_config:
        parking_section = spawner.anchor_config['parking'].copy()
        anchors = parking_section.get('anchors', [])
        
        filtered_parking = []
        for anchor in anchors:
            # Handle both new format (dict) and old format (string)
            if isinstance(anchor, dict):
                anchor_name = anchor.get('name')
                # Use position from YAML if available
                if 'position' in anchor:
                    y_pos = anchor['position'][1]  # Y is second element
                    if y_min <= y_pos < y_max:
                        filtered_parking.append(anchor)
                else:
                    # Fallback to fetching from UE5
                    transform = spawner._get_anchor_transform(anchor_name)
                    if transform:
                        y_pos = transform['location'].get('Y', 0)
                        if y_min <= y_pos < y_max:
                            filtered_parking.append(anchor)
            else:
                # Old format: anchor is just a string name
                transform = spawner._get_anchor_transform(anchor)
                if transform:
                    y_pos = transform['location'].get('Y', 0)
                    if y_min <= y_pos < y_max:
                        filtered_parking.append(anchor)
        
        parking_section['anchors'] = filtered_parking
        filtered_config['parking'] = parking_section
    
    # Filter lanes (list of dicts with start/end anchor names)
    if 'lanes' in spawner.anchor_config:
        lanes_section = spawner.anchor_config['lanes'].copy()
        lane_defs = lanes_section.get('definitions', [])
        
        filtered_lanes = []
        for lane in lane_defs:
            # Use YAML position if available, otherwise query UE5
            if 'start_position' in lane:
                y_pos = lane['start_position'][1]  # Y is second element
                if y_min <= y_pos < y_max:
                    filtered_lanes.append(lane)
            else:
                # Fallback to UE5 query
                start_name = lane.get('start_anchor') or lane.get('start')
                if start_name:
                    transform = spawner._get_anchor_transform(start_name)
                    if transform:
                        y_pos = transform['location'].get('Y', 0)
                        if y_min <= y_pos < y_max:
                            filtered_lanes.append(lane)
        
        lanes_section['definitions'] = filtered_lanes
        filtered_config['lanes'] = lanes_section
    
    # Filter sidewalks (both singular 'sidewalk' and plural 'sidewalks')
    # Handle new format (sidewalks with definitions list)
    if 'sidewalks' in spawner.anchor_config:
        sidewalks_section = spawner.anchor_config['sidewalks'].copy()
        sidewalk_defs = sidewalks_section.get('definitions', [])
        
        filtered_sidewalks = []
        for sidewalk in sidewalk_defs:
            # Use YAML position if available, otherwise query UE5
            if 'position_1' in sidewalk:
                y_pos = sidewalk['position_1'][1]  # Y is second element
                if y_min <= y_pos < y_max:
                    filtered_sidewalks.append(sidewalk)
            else:
                # Fallback to UE5 query
                anchor_1_name = sidewalk.get('anchor_1')
                if anchor_1_name:
                    transform = spawner._get_anchor_transform(anchor_1_name)
                    if transform:
                        y_pos = transform['location'].get('Y', 0)
                        if y_min <= y_pos < y_max:
                            filtered_sidewalks.append(sidewalk)
        
        sidewalks_section['definitions'] = filtered_sidewalks
        filtered_config['sidewalks'] = sidewalks_section
    
    # Handle old format (singular sidewalk with anchor_1/anchor_2)
    elif 'sidewalk' in spawner.anchor_config:
        sidewalk_section = spawner.anchor_config['sidewalk']
        anchor_1_name = sidewalk_section.get('anchor_1')
        
        if anchor_1_name:
            transform = spawner._get_anchor_transform(anchor_1_name)
            if transform:
                y_pos = transform['location'].get('Y', 0)
                if y_min <= y_pos < y_max:
                    filtered_config['sidewalk'] = sidewalk_section
    
    return filtered_config


def filter_zones_by_location(zones: Dict[str, List], location: int) -> Dict[str, List]:
    """Filter zones to only those within a specific location's Y boundaries."""
    if location not in LOCATION_BOUNDARIES:
        print(f"WARNING: Invalid location {location}, using all zones")
        return zones
    
    y_min, y_max = LOCATION_BOUNDARIES[location]
    filtered = {}
    
    for zone_type, zone_list in zones.items():
        filtered[zone_type] = []
        for zone in zone_list:
            # Extract Y position from zone
            if hasattr(zone, 'position'):
                y_pos = zone.position[1]
            elif isinstance(zone, dict) and 'position' in zone:
                y_pos = zone['position'][1]
            else:
                continue
            
            # Check if in location bounds
            if y_min <= y_pos < y_max:
                filtered[zone_type].append(zone)
    
    return filtered


def filter_anchors_by_location(anchors: Dict[str, List], location: int) -> Dict[str, List]:
    """Filter prop anchors to only those within a specific location's Y boundaries."""
    if location not in LOCATION_BOUNDARIES:
        print(f"WARNING: Invalid location {location}, using all anchors")
        return anchors
    
    y_min, y_max = LOCATION_BOUNDARIES[location]
    filtered = {}
    
    total_before = 0
    total_after = 0
    
    for anchor_type, anchor_list in anchors.items():
        filtered[anchor_type] = []
        total_before += len(anchor_list)
        
        for anchor in anchor_list:
            # AnchorInfo.location is a dict with X, Y, Z keys
            y_pos = anchor.location.get("Y", 0)
            
            # Check if in location bounds
            if y_min <= y_pos < y_max:
                filtered[anchor_type].append(anchor)
                total_after += 1
    
    print(f"  Prop anchors filtered: {total_before} total → {total_after} in location {location} (Y ∈ [{y_min}, {y_max}))")
    
    return filtered


# =============================================================================
# CAMERA BOUNDARY DETECTION
# =============================================================================

def get_camera_spawn_bounds(host="127.0.0.1", port=30010,
                            level_path="/Game/automobileV2.automobileV2",
                            actor="DataCapture_2"):
    """
    Query the 4 boundary cubes on the DataCapture actor.
    Returns (x_min, x_max, y_min, y_max) in world-space cm,
    or None if detection fails.
    
    The DataCapture actor has 4 static meshes (Cube, Cube1, Cube2, Cube3)
    whose positions define the region where vehicles should spawn.
    """
    import requests
    base_url = f"http://{host}:{port}/remote"
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    path = f"{level_path}:PersistentLevel.{actor}"
    
    # Get all StaticMeshComponents
    try:
        r = s.put(f"{base_url}/object/call", json={
            "objectPath": path,
            "functionName": "GetComponentsByClass",
            "parameters": {"ComponentClass": "/Script/Engine.StaticMeshComponent"}
        }, timeout=5)
        if r.status_code != 200:
            print(f"  [WARN] Failed to query {actor} components")
            return None
    except Exception as e:
        print(f"  [WARN] Could not reach UE5: {e}")
        return None
    
    comps = r.json().get("ReturnValue", [])
    
    # Collect world positions of boundary cubes (skip StaticMeshComponent_0 = root mesh)
    cube_positions = []
    for c in comps:
        name = c.split(".")[-1] if "." in c else c
        if not name.startswith("Cube"):
            continue
        try:
            lr = s.put(f"{base_url}/object/call", json={
                "objectPath": c,
                "functionName": "K2_GetComponentLocation"
            }, timeout=3)
            if lr.status_code == 200:
                loc = lr.json().get("ReturnValue", {})
                cube_positions.append({
                    "name": name,
                    "X": loc.get("X", 0),
                    "Y": loc.get("Y", 0),
                })
        except:
            continue
    
    if len(cube_positions) < 2:
        print(f"  [WARN] Only found {len(cube_positions)} boundary cubes on {actor}")
        return None
    
    xs = [p["X"] for p in cube_positions]
    ys = [p["Y"] for p in cube_positions]
    bounds = (min(xs), max(xs), min(ys), max(ys))
    
    print(f"  Camera spawn bounds: X=[{bounds[0]:.0f}, {bounds[1]:.0f}], "
          f"Y=[{bounds[2]:.0f}, {bounds[3]:.0f}]")
    for p in cube_positions:
        print(f"    {p['name']}: X={p['X']:.0f}, Y={p['Y']:.0f}")
    
    return bounds


def set_camera_bounds_visibility(visible: bool, host="127.0.0.1", port=30010,
                                  level_path="/Game/automobileV2.automobileV2",
                                  actor="DataCapture_2"):
    """Show or hide the boundary cubes on DataCapture_2."""
    import requests
    base_url = f"http://{host}:{port}/remote"
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    path = f"{level_path}:PersistentLevel.{actor}"

    try:
        r = s.put(f"{base_url}/object/call", json={
            "objectPath": path,
            "functionName": "GetComponentsByClass",
            "parameters": {"ComponentClass": "/Script/Engine.StaticMeshComponent"}
        }, timeout=5)
        if r.status_code != 200:
            return
    except Exception:
        return

    for c in r.json().get("ReturnValue", []):
        name = c.split(".")[-1] if "." in c else c
        if not name.startswith("Cube"):
            continue
        try:
            s.put(f"{base_url}/object/call", json={
                "objectPath": c,
                "functionName": "SetVisibility",
                "parameters": {"bNewVisibility": visible, "bPropagateToChildren": False}
            }, timeout=3)
        except Exception:
            pass

    state = "shown" if visible else "hidden"
    print(f"  Camera boundary cubes {state}")


def filter_vehicles_by_camera_bounds(spawned_vehicles, spawner, bounds):
    """
    DEPRECATED — replaced by filter_anchor_config_by_camera_bounds.
    Kept as safety net only.
    """
    x_min, x_max, y_min, y_max = bounds
    kept = []
    hidden = 0

    for v in spawned_vehicles:
        loc = v.spawn_location
        vx = loc.get("X", 0)
        vy = loc.get("Y", 0)

        if x_min <= vx <= x_max and y_min <= vy <= y_max:
            kept.append(v)
        else:
            spawner._set_actor_hidden(v.name, True)
            print(f"    [BOUNDS HIDE] {v.name}: X={vx:.0f}, Y={vy:.0f} outside camera bounds")
            hidden += 1

    if hidden > 0:
        print(f"  Camera bounds filter: {len(kept)} kept, {hidden} hidden")

    return kept


def compute_lane_end_cameras(spawner, dashcam_height=150.0, dashcam_fov=90.0,
                              dashcam_pitch=-3.0):
    """
    Build a list of camera placements — one per lane endpoint.
    
    For each lane, uses the vehicle_yaw to determine which endpoint is
    "behind" (where a dashcam driver would enter the lane). The camera
    is placed at that endpoint, looking along the lane.
    
    Returns:
        List of (CameraPlacement, lane_id, yaw) tuples
    """
    from vantagecv.research_v2.smart_camera_capture_controller import CameraPlacement
    
    lanes = spawner._get_lane_definitions()
    if not lanes:
        print("  [WARN] No lanes for camera positions")
        return []
    
    cameras = []
    for lane in lanes:
        yaw = lane.get('vehicle_yaw')
        if yaw is None:
            # Fallback: compute yaw from start→end direction
            if 'start_position' in lane and 'end_position' in lane:
                dx = lane['end_position'][0] - lane['start_position'][0]
                dy = lane['end_position'][1] - lane['start_position'][1]
                yaw = math.degrees(math.atan2(dy, dx))
            else:
                continue
        
        fx = math.cos(math.radians(yaw))
        fy = math.sin(math.radians(yaw))
        
        # Get both endpoints
        if 'start_position' not in lane or 'end_position' not in lane:
            continue
        sp = lane['start_position']
        ep = lane['end_position']
        
        # "Behind" endpoint = the one with lower dot product along forward
        # (farther back in the direction the camera faces)
        start_dot = sp[0] * fx + sp[1] * fy
        end_dot = ep[0] * fx + ep[1] * fy
        
        if start_dot <= end_dot:
            cam_pos = sp  # Start is farther back → camera goes here
        else:
            cam_pos = ep  # End is farther back → camera goes here
        
        placement = CameraPlacement(
            location={"X": cam_pos[0], "Y": cam_pos[1], "Z": cam_pos[2] + dashcam_height},
            rotation={"Pitch": dashcam_pitch, "Yaw": yaw, "Roll": 0.0},
            fov=dashcam_fov,
            target_centroid={
                "X": cam_pos[0] + fx * 2000,
                "Y": cam_pos[1] + fy * 2000,
                "Z": cam_pos[2] + dashcam_height,
            },
        )
        
        lane_id = lane.get('id', '?')
        print(f"    {lane_id}: pos=({cam_pos[0]:.0f}, {cam_pos[1]:.0f}), yaw={yaw:.0f}°")
        cameras.append((placement, lane_id, yaw))
    
    print(f"  Total camera positions: {len(cameras)}")
    return cameras


def _segment_overlaps_box(sx, sy, ex, ey, x_min, x_max, y_min, y_max):
    """Check if a line segment (sx,sy)→(ex,ey) overlaps an AABB."""
    seg_x_min, seg_x_max = min(sx, ex), max(sx, ex)
    seg_y_min, seg_y_max = min(sy, ey), max(sy, ey)
    return (seg_x_max >= x_min and seg_x_min <= x_max and
            seg_y_max >= y_min and seg_y_min <= y_max)


def _clamp_segment_to_box(sx, sy, sz, ex, ey, ez, x_min, x_max, y_min, y_max):
    """Clamp a 3D line segment so both endpoints are within an AABB (X/Y only).
    
    Uses parametric clipping: finds the t-range [t0, t1] where the segment
    is inside the box, then returns the clamped start/end positions.
    Returns None if the segment doesn't intersect the box at all.
    """
    dx = ex - sx
    dy = ey - sy
    dz = ez - sz
    
    t0, t1 = 0.0, 1.0
    
    for p, d, lo, hi in [(sx, dx, x_min, x_max), (sy, dy, y_min, y_max)]:
        if abs(d) < 1e-6:
            # Segment is parallel to this axis
            if p < lo or p > hi:
                return None  # Entirely outside
        else:
            t_enter = (lo - p) / d
            t_exit = (hi - p) / d
            if t_enter > t_exit:
                t_enter, t_exit = t_exit, t_enter
            t0 = max(t0, t_enter)
            t1 = min(t1, t_exit)
            if t0 > t1:
                return None  # No overlap
    
    # Compute clamped endpoints
    new_sx = sx + t0 * dx
    new_sy = sy + t0 * dy
    new_sz = sz + t0 * dz
    new_ex = sx + t1 * dx
    new_ey = sy + t1 * dy
    new_ez = sz + t1 * dz
    
    return ([new_sx, new_sy, new_sz], [new_ex, new_ey, new_ez])


def filter_anchor_config_by_camera_bounds(spawner, bounds):
    """Filter anchor config to only zones within the camera boundary cubes.
    
    This ensures vehicles can ONLY spawn inside the camera bounds,
    rather than spawning anywhere and getting filtered afterwards.
    
    Args:
        spawner: VehicleSpawnController with anchor_config loaded
        bounds: (x_min, x_max, y_min, y_max) from get_camera_spawn_bounds
    
    Returns:
        Filtered anchor config dict (also sets spawner.anchor_config)
    """
    if not spawner.anchor_config or not bounds:
        return spawner.anchor_config
    
    x_min, x_max, y_min, y_max = bounds
    filtered_config = {}
    
    # ---------- Parking anchors ----------
    if 'parking' in spawner.anchor_config:
        parking_section = spawner.anchor_config['parking'].copy()
        anchors = parking_section.get('anchors', [])
        
        original = len(anchors)
        filtered_parking = []
        for anchor in anchors:
            if isinstance(anchor, dict):
                if 'position' in anchor:
                    ax, ay = anchor['position'][0], anchor['position'][1]
                    if x_min <= ax <= x_max and y_min <= ay <= y_max:
                        filtered_parking.append(anchor)
                else:
                    transform = spawner._get_anchor_transform(anchor.get('name'))
                    if transform:
                        ax = transform['location'].get('X', 0)
                        ay = transform['location'].get('Y', 0)
                        if x_min <= ax <= x_max and y_min <= ay <= y_max:
                            filtered_parking.append(anchor)
            else:
                transform = spawner._get_anchor_transform(anchor)
                if transform:
                    ax = transform['location'].get('X', 0)
                    ay = transform['location'].get('Y', 0)
                    if x_min <= ax <= x_max and y_min <= ay <= y_max:
                        filtered_parking.append(anchor)
        
        parking_section['anchors'] = filtered_parking
        filtered_config['parking'] = parking_section
        print(f"  Parking: {original} → {len(filtered_parking)} within camera bounds")
    
    # ---------- Lanes (clamp endpoints to bounds) ----------
    if 'lanes' in spawner.anchor_config:
        lanes_section = spawner.anchor_config['lanes'].copy()
        lane_defs = lanes_section.get('definitions', [])
        
        original = len(lane_defs)
        filtered_lanes = []
        for lane in lane_defs:
            if 'start_position' in lane and 'end_position' in lane:
                sp = lane['start_position']
                ep = lane['end_position']
                clamped = _clamp_segment_to_box(
                    sp[0], sp[1], sp[2], ep[0], ep[1], ep[2],
                    x_min, x_max, y_min, y_max
                )
                if clamped:
                    new_lane = dict(lane)
                    new_lane['start_position'] = list(clamped[0])
                    new_lane['end_position'] = list(clamped[1])
                    filtered_lanes.append(new_lane)
                    print(f"    {lane.get('id','?')}: "
                          f"({sp[0]:.0f},{sp[1]:.0f})→({ep[0]:.0f},{ep[1]:.0f}) "
                          f"clamped to ({clamped[0][0]:.0f},{clamped[0][1]:.0f})→"
                          f"({clamped[1][0]:.0f},{clamped[1][1]:.0f})")
            elif 'start_position' in lane:
                sx, sy = lane['start_position'][0], lane['start_position'][1]
                if x_min <= sx <= x_max and y_min <= sy <= y_max:
                    filtered_lanes.append(lane)
            else:
                start_name = lane.get('start_anchor') or lane.get('start')
                if start_name:
                    transform = spawner._get_anchor_transform(start_name)
                    if transform:
                        sx = transform['location'].get('X', 0)
                        sy = transform['location'].get('Y', 0)
                        if x_min <= sx <= x_max and y_min <= sy <= y_max:
                            filtered_lanes.append(lane)
        
        lanes_section['definitions'] = filtered_lanes
        filtered_config['lanes'] = lanes_section
        print(f"  Lanes: {original} → {len(filtered_lanes)} within camera bounds")
    
    # ---------- Sidewalks (clamp to bounds) ----------
    if 'sidewalks' in spawner.anchor_config:
        sidewalks_section = spawner.anchor_config['sidewalks'].copy()
        sidewalk_defs = sidewalks_section.get('definitions', [])
        
        original = len(sidewalk_defs)
        filtered_sidewalks = []
        for sw in sidewalk_defs:
            if 'position_1' in sw and 'position_2' in sw:
                p1 = sw['position_1']
                p2 = sw['position_2']
                clamped = _clamp_segment_to_box(
                    p1[0], p1[1], p1[2], p2[0], p2[1], p2[2],
                    x_min, x_max, y_min, y_max
                )
                if clamped:
                    new_sw = dict(sw)
                    new_sw['position_1'] = list(clamped[0])
                    new_sw['position_2'] = list(clamped[1])
                    filtered_sidewalks.append(new_sw)
                    print(f"    {sw.get('id','?')}: "
                          f"({p1[0]:.0f},{p1[1]:.0f})→({p2[0]:.0f},{p2[1]:.0f}) "
                          f"clamped to ({clamped[0][0]:.0f},{clamped[0][1]:.0f})→"
                          f"({clamped[1][0]:.0f},{clamped[1][1]:.0f})")
            elif 'position_1' in sw:
                sx, sy = sw['position_1'][0], sw['position_1'][1]
                if x_min <= sx <= x_max and y_min <= sy <= y_max:
                    filtered_sidewalks.append(sw)
            else:
                anchor_name = sw.get('anchor_1')
                if anchor_name:
                    transform = spawner._get_anchor_transform(anchor_name)
                    if transform:
                        sx = transform['location'].get('X', 0)
                        sy = transform['location'].get('Y', 0)
                        if x_min <= sx <= x_max and y_min <= sy <= y_max:
                            filtered_sidewalks.append(sw)
        
        sidewalks_section['definitions'] = filtered_sidewalks
        filtered_config['sidewalks'] = sidewalks_section
        print(f"  Sidewalks: {original} → {len(filtered_sidewalks)} within camera bounds")
    
    # ---------- Sidewalk (singular, old format) ----------
    elif 'sidewalk' in spawner.anchor_config:
        sw = spawner.anchor_config['sidewalk']
        anchor_name = sw.get('anchor_1')
        if anchor_name:
            transform = spawner._get_anchor_transform(anchor_name)
            if transform:
                sx = transform['location'].get('X', 0)
                sy = transform['location'].get('Y', 0)
                if x_min <= sx <= x_max and y_min <= sy <= y_max:
                    filtered_config['sidewalk'] = sw
    
    # Apply to spawner
    spawner.anchor_config = filtered_config
    return filtered_config


# =============================================================================
# VEHICLE SPAWNING WITH ZONE CONSTRAINTS
# =============================================================================

# Total vehicles per picture
MIN_VEHICLES_PER_FRAME = 1
MAX_VEHICLES_PER_FRAME = 2


def spawn_vehicles_with_constraints(
    spawner: VehicleSpawnController,
    seed: int,
    vehicle_count: int,
    parking_ratio: float,
    stats: SpawnStats
) -> List:
    """
    Spawn 1–5 vehicles total per picture.
    
    Each vehicle slot randomly picks a category (equal 20% chance per
    category).  The vehicle is then placed in a zone allowed for that
    category.
    
    Zone constraints:
    - Bikes: Sidewalks only
    - Motorcycles: Parking slots only
    - Buses: Road lanes only (max 1 bus per lane)
    - Cars: Parking slots OR road lanes
    - Trucks: Parking slots OR road lanes
    
    Args:
        spawner: Vehicle spawn controller
        seed: Random seed
        vehicle_count: Ignored; total is random 1–5
        parking_ratio: For cats that support both parking + lane, ratio that
                       go to parking vs lane
        stats: Statistics tracker
    
    Returns:
        List of spawned vehicle instances
    """
    import random
    random.seed(seed)
    
    all_spawned = []
    
    # Check which zones are available
    parking_anchors = spawner._get_parking_anchors() if spawner.anchor_config else []
    lane_defs = spawner._get_lane_definitions() if spawner.anchor_config else []
    sidewalk_bounds = spawner._get_sidewalk_bounds() if spawner.anchor_config else None
    
    has_parking = len(parking_anchors) > 0
    has_lanes = len(lane_defs) > 0
    has_sidewalk = sidewalk_bounds is not None
    
    # ------------------------------------------------------------------
    # Pick total count (1–5), then assign each slot a random category
    # ------------------------------------------------------------------
    total_count = random.randint(MIN_VEHICLES_PER_FRAME, MAX_VEHICLES_PER_FRAME)
    
    # Build list of spawnable categories (those with at least one available zone)
    spawnable_cats = []
    for cat in ALL_VEHICLE_CATEGORIES:
        allowed_zones = VEHICLE_ZONE_CONSTRAINTS.get(cat, [])
        has_any_zone = (
            ("parking" in allowed_zones and has_parking) or
            ("lane" in allowed_zones and has_lanes) or
            ("sidewalk" in allowed_zones and has_sidewalk)
        )
        if has_any_zone:
            spawnable_cats.append(cat)
        else:
            stats.log_skip_no_zone(cat)
    
    if not spawnable_cats:
        print("    [SKIP] No spawnable categories (no zones available)")
        return all_spawned
    
    # Assign each vehicle slot a random category (equal probability)
    category_counts: Dict[str, int] = {cat: 0 for cat in spawnable_cats}
    for _ in range(total_count):
        chosen = random.choice(spawnable_cats)
        category_counts[chosen] += 1
    
    # Cap buses by number of available lanes
    if "bus" in category_counts and has_lanes:
        category_counts["bus"] = min(category_counts["bus"], len(lane_defs))
    
    print(f"    Total vehicles: {total_count}  →  {', '.join(f'{c}={n}' for c, n in category_counts.items() if n > 0)}")
    
    # ------------------------------------------------------------------
    # Dispatch each category to its allowed zone(s)
    # ------------------------------------------------------------------
    lane_spawned_bounds = []
    
    for cat in ALL_VEHICLE_CATEGORIES:
        cat_count = category_counts.get(cat, 0)
        if cat_count == 0:
            continue
        
        allowed_zones = VEHICLE_ZONE_CONSTRAINTS.get(cat, [])
        zone_options = [z for z in allowed_zones
                        if (z == "parking" and has_parking) or
                           (z == "lane" and has_lanes) or
                           (z == "sidewalk" and has_sidewalk)]
        
        parking_count = 0
        lane_count = 0
        sidewalk_count = 0
        
        if len(zone_options) == 1:
            zone = zone_options[0]
            if zone == "parking":
                parking_count = cat_count
            elif zone == "lane":
                lane_count = cat_count
            elif zone == "sidewalk":
                sidewalk_count = cat_count
        else:
            # Multiple zone options — split using parking_ratio
            for _ in range(cat_count):
                if "parking" in zone_options and "lane" in zone_options:
                    if random.random() < parking_ratio:
                        parking_count += 1
                    else:
                        lane_count += 1
                elif "parking" in zone_options and "sidewalk" in zone_options:
                    if random.random() < parking_ratio:
                        parking_count += 1
                    else:
                        sidewalk_count += 1
                else:
                    if "lane" in zone_options:
                        lane_count += 1
                    elif "sidewalk" in zone_options:
                        sidewalk_count += 1
        
        print(f"    [{cat}] {cat_count} (parking={parking_count}, lane={lane_count}, sidewalk={sidewalk_count})")
        
        # ---- Parking spawn for this category ----
        if parking_count > 0:
            stats.log_attempt(cat, f"{parking_count} parking")
            parking_result = spawner.spawn_parking(
                seed=seed + hash(cat) % 10000,
                count=parking_count,
                vehicle_types=[cat]
            )
            for v in parking_result.spawned_vehicles:
                stats.log_success(v.category, v.name, v.anchor_name)
                all_spawned.append(v)
        
        # ---- Lane spawn for this category ----
        if lane_count > 0:
            stats.log_attempt(cat, f"{lane_count} lane")
            lane_result = spawner.spawn_lane(
                seed=seed + hash(cat) % 10000 + 1000,
                count=lane_count,
                vehicle_types=[cat],
                existing_bounds=lane_spawned_bounds
            )
            for v in lane_result.spawned_vehicles:
                stats.log_success(v.category, v.name, v.anchor_name)
                all_spawned.append(v)
            lane_spawned_bounds = lane_result.spawned_bounds
        
        # ---- Sidewalk spawn for this category ----
        if sidewalk_count > 0:
            stats.log_attempt(cat, f"{sidewalk_count} sidewalk")
            sidewalk_result = spawner.spawn_sidewalk(
                seed=seed + hash(cat) % 10000 + 3000,
                count=sidewalk_count,
                vehicle_types=[cat]
            )
            for v in sidewalk_result.spawned_vehicles:
                stats.log_success(v.category, v.name, v.anchor_name)
                all_spawned.append(v)
    
    return all_spawned


def main():
    # =============================================================================
    # CONFIGURATION - Prompt user for location
    # =============================================================================
    print("\n" + "=" * 60)
    print("RANDOMIZATION TEST - 20 Captures")
    print("=" * 60)
    print("\nAvailable locations:")
    for loc_num in sorted(LOCATION_BOUNDARIES.keys()):
        y_min, y_max = LOCATION_BOUNDARIES[loc_num]
        print(f"  {loc_num}: Y ∈ [{y_min}, {y_max})")
    print("  0: Test all locations (no filter)")
    
    while True:
        try:
            user_input = input("\nSelect location to test (0-7): ").strip()
            location_choice = int(user_input)
            if location_choice == 0:
                TEST_LOCATION = None
                break
            elif location_choice in LOCATION_BOUNDARIES:
                TEST_LOCATION = location_choice
                break
            else:
                print(f"Invalid choice. Please enter 0-7.")
        except ValueError:
            print(f"Invalid input. Please enter a number 0-7.")
        except KeyboardInterrupt:
            print("\nTest cancelled.")
            return
    
    print("\n" + "=" * 60)
    if TEST_LOCATION:
        print(f"LOCATION FILTER: Testing Location {TEST_LOCATION} only")
    else:
        print("LOCATION FILTER: Testing all locations")
    print("=" * 60)
    print("\nInitializing controllers...")
    
    spawner = VehicleSpawnController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2"
    )
    
    prop_controller = PropZoneController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2"
    )
    
    time_controller = TimeAugmentationController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2"
    )
    
    weather_controller = WeatherAugmentationController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2"
    )
    
    # Detect prop anchors and prop pool once at startup
    print("\nDetecting prop anchors...")
    prop_controller.detect_anchors()
    print("\nDetecting prop pool...")
    prop_controller.detect_prop_pool()
    # Note: We use prop pool (existing actors), not asset discovery
    
    # Detect vehicle pool once at startup
    print("\nDetecting vehicle pool...")
    spawner.detect_vehicle_pool()
    
    # Apply location filter if specified
    if TEST_LOCATION:
        print(f"\nApplying location {TEST_LOCATION} filter...")
        
        # Count original vehicle anchors
        original_parking = len(spawner.anchor_config.get('parking', {}).get('anchors', [])) if spawner.anchor_config else 0
        original_lanes = len(spawner.anchor_config.get('lanes', {}).get('definitions', [])) if spawner.anchor_config else 0
        original_sidewalk = 1 if spawner.anchor_config and 'sidewalk' in spawner.anchor_config else 0
        
        # Filter vehicle anchor config (pass spawner object for UE5 queries)
        if spawner.anchor_config:
            spawner.anchor_config = filter_anchor_config_by_location(spawner, TEST_LOCATION)
        
        # Count filtered vehicle anchors
        filtered_parking = len(spawner.anchor_config.get('parking', {}).get('anchors', [])) if spawner.anchor_config else 0
        filtered_lanes = len(spawner.anchor_config.get('lanes', {}).get('definitions', [])) if spawner.anchor_config else 0
        filtered_sidewalk = 1 if spawner.anchor_config and 'sidewalk' in spawner.anchor_config else 0
        
        # Filter prop anchors
        original_anchors = {k: len(v) for k, v in prop_controller.detected_anchors.items()}
        prop_controller.detected_anchors = filter_anchors_by_location(prop_controller.detected_anchors, TEST_LOCATION)
        filtered_anchors = {k: len(v) for k, v in prop_controller.detected_anchors.items()}
        
        # SET STRICT LOCATION BOUNDARIES in prop controller
        y_min, y_max = LOCATION_BOUNDARIES[TEST_LOCATION]
        prop_controller.set_location_boundaries(y_min, y_max)
        
        print(f"  Vehicle anchors: parking {original_parking}→{filtered_parking}, lanes {original_lanes}→{filtered_lanes}, sidewalk {original_sidewalk}→{filtered_sidewalk}")
        print(f"  Prop anchors filtered: {sum(original_anchors.values())} → {sum(filtered_anchors.values())}")
    
    # Detect lighting actors for time augmentation
    print("\nDetecting lighting actors...")
    if not time_controller.detect_lighting_actors():
        print("WARNING: Time augmentation may be limited - some lighting actors not found")
    
    # Detect weather actors
    print("\nDetecting weather actors...")
    if not weather_controller.detect_weather_actors():
        print("WARNING: Weather augmentation may be limited - some weather actors not found")
    
    # Set location-specific rain actors
    if TEST_LOCATION:
        weather_controller.set_location(TEST_LOCATION)
    
    # Print detection summary
    print("\n" + "=" * 60)
    print("DETECTION SUMMARY")
    print("=" * 60)
    print("\nAnchors (spawn zones):")
    for anchor_type, anchors in prop_controller.detected_anchors.items():
        print(f"  {anchor_type.capitalize():12}: {len(anchors)} anchors")
    print(f"\nProp Pool (available props):")
    for prop_class, props in prop_controller.prop_pool.items():
        print(f"  {prop_class.capitalize():12}: {len(props)} props")
    print(f"\nLighting:")
    print(f"  DirectionalLight: {time_controller.directional_light or 'NOT FOUND'}")
    print(f"  SkyLight: {time_controller.sky_light or 'NOT FOUND'}")
    print(f"  Available times: {', '.join(time_controller.get_available_states())}")
    print(f"\nWeather:")
    print(f"  ExponentialHeightFog: {weather_controller.exponential_fog or 'NOT FOUND'}")
    print(f"  Rain System: {weather_controller.rain_system or 'NOT FOUND'}")
    print(f"  Available weather: {', '.join(weather_controller.get_available_states())}")
    
    # Detect camera spawn bounds from boundary cubes and pre-filter anchors
    print("\nDetecting camera spawn bounds...")
    camera_bounds = get_camera_spawn_bounds()
    if camera_bounds:
        print("\nFiltering spawn anchors to camera bounds...")
        filter_anchor_config_by_camera_bounds(spawner, camera_bounds)
        set_camera_bounds_visibility(False)
    else:
        print("WARNING: Could not detect camera spawn bounds - vehicles may spawn outside camera view")
    
    # Build camera positions from lane endpoints (one per lane)
    print("\nBuilding lane-end camera positions...")
    lane_cameras = compute_lane_end_cameras(spawner)
    if not lane_cameras:
        print("WARNING: No lane-end camera positions found — falling back to dashcam")
    
    # Print vehicle zone constraints
    print(f"\nVehicle Zone Constraints:")
    for cat, zones in VEHICLE_ZONE_CONSTRAINTS.items():
        print(f"  {cat:12}: {', '.join(zones)}")
    print("=" * 60)
    
    # Initialize cleanup handler and save all transforms BEFORE any spawning
    cleanup = TestCleanup(spawner, prop_controller, time_controller, weather_controller)
    cleanup.save_all_transforms()
    
    # Set baseline environment (noon, clear weather) for deterministic testing
    if not cleanup.reset_to_baseline():
        print("\nWARNING: Failed to set baseline environment - test may have inconsistent results")
    
    capture_controller = SmartCameraCaptureController(
        host="127.0.0.1",
        port=30010,
        level_path="/Game/automobileV2.automobileV2",
        data_capture_actor="DataCapture_2"
    )
    
    output_dir = Path("output/randomization_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    success = 0
    failed = 0
    
    # Global spawn statistics
    global_stats = SpawnStats()
    
    # Wrap entire test in try/finally for guaranteed cleanup
    try:
        import random
        base_seed = random.randint(0, 1000000)  # Random base seed for this run
        print(f"\nRun seed base: {base_seed}")
        
        for i in range(20):
            seed = base_seed + i
            
            # Vary parameters
            if i % 3 == 0:
                parking_ratio = 1.0  # All parking
                vehicle_count = 2
            elif i % 3 == 1:
                parking_ratio = 0.0  # All lanes
                vehicle_count = 2
            else:
                parking_ratio = 0.5  # Mixed
                vehicle_count = 2
            
            output_path = output_dir / f"frame_{i:03d}.png"
            
            print(f"\n[{i+1}/20] Seed={seed}, Vehicles={vehicle_count}, Parking={parking_ratio:.0%}")
            
            # Per-iteration stats
            iter_stats = SpawnStats()
            
            try:
                # Step 1: Time augmentation (before any spawning)
                # Exclude night/dawn/sunset — too dark without exposure compensation
                time_result = time_controller.randomize(
                    seed=seed,
                    allowed_states=["morning", "noon", "afternoon"]
                )
                if not time_result.success:
                    print(f"  ✗ Time augmentation failed: {time_result.failure_reason}")
                    failed += 1
                    continue
                print(f"  Time: {time_result.time_state}")
                
                # Step 2: Weather augmentation
                weather_result = weather_controller.randomize(seed=seed)
                if not weather_result.success:
                    print(f"  ✗ Weather augmentation failed: {weather_result.failure_reason}")
                    failed += 1
                    continue
                print(f"  Weather: {weather_result.weather_state}")
                
                # Step 3: Hide all vehicles and spawn with zone constraints
                spawner.hide_all_vehicles()
                
                spawned_vehicles = spawn_vehicles_with_constraints(
                    spawner=spawner,
                    seed=seed,
                    vehicle_count=vehicle_count,
                    parking_ratio=parking_ratio,
                    stats=iter_stats
                )
                
                # Merge iteration stats into global
                for cat in ALL_VEHICLE_CATEGORIES:
                    global_stats.attempts[cat] += iter_stats.attempts[cat]
                    global_stats.successes[cat] += iter_stats.successes[cat]
                    global_stats.skipped_no_zone[cat] += iter_stats.skipped_no_zone[cat]
                    global_stats.skipped_constraint[cat] += iter_stats.skipped_constraint[cat]
                global_stats.collision_removed += iter_stats.collision_removed
                
                print(f"  Vehicles spawned: {len(spawned_vehicles)}")
                
                # Step 3b: Safety-net — hide any vehicle that landed outside bounds
                if camera_bounds and spawned_vehicles:
                    spawned_vehicles = filter_vehicles_by_camera_bounds(
                        spawned_vehicles, spawner, camera_bounds
                    )
                
                if not spawned_vehicles:
                    print(f"  ✗ No vehicles spawned (or all outside bounds)")
                    failed += 1
                    continue
                
                # Step 4: Camera placement — cycle through lane endpoints
                camera_placement = None
                if lane_cameras:
                    cam_idx = i % len(lane_cameras)
                    camera_placement, cam_lane_id, cam_yaw = lane_cameras[cam_idx]
                    print(f"  Camera: {cam_lane_id} ({cam_idx+1}/{len(lane_cameras)}), "
                          f"pos=({camera_placement.location['X']:.0f}, "
                          f"{camera_placement.location['Y']:.0f}), "
                          f"yaw={camera_placement.rotation['Yaw']:.0f}°")
                    
                    # Apply dashcam spatial filter using this camera position
                    yaw_rad = math.radians(cam_yaw)
                    fx = math.cos(yaw_rad)
                    fy = math.sin(yaw_rad)
                    dashcam = DashcamPlacement(
                        location=camera_placement.location,
                        rotation=camera_placement.rotation,
                        fov=camera_placement.fov,
                        lane_id=cam_lane_id,
                        lane_forward=(fx, fy),
                        lane_right=(math.sin(yaw_rad), -math.cos(yaw_rad)),
                        lane_width_cm=400.0,
                    )
                    filter_result = filter_vehicles_for_dashcam(
                        dashcam, spawned_vehicles, spawner
                    )
                    
                    if not filter_result.kept_vehicles:
                        print(f"  ✗ All vehicles filtered out by dashcam rules")
                        failed += 1
                        continue
                else:
                    print("  [WARN] No lane cameras — falling back to orbit camera")
                
                # Step 5: Spawn props with same seed
                prop_result = prop_controller.spawn_all(seed=seed, spawn_chance=0.2)
                print(f"  Props spawned: {len(prop_result.spawned_props)}")
                
                # Step 6: Let UE5 settle before capture
                # Scene changes (vehicle teleports, lighting, weather) need time to render
                time.sleep(0.3)
                
                # Step 7: Capture (dashcam override or default orbit)
                result = capture_controller.capture(
                    output_path=str(output_path),
                    seed=seed,
                    width=1920,
                    height=1080,
                    validate_scene=False,  # Skip for speed
                    camera_override=camera_placement
                )
                
                if result.status.value == "SUCCESS":
                    print(f"  [OK] Captured")
                    success += 1
                else:
                    print(f"  [FAIL] {result.status.value}")
                    failed += 1
            
            except Exception as e:
                import traceback
                print(f"  [ERROR] {e}")
                traceback.print_exc()
                failed += 1
            
            finally:
                # Per-iteration cleanup
                spawner.reset_all()
                prop_controller.reset_all()
            
            # Brief pause to allow video recording
            time.sleep(0.1)
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        print(f"  Success: {success}/20")
        print(f"  Failed:  {failed}/20")
        print(f"  Output:  {output_dir}")
        
        # Print global spawn statistics
        global_stats.print_summary()
    
    finally:
        # GUARANTEED CLEANUP: Restore all actors to original transforms
        # This runs even if test aborts early (Ctrl+C, exception, etc.)
        print("\n" + "=" * 60)
        print("FINAL CLEANUP - RESTORING LEVEL STATE")
        print("=" * 60)
        restored, failures = cleanup.restore_all_transforms()
        if failures > 0:
            print(f"\n[WARNING] {failures} actors failed to restore")
        else:
            print(f"\n[OK] Level restored to pre-test state ({restored} actors)")
        print("=" * 60)
        set_camera_bounds_visibility(True)

if __name__ == "__main__":
    main()
