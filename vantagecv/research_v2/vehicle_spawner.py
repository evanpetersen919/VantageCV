"""
Research v2 - MODULE 2: Vehicle Spawner

Responsibilities:
- Spawn N vehicles per frame
- Enforce realistic lane placement
- Maintain class balance across dataset

Vehicle count distribution (fixed for v1):
- 1 vehicle: 20%
- 2–4 vehicles: 50%
- 5–6 vehicles: 30%

Per-vehicle randomization:
- Class (weighted)
- Model variant (if available)
- Color
- Scale jitter ±5%
- Position offset within lane
- Static only (no motion in v1)

Logging (REQUIRED):
- Spawn request received
- Vehicle count sampled
- For each vehicle: instance_id, class, world transform, scale
- Spawn success / failure reason
"""

from dataclasses import dataclass, field
from typing import Optional
import random
import uuid

from .logging_utils import ResearchLogger
from .config import VehicleSpawnerConfig, VehicleClass, SceneConfig


@dataclass
class VehicleTransform:
    """3D transform for a vehicle."""
    x: float = 0.0       # Forward position (meters)
    y: float = 0.0       # Lateral position (meters)
    z: float = 0.0       # Height (meters)
    yaw: float = 0.0     # Rotation around Z (degrees)
    pitch: float = 0.0   # Rotation around Y (degrees)
    roll: float = 0.0    # Rotation around X (degrees)
    
    def to_dict(self) -> dict:
        return {
            "position": {"x": self.x, "y": self.y, "z": self.z},
            "rotation": {"yaw": self.yaw, "pitch": self.pitch, "roll": self.roll},
        }


@dataclass
class SpawnedVehicle:
    """Represents a spawned vehicle instance."""
    instance_id: str
    vehicle_class: VehicleClass
    actor_name: str            # UE5 actor name (e.g., "Car_1")
    transform: VehicleTransform
    scale: float
    color: tuple[int, int, int]  # RGB
    lane_index: int
    
    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "class": self.vehicle_class.value,
            "class_id": VehicleClass.get_id(self.vehicle_class),
            "actor_name": self.actor_name,
            "transform": self.transform.to_dict(),
            "scale": self.scale,
            "color": {"r": self.color[0], "g": self.color[1], "b": self.color[2]},
            "lane_index": self.lane_index,
        }


@dataclass
class SpawnResult:
    """Result of a spawn operation."""
    success: bool
    vehicles: list[SpawnedVehicle] = field(default_factory=list)
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


class VehicleSpawner:
    """
    MODULE 2 - Vehicle Spawner
    
    Spawns vehicles with realistic placement and class distribution.
    """
    
    MODULE_NAME = "VehicleSpawner"
    
    # Default vehicle dimensions for collision checking (length, width in meters)
    VEHICLE_DIMENSIONS = {
        VehicleClass.CAR: (4.5, 1.8),
        VehicleClass.TRUCK: (6.0, 2.2),
        VehicleClass.BUS: (12.0, 2.5),
        VehicleClass.MOTORCYCLE: (2.2, 0.8),
        VehicleClass.BICYCLE: (1.8, 0.6),
    }
    
    # Default vehicle colors (common colors)
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
        config: VehicleSpawnerConfig,
        scene_config: SceneConfig,
        logger: Optional[ResearchLogger] = None,
    ):
        """
        Initialize vehicle spawner.
        
        Args:
            config: Vehicle spawner configuration
            scene_config: Scene configuration for lane info
            logger: Optional logger
        """
        self.config = config
        self.scene_config = scene_config
        self.logger = logger or ResearchLogger(self.MODULE_NAME)
        self._rng = random.Random()
        
        # Statistics tracking
        self._total_spawned = 0
        self._class_counts: dict[str, int] = {c.value: 0 for c in VehicleClass}
        self._spawn_failures = 0
        
        self.logger.log_init(
            spawn_x_range=(config.spawn_x_min, config.spawn_x_max),
            scale_jitter=config.scale_jitter,
            position_jitter=config.position_jitter,
            min_spacing=config.min_spacing,
            class_weights=config.class_weights,
        )
    
    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)
        self.logger.debug("Random seed set", seed=seed)
    
    def sample_vehicle_count(self) -> int:
        """
        Sample number of vehicles based on distribution.
        
        Distribution:
        - 1 vehicle: 20%
        - 2-4 vehicles: 50%
        - 5-6 vehicles: 30%
        
        Returns:
            Number of vehicles to spawn
        """
        r = self._rng.random()
        
        if r < 0.20:
            count = 1
        elif r < 0.70:  # 0.20 + 0.50
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
        """
        Sample vehicle class based on weights.
        
        Returns:
            Sampled vehicle class
        """
        classes = list(VehicleClass)
        weights = [self.config.class_weights.get(c.value, 0.2) for c in classes]
        
        # Normalize weights
        total = sum(weights)
        weights = [w / total for w in weights]
        
        chosen = self._rng.choices(classes, weights=weights, k=1)[0]
        
        self.logger.debug(
            "Vehicle class sampled",
            vehicle_class=chosen.value,
        )
        
        return chosen
    
    def sample_actor(self, vehicle_class: VehicleClass) -> str:
        """
        Sample actor name for vehicle class.
        
        Args:
            vehicle_class: Vehicle class to get actor for
            
        Returns:
            Actor name string (e.g., "Car_1")
        """
        actors = self.config.vehicle_actors.get(vehicle_class.value, [])
        
        if not actors:
            # Use placeholder
            return f"{vehicle_class.value.title()}_Placeholder"
        
        return self._rng.choice(actors)
    
    def sample_color(self) -> tuple[int, int, int]:
        """Sample a random vehicle color."""
        return self._rng.choice(self.VEHICLE_COLORS)
    
    def sample_scale(self) -> float:
        """
        Sample scale with jitter.
        
        Returns:
            Scale factor (1.0 ± jitter)
        """
        jitter = self.config.scale_jitter
        return 1.0 + self._rng.uniform(-jitter, jitter)
    
    def sample_position(
        self,
        lane_index: int,
        existing_vehicles: list[SpawnedVehicle],
        vehicle_class: VehicleClass,
    ) -> Optional[VehicleTransform]:
        """
        Sample valid position for vehicle.
        
        Args:
            lane_index: Lane to spawn in
            existing_vehicles: Already spawned vehicles (for collision check)
            vehicle_class: Class of vehicle being spawned
            
        Returns:
            Transform if valid position found, None otherwise
        """
        # Get lane Y position
        lane_y = self.scene_config.lane_positions[lane_index]
        
        # Add lateral jitter
        y_jitter = self._rng.uniform(-self.config.position_jitter, 
                                      self.config.position_jitter)
        y = lane_y + y_jitter
        
        # Get vehicle dimensions
        length, width = self.VEHICLE_DIMENSIONS[vehicle_class]
        
        # Try to find valid X position
        max_attempts = 20
        for attempt in range(max_attempts):
            # Sample X position
            x = self._rng.uniform(self.config.spawn_x_min, self.config.spawn_x_max)
            
            # Check collision with existing vehicles
            is_valid = True
            for existing in existing_vehicles:
                ex_length, _ = self.VEHICLE_DIMENSIONS[existing.vehicle_class]
                
                # Check X overlap with spacing
                x_dist = abs(x - existing.transform.x)
                min_x_dist = (length + ex_length) / 2 + self.config.min_spacing
                
                # Check Y overlap (lane collision)
                y_dist = abs(y - existing.transform.y)
                min_y_dist = self.scene_config.lane_width * 0.8  # Allow some lane sharing
                
                if x_dist < min_x_dist and y_dist < min_y_dist:
                    is_valid = False
                    break
            
            if is_valid:
                transform = VehicleTransform(
                    x=x,
                    y=y,
                    z=0.0,  # Ground level
                    yaw=0.0,  # Facing forward
                )
                
                self.logger.debug(
                    "Position sampled",
                    x=x,
                    y=y,
                    lane_index=lane_index,
                    attempts=attempt + 1,
                )
                
                return transform
        
        # Failed to find valid position
        self.logger.warning(
            "Failed to find valid position",
            lane_index=lane_index,
            vehicle_class=vehicle_class.value,
            existing_count=len(existing_vehicles),
            max_attempts=max_attempts,
        )
        return None
    
    def spawn_vehicles(self, count: Optional[int] = None) -> SpawnResult:
        """
        Spawn vehicles for current frame.
        
        Args:
            count: Number of vehicles (sampled if not provided)
            
        Returns:
            SpawnResult with spawned vehicles
        """
        if count is None:
            count = self.sample_vehicle_count()
        
        self.logger.log_input(
            "Spawn request received",
            requested_count=count,
        )
        
        vehicles: list[SpawnedVehicle] = []
        failures: list[dict] = []
        
        for i in range(count):
            # Sample vehicle properties
            vehicle_class = self.sample_vehicle_class()
            lane_index = self._rng.randint(0, self.scene_config.num_lanes - 1)
            
            # Try to sample valid position
            transform = self.sample_position(lane_index, vehicles, vehicle_class)
            
            if transform is None:
                failure = {
                    "index": i,
                    "class": vehicle_class.value,
                    "lane_index": lane_index,
                    "reason": "No valid position found",
                    "suggested_fix": "Reduce vehicle count or increase lane spacing",
                }
                failures.append(failure)
                self._spawn_failures += 1
                
                self.logger.error(
                    "Spawn failed",
                    **failure,
                )
                continue
            
            # Create vehicle instance
            instance_id = f"vehicle_{uuid.uuid4().hex[:8]}"
            
            vehicle = SpawnedVehicle(
                instance_id=instance_id,
                vehicle_class=vehicle_class,
                actor_name=self.sample_actor(vehicle_class),
                transform=transform,
                scale=self.sample_scale(),
                color=self.sample_color(),
                lane_index=lane_index,
            )
            
            vehicles.append(vehicle)
            self._total_spawned += 1
            self._class_counts[vehicle_class.value] += 1
            
            self.logger.info(
                "Vehicle spawned",
                instance_id=instance_id,
                vehicle_class=vehicle_class.value,
                position={"x": transform.x, "y": transform.y, "z": transform.z},
                scale=vehicle.scale,
                lane_index=lane_index,
            )
        
        # Create result
        success = len(vehicles) > 0
        result = SpawnResult(
            success=success,
            vehicles=vehicles,
            requested_count=count,
            actual_count=len(vehicles),
            failures=failures,
        )
        
        self.logger.log_output(
            "Spawn completed",
            success=success,
            requested=count,
            spawned=len(vehicles),
            failed=len(failures),
        )
        
        return result
    
    def get_statistics(self) -> dict:
        """Get spawning statistics."""
        total = self._total_spawned
        return {
            "total_spawned": total,
            "spawn_failures": self._spawn_failures,
            "class_distribution": {
                cls: count / max(total, 1)
                for cls, count in self._class_counts.items()
            },
            "class_counts": self._class_counts.copy(),
        }
    
    def reset_statistics(self) -> None:
        """Reset all statistics counters."""
        self._total_spawned = 0
        self._class_counts = {c.value: 0 for c in VehicleClass}
        self._spawn_failures = 0
        self.logger.info("Statistics reset")
    
    def get_ue5_spawn_commands(self, vehicles: list[SpawnedVehicle]) -> list[dict]:
        """
        Convert vehicles to UE5 visibility/positioning commands.
        
        Uses visibility-based spawning:
        1. Hide all vehicle actors
        2. Show and reposition selected actors
        
        Args:
            vehicles: List of vehicles to spawn
            
        Returns:
            List of command dictionaries for UE5
        """
        commands = []
        
        # First: hide all vehicle actors
        for class_name, actors in self.config.vehicle_actors.items():
            for actor_name in actors:
                commands.append({
                    "type": "set_visibility",
                    "actor_name": actor_name,
                    "visible": False,
                })
        
        # Get world offset from config (camera position in level)
        offset_x = getattr(self.config, 'world_offset_x', 0.0)
        offset_y = getattr(self.config, 'world_offset_y', 0.0)
        offset_z = getattr(self.config, 'world_offset_z', 0.0)
        
        # Then: show and position selected vehicles
        for vehicle in vehicles:
            commands.append({
                "type": "set_visibility",
                "actor_name": vehicle.actor_name,
                "visible": True,
            })
            
            # Convert spawn coordinates (meters) to world coordinates (cm)
            # Spawn X (forward) maps to UE5 X, Spawn Y (lateral) maps to UE5 Y
            world_x = vehicle.transform.x * 100 + offset_x
            world_y = vehicle.transform.y * 100 + offset_y
            world_z = vehicle.transform.z * 100 + offset_z
            
            commands.append({
                "type": "set_transform",
                "actor_name": vehicle.actor_name,
                "location": {
                    "x": world_x,
                    "y": world_y,
                    "z": world_z,
                },
                "rotation": {
                    "yaw": vehicle.transform.yaw,
                    "pitch": vehicle.transform.pitch,
                    "roll": vehicle.transform.roll,
                },
                "scale": vehicle.scale,
            })
        
        return commands
    
    def validate(self) -> tuple[bool, list[str]]:
        """Validate spawner configuration."""
        issues = []
        
        # Check class weights sum to ~1
        total_weight = sum(self.config.class_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            issues.append(f"Class weights sum to {total_weight}, should be 1.0")
        
        # Check spawn range
        if self.config.spawn_x_min >= self.config.spawn_x_max:
            issues.append("spawn_x_min must be less than spawn_x_max")
        
        # Check for missing actors
        for cls in VehicleClass:
            if cls.value not in self.config.vehicle_actors:
                issues.append(f"No actors defined for class {cls.value}")
            elif not self.config.vehicle_actors[cls.value]:
                issues.append(f"Empty actor list for class {cls.value}")
        
        is_valid = len(issues) == 0
        
        if is_valid:
            self.logger.info("Spawner configuration validated successfully")
        else:
            for issue in issues:
                self.logger.warning("Spawner validation issue", issue=issue)
        
        return is_valid, issues
