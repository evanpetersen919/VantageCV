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
            
            # Disable rain
            if self.weather_controller.rain_system:
                rain_path = f"{self.weather_controller.level_path}:PersistentLevel.{self.weather_controller.rain_system}"
                if self.weather_controller._call_remote(rain_path, "SetActorHiddenInGame", {"bNewHidden": True}):
                    print("    [OK] Rain disabled")
                else:
                    print("    [FAIL] Could not disable rain")
            
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
# VEHICLE SPAWNING WITH ZONE CONSTRAINTS
# =============================================================================

def spawn_vehicles_with_constraints(
    spawner: VehicleSpawnController,
    seed: int,
    vehicle_count: int,
    parking_ratio: float,
    stats: SpawnStats
) -> List:
    """
    Spawn vehicles respecting zone constraints.
    
    Constraints:
    - Bikes: Parking slots OR sidewalks (sidewalks not implemented yet)
    - Motorcycles: Parking slots only
    - Buses: Road lanes only (max 1 bus per lane)
    - Cars: Parking slots OR road lanes
    - Trucks: Parking slots OR road lanes
    
    Args:
        spawner: Vehicle spawn controller
        seed: Random seed
        vehicle_count: Target number of vehicles
        parking_ratio: Ratio of parking vs lane placements
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
    
    # Determine vehicle types for parking, lanes, and sidewalks based on constraints
    parking_vehicle_types = []
    lane_vehicle_types = []
    sidewalk_vehicle_types = []
    
    for cat in ALL_VEHICLE_CATEGORIES:
        allowed_zones = VEHICLE_ZONE_CONSTRAINTS.get(cat, [])
        
        # Check if ANY allowed zone is available
        has_any_zone = (
            ("parking" in allowed_zones and has_parking) or
            ("lane" in allowed_zones and has_lanes) or
            ("sidewalk" in allowed_zones and has_sidewalk)
        )
        
        if not has_any_zone:
            # No valid zones for this category - skip it
            stats.log_skip_no_zone(cat)
            continue
        
        # Add to appropriate zone lists
        if "parking" in allowed_zones and has_parking:
            parking_vehicle_types.append(cat)
        
        if "lane" in allowed_zones and has_lanes:
            lane_vehicle_types.append(cat)
        
        if "sidewalk" in allowed_zones and has_sidewalk:
            sidewalk_vehicle_types.append(cat)
    
    # Decide how many go to parking vs lanes
    parking_count = sum(1 for _ in range(vehicle_count) if random.random() < parking_ratio)
    lane_count = vehicle_count - parking_count
    
    # Spawn parking vehicles (motorcycles, cars, trucks)
    if parking_count > 0 and parking_vehicle_types:
        stats.log_attempt("parking", f"{parking_count} vehicles")
        parking_result = spawner.spawn_parking(
            seed=seed,
            count=parking_count,
            vehicle_types=parking_vehicle_types
        )
        for v in parking_result.spawned_vehicles:
            stats.log_success(v.category, v.name, v.anchor_name)
            all_spawned.append(v)
    elif parking_count > 0:
        print(f"    [SKIP] No valid vehicle types for parking")
    
    # Spawn lane vehicles (buses, cars, trucks)
    # CONSTRAINT: Max 1 bus per lane
    if lane_count > 0 and lane_vehicle_types:
        stats.log_attempt("lane", f"{lane_count} vehicles")
        
        # If buses are allowed, limit to max 1 per lane
        if "bus" in lane_vehicle_types:
            max_buses = len(lane_defs)  # One bus per lane maximum
            
            # Spawn buses first (limited to number of lanes)
            bus_count = min(
                sum(1 for _ in range(lane_count) if random.random() < 0.3),  # 30% chance for bus
                max_buses  # But never more than number of lanes
            )
            
            # Track bounds across multiple spawn calls for collision detection
            lane_spawned_bounds = []
            
            if bus_count > 0:
                bus_result = spawner.spawn_lane(
                    seed=seed + 1000,
                    count=bus_count,
                    vehicle_types=["bus"]
                )
                for v in bus_result.spawned_vehicles:
                    stats.log_success(v.category, v.name, v.anchor_name)
                    all_spawned.append(v)
                
                # Collect bounds from spawned buses for next spawn call
                lane_spawned_bounds = bus_result.spawned_bounds
                
                # Reduce lane_count for remaining vehicles
                lane_count -= bus_count
            
            # Remove bus from available types for remaining vehicles
            lane_vehicle_types_remaining = [t for t in lane_vehicle_types if t != "bus"]
        else:
            lane_vehicle_types_remaining = lane_vehicle_types
            lane_spawned_bounds = []
        
        # Spawn remaining lane vehicles (cars, trucks)
        # Pass existing bounds so they don't spawn inside buses!
        if lane_count > 0 and lane_vehicle_types_remaining:
            other_result = spawner.spawn_lane(
                seed=seed + 2000,
                count=lane_count,
                vehicle_types=lane_vehicle_types_remaining,
                existing_bounds=lane_spawned_bounds  # Pass bus bounds!
            )
            for v in other_result.spawned_vehicles:
                stats.log_success(v.category, v.name, v.anchor_name)
                all_spawned.append(v)
    elif lane_count > 0:
        print(f"    [SKIP] No valid vehicle types for lanes")
    
    # Spawn sidewalk vehicles (bicycles)
    # Uses anchor-based bounds (2 corner anchors define sidewalk region)
    # Bicycles spawn at random positions within anchor-defined bounds with collision avoidance
    if has_sidewalk and sidewalk_vehicle_types:
        # 50% chance to spawn bicycles on sidewalk
        if random.random() < 0.5:
            sidewalk_count = random.randint(1, 2)  # 1-2 bicycles per sidewalk
            stats.log_attempt("sidewalk", f"{sidewalk_count} vehicles")
            
            sidewalk_result = spawner.spawn_sidewalk(
                seed=seed + 3000,  # Separate seed for sidewalk
                count=sidewalk_count,
                vehicle_types=sidewalk_vehicle_types
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
        data_capture_actor="DataCapture_1"
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
                vehicle_count = 3
            elif i % 3 == 1:
                parking_ratio = 0.0  # All lanes
                vehicle_count = 4
            else:
                parking_ratio = 0.5  # Mixed
                vehicle_count = 5
            
            output_path = output_dir / f"frame_{i:03d}.png"
            
            print(f"\n[{i+1}/20] Seed={seed}, Vehicles={vehicle_count}, Parking={parking_ratio:.0%}")
            
            # Per-iteration stats
            iter_stats = SpawnStats()
            
            try:
                # Step 1: Time augmentation (before any spawning)
                time_result = time_controller.randomize(seed=seed)
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
                
                if not spawned_vehicles:
                    print(f"  ✗ No vehicles spawned")
                    failed += 1
                    continue
                
                # Step 4: Spawn props with same seed
                prop_result = prop_controller.spawn_all(seed=seed, spawn_chance=0.2)
                print(f"  Props spawned: {len(prop_result.spawned_props)}")
                
                # Step 5: Capture
                result = capture_controller.capture(
                    output_path=str(output_path),
                    seed=seed,
                    width=1920,
                    height=1080,
                    validate_scene=False  # Skip for speed
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

if __name__ == "__main__":
    main()
