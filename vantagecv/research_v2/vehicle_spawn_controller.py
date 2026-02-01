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
                 anchor_config_path: str = "configs/levels/automobileV2_anchors_detected.yaml",
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
        # IMPORTANT: Preserve start_position/end_position for YAML-based positioning
        normalized = []
        for lane in definitions:
            if 'start_anchor' in lane and 'end_anchor' in lane:
                # New format - convert to old format but PRESERVE YAML positions
                normalized_lane = {
                    'id': lane.get('id', ''),
                    'start': lane['start_anchor'],
                    'end': lane['end_anchor'],
                    'start_anchor': lane['start_anchor'],  # Keep new format too
                    'end_anchor': lane['end_anchor'],
                    'width_cm': lane.get('width_cm', 5000.0)  # Lane capacity in abstract units (5000 = 2 cars + 1 bus)
                }
                # Preserve YAML positions if available (for aligned coordinates)
                if 'start_position' in lane:
                    normalized_lane['start_position'] = lane['start_position']
                if 'end_position' in lane:
                    normalized_lane['end_position'] = lane['end_position']
                # Preserve vehicle_yaw if available (pre-computed rotation)
                if 'vehicle_yaw' in lane:
                    normalized_lane['vehicle_yaw'] = lane['vehicle_yaw']
                normalized.append(normalized_lane)
            else:
                # Old format - pass through
                normalized.append(lane)
        
        return normalized
    
    def _get_sidewalk_bounds(self) -> Optional[Tuple[Dict, Dict]]:
        """Get sidewalk bounds from two corner anchors (supports both old and new YAML formats)
        
        Returns transforms with location from YAML if available (aligned coordinates),
        otherwise queries UE5 for live positions.
        """
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
                    # Use YAML positions if available (aligned coordinates)
                    if 'position_1' in sidewalk and 'position_2' in sidewalk:
                        pos1 = sidewalk['position_1']
                        pos2 = sidewalk['position_2']
                        t1 = {"location": {"X": pos1[0], "Y": pos1[1], "Z": pos1[2]}}
                        t2 = {"location": {"X": pos2[0], "Y": pos2[1], "Z": pos2[2]}}
                        logger.info(f"[SIDEWALK YAML] Using YAML positions: Y={pos1[1]}")
                        return (t1, t2)
                    else:
                        # Fallback to UE5 query
                        logger.info(f"[SIDEWALK UE5] No YAML positions, querying UE5")
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
    
    def _discover_lane_segments(self, lane: Dict) -> List[Dict]:
        """
        Returns the lane as a single segment for spawning.
        We constrain `t` to middle portion to avoid edge artifacts.
        
        Returns:
            List with single lane segment
        """
        return [{
            'id': lane.get('id'),
            'start_anchor': lane.get('start_anchor'),
            'end_anchor': lane.get('end_anchor'),
            'start_position': lane.get('start_position'),
            'end_position': lane.get('end_position'),
            'vehicle_yaw': lane.get('vehicle_yaw')  # Include pre-computed rotation
        }]
    
    def _compute_lane_transform_with_offset(self, lane: Dict, t: float, lateral_offset: float = 0.0) -> Optional[Dict]:
        """
        Compute position and rotation along a lane with lateral offset.
        
        Args:
            lane: Lane definition with start/end anchors (or segment)
            t: Position along lane (0.0 = start, 1.0 = end)
            lateral_offset: Perpendicular offset from centerline in cm (positive = right, negative = left)
        
        Returns:
            Dict with location, rotation, start_loc, end_loc for validation
        """
        # Use YAML positions if available (aligned coordinates), otherwise query UE5
        if 'start_position' in lane and 'end_position' in lane:
            start_loc = {"X": lane['start_position'][0], "Y": lane['start_position'][1], "Z": lane['start_position'][2]}
            end_loc = {"X": lane['end_position'][0], "Y": lane['end_position'][1], "Z": lane['end_position'][2]}
        else:
            start_anchor = lane.get("start", lane.get("start_anchor"))
            end_anchor = lane.get("end", lane.get("end_anchor"))
            start_transform = self._get_anchor_transform(start_anchor)
            end_transform = self._get_anchor_transform(end_anchor)
            if not start_transform or not end_transform:
                return None
            start_loc = start_transform["location"]
            end_loc = end_transform["location"]
        
        # Calculate lane direction vector
        dx = end_loc["X"] - start_loc["X"]
        dy = end_loc["Y"] - start_loc["Y"]
        lane_length = math.sqrt(dx*dx + dy*dy)
        
        # Interpolate position on centerline
        x = start_loc["X"] + t * dx
        y = start_loc["Y"] + t * dy
        z = start_loc["Z"] + t * (end_loc["Z"] - start_loc["Z"])
        
        # Apply lateral offset (perpendicular to lane direction)
        if lane_length > 0 and lateral_offset != 0:
            # Normalize lane direction
            dir_x = dx / lane_length
            dir_y = dy / lane_length
            # Perpendicular vector (90 degrees clockwise)
            perp_x = dir_y
            perp_y = -dir_x
            # Apply offset
            x += perp_x * lateral_offset
            y += perp_y * lateral_offset
        
        # Use vehicle_yaw from YAML if available (pre-computed correct direction)
        yaml_yaw = lane.get('vehicle_yaw')
        if yaml_yaw is not None:
            yaw = yaml_yaw
            lane_id = lane.get('id', 'unknown')
            print(f"            [ROTATION] {lane_id}: Using YAML vehicle_yaw={yaw:.1f}°")
        else:
            # Fallback: compute rotation from arrow direction vs lane direction
            start_anchor = lane.get("start", lane.get("start_anchor"))
            start_transform = self._get_anchor_transform(start_anchor)
            if start_transform:
                start_yaw = start_transform["rotation"]["Yaw"]
                lane_yaw = math.degrees(math.atan2(dy, dx))
                angle_diff = (start_yaw - lane_yaw + 180) % 360 - 180
                if abs(angle_diff) > 90:
                    yaw = start_yaw + 180
                else:
                    yaw = start_yaw
            else:
                # Last resort: use lane direction
                yaw = math.degrees(math.atan2(dy, dx))
        
        return {
            "location": {"X": x, "Y": y, "Z": z},
            "rotation": {"Pitch": 0, "Yaw": yaw, "Roll": 0},
            "start_loc": start_loc,
            "end_loc": end_loc
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
        # Allow spawn anywhere within lane width (not just centerline)
        yaw_jitter = lane_config.get("yaw_jitter_degrees", 2.0)
        
        spawned = []
        vehicle_idx = 0
        
        # Lane capacity based on width and vehicle "space value"
        # Space values in UE units (centimeters)
        SPACE_VALUE = {
            "car": 1000,       # Car takes 1000 units
            "truck": 1000,     # Truck takes 1000 units
            "bus": 3000,       # Bus takes 3000 units
            "motorcycle": 800, # Motorcycle takes less space
            "bicycle": 600     # Bicycle takes less space
        }
        
        # Track used space per lane: {lane_id: [(t_value, lateral_offset, space_value, category), ...]}
        lane_occupancy = {}  # {lane_id: used_space_total}
        lane_positions = {}  # {lane_id: [(t, lateral_offset, half_width, category), ...]} for overlap checks
        
        for i in range(count):
            if vehicle_idx >= len(available):
                logger.warning("Not enough vehicles in pool")
                break
            
            # Get current vehicle info
            vehicle = available[vehicle_idx]
            vehicle_name = vehicle["name"]
            category = vehicle["category"]
            current_space = SPACE_VALUE.get(category, 1000)
            
            # Try to find non-overlapping position
            max_attempts = 20
            for attempt in range(max_attempts):
                # Pick random lane
                lane = random.choice(lanes)
                lane_id = lane["id"]
                lane_capacity = lane.get('width_cm', 5000.0)  # Lane capacity in abstract units
                
                # Check if lane has capacity for this vehicle
                current_occupancy = lane_occupancy.get(lane_id, 0)
                if current_occupancy + current_space > lane_capacity:
                    # Lane full, try another
                    if attempt == max_attempts - 1:
                        print(f"            [CAPACITY] {lane_id} full: {current_occupancy} + {current_space} > {lane_capacity}")
                    continue
                
                # Discover mesh segments for this lane
                segments = self._discover_lane_segments(lane)
                if not segments:
                    continue
                
                # Pick random segment
                segment = random.choice(segments)
                
                # Random position along lane (t value)
                t = random.uniform(0.3, 0.7)  # Stay away from endpoints
                
                # Random lateral offset within physical lane width (perpendicular to centerline)
                # Read lane_width from scene config (in meters), convert to cm
                scene_config = self.anchor_config.get("scene", {})
                lane_width_meters = scene_config.get("lane_width", 4.0)  # Default 4m
                physical_lane_width = lane_width_meters * 100.0  # Convert to cm
                max_lateral = (physical_lane_width / 2.0) - 100.0  # Keep 100cm margin from edge
                lateral_offset = random.uniform(-max_lateral, max_lateral) if max_lateral > 0 else 0.0
                
                # Vehicle half-width for overlap check (use physical width, not capacity)
                # Approximate physical widths: car ~180cm, truck ~250cm, bus ~260cm
                PHYSICAL_HALF_WIDTH = {
                    "car": 90.0,
                    "truck": 125.0,
                    "bus": 130.0,
                    "motorcycle": 50.0,
                    "bicycle": 40.0
                }
                vehicle_half_width = PHYSICAL_HALF_WIDTH.get(category, 90.0)
                
                # Check for overlap with existing vehicles on same lane
                overlap = False
                if lane_id in lane_positions:
                    for used_t, used_lateral, used_half_width, used_category in lane_positions[lane_id]:
                        # Check longitudinal overlap (t-based, scaled by space)
                        t_distance = abs(t - used_t)
                        min_t_spacing = 0.12  # Minimum t-spacing
                        
                        # Check lateral overlap
                        lateral_distance = abs(lateral_offset - used_lateral)
                        min_lateral_spacing = vehicle_half_width + used_half_width
                        
                        # Overlap if both longitudinal AND lateral are too close
                        if t_distance < min_t_spacing and lateral_distance < min_lateral_spacing:
                            overlap = True
                            if attempt == max_attempts - 1:
                                print(f"            [OVERLAP] {category} would overlap {used_category} on {lane_id}")
                            break
                
                if not overlap:
                    break
            else:
                logger.warning(f"Could not find non-overlapping lane position after {max_attempts} attempts")
                continue
            
            # Compute transform using the specific mesh segment
            transform = self._compute_lane_transform_with_offset(segment, t, lateral_offset)
            if not transform:
                logger.error(f"Could not compute lane transform for {lane['id']}")
                continue
            
            location = transform["location"]
            start_loc = transform["start_loc"]
            end_loc = transform["end_loc"]
            
            # Get mesh names for logging (use segment, not full lane)
            mesh_a = segment.get('start_anchor', 'unknown')
            mesh_b = segment.get('end_anchor', 'unknown')
            
            # Enhanced diagnostic logging
            print(f"  [LANE OK] {lane['id']}: segment {mesh_a} -> {mesh_b}")
            print(f"            start=({start_loc['X']:.0f}, {start_loc['Y']:.0f}, {start_loc['Z']:.0f})")
            print(f"            end=({end_loc['X']:.0f}, {end_loc['Y']:.0f}, {end_loc['Z']:.0f})")
            print(f"            spawn=({location['X']:.0f}, {location['Y']:.0f}, {location['Z']:.0f}) at t={t:.2f}, lateral={lateral_offset:.0f}cm")
            
            # Log rotation details BEFORE computing final rotation
            lane_yaw = transform["rotation"]["Yaw"]
            
            # Get vehicle's default rotation from config (vehicle already retrieved above)
            vehicle_default_yaw = vehicle.get("default_transform", {}).get("rotation", {}).get("Yaw", 0)
            
            # ADD lane direction to vehicle's default rotation
            rotation = {"Pitch": 0, "Roll": 0}
            rotation["Yaw"] = vehicle_default_yaw + lane_yaw
            
            # Add yaw jitter
            yaw_jitter_amount = random.uniform(-yaw_jitter, yaw_jitter)
            rotation["Yaw"] += yaw_jitter_amount
            
            # Log rotation composition
            print(f"            rotation: vehicle_default={vehicle_default_yaw:.1f}° + lane_dir={lane_yaw:.1f}° + jitter={yaw_jitter_amount:.1f}° = {rotation['Yaw']:.1f}°")
            
            # Track lane occupancy and positions for overlap checks
            lane_occupancy[lane_id] = lane_occupancy.get(lane_id, 0) + current_space
            if lane_id not in lane_positions:
                lane_positions[lane_id] = []
            lane_positions[lane_id].append((t, lateral_offset, vehicle_half_width, category))
            
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
        
        # Sidewalk anchors define CENTERLINE (not bounding box)
        # Calculate centerline direction for perpendicular offset
        dx = loc2["X"] - loc1["X"]
        dy = loc2["Y"] - loc1["Y"]
        centerline_length = math.sqrt(dx*dx + dy*dy)
        
        logger.info(f"Sidewalk centerline: ({loc1['X']:.0f}, {loc1['Y']:.0f}) → ({loc2['X']:.0f}, {loc2['Y']:.0f}), length={centerline_length:.0f}cm")
        
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
        
        # Sidewalk config - STRICT CENTERLINE: Bikes spawn EXACTLY on centerline
        MAX_CENTERLINE_TOLERANCE_CM = 5.0  # Maximum allowed deviation
        
        # Collision check: maintain minimum distance between spawns
        BASE_SPACING_CM = 120.0  # Base spacing for regular vehicles (1.2m)
        SPACING_MULTIPLIER = {
            "bus": 2.0,        # Buses need 2x spacing
            "truck": 1.2,      # Trucks need 1.2x spacing
            "car": 1.0,        # Cars use base spacing
            "motorcycle": 0.8, # Motorcycles can be closer
            "bicycle": 0.8     # Bicycles can be closer
        }
        spawned_positions = []  # Store (t-value, category) tuples
        spawned = []
        
        # Get mesh names for logging
        sidewalk_def = self.anchor_config.get("sidewalks", {}).get("definitions", [{}])[0]
        mesh_a = sidewalk_def.get("anchor_1", "unknown")
        mesh_b = sidewalk_def.get("anchor_2", "unknown")
        
        for i in range(min(count, len(available))):
            vehicle = available[i]
            vehicle_name = vehicle["name"]
            category = vehicle["category"]
            current_spacing_mult = SPACING_MULTIPLIER.get(category, 1.0)
            
            # Try to find non-overlapping position along centerline
            max_attempts = 20
            for attempt in range(max_attempts):
                # Random position along centerline (0.0 = anchor1, 1.0 = anchor2)
                t = random.uniform(0.1, 0.9)  # Avoid endpoints
                
                # Check collision with existing spawns
                collision = False
                for prev_t, prev_category in spawned_positions:
                    # Calculate required spacing based on both vehicle sizes
                    prev_spacing_mult = SPACING_MULTIPLIER.get(prev_category, 1.0)
                    required_spacing = BASE_SPACING_CM * max(current_spacing_mult, prev_spacing_mult)
                    
                    t_distance = abs(t - prev_t) * centerline_length
                    if t_distance < required_spacing:
                        collision = True
                        if attempt == max_attempts - 1:  # Log only on final attempt
                            print(f"                [OVERLAP] {category} would overlap {prev_category} on sidewalk (spacing={t_distance:.0f}cm < {required_spacing:.0f}cm)")
                        break
                
                if not collision:
                    # Valid position found - interpolate EXACTLY on centerline (no offset)
                    x = loc1["X"] + t * dx
                    y = loc1["Y"] + t * dy
                    z = loc1["Z"] + t * (loc2["Z"] - loc1["Z"])
                    
                    # VALIDATION: Verify position is on line segment
                    # Compute actual distance from centerline
                    if centerline_length > 0:
                        # Vector from start to spawn point
                        vx = x - loc1["X"]
                        vy = y - loc1["Y"]
                        
                        # Project onto line to get closest point
                        proj_t = (vx * dx + vy * dy) / (centerline_length * centerline_length)
                        closest_x = loc1["X"] + proj_t * dx
                        closest_y = loc1["Y"] + proj_t * dy
                        
                        # Distance from spawn to closest point on line
                        dist_x = x - closest_x
                        dist_y = y - closest_y
                        centerline_distance = math.sqrt(dist_x*dist_x + dist_y*dist_y)
                    else:
                        centerline_distance = 0.0
                    
                    # Reject if too far from centerline
                    if centerline_distance > MAX_CENTERLINE_TOLERANCE_CM:
                        logger.error(f"[SIDEWALK REJECT] distance={centerline_distance:.2f}cm > {MAX_CENTERLINE_TOLERANCE_CM}cm")
                        print(f"  [SIDEWALK REJECT] OFF CENTERLINE by {centerline_distance:.2f}cm - REJECTED")
                        continue
                    
                    yaw = random.uniform(0, 360)
                    spawned_positions.append((t, category))  # Track t-value and category for size-aware collision
                    
                    # Enhanced diagnostic logging
                    print(f"  [SIDEWALK OK] mesh {mesh_a} <- {mesh_b} (bidirectional)")
                    print(f"                start=({loc1['X']:.0f}, {loc1['Y']:.0f}, {loc1['Z']:.0f})")
                    print(f"                end=({loc2['X']:.0f}, {loc2['Y']:.0f}, {loc2['Z']:.0f})")
                    print(f"                spawn=({x:.0f}, {y:.0f}, {z:.0f}) at t={t:.2f}")
                    print(f"                centerline_dist={centerline_distance:.2f}cm (max={MAX_CENTERLINE_TOLERANCE_CM}cm)")
                    print(f"                rotation: random_yaw={yaw:.1f}° (bidirectional sidewalk)")
                    
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
                logger.warning(f"            [SKIP] Could not place {vehicle_name} on sidewalk after {max_attempts} attempts")
        
        print(f"        [SPAWN] Sidewalk spawned {len(spawned)} vehicles on centerline (anchors: {mesh_a} → {mesh_b})")
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
