"""
VantageCV Zone System

Zone-based spatial placement system for deterministic, asset-aware vehicle spawning.

Zones are DATA, NOT LOGIC:
- Zones are explicitly defined and attached to assets
- An asset without zones cannot spawn vehicles
- No guessing, no inference, no magic

Zone Types:
- ROAD_ZONE: Vehicles spawn aligned to direction (traffic)
- PARKING_ZONE: Vehicles spawn static in discrete slots
- EXCLUSION_ZONE: Vehicles may NEVER spawn here

Usage:
    from vantagecv.research_v2.zones import ZoneRegistry, ZoneType
    
    # Load zones from asset manifest
    registry = ZoneRegistry()
    registry.load_from_manifest("path/to/zones.yaml")
    
    # Query available zones
    road_zones = registry.get_zones_by_type(ZoneType.ROAD)
    parking_zones = registry.get_zones_by_type(ZoneType.PARKING)
    
    # Find spawn location
    slot = registry.allocate_parking_slot("parking_lot_A", VehicleClass.CAR)
"""

from .zone_types import ZoneType, ZoneShape, LaneDirection, SlotState
from .zone_data import (
    Vector3,
    Rotation3,
    Transform3D,
    ZoneBounds,
    ParkingSlot,
    Zone,
    RoadZone,
    ParkingZone,
    ExclusionZone,
)
from .zone_registry import ZoneRegistry, ZoneQueryResult, SpawnAllocation
from .zone_spawner import ZoneBasedSpawner, ZoneSpawnedVehicle, ZoneSpawnResult
from .zone_visualizer import ZoneVisualizer, create_test_zones
from .zone_config import ZoneConfig

__all__ = [
    # Types
    "ZoneType",
    "ZoneShape",
    "LaneDirection",
    "SlotState",
    # Geometry
    "Vector3",
    "Rotation3",
    "Transform3D",
    # Data structures
    "ZoneBounds",
    "ParkingSlot",
    "Zone",
    "RoadZone",
    "ParkingZone",
    "ExclusionZone",
    # Registry
    "ZoneRegistry",
    "ZoneQueryResult",
    "SpawnAllocation",
    # Spawner
    "ZoneBasedSpawner",
    "ZoneSpawnedVehicle",
    "ZoneSpawnResult",
    # Visualization
    "ZoneVisualizer",
    "create_test_zones",
    # Config
    "ZoneConfig",
]
