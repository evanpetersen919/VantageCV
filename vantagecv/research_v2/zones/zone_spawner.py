"""
Zone-Based Vehicle Spawner

Replaces old placement heuristics with strict zone-based spawning.
Vehicles may ONLY spawn inside valid zones.

Key differences from legacy spawner:
- No fallback spawning
- No random placement outside zones
- Explicit failure logging
- Zone capacity enforcement
"""

from dataclasses import dataclass, field
from typing import Optional
import random
import uuid

from .zone_types import ZoneType
from .zone_data import (
    Zone, RoadZone, ParkingZone,
    Vector3, Transform3D, Rotation3, ParkingSlot,
)
from .zone_registry import ZoneRegistry, SpawnAllocation
from ..config import VehicleClass, VehicleSpawnerConfig, SceneConfig
from ..logging_utils import ResearchLogger


@dataclass
class ZoneSpawnedVehicle:
    """Represents a vehicle spawned via the zone system."""
    instance_id: str
    vehicle_class: VehicleClass
    actor_name: str
    transform: Transform3D
    dimensions: "VehicleDimensions"
    color: tuple[int, int, int]
    
    # Zone tracking
    zone_id: str
    zone_type: ZoneType
    slot_id: Optional[str] = None  # For parking zones
    
    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "class": self.vehicle_class.value,
            "class_id": VehicleClass.get_id(self.vehicle_class),
            "actor_name": self.actor_name,
            "transform": self.transform.to_dict(),
            "dimensions": self.dimensions.to_dict(),
            "color": {"r": self.color[0], "g": self.color[1], "b": self.color[2]},
            "zone_id": self.zone_id,
            "zone_type": self.zone_type.value,
            "slot_id": self.slot_id,
        }


@dataclass
class VehicleDimensions:
    """Vehicle dimensions in meters."""
    length: float
    width: float
    height: float
    
    def to_dict(self) -> dict:
        return {"length": self.length, "width": self.width, "height": self.height}


@dataclass
class ZoneSpawnResult:
    """Result of a zone-based spawn operation."""
    success: bool
    vehicles: list[ZoneSpawnedVehicle] = field(default_factory=list)
    requested_count: int = 0
    actual_count: int = 0
    failures: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "requested_count": self.requested_count,
            "actual_count": self.actual_count,
            "vehicles": [v.to_dict() for v in self.vehicles],
            "failures": self.failures,
        }


class ZoneBasedSpawner:
    """
    Zone-based vehicle spawner.
    
    STRICT RULES:
    1. Vehicles may spawn ONLY inside valid zones
    2. If no valid zone exists: ABORT spawn, LOG error
    3. NO fallback spawning
    4. NO "place anyway"
    
    Usage:
        registry = ZoneRegistry()
        registry.load_from_manifest("zones.yaml")
        
        spawner = ZoneBasedSpawner(registry, config, scene_config)
        result = spawner.spawn_vehicles(count=5)
    """
    
    MODULE_NAME = "ZoneBasedSpawner"
    
    # Default vehicle dimensions (length, width, height in meters)
    VEHICLE_DIMENSIONS = {
        VehicleClass.CAR: VehicleDimensions(4.5, 1.8, 1.5),
        VehicleClass.TRUCK: VehicleDimensions(6.0, 2.2, 2.5),
        VehicleClass.BUS: VehicleDimensions(12.0, 2.5, 3.5),
        VehicleClass.MOTORCYCLE: VehicleDimensions(2.2, 0.8, 1.2),
        VehicleClass.BICYCLE: VehicleDimensions(1.8, 0.6, 1.1),
    }
    
    # Default vehicle colors
    VEHICLE_COLORS = [
        (255, 255, 255),  # White
        (0, 0, 0),        # Black
        (128, 128, 128),  # Gray
        (192, 192, 192),  # Silver
        (255, 0, 0),      # Red
        (0, 0, 255),      # Blue
        (0, 128, 0),      # Green
        (255, 255, 0),    # Yellow
    ]
    
    def __init__(
        self,
        registry: ZoneRegistry,
        config: VehicleSpawnerConfig,
        scene_config: SceneConfig,
        logger: Optional[ResearchLogger] = None,
    ):
        """
        Initialize zone-based spawner.
        
        Args:
            registry: Zone registry (must be loaded and validated)
            config: Spawner configuration
            scene_config: Scene configuration
            logger: Optional logger
        """
        self.registry = registry
        self.config = config
        self.scene_config = scene_config
        self.logger = logger or ResearchLogger(self.MODULE_NAME)
        self._rng = random.Random()
        
        # Actor pool (from config)
        self._actor_pool: dict[VehicleClass, list[str]] = {}
        for class_name, actors in config.vehicle_actors.items():
            self._actor_pool[VehicleClass(class_name)] = list(actors)
        
        # Track used actors per frame
        self._used_actors_this_frame: set[str] = set()
        
        # Statistics
        self._total_spawned = 0
        self._class_counts: dict[str, int] = {c.value: 0 for c in VehicleClass}
        self._spawn_failures = 0
        self._zone_failures: dict[str, int] = {}
        
        self.logger.log_init(
            zone_count=registry.zone_count,
            road_zones=registry.road_zone_count,
            parking_zones=registry.parking_zone_count,
            class_weights=config.class_weights,
        )
    
    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)
        self.logger.debug("Random seed set", seed=seed)
    
    def reset_frame(self) -> None:
        """Reset per-frame state. Call before each frame."""
        self._used_actors_this_frame.clear()
        self.registry.release_all_allocations()
    
    def validate_config(self) -> bool:
        """
        Validate spawner configuration.
        
        Returns:
            True if configuration is valid
        """
        # Check registry has zones
        if self.registry.zone_count == 0:
            self.logger.error(
                "No zones registered",
                suggested_fix="Load zone manifest with registry.load_from_manifest()",
            )
            return False
        
        # Validate registry
        valid, errors = self.registry.validate()
        if not valid:
            for error in errors:
                self.logger.error("Zone validation error", error=error)
            return False
        
        # Check at least one spawn zone exists
        spawn_zones = (
            self.registry.road_zone_count +
            self.registry.parking_zone_count
        )
        if spawn_zones == 0:
            self.logger.error(
                "No spawn zones registered (road or parking)",
                suggested_fix="Add road or parking zones to manifest",
            )
            return False
        
        self.logger.info("Spawner configuration validated")
        return True
    
    # ========================================
    # VEHICLE SAMPLING
    # ========================================
    
    def sample_vehicle_count(self) -> int:
        """Sample number of vehicles based on distribution."""
        r = self._rng.random()
        
        if r < 0.20:
            count = 1
        elif r < 0.70:
            count = self._rng.randint(2, 4)
        else:
            count = self._rng.randint(5, 6)
        
        self.logger.debug(
            "Vehicle count sampled",
            count=count,
            random_value=r,
        )
        return count
    
    def sample_vehicle_class(self) -> VehicleClass:
        """Sample vehicle class based on weights."""
        weights = self.config.class_weights
        classes = list(weights.keys())
        probs = list(weights.values())
        
        selected = self._rng.choices(classes, weights=probs, k=1)[0]
        return VehicleClass(selected)
    
    def sample_color(self) -> tuple[int, int, int]:
        """Sample a random vehicle color."""
        return self._rng.choice(self.VEHICLE_COLORS)
    
    # ========================================
    # ACTOR SELECTION
    # ========================================
    
    def select_actor(self, vehicle_class: VehicleClass) -> Optional[str]:
        """
        Select an unused actor for the vehicle class.
        
        Returns:
            Actor name or None if no actors available
        """
        if vehicle_class not in self._actor_pool:
            self.logger.error(
                "No actors defined for vehicle class",
                vehicle_class=vehicle_class.value,
                suggested_fix=f"Add {vehicle_class.value} actors to config",
            )
            return None
        
        available = [
            a for a in self._actor_pool[vehicle_class]
            if a not in self._used_actors_this_frame
        ]
        
        if not available:
            self.logger.warning(
                "No available actors for vehicle class",
                vehicle_class=vehicle_class.value,
                total_actors=len(self._actor_pool[vehicle_class]),
                used_actors=len(self._used_actors_this_frame),
            )
            return None
        
        actor = self._rng.choice(available)
        self._used_actors_this_frame.add(actor)
        
        return actor
    
    # ========================================
    # SPAWNING
    # ========================================
    
    def spawn_vehicles(
        self,
        count: Optional[int] = None,
        zone_type: Optional[ZoneType] = None,
        preferred_zone_id: Optional[str] = None,
    ) -> ZoneSpawnResult:
        """
        Spawn vehicles using zone-based placement.
        
        This is the PRIMARY spawn API.
        
        Args:
            count: Number of vehicles (or sample from distribution)
            zone_type: Filter by zone type (ROAD, PARKING)
            preferred_zone_id: Preferred zone ID
            
        Returns:
            ZoneSpawnResult with spawned vehicles or failure info
        """
        if count is None:
            count = self.sample_vehicle_count()
        
        self.logger.log_input(
            "Spawn request received",
            requested_count=count,
            zone_type=zone_type.value if zone_type else None,
            preferred_zone_id=preferred_zone_id,
        )
        
        result = ZoneSpawnResult(
            success=True,
            requested_count=count,
        )
        
        for i in range(count):
            spawn_result = self._spawn_single_vehicle(
                zone_type=zone_type,
                preferred_zone_id=preferred_zone_id,
            )
            
            if spawn_result:
                result.vehicles.append(spawn_result)
                result.actual_count += 1
            else:
                result.failures.append({
                    "index": i,
                    "reason": "Spawn failed (see logs)",
                })
        
        if result.actual_count == 0:
            result.success = False
            self.logger.error(
                "All spawn attempts failed",
                requested_count=count,
                failures=result.failures,
            )
        elif result.actual_count < count:
            self.logger.warning(
                "Partial spawn success",
                requested_count=count,
                actual_count=result.actual_count,
                failures=result.failures,
            )
        else:
            self.logger.log_output(
                "Spawn completed",
                success=True,
                requested=count,
                spawned=result.actual_count,
                failed=len(result.failures),
            )
        
        return result
    
    def _spawn_single_vehicle(
        self,
        zone_type: Optional[ZoneType] = None,
        preferred_zone_id: Optional[str] = None,
    ) -> Optional[ZoneSpawnedVehicle]:
        """Spawn a single vehicle."""
        
        # 1. Sample vehicle class
        vehicle_class = self.sample_vehicle_class()
        
        self.logger.debug(
            "Vehicle class sampled",
            vehicle_class=vehicle_class.value,
        )
        
        # 2. Select actor
        actor_name = self.select_actor(vehicle_class)
        if not actor_name:
            self._spawn_failures += 1
            self.logger.error(
                "No actor available",
                vehicle_class=vehicle_class.value,
                module=self.MODULE_NAME,
                level="ERROR",
                reason="No available actors for vehicle class",
                suggested_fix="Add more actors or reduce vehicle count",
            )
            return None
        
        # 3. Allocate spawn position from zone
        allocation = self.registry.allocate_spawn(
            vehicle_class=vehicle_class,
            zone_type=zone_type,
            preferred_zone_id=preferred_zone_id,
        )
        
        if not allocation.success:
            self._spawn_failures += 1
            self._zone_failures[allocation.failure_reason or "unknown"] = (
                self._zone_failures.get(allocation.failure_reason or "unknown", 0) + 1
            )
            
            # STRICT: Log failure with structured format
            self.logger.error(
                "Zone allocation failed",
                module=self.MODULE_NAME,
                level="ERROR",
                reason=allocation.failure_reason,
                vehicle_class=vehicle_class.value,
                zone_id=allocation.zone.zone_id if allocation.zone else None,
                suggested_fix=allocation.suggested_fix,
            )
            
            # NO FALLBACK - return None
            return None
        
        # 4. Build vehicle data
        instance_id = f"vehicle_{uuid.uuid4().hex[:8]}"
        dimensions = self.VEHICLE_DIMENSIONS[vehicle_class]
        color = self.sample_color()
        
        vehicle = ZoneSpawnedVehicle(
            instance_id=instance_id,
            vehicle_class=vehicle_class,
            actor_name=actor_name,
            transform=allocation.transform,
            dimensions=dimensions,
            color=color,
            zone_id=allocation.zone.zone_id,
            zone_type=allocation.zone.zone_type,
            slot_id=allocation.slot.slot_id if allocation.slot else None,
        )
        
        # Update statistics
        self._total_spawned += 1
        self._class_counts[vehicle_class.value] += 1
        
        self.logger.debug(
            "Vehicle spawned",
            instance_id=instance_id,
            vehicle_class=vehicle_class.value,
            actor_name=actor_name,
            zone_id=vehicle.zone_id,
            zone_type=vehicle.zone_type.value,
            slot_id=vehicle.slot_id,
            position=allocation.transform.position.to_dict() if allocation.transform else None,
        )
        
        return vehicle
    
    # ========================================
    # CONVENIENCE METHODS
    # ========================================
    
    def spawn_in_parking(
        self,
        count: int = 1,
        zone_id: Optional[str] = None,
    ) -> ZoneSpawnResult:
        """Spawn vehicles specifically in parking zones."""
        return self.spawn_vehicles(
            count=count,
            zone_type=ZoneType.PARKING,
            preferred_zone_id=zone_id,
        )
    
    def spawn_on_road(
        self,
        count: int = 1,
        zone_id: Optional[str] = None,
    ) -> ZoneSpawnResult:
        """Spawn vehicles specifically on road zones."""
        return self.spawn_vehicles(
            count=count,
            zone_type=ZoneType.ROAD,
            preferred_zone_id=zone_id,
        )
    
    # ========================================
    # UE5 COMMAND GENERATION
    # ========================================
    
    def get_ue5_spawn_commands(
        self,
        vehicles: list[ZoneSpawnedVehicle],
    ) -> list[dict]:
        """
        Generate UE5 Remote Control API commands for spawning.
        
        Args:
            vehicles: List of vehicles to spawn
            
        Returns:
            List of command dictionaries
        """
        commands = []
        
        # World offset from config (centimeters)
        world_offset_x = self.config.world_offset_x
        world_offset_y = self.config.world_offset_y
        world_offset_z = self.config.world_offset_z
        
        for vehicle in vehicles:
            actor_path = f"/Game/{self.scene_config.level_path.split('/')[-1]}.{self.scene_config.level_path.split('/')[-1]}:PersistentLevel.{vehicle.actor_name}"
            
            # Convert from meters to centimeters and apply world offset
            pos = vehicle.transform.position
            world_x = world_offset_x + pos.x * 100
            world_y = world_offset_y + pos.y * 100
            world_z = world_offset_z + pos.z * 100
            
            rot = vehicle.transform.rotation
            
            # Set visibility
            commands.append({
                "type": "function",
                "actor_path": actor_path,
                "function": "SetActorHiddenInGame",
                "params": {"bNewHidden": False},
            })
            
            # Set location
            commands.append({
                "type": "function",
                "actor_path": actor_path,
                "function": "K2_SetActorLocation",
                "params": {
                    "NewLocation": {
                        "X": world_x,
                        "Y": world_y,
                        "Z": world_z,
                    },
                    "bSweep": False,
                    "bTeleport": True,
                },
            })
            
            # Set rotation
            commands.append({
                "type": "function",
                "actor_path": actor_path,
                "function": "K2_SetActorRotation",
                "params": {
                    "NewRotation": {
                        "Pitch": rot.pitch,
                        "Yaw": rot.yaw,
                        "Roll": rot.roll,
                    },
                    "bTeleportPhysics": True,
                },
            })
        
        return commands
    
    # ========================================
    # STATISTICS
    # ========================================
    
    def get_statistics(self) -> dict:
        """Get spawner statistics."""
        return {
            "total_spawned": self._total_spawned,
            "class_counts": self._class_counts.copy(),
            "spawn_failures": self._spawn_failures,
            "zone_failures": self._zone_failures.copy(),
            "used_actors_this_frame": len(self._used_actors_this_frame),
            "registry_stats": self.registry.get_statistics(),
        }
