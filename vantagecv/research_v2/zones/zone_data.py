"""
Zone Data Structures

Immutable data classes representing zones and their properties.
All zones are explicitly defined - no inference.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from .zone_types import ZoneType, ZoneShape, LaneDirection, SlotState
from ..config import VehicleClass


@dataclass(frozen=True)
class Vector3:
    """Immutable 3D vector."""
    x: float
    y: float
    z: float
    
    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "z": self.z}
    
    @classmethod
    def from_dict(cls, data: dict) -> "Vector3":
        return cls(
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            z=float(data.get("z", 0)),
        )
    
    def __add__(self, other: "Vector3") -> "Vector3":
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other: "Vector3") -> "Vector3":
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)


@dataclass(frozen=True)
class Rotation3:
    """Immutable 3D rotation (Euler angles in degrees)."""
    pitch: float = 0.0  # Rotation around Y
    yaw: float = 0.0    # Rotation around Z
    roll: float = 0.0   # Rotation around X
    
    def to_dict(self) -> dict:
        return {"pitch": self.pitch, "yaw": self.yaw, "roll": self.roll}
    
    @classmethod
    def from_dict(cls, data: dict) -> "Rotation3":
        return cls(
            pitch=float(data.get("pitch", 0)),
            yaw=float(data.get("yaw", 0)),
            roll=float(data.get("roll", 0)),
        )


@dataclass(frozen=True)
class Transform3D:
    """Immutable 3D transform (position + rotation)."""
    position: Vector3
    rotation: Rotation3 = field(default_factory=lambda: Rotation3())
    
    def to_dict(self) -> dict:
        return {
            "position": self.position.to_dict(),
            "rotation": self.rotation.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Transform3D":
        return cls(
            position=Vector3.from_dict(data.get("position", {})),
            rotation=Rotation3.from_dict(data.get("rotation", {})),
        )


@dataclass(frozen=True)
class ZoneBounds:
    """
    Zone boundary specification.
    
    For BOX shape:
        - center: Center point of the box
        - size: (length_x, width_y, height_z) in meters
        - rotation: Orientation of the box
    
    For POLYGON shape:
        - vertices: List of (x, y) points defining convex hull
        - z_min, z_max: Height range
        - center: Computed centroid (optional, for convenience)
    """
    shape: ZoneShape
    
    # BOX parameters
    center: Optional[Vector3] = None
    size: Optional[Vector3] = None  # (length, width, height)
    rotation: Optional[Rotation3] = None
    
    # POLYGON parameters
    vertices: Optional[tuple[tuple[float, float], ...]] = None
    z_min: float = 0.0
    z_max: float = 10.0  # Default 10m height allowance
    
    def to_dict(self) -> dict:
        data = {"shape": self.shape.value}
        if self.shape == ZoneShape.BOX:
            data["center"] = self.center.to_dict() if self.center else None
            data["size"] = self.size.to_dict() if self.size else None
            data["rotation"] = self.rotation.to_dict() if self.rotation else None
        else:
            data["vertices"] = list(self.vertices) if self.vertices else []
            data["z_min"] = self.z_min
            data["z_max"] = self.z_max
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "ZoneBounds":
        shape = ZoneShape.from_string(data.get("shape", "box"))
        
        if shape == ZoneShape.BOX:
            return cls(
                shape=shape,
                center=Vector3.from_dict(data.get("center", {})) if data.get("center") else None,
                size=Vector3.from_dict(data.get("size", {})) if data.get("size") else None,
                rotation=Rotation3.from_dict(data.get("rotation", {})) if data.get("rotation") else None,
            )
        else:
            vertices = data.get("vertices", [])
            return cls(
                shape=shape,
                vertices=tuple(tuple(v) for v in vertices) if vertices else None,
                z_min=float(data.get("z_min", 0)),
                z_max=float(data.get("z_max", 10)),
            )
    
    def contains_point(self, point: Vector3) -> bool:
        """Check if a point is inside the zone bounds."""
        if self.shape == ZoneShape.BOX:
            return self._box_contains(point)
        else:
            return self._polygon_contains(point)
    
    def _box_contains(self, point: Vector3) -> bool:
        """Check if point is inside axis-aligned box (rotation not yet supported)."""
        if not self.center or not self.size:
            return False
        
        half = Vector3(self.size.x / 2, self.size.y / 2, self.size.z / 2)
        min_pt = self.center - half
        max_pt = self.center + half
        
        return (
            min_pt.x <= point.x <= max_pt.x and
            min_pt.y <= point.y <= max_pt.y and
            min_pt.z <= point.z <= max_pt.z
        )
    
    def _polygon_contains(self, point: Vector3) -> bool:
        """Check if point is inside convex polygon (2D check + Z range)."""
        if not self.vertices:
            return False
        
        # Z range check
        if not (self.z_min <= point.z <= self.z_max):
            return False
        
        # 2D point-in-polygon (ray casting)
        n = len(self.vertices)
        inside = False
        x, y = point.x, point.y
        
        j = n - 1
        for i in range(n):
            xi, yi = self.vertices[i]
            xj, yj = self.vertices[j]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside


@dataclass
class ParkingSlot:
    """
    A discrete parking slot within a parking zone.
    
    Each slot:
    - Has a fixed transform
    - Can be occupied by only one vehicle
    - Is logged when used
    """
    slot_id: str
    transform: Transform3D
    allowed_classes: frozenset[VehicleClass]
    state: SlotState = SlotState.AVAILABLE
    occupied_by: Optional[str] = None  # instance_id of vehicle
    
    def to_dict(self) -> dict:
        return {
            "slot_id": self.slot_id,
            "transform": self.transform.to_dict(),
            "allowed_classes": [c.value for c in self.allowed_classes],
            "state": self.state.name,
            "occupied_by": self.occupied_by,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ParkingSlot":
        allowed = data.get("allowed_classes", ["car", "truck", "bus", "motorcycle", "bicycle"])
        return cls(
            slot_id=data["slot_id"],
            transform=Transform3D.from_dict(data.get("transform", {})),
            allowed_classes=frozenset(VehicleClass(c) for c in allowed),
            state=SlotState[data.get("state", "AVAILABLE")],
            occupied_by=data.get("occupied_by"),
        )
    
    def can_accept(self, vehicle_class: VehicleClass) -> bool:
        """Check if slot can accept the given vehicle class."""
        return (
            self.state == SlotState.AVAILABLE and
            vehicle_class in self.allowed_classes
        )
    
    def occupy(self, instance_id: str) -> None:
        """Mark slot as occupied."""
        self.state = SlotState.OCCUPIED
        self.occupied_by = instance_id
    
    def release(self) -> None:
        """Release the slot."""
        self.state = SlotState.AVAILABLE
        self.occupied_by = None


@dataclass
class Zone:
    """
    Base zone class.
    
    All zones have:
    - Unique ID
    - Asset association
    - Type
    - Bounds
    - Allowed vehicle classes
    """
    zone_id: str
    asset_id: str  # ID of the asset this zone belongs to
    zone_type: ZoneType
    bounds: ZoneBounds
    allowed_classes: frozenset[VehicleClass]
    max_vehicles: Optional[int] = None  # None = unlimited
    enabled: bool = True
    
    # Runtime tracking
    current_vehicle_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "asset_id": self.asset_id,
            "zone_type": self.zone_type.value,
            "bounds": self.bounds.to_dict(),
            "allowed_classes": [c.value for c in self.allowed_classes],
            "max_vehicles": self.max_vehicles,
            "enabled": self.enabled,
            "current_vehicle_count": self.current_vehicle_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Zone":
        zone_type = ZoneType.from_string(data["zone_type"])
        allowed = data.get("allowed_classes", ["car", "truck", "bus", "motorcycle", "bicycle"])
        
        # Dispatch to specialized zone types
        if zone_type == ZoneType.ROAD:
            return RoadZone.from_dict(data)
        elif zone_type == ZoneType.PARKING:
            return ParkingZone.from_dict(data)
        elif zone_type == ZoneType.EXCLUSION:
            return ExclusionZone.from_dict(data)
        else:
            # Generic zone
            return cls(
                zone_id=data["zone_id"],
                asset_id=data["asset_id"],
                zone_type=zone_type,
                bounds=ZoneBounds.from_dict(data["bounds"]),
                allowed_classes=frozenset(VehicleClass(c) for c in allowed),
                max_vehicles=data.get("max_vehicles"),
                enabled=data.get("enabled", True),
            )
    
    def can_spawn(self, vehicle_class: VehicleClass) -> bool:
        """Check if the zone can accept a vehicle of the given class."""
        if not self.enabled:
            return False
        if vehicle_class not in self.allowed_classes:
            return False
        if self.max_vehicles is not None and self.current_vehicle_count >= self.max_vehicles:
            return False
        return True
    
    def contains_point(self, point: Vector3) -> bool:
        """Check if a point is inside the zone."""
        return self.bounds.contains_point(point)


@dataclass
class RoadZone(Zone):
    """
    Road zone for traffic placement.
    
    Additional properties:
    - Lane definitions
    - Direction of travel
    - Speed limits (optional, for future use)
    """
    lanes: list[dict] = field(default_factory=list)  # List of lane definitions
    direction: LaneDirection = LaneDirection.FORWARD
    speed_limit_mps: Optional[float] = None  # meters per second
    
    def __post_init__(self):
        self.zone_type = ZoneType.ROAD
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["lanes"] = self.lanes
        data["direction"] = self.direction.value
        data["speed_limit_mps"] = self.speed_limit_mps
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "RoadZone":
        allowed = data.get("allowed_classes", ["car", "truck", "bus", "motorcycle", "bicycle"])
        return cls(
            zone_id=data["zone_id"],
            asset_id=data["asset_id"],
            zone_type=ZoneType.ROAD,
            bounds=ZoneBounds.from_dict(data["bounds"]),
            allowed_classes=frozenset(VehicleClass(c) for c in allowed),
            max_vehicles=data.get("max_vehicles"),
            enabled=data.get("enabled", True),
            lanes=data.get("lanes", []),
            direction=LaneDirection.from_string(data.get("direction", "forward")),
            speed_limit_mps=data.get("speed_limit_mps"),
        )
    
    def get_lane_center(self, lane_index: int) -> Optional[float]:
        """Get the Y offset for a lane by index."""
        if 0 <= lane_index < len(self.lanes):
            return self.lanes[lane_index].get("y_offset", 0.0)
        return None
    
    def get_lane_yaw(self, lane_index: int) -> float:
        """Get the yaw angle for a lane based on direction."""
        if self.direction == LaneDirection.FORWARD:
            return 0.0
        elif self.direction == LaneDirection.BACKWARD:
            return 180.0
        else:
            # Bidirectional - alternate by lane
            return 0.0 if lane_index % 2 == 0 else 180.0


@dataclass
class ParkingZone(Zone):
    """
    Parking zone with discrete slots.
    
    Vehicles spawn static in pre-defined slots.
    No random placement unless explicitly enabled.
    """
    slots: list[ParkingSlot] = field(default_factory=list)
    allow_random_placement: bool = False  # Default: slots only
    slot_jitter_meters: float = 0.0  # Max position jitter within slot
    
    def __post_init__(self):
        self.zone_type = ZoneType.PARKING
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["slots"] = [s.to_dict() for s in self.slots]
        data["allow_random_placement"] = self.allow_random_placement
        data["slot_jitter_meters"] = self.slot_jitter_meters
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "ParkingZone":
        allowed = data.get("allowed_classes", ["car", "truck", "bus", "motorcycle", "bicycle"])
        slots = [ParkingSlot.from_dict(s) for s in data.get("slots", [])]
        
        return cls(
            zone_id=data["zone_id"],
            asset_id=data["asset_id"],
            zone_type=ZoneType.PARKING,
            bounds=ZoneBounds.from_dict(data["bounds"]),
            allowed_classes=frozenset(VehicleClass(c) for c in allowed),
            max_vehicles=data.get("max_vehicles", len(slots)),
            enabled=data.get("enabled", True),
            slots=slots,
            allow_random_placement=data.get("allow_random_placement", False),
            slot_jitter_meters=data.get("slot_jitter_meters", 0.0),
        )
    
    def get_available_slots(self, vehicle_class: VehicleClass) -> list[ParkingSlot]:
        """Get all available slots that can accept the given vehicle class."""
        return [s for s in self.slots if s.can_accept(vehicle_class)]
    
    def allocate_slot(self, vehicle_class: VehicleClass, instance_id: str) -> Optional[ParkingSlot]:
        """Allocate an available slot for a vehicle. Returns None if no slot available."""
        available = self.get_available_slots(vehicle_class)
        if not available:
            return None
        
        # Take first available slot (deterministic)
        slot = available[0]
        slot.occupy(instance_id)
        self.current_vehicle_count += 1
        return slot
    
    def release_slot(self, slot_id: str) -> bool:
        """Release a slot by ID. Returns True if found and released."""
        for slot in self.slots:
            if slot.slot_id == slot_id:
                slot.release()
                self.current_vehicle_count = max(0, self.current_vehicle_count - 1)
                return True
        return False
    
    def release_all(self) -> int:
        """Release all slots. Returns count of slots released."""
        count = 0
        for slot in self.slots:
            if slot.state == SlotState.OCCUPIED:
                slot.release()
                count += 1
        self.current_vehicle_count = 0
        return count


@dataclass
class ExclusionZone(Zone):
    """
    Exclusion zone where vehicles may NEVER spawn.
    
    Used for:
    - Buildings
    - Obstacles
    - Restricted areas
    """
    reason: str = "No vehicles allowed"  # Human-readable reason
    
    def __post_init__(self):
        self.zone_type = ZoneType.EXCLUSION
        self.allowed_classes = frozenset()  # No classes allowed
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["reason"] = self.reason
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExclusionZone":
        return cls(
            zone_id=data["zone_id"],
            asset_id=data["asset_id"],
            zone_type=ZoneType.EXCLUSION,
            bounds=ZoneBounds.from_dict(data["bounds"]),
            allowed_classes=frozenset(),
            max_vehicles=0,
            enabled=data.get("enabled", True),
            reason=data.get("reason", "No vehicles allowed"),
        )
    
    def can_spawn(self, vehicle_class: VehicleClass) -> bool:
        """Exclusion zones never allow spawning."""
        return False
