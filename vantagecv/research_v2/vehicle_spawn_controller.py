"""
VehicleSpawnController - Vehicle Pool Management and Spawning

RESPONSIBILITY:
- Manage the vehicle pool (all vehicles start hidden)
- Pick random vehicles based on seed
- Teleport vehicles to anchor positions
- Unhide vehicles for scene
- Reset vehicles to pool after capture

VEHICLE POOL RULES:
- All vehicles are HIDDEN by default at pool positions (0, Y, 0)
- Spawning = unhide + teleport to anchor
- Reset = hide + teleport back to default position
- Scale is LOCKED - never modify scale

SPAWNING LOGIC:
- Parking slots: 1 vehicle per anchor, random from pool
- Lanes: Multiple vehicles along lane path
- Sidewalks: Pedestrians/bikes only (future)
"""

import math
import random
import logging
import requests
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class VehicleInstance:
    """A spawned vehicle instance"""
    name: str
    category: str
    spawn_location: Dict[str, float]
    spawn_rotation: Dict[str, float]
    anchor_name: Optional[str] = None


@dataclass 
class SpawnResult:
    """Result of a spawn operation"""
    success: bool
    spawned_vehicles: List[VehicleInstance] = field(default_factory=list)
    failure_reason: Optional[str] = None


class VehicleSpawnController:
    """
    Vehicle Spawn Controller
    
    Manages spawning vehicles from pool to scene anchors.
    """
    
    def __init__(self,
                 host: str = "127.0.0.1",
                 port: int = 30010,
                 level_path: str = "/Game/automobileV2.automobileV2",
                 anchor_config_path: str = "configs/levels/automobileV2_anchors.yaml",
                 vehicle_config_path: str = "configs/levels/automobileV2_vehicles.yaml"):
        self.base_url = f"http://{host}:{port}/remote"
        self.level_path = level_path
        self.session = requests.Session()
        
        # Load configs
        self.anchor_config = None
        self.vehicle_config = None
        
        anchor_path = Path(anchor_config_path)
        vehicle_path = Path(vehicle_config_path)
        
        if anchor_path.exists():
            with open(anchor_path, 'r') as f:
                self.anchor_config = yaml.safe_load(f)
        
        if vehicle_path.exists():
            with open(vehicle_path, 'r') as f:
                self.vehicle_config = yaml.safe_load(f)
        
        # Track currently spawned vehicles
        self.spawned_vehicles: List[VehicleInstance] = []
        
        logger.info("VehicleSpawnController initialized")
        logger.info(f"  Level: {level_path}")
        logger.info(f"  Anchor Config: {anchor_config_path}")
        logger.info(f"  Vehicle Config: {vehicle_config_path}")
    
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
                timeout=5.0
            )
            
            if response.status_code == 200:
                return response.json()
            return None
                
        except Exception as e:
            logger.error(f"Remote call error: {e}")
            return None
    
    def _set_property(self, object_path: str, property_name: str, value: Any) -> bool:
        """Set a property on an actor"""
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
            logger.error(f"Set property error: {e}")
            return False
    
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
    # VEHICLE POOL DETECTION
    # ========================================================================
    
    def detect_vehicle_pool(self) -> Dict[str, List[Dict]]:
        """
        Scan level for vehicle pool actors by detecting StaticMeshActors at specific X-coordinates.
        
        Classification rule (EXACT match):
        X == 0    → Car
        X == 1000 → Bus
        X == 2000 → Motorcycle
        X == 3000 → Bike
        X == 4000 → Truck
        
        Returns:
            Dict mapping vehicle category to list of vehicle dicts
        """
        print("=" * 60)
        print("VEHICLE POOL DETECTION (BY X-COORDINATE)")
        print("=" * 60)
        
        # Vehicle classification by X coordinate
        VEHICLE_X_COORDINATES = {
            0: "car",
            1000: "bus",
            2000: "motorcycle",
            3000: "bicycle",
            4000: "truck"
        }
        
        # Initialize vehicle pool
        detected_pool = {
            "bicycle": [],
            "bus": [],
            "car": [],
            "motorcycle": [],
            "truck": []
        }
        
        # Store original transforms for reset
        self.vehicle_pool_original_transforms = {}
        
        # Scan StaticMeshActor_* naming pattern
        for i in range(1, 500):
            actor_name = f"StaticMeshActor_{i}"
            transform = self._get_actor_transform(actor_name)
            
            if not transform:
                continue
            
            x_coord = transform["location"].get("X", 0)
            
            # Check if X matches any vehicle pool classification (exact match)
            for target_x, vehicle_category in VEHICLE_X_COORDINATES.items():
                if abs(x_coord - target_x) < 1.0:  # Allow 1 unit tolerance for floating point
                    vehicle_dict = {
                        "name": actor_name,
                        "category": vehicle_category,
                        "default_transform": {
                            "location": transform["location"].copy(),
                            "rotation": transform["rotation"].copy(),
                            "scale": transform["scale"].copy()
                        }
                    }
                    
                    detected_pool[vehicle_category].append(vehicle_dict)
                    
                    # Store original transform for reset
                    self.vehicle_pool_original_transforms[actor_name] = {
                        "location": transform["location"].copy(),
                        "rotation": transform["rotation"].copy(),
                        "scale": transform["scale"].copy()
                    }
                    break
        
        # Log summary
        print("VEHICLE POOL SUMMARY:")
        total_vehicles = 0
        for category, vehicles in detected_pool.items():
            print(f"  {category.capitalize()}: {len(vehicles)} vehicles available")
            total_vehicles += len(vehicles)
        print(f"  TOTAL: {total_vehicles} vehicles in pool")
        
        # Update vehicle_config with detected pool
        if not self.vehicle_config:
            self.vehicle_config = {}
        self.vehicle_config["vehicles"] = detected_pool
        
        return detected_pool
    
    def _get_actor_transform(self, actor_name: str) -> Optional[Dict]:
        """Get actor transform (location, rotation, scale)"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        
        loc = self._call_remote(path, "K2_GetActorLocation")
        rot = self._call_remote(path, "K2_GetActorRotation")
        scale_result = self._call_remote(path, "GetActorScale3D")
        
        if not loc or not rot:
            return None
        
        return {
            "location": loc.get("ReturnValue", {}),
            "rotation": rot.get("ReturnValue", {}),
            "scale": scale_result.get("ReturnValue", {"X": 1, "Y": 1, "Z": 1}) if scale_result else {"X": 1, "Y": 1, "Z": 1}
        }
    
    # ========================================================================
    # VEHICLE POOL
    # ========================================================================
    
    def _get_vehicle_pool(self) -> Dict[str, List[Dict]]:
        """Get all vehicles from config organized by category"""
        if not self.vehicle_config:
            return {}
        
        return self.vehicle_config.get("vehicles", {})
    
    def _get_all_vehicle_names(self) -> List[str]:
        """Get all vehicle names from pool config"""
        pool = self._get_vehicle_pool()
        names = []
        for cat in ["bicycle", "bus", "car", "motorcycle", "truck"]:
            for v in pool.get(cat, []):
                names.append(v["name"])
        return names
    
    def hide_all_vehicles(self) -> int:
        """Hide ALL vehicles in pool (cleanup any previous state)"""
        logger.info("Hiding all vehicles in pool...")
        count = 0
        
        for name in self._get_all_vehicle_names():
            if self._set_actor_hidden(name, True):
                count += 1
        
        # Clear spawned tracking
        self.spawned_vehicles.clear()
        
        logger.info(f"  Hidden {count} vehicles")
        return count
    
    def _get_available_vehicles(self, category: str = None) -> List[Dict]:
        """Get available (not currently spawned) vehicles"""
        pool = self._get_vehicle_pool()
        spawned_names = {v.name for v in self.spawned_vehicles}
        
        available = []
        categories = [category] if category else ["bicycle", "bus", "car", "motorcycle", "truck"]
        
        for cat in categories:
            for v in pool.get(cat, []):
                if v["name"] not in spawned_names:
                    available.append({**v, "category": cat})
        
        return available
    
    # ========================================================================
    # ANCHOR POSITIONS
    # ========================================================================
    
    def _get_parking_anchors(self) -> List[str]:
        """Get parking anchor names (supports both old and new YAML formats)"""
        if not self.anchor_config:
            return []
        
        anchors = self.anchor_config.get("parking", {}).get("anchors", [])
        
        # Handle new format (list of dicts with 'name' key)
        if anchors and isinstance(anchors[0], dict):
            return [a['name'] for a in anchors]
        
        # Handle old format (list of strings)
        return anchors
    
    def _get_lane_definitions(self) -> List[Dict]:
        """Get lane definitions with start/end anchors (supports both old and new YAML formats)"""
        if not self.anchor_config:
            return []
        
        definitions = self.anchor_config.get("lanes", {}).get("definitions", [])
        
        # Normalize format: new format uses 'start_anchor'/'end_anchor', old uses 'start'/'end'
        normalized = []
        for lane in definitions:
            if 'start_anchor' in lane and 'end_anchor' in lane:
                # New format - convert to old format
                normalized.append({
                    'id': lane.get('id', ''),
                    'start': lane['start_anchor'],
                    'end': lane['end_anchor'],
                    'width_cm': lane.get('width_cm', 350.0)
                })
            else:
                # Old format - pass through
                normalized.append(lane)
        
        return normalized
    
    def _get_sidewalk_bounds(self) -> Optional[Tuple[Dict, Dict]]:
        """Get sidewalk bounds from two corner anchors (supports both old and new YAML formats)"""
        if not self.anchor_config:
            return None
        
        # Try new format first (sidewalks with definitions list)
        sidewalks = self.anchor_config.get("sidewalks", {})
        if sidewalks:
            definitions = sidewalks.get("definitions", [])
            if definitions:
                # Use first sidewalk definition
                sidewalk = definitions[0]
                anchor1 = sidewalk.get("anchor_1")
                anchor2 = sidewalk.get("anchor_2")
                
                if anchor1 and anchor2:
                    t1 = self._get_anchor_transform(anchor1)
                    t2 = self._get_anchor_transform(anchor2)
                    
                    if t1 and t2:
                        return (t1, t2)
        
        # Try old format (singular sidewalk with anchor_1/anchor_2)
        sidewalk = self.anchor_config.get("sidewalk", {})
        anchor1 = sidewalk.get("anchor_1")
        anchor2 = sidewalk.get("anchor_2")
        
        if not anchor1 or not anchor2:
            return None
        
        t1 = self._get_anchor_transform(anchor1)
        t2 = self._get_anchor_transform(anchor2)
        
        if not t1 or not t2:
            return None
        
        return (t1, t2)
    
    def _get_anchor_transform(self, anchor_name: str) -> Optional[Dict]:
        """Get anchor location and rotation"""
        path = f"{self.level_path}:PersistentLevel.{anchor_name}"
        
        loc = self._call_remote(path, "K2_GetActorLocation")
        rot = self._call_remote(path, "K2_GetActorRotation")
        
        if not loc or not rot:
            return None
        
        return {
            "location": loc.get("ReturnValue", {}),
            "rotation": rot.get("ReturnValue", {})
        }
    
    def _compute_lane_transform(self, lane: Dict, t: float, lateral_offset: float = 0) -> Optional[Dict]:
        """
        Compute position and rotation along a lane.
        
        Args:
            lane: Lane definition with start/end anchors
            t: Position along lane (0.0 = start, 1.0 = end)
            lateral_offset: Perpendicular offset from lane center (cm)
        
        Returns:
            Dict with location and rotation facing lane direction
        """
        start_transform = self._get_anchor_transform(lane["start"])
        end_transform = self._get_anchor_transform(lane["end"])
        
        if not start_transform or not end_transform:
            return None
        
        start_loc = start_transform["location"]
        end_loc = end_transform["location"]
        
        # Interpolate position
        x = start_loc["X"] + t * (end_loc["X"] - start_loc["X"])
        y = start_loc["Y"] + t * (end_loc["Y"] - start_loc["Y"])
        z = start_loc["Z"] + t * (end_loc["Z"] - start_loc["Z"])
        
        # Use Start anchor's red arrow rotation (NOT geometric direction)
        yaw = start_transform["rotation"]["Yaw"]
        
        # Apply lateral offset (perpendicular to lane)
        perp_angle = math.radians(yaw + 90)
        x += lateral_offset * math.cos(perp_angle)
        y += lateral_offset * math.sin(perp_angle)
        
        return {
            "location": {"X": x, "Y": y, "Z": z},
            "rotation": {"Pitch": 0, "Yaw": yaw, "Roll": 0}
        }
    
    # ========================================================================
    # SPAWN OPERATIONS
    # ========================================================================
    
    def _set_actor_hidden(self, actor_name: str, hidden: bool) -> bool:
        """Set actor visibility using SetActorHiddenInGame function"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        result = self._call_remote(path, "SetActorHiddenInGame", {"bNewHidden": hidden})
        return result is not None
    
    def _teleport_actor(self, actor_name: str, location: Dict, rotation: Dict) -> bool:
        """Teleport actor to new position"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        
        # Set location
        loc_result = self._call_remote(path, "K2_SetActorLocation", {
            "NewLocation": location,
            "bSweep": False,
            "bTeleport": True
        })
        
        # Set rotation
        rot_result = self._call_remote(path, "K2_SetActorRotation", {
            "NewRotation": rotation,
            "bTeleportPhysics": True
        })
        
        return loc_result is not None and rot_result is not None
    
    def spawn_parking(self, seed: int, count: int = 3, 
                     vehicle_types: List[str] = None) -> SpawnResult:
        """
        Spawn vehicles in parking slots
        
        Args:
            seed: Random seed for determinism
            count: Number of vehicles to spawn
            vehicle_types: List of vehicle categories to use (default: cars only)
        """
        random.seed(seed)
        
        if vehicle_types is None:
            vehicle_types = ["car"]
        
        logger.info(f"Spawning {count} vehicles in parking (seed={seed})")
        
        # Get parking anchors
        anchors = self._get_parking_anchors()
        if not anchors:
            return SpawnResult(success=False, failure_reason="No parking anchors configured")
        
        # Get available vehicles
        available = []
        for vtype in vehicle_types:
            available.extend(self._get_available_vehicles(vtype))
        
        if not available:
            return SpawnResult(success=False, failure_reason="No available vehicles in pool")
        
        # Shuffle for randomness
        random.shuffle(anchors)
        random.shuffle(available)
        
        # Spawn vehicles
        spawned = []
        anchors_to_use = anchors[:count]
        
        for i, anchor_name in enumerate(anchors_to_use):
            if i >= len(available):
                logger.warning(f"Not enough vehicles in pool for all anchors")
                break
            
            vehicle = available[i]
            vehicle_name = vehicle["name"]
            category = vehicle["category"]
            
            # Get vehicle's default rotation from config
            vehicle_default_yaw = vehicle.get("default_transform", {}).get("rotation", {}).get("Yaw", 0)
            
            # Get anchor transform
            anchor_transform = self._get_anchor_transform(anchor_name)
            if not anchor_transform:
                logger.error(f"Could not get transform for anchor {anchor_name}")
                continue
            
            location = anchor_transform["location"]
            anchor_yaw = anchor_transform["rotation"]["Yaw"]
            anchor_pitch = anchor_transform["rotation"]["Pitch"]
            
            # Add slight randomization from config
            parking_config = self.anchor_config.get("parking", {})
            jitter = parking_config.get("position_jitter_cm", 10.0)
            yaw_jitter = parking_config.get("yaw_jitter_degrees", 5.0)
            
            location["X"] += random.uniform(-jitter, jitter)
            location["Y"] += random.uniform(-jitter, jitter)
            
            # Parking rotation: start with vehicle's default, ADD anchor direction
            yaw_offset = anchor_yaw
            yaw_offset += random.uniform(-yaw_jitter, yaw_jitter)
            
            # Reverse parking probability - also negate pitch when reversed
            is_reversed = random.random() < parking_config.get("reverse_probability", 0.3)
            if is_reversed:
                yaw_offset += 180.0
            
            # Use anchor's pitch for sloped parking spots
            # Negate pitch if reversed (front of car faces opposite direction on slope)
            final_pitch = -anchor_pitch if is_reversed else anchor_pitch
            rotation = {"Pitch": final_pitch, "Roll": 0}
            
            # ADD to vehicle's default rotation
            rotation["Yaw"] = vehicle_default_yaw + yaw_offset
            
            # Teleport vehicle
            if not self._teleport_actor(vehicle_name, location, rotation):
                logger.error(f"Failed to teleport {vehicle_name}")
                continue
            
            # Unhide vehicle
            if not self._set_actor_hidden(vehicle_name, False):
                logger.error(f"Failed to unhide {vehicle_name}")
                continue
            
            instance = VehicleInstance(
                name=vehicle_name,
                category=category,
                spawn_location=location,
                spawn_rotation=rotation,
                anchor_name=anchor_name
            )
            
            spawned.append(instance)
            self.spawned_vehicles.append(instance)
            
            logger.info(f"  ✓ {vehicle_name} ({category}) → {anchor_name}")
        
        logger.info(f"Spawned {len(spawned)}/{count} vehicles")
        
        return SpawnResult(
            success=len(spawned) > 0,
            spawned_vehicles=spawned
        )
    
    def spawn_lane(self, seed: int, count: int = 2,
                   vehicle_types: List[str] = None) -> SpawnResult:
        """
        Spawn vehicles in road lanes
        
        Args:
            seed: Random seed for determinism
            count: Number of vehicles to spawn
            vehicle_types: List of vehicle categories to use (default: cars only)
        """
        random.seed(seed)
        
        if vehicle_types is None:
            vehicle_types = ["car", "truck", "bus"]
        
        logger.info(f"Spawning {count} vehicles in lanes (seed={seed})")
        
        # Get lane definitions
        lanes = self._get_lane_definitions()
        if not lanes:
            return SpawnResult(success=False, failure_reason="No lane definitions configured")
        
        # Get available vehicles
        available = []
        for vtype in vehicle_types:
            available.extend(self._get_available_vehicles(vtype))
        
        if not available:
            return SpawnResult(success=False, failure_reason="No available vehicles in pool")
        
        random.shuffle(available)
        
        # Lane config
        lane_config = self.anchor_config.get("lanes", {})
        lateral_jitter = lane_config.get("lateral_jitter_cm", 30.0)
        yaw_jitter = lane_config.get("yaw_jitter_degrees", 2.0)
        
        spawned = []
        vehicle_idx = 0
        
        # Track used lane positions to prevent overlap
        # Each entry: (lane_id, t_value) - new vehicles must be MIN_SPACING apart
        MIN_SPACING = 0.25  # Minimum t-distance between vehicles on same lane
        used_positions = []  # List of (lane_id, t)
        
        for i in range(count):
            if vehicle_idx >= len(available):
                logger.warning("Not enough vehicles in pool")
                break
            
            # Try to find non-overlapping position
            max_attempts = 10
            for attempt in range(max_attempts):
                lane = random.choice(lanes)
                t = random.uniform(0.2, 0.8)  # Avoid edges
                
                # Check for overlap with existing positions on same lane
                overlap = False
                for used_lane_id, used_t in used_positions:
                    if used_lane_id == lane["id"] and abs(t - used_t) < MIN_SPACING:
                        overlap = True
                        break
                
                if not overlap:
                    break
            else:
                logger.warning(f"Could not find non-overlapping lane position after {max_attempts} attempts")
                continue
            
            lateral_offset = random.uniform(-lateral_jitter, lateral_jitter)
            
            transform = self._compute_lane_transform(lane, t, lateral_offset)
            if not transform:
                logger.error(f"Could not compute lane transform for {lane['id']}")
                continue
            
            location = transform["location"]
            
            # Get vehicle's default rotation from config
            vehicle = available[vehicle_idx]
            vehicle_name = vehicle["name"]
            category = vehicle["category"]
            vehicle_default_yaw = vehicle.get("default_transform", {}).get("rotation", {}).get("Yaw", 0)
            
            # Lane direction yaw (computed from atan2)
            lane_yaw = transform["rotation"]["Yaw"]
            
            # ADD lane direction to vehicle's default rotation
            rotation = {"Pitch": 0, "Roll": 0}
            rotation["Yaw"] = vehicle_default_yaw + lane_yaw
            
            # Add yaw jitter
            rotation["Yaw"] += random.uniform(-yaw_jitter, yaw_jitter)
            
            # Track this position
            used_positions.append((lane["id"], t))
            
            vehicle_idx += 1
            
            # Teleport vehicle
            if not self._teleport_actor(vehicle_name, location, rotation):
                logger.error(f"Failed to teleport {vehicle_name}")
                continue
            
            # Unhide vehicle
            if not self._set_actor_hidden(vehicle_name, False):
                logger.error(f"Failed to unhide {vehicle_name}")
                continue
            
            instance = VehicleInstance(
                name=vehicle_name,
                category=category,
                spawn_location=location,
                spawn_rotation=rotation,
                anchor_name=lane["id"]
            )
            
            spawned.append(instance)
            self.spawned_vehicles.append(instance)
            
            logger.info(f"  ✓ {vehicle_name} ({category}) → {lane['id']} t={t:.2f}")
        
        logger.info(f"Spawned {len(spawned)}/{count} vehicles in lanes")
        
        return SpawnResult(
            success=len(spawned) > 0,
            spawned_vehicles=spawned
        )
    
    def spawn(self, seed: int, count: int = 5,
              parking_ratio: float = 0.5,
              vehicle_types: List[str] = None) -> SpawnResult:
        """
        Unified spawn: randomly distribute vehicles between parking and lanes.
        
        Args:
            seed: Random seed for determinism
            count: Total number of vehicles to spawn
            parking_ratio: Probability of parking vs lane (0.5 = equal chance)
            vehicle_types: List of vehicle categories (default: car only)
        
        Rotation is automatically adjusted based on zone type:
        - Parking: Face anchor direction ± 5° jitter, 30% reversed
        - Lane: Face lane direction (start→end) ± 2° jitter
        """
        random.seed(seed)
        
        if vehicle_types is None:
            vehicle_types = ["car"]
        
        logger.info(f"Spawning {count} vehicles (seed={seed}, parking_ratio={parking_ratio})")
        
        # Decide how many go to parking vs lanes
        parking_count = sum(1 for _ in range(count) if random.random() < parking_ratio)
        lane_count = count - parking_count
        
        logger.info(f"  Distribution: {parking_count} parking, {lane_count} lanes")
        
        all_spawned = []
        
        # Spawn parking vehicles
        if parking_count > 0:
            parking_result = self.spawn_parking(
                seed=seed,
                count=parking_count,
                vehicle_types=vehicle_types
            )
            all_spawned.extend(parking_result.spawned_vehicles)
        
        # Spawn lane vehicles (use offset seed to avoid collision)
        if lane_count > 0:
            lane_result = self.spawn_lane(
                seed=seed + 1000,
                count=lane_count,
                vehicle_types=vehicle_types
            )
            all_spawned.extend(lane_result.spawned_vehicles)
        
        logger.info(f"Total spawned: {len(all_spawned)}/{count}")
        
        return SpawnResult(
            success=len(all_spawned) > 0,
            spawned_vehicles=all_spawned
        )
    
    def spawn_sidewalk(self, seed: int, count: int = 3,
                      vehicle_types: List[str] = None) -> SpawnResult:
        """
        Spawn vehicles (bicycles) randomly within sidewalk bounds.
                ANCHOR USAGE:
        - Uses 2 corner anchors to define rectangular sidewalk region
        - Anchors retrieved from config: sidewalk.anchor_1 and sidewalk.anchor_2
        - Bounding box computed from anchor transforms (min/max X/Y)
        - Random placement within bounds with collision avoidance (100cm spacing)
        - Z coordinate averaged from both anchors
        
        CONSISTENCY NOTE:
        Unlike parking (1 vehicle per anchor) and lanes (interpolated positions),
        sidewalk spawning uses random positions within anchor-defined bounds.
        This is intentional for pedestrian/bike realism (not fixed parking spots).
                Args:
            seed: Random seed for deterministic spawning
            count: Number of vehicles to spawn
            vehicle_types: List of vehicle categories to spawn (default: ["bicycle"])
        
        Returns:
            SpawnResult with spawned vehicles
        """
        random.seed(seed)
        
        if vehicle_types is None:
            vehicle_types = ["bicycle"]
        
        # Get sidewalk bounds
        bounds = self._get_sidewalk_bounds()
        if not bounds:
            logger.error("No sidewalk bounds configured")
            return SpawnResult(
                success=False,
                spawned_vehicles=[],
                failure_reason="No sidewalk bounds configured"
            )
        
        anchor1_transform, anchor2_transform = bounds
        loc1 = anchor1_transform["location"]
        loc2 = anchor2_transform["location"]
        
        # Calculate bounding box
        min_x = min(loc1["X"], loc2["X"])
        max_x = max(loc1["X"], loc2["X"])
        min_y = min(loc1["Y"], loc2["Y"])
        max_y = max(loc1["Y"], loc2["Y"])
        z = (loc1["Z"] + loc2["Z"]) / 2
        
        logger.info(f"Sidewalk bounds: X=[{min_x:.0f}, {max_x:.0f}] Y=[{min_y:.0f}, {max_y:.0f}]")
        
        # Get available vehicles
        available = []
        for vtype in vehicle_types:
            available.extend(self._get_available_vehicles(vtype))
        
        if not available:
            logger.warning(f"No available vehicles for types: {vehicle_types}")
            return SpawnResult(
                success=False,
                spawned_vehicles=[],
                failure_reason="No vehicles available in pool"
            )
        
        random.shuffle(available)
        
        # Collision check: maintain minimum distance between spawns
        MIN_SPACING = 100.0  # 100cm = 1m minimum distance
        spawned_positions = []
        spawned = []
        
        for i in range(min(count, len(available))):
            vehicle = available[i]
            vehicle_name = vehicle["name"]
            category = vehicle["category"]
            
            # Try to find non-overlapping position
            max_attempts = 20
            for attempt in range(max_attempts):
                # Random position within bounds
                x = random.uniform(min_x, max_x)
                y = random.uniform(min_y, max_y)
                yaw = random.uniform(0, 360)
                
                # Check collision with existing spawns
                collision = False
                for prev_pos in spawned_positions:
                    dx = x - prev_pos[0]
                    dy = y - prev_pos[1]
                    dist = math.sqrt(dx*dx + dy*dy)
                    if dist < MIN_SPACING:
                        collision = True
                        break
                
                if not collision:
                    # Valid position found
                    spawned_positions.append((x, y))
                    
                    # Build location and rotation dicts
                    location = {"X": x, "Y": y, "Z": z}
                    rotation = {"Pitch": 0, "Yaw": yaw, "Roll": 0}
                    
                    # Teleport vehicle to position
                    teleport_success = self._teleport_actor(vehicle_name, location, rotation)
                    
                    if teleport_success:
                        # Unhide vehicle
                        self._set_actor_hidden(vehicle_name, False)
                        
                        instance = VehicleInstance(
                            name=vehicle_name,
                            category=category,
                            spawn_location=location,
                            spawn_rotation=rotation,
                            anchor_name=f"sidewalk_{i}"
                        )
                        
                        self.spawned_vehicles.append(instance)
                        spawned.append(instance)
                        logger.info(f"  Spawned {vehicle_name} ({category}) at sidewalk ({x:.0f}, {y:.0f}, yaw={yaw:.0f}°)")
                        break
                    else:
                        logger.error(f"Failed to teleport {vehicle_name}")
            else:
                logger.warning(f"Could not find non-colliding position for vehicle {i+1} after {max_attempts} attempts")
        
        logger.info(f"Spawned {len(spawned)}/{count} vehicles on sidewalk")
        
        return SpawnResult(
            success=len(spawned) > 0,
            spawned_vehicles=spawned
        )
    
    def reset_all(self) -> bool:
        """Reset all spawned vehicles back to pool (hide + return to default position)"""
        logger.info(f"Resetting {len(self.spawned_vehicles)} vehicles to pool")
        
        success_count = 0
        
        for instance in self.spawned_vehicles:
            vehicle_name = instance.name
            
            # Hide vehicle
            self._set_actor_hidden(vehicle_name, True)
            
            # Return to original pool position using stored transforms
            if vehicle_name in self.vehicle_pool_original_transforms:
                default = self.vehicle_pool_original_transforms[vehicle_name]
                location = default.get("location", {"X": 0, "Y": 0, "Z": 0})
                rotation = default.get("rotation", {"Pitch": 0, "Yaw": 0, "Roll": 0})
                self._teleport_actor(vehicle_name, location, rotation)
                logger.info(f"  ✓ Reset {vehicle_name} to pool position X={location['X']:.0f}")
            else:
                logger.warning(f"  ⚠ No original transform for {vehicle_name}, leaving at current position")
            
            success_count += 1
        
        self.spawned_vehicles.clear()
        logger.info(f"Reset complete: {success_count} vehicles returned to pool")
        
        return True
    
    def get_spawned_count(self) -> int:
        """Get count of currently spawned vehicles"""
        return len(self.spawned_vehicles)


def main():
    """Test vehicle spawning"""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    print("=" * 60)
    print("VEHICLE SPAWN CONTROLLER TEST")
    print("=" * 60)
    
    controller = VehicleSpawnController()
    
    # Reset any existing spawns
    print("\n--- Reset All ---")
    controller.reset_all()
    
    # Spawn 3 cars in parking
    print("\n--- Spawn Parking (3 cars) ---")
    result = controller.spawn_parking(seed=42, count=3, vehicle_types=["car"])
    
    if result.success:
        print(f"\n✅ Spawned {len(result.spawned_vehicles)} vehicles")
        for v in result.spawned_vehicles:
            print(f"   {v.name} ({v.category}) at {v.anchor_name}")
    else:
        print(f"\n❌ Spawn failed: {result.failure_reason}")
        return 1
    
    print("\n--- Press Enter to reset vehicles ---")
    input()
    
    controller.reset_all()
    print("\n✅ Vehicles reset to pool")
    
    return 0


if __name__ == "__main__":
    exit(main())
