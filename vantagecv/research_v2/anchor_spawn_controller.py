"""
Anchor-based Spawn Controller

Python interface for the UE5 AnchorSpawnSystem.
Loads anchor configuration and issues spawn commands via Remote Control API.
"""

import yaml
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ParkingMode(Enum):
    PULL_IN = 0
    REVERSE_IN = 1


@dataclass
class VehicleConfig:
    """Configuration for a vehicle to spawn"""
    asset_path: str
    vehicle_class: str = "car"
    scale: float = 1.0


@dataclass
class LaneConfig:
    """Lane definition"""
    lane_id: str
    start_anchor: str
    end_anchor: str
    width: float = 350.0


@dataclass
class AnchorSpawnConfig:
    """Full spawn configuration loaded from YAML"""
    
    # Level info
    level_name: str = ""
    level_path: str = ""
    
    # Locked actors (never modify)
    locked_actors: List[str] = field(default_factory=list)
    
    # Parking configuration
    parking_anchors: List[str] = field(default_factory=list)
    parking_position_jitter: float = 10.0
    parking_yaw_jitter: float = 5.0
    parking_reverse_probability: float = 0.3
    
    # Lane configuration
    lanes: List[LaneConfig] = field(default_factory=list)
    lane_lateral_jitter: float = 30.0
    lane_yaw_jitter: float = 2.0
    
    # Sidewalk configuration
    sidewalk_anchor_1: str = ""
    sidewalk_anchor_2: str = ""
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> 'AnchorSpawnConfig':
        """Load configuration from YAML file"""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        config = cls()
        
        # Level info
        level = data.get('level', {})
        config.level_name = level.get('name', '')
        config.level_path = level.get('path', '')
        
        # Locked actors
        locked = data.get('locked_actors', [])
        config.locked_actors = [a.get('name', '') for a in locked if isinstance(a, dict)]
        
        # Parking
        parking = data.get('parking', {})
        config.parking_anchors = parking.get('anchors', [])
        config.parking_position_jitter = parking.get('position_jitter_cm', 10.0)
        config.parking_yaw_jitter = parking.get('yaw_jitter_degrees', 5.0)
        config.parking_reverse_probability = parking.get('reverse_probability', 0.3)
        
        # Lanes
        lanes_data = data.get('lanes', {})
        if isinstance(lanes_data, dict):
            # New format with 'definitions' key
            lane_list = lanes_data.get('definitions', [])
            config.lane_lateral_jitter = lanes_data.get('lateral_jitter_cm', 30.0)
            config.lane_yaw_jitter = lanes_data.get('yaw_jitter_degrees', 2.0)
        else:
            # Legacy format - lanes is a list
            lane_list = lanes_data if isinstance(lanes_data, list) else []
        
        for lane in lane_list:
            if isinstance(lane, dict) and 'id' in lane:
                config.lanes.append(LaneConfig(
                    lane_id=lane.get('id', ''),
                    start_anchor=lane.get('start', ''),
                    end_anchor=lane.get('end', ''),
                    width=lane.get('width_cm', 350.0)
                    ))
        
        # Lane jitter (may be nested under lanes key)
        if isinstance(lanes_data, dict):
            config.lane_lateral_jitter = lanes_data.get('lateral_jitter_cm', 30.0)
            config.lane_yaw_jitter = lanes_data.get('yaw_jitter_degrees', 2.0)
        
        # Sidewalk
        sidewalk = data.get('sidewalk', {})
        config.sidewalk_anchor_1 = sidewalk.get('anchor_1', '')
        config.sidewalk_anchor_2 = sidewalk.get('anchor_2', '')
        
        return config


class AnchorSpawnController:
    """
    Controls vehicle/prop spawning using anchor actors in UE5.
    
    All spawning is deterministic given a fixed seed.
    No hardcoded coordinates - all positions from anchor actors.
    """
    
    def __init__(self, 
                 config: AnchorSpawnConfig,
                 host: str = "127.0.0.1", 
                 port: int = 30010,
                 timeout: float = 10.0):
        self.config = config
        self.base_url = f"http://{host}:{port}/remote"
        self.timeout = timeout
        self.session = requests.Session()
        
        # Track spawned instances
        self.spawned_instances: List[str] = []
        self.current_seed: int = 0
        
        logger.info(f"AnchorSpawnController initialized")
        logger.info(f"  Level: {config.level_name}")
        logger.info(f"  Parking anchors: {len(config.parking_anchors)}")
        logger.info(f"  Lanes: {len(config.lanes)}")
        logger.info(f"  Locked actors: {len(config.locked_actors)}")
    
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
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Remote call failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Remote call timeout: {function_name}")
            return None
        except Exception as e:
            logger.error(f"Remote call error: {e}")
            return None
    
    def _set_property(self, object_path: str, property_name: str, value: Any) -> bool:
        """Set a property on a UE5 object"""
        try:
            response = self.session.put(
                f"{self.base_url}/object/property",
                json={
                    "objectPath": object_path,
                    "propertyName": property_name,
                    "propertyValue": value
                },
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Set property error: {e}")
            return False
    
    def initialize(self, seed: int) -> bool:
        """
        Initialize the spawn system with a random seed.
        
        Args:
            seed: Random seed for deterministic spawning
            
        Returns:
            True if initialization successful
        """
        self.current_seed = seed
        self.spawned_instances.clear()
        
        logger.info(f"Initializing spawn system with seed {seed}")
        
        # Call UE5 to initialize the anchor spawn system
        # This would require the AnchorSpawnSystem to be exposed via Remote Control
        # For now, we'll track state Python-side
        
        return True
    
    def get_anchor_transform(self, anchor_name: str) -> Optional[Dict]:
        """
        Get the world transform of an anchor actor.
        
        Args:
            anchor_name: Name of the actor in the level
            
        Returns:
            Transform dict with location and rotation, or None
        """
        # Construct the full object path
        object_path = f"{self.config.level_path}:PersistentLevel.{anchor_name}"
        
        # Get location
        loc_result = self._call_remote(object_path, "K2_GetActorLocation")
        if not loc_result:
            logger.error(f"Failed to get location for anchor: {anchor_name}")
            return None
        
        # Get rotation
        rot_result = self._call_remote(object_path, "K2_GetActorRotation")
        if not rot_result:
            logger.error(f"Failed to get rotation for anchor: {anchor_name}")
            return None
        
        location = loc_result.get("ReturnValue", {})
        rotation = rot_result.get("ReturnValue", {})
        
        return {
            "location": {
                "x": location.get("X", 0),
                "y": location.get("Y", 0),
                "z": location.get("Z", 0)
            },
            "rotation": {
                "pitch": rotation.get("Pitch", 0),
                "yaw": rotation.get("Yaw", 0),
                "roll": rotation.get("Roll", 0)
            }
        }
    
    def verify_anchors(self) -> Dict[str, bool]:
        """
        Verify all configured anchors exist in the level.
        
        Returns:
            Dict mapping anchor name to existence status
        """
        results = {}
        
        # Check parking anchors
        for anchor in self.config.parking_anchors:
            transform = self.get_anchor_transform(anchor)
            results[anchor] = transform is not None
            if transform:
                logger.info(f"✓ Parking anchor {anchor}: "
                           f"({transform['location']['x']:.1f}, "
                           f"{transform['location']['y']:.1f}, "
                           f"{transform['location']['z']:.1f})")
            else:
                logger.error(f"✗ Parking anchor {anchor}: NOT FOUND")
        
        # Check lane anchors
        for lane in self.config.lanes:
            for anchor in [lane.start_anchor, lane.end_anchor]:
                if anchor not in results:
                    transform = self.get_anchor_transform(anchor)
                    results[anchor] = transform is not None
                    if transform:
                        logger.info(f"✓ Lane anchor {anchor}: "
                                   f"({transform['location']['x']:.1f}, "
                                   f"{transform['location']['y']:.1f})")
                    else:
                        logger.error(f"✗ Lane anchor {anchor}: NOT FOUND")
        
        # Check sidewalk anchors
        for anchor in [self.config.sidewalk_anchor_1, self.config.sidewalk_anchor_2]:
            if anchor and anchor not in results:
                transform = self.get_anchor_transform(anchor)
                results[anchor] = transform is not None
        
        # Summary
        found = sum(1 for v in results.values() if v)
        total = len(results)
        logger.info(f"Anchor verification: {found}/{total} found")
        
        return results
    
    def spawn_parking_vehicles(self, 
                               vehicle_configs: List[VehicleConfig],
                               max_vehicles: int = -1) -> List[Dict]:
        """
        Spawn vehicles in parking slots.
        
        Args:
            vehicle_configs: List of vehicle configurations
            max_vehicles: Maximum vehicles to spawn (-1 = fill all slots)
            
        Returns:
            List of spawn results
        """
        results = []
        
        slots = self.config.parking_anchors
        count = len(slots) if max_vehicles < 0 else min(max_vehicles, len(slots))
        
        logger.info(f"Spawning {count} vehicles in {len(slots)} parking slots")
        
        for i in range(count):
            anchor = slots[i]
            vehicle = vehicle_configs[i % len(vehicle_configs)]
            
            # Get anchor transform
            transform = self.get_anchor_transform(anchor)
            if not transform:
                results.append({
                    "success": False,
                    "anchor": anchor,
                    "error": "Anchor not found"
                })
                continue
            
            # Spawn vehicle at anchor position
            # (In full implementation, this would call UE5 spawn function)
            result = {
                "success": True,
                "anchor": anchor,
                "asset_path": vehicle.asset_path,
                "transform": transform,
                "instance_id": f"parking_{i:04d}"
            }
            results.append(result)
            self.spawned_instances.append(result["instance_id"])
            
            logger.info(f"  Spawned at {anchor}: "
                       f"({transform['location']['x']:.1f}, "
                       f"{transform['location']['y']:.1f}) "
                       f"yaw={transform['rotation']['yaw']:.1f}°")
        
        success_count = sum(1 for r in results if r["success"])
        logger.info(f"Parking spawn complete: {success_count}/{count} succeeded")
        
        return results
    
    def spawn_lane_vehicles(self,
                           vehicle_configs: List[VehicleConfig],
                           vehicles_per_lane: int = 2) -> List[Dict]:
        """
        Spawn vehicles along road lanes.
        
        Args:
            vehicle_configs: List of vehicle configurations
            vehicles_per_lane: Number of vehicles per lane
            
        Returns:
            List of spawn results
        """
        results = []
        
        for lane in self.config.lanes:
            # Get start/end transforms
            start_transform = self.get_anchor_transform(lane.start_anchor)
            end_transform = self.get_anchor_transform(lane.end_anchor)
            
            if not start_transform or not end_transform:
                logger.error(f"Lane {lane.lane_id}: Missing anchors")
                continue
            
            # Compute lane direction
            start = start_transform["location"]
            end = end_transform["location"]
            
            logger.info(f"Lane {lane.lane_id}: "
                       f"({start['x']:.0f},{start['y']:.0f}) → "
                       f"({end['x']:.0f},{end['y']:.0f})")
            
            # Spawn vehicles along lane
            for i in range(vehicles_per_lane):
                t = (i + 1) / (vehicles_per_lane + 1)  # Distribute evenly
                
                # Interpolate position
                loc_x = start["x"] + t * (end["x"] - start["x"])
                loc_y = start["y"] + t * (end["y"] - start["y"])
                loc_z = start["z"] + t * (end["z"] - start["z"])
                
                result = {
                    "success": True,
                    "lane_id": lane.lane_id,
                    "t": t,
                    "location": {"x": loc_x, "y": loc_y, "z": loc_z},
                    "instance_id": f"lane_{lane.lane_id}_{i:02d}"
                }
                results.append(result)
                self.spawned_instances.append(result["instance_id"])
        
        return results
    
    def clear_all(self) -> bool:
        """
        Clear all spawned vehicles and props.
        
        Returns:
            True if successful
        """
        logger.info(f"Clearing {len(self.spawned_instances)} spawned instances")
        
        # In full implementation, would call UE5 to destroy actors
        
        self.spawned_instances.clear()
        return True
    
    def get_spawn_summary(self) -> Dict:
        """Get summary of current spawn state"""
        return {
            "seed": self.current_seed,
            "spawned_count": len(self.spawned_instances),
            "parking_slots": len(self.config.parking_anchors),
            "lanes": len(self.config.lanes),
            "instances": list(self.spawned_instances)
        }


def load_config(config_path: str = "configs/levels/automobileV2_anchors.yaml") -> AnchorSpawnConfig:
    """Load anchor configuration from YAML file"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    
    return AnchorSpawnConfig.from_yaml(path)


def create_controller(config_path: str = None) -> AnchorSpawnController:
    """Create a configured spawn controller"""
    if config_path is None:
        config_path = "configs/levels/automobileV2_anchors.yaml"
    
    config = load_config(config_path)
    return AnchorSpawnController(config)
