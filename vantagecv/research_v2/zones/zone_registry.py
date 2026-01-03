"""
Zone Registry

Central authority for all zone management.
Single source of truth for zone queries.

All zone access MUST go through the registry.
No direct zone manipulation outside this module.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Iterator
import yaml
import json

from .zone_types import ZoneType, SlotState
from .zone_data import (
    Zone, RoadZone, ParkingZone, ExclusionZone,
    ZoneBounds, ParkingSlot, Vector3, Transform3D, Rotation3,
    ZoneShape,
)
from ..config import VehicleClass
from ..logging_utils import ResearchLogger


@dataclass
class ZoneQueryResult:
    """Result of a zone query."""
    success: bool
    zones: list[Zone] = field(default_factory=list)
    message: str = ""
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "zone_count": len(self.zones),
            "zone_ids": [z.zone_id for z in self.zones],
            "message": self.message,
        }


@dataclass
class SpawnAllocation:
    """Result of a spawn allocation request."""
    success: bool
    zone: Optional[Zone] = None
    slot: Optional[ParkingSlot] = None
    transform: Optional[Transform3D] = None
    failure_reason: Optional[str] = None
    suggested_fix: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "zone_id": self.zone.zone_id if self.zone else None,
            "zone_type": self.zone.zone_type.value if self.zone else None,
            "slot_id": self.slot.slot_id if self.slot else None,
            "transform": self.transform.to_dict() if self.transform else None,
            "failure_reason": self.failure_reason,
            "suggested_fix": self.suggested_fix,
        }


class ZoneRegistry:
    """
    Central registry for all zones.
    
    Responsibilities:
    - Load zone definitions from manifests
    - Register/unregister zones
    - Query zones by type, asset, location
    - Allocate spawn positions
    - Validate zone configurations
    - Track zone state
    
    Thread Safety: NOT thread-safe. Use external locking if needed.
    """
    
    MODULE_NAME = "ZoneRegistry"
    
    def __init__(self, logger: Optional[ResearchLogger] = None):
        """Initialize empty registry."""
        self.logger = logger or ResearchLogger(self.MODULE_NAME)
        
        # Zone storage by ID (primary key)
        self._zones: dict[str, Zone] = {}
        
        # Indices for fast lookup
        self._by_type: dict[ZoneType, set[str]] = {t: set() for t in ZoneType}
        self._by_asset: dict[str, set[str]] = {}
        
        # Validation state
        self._validated = False
        self._validation_errors: list[str] = []
        
        self.logger.debug("ZoneRegistry initialized")
    
    # ========================================
    # LOADING
    # ========================================
    
    def load_from_manifest(self, manifest_path: str | Path) -> bool:
        """
        Load zones from a YAML/JSON manifest file.
        
        Args:
            manifest_path: Path to zone manifest file
            
        Returns:
            True if loaded successfully, False otherwise
        """
        path = Path(manifest_path)
        if not path.exists():
            self.logger.error(
                "Zone manifest not found",
                path=str(path),
                suggested_fix="Create zone manifest file or check path",
            )
            return False
        
        try:
            with open(path) as f:
                if path.suffix in ('.yaml', '.yml'):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            return self.load_from_dict(data, source=str(path))
            
        except Exception as e:
            self.logger.error(
                "Failed to parse zone manifest",
                path=str(path),
                error=str(e),
            )
            return False
    
    def load_from_dict(self, data: dict, source: str = "dict") -> bool:
        """
        Load zones from a dictionary.
        
        Expected format:
        {
            "asset_id": "road_segment_01",
            "zones": [
                { zone definition },
                ...
            ]
        }
        
        Or multiple assets:
        {
            "assets": [
                {
                    "asset_id": "road_segment_01",
                    "zones": [...]
                },
                ...
            ]
        }
        """
        try:
            zones_loaded = 0
            
            # Handle single asset or multiple assets
            if "assets" in data:
                for asset_data in data["assets"]:
                    asset_id = asset_data["asset_id"]
                    for zone_data in asset_data.get("zones", []):
                        zone_data["asset_id"] = asset_id
                        zone = Zone.from_dict(zone_data)
                        self.register_zone(zone)
                        zones_loaded += 1
            elif "zones" in data:
                asset_id = data.get("asset_id", "default")
                for zone_data in data["zones"]:
                    zone_data["asset_id"] = asset_id
                    zone = Zone.from_dict(zone_data)
                    self.register_zone(zone)
                    zones_loaded += 1
            
            self.logger.info(
                "Zones loaded from manifest",
                source=source,
                zones_loaded=zones_loaded,
            )
            
            self._validated = False  # Need re-validation
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to load zones from dict",
                source=source,
                error=str(e),
            )
            return False
    
    # ========================================
    # REGISTRATION
    # ========================================
    
    def register_zone(self, zone: Zone) -> bool:
        """
        Register a zone with the registry.
        
        Args:
            zone: Zone to register
            
        Returns:
            True if registered, False if ID already exists
        """
        if zone.zone_id in self._zones:
            self.logger.warning(
                "Zone ID already registered",
                zone_id=zone.zone_id,
                existing_asset=self._zones[zone.zone_id].asset_id,
                new_asset=zone.asset_id,
            )
            return False
        
        # Add to primary storage
        self._zones[zone.zone_id] = zone
        
        # Update indices
        self._by_type[zone.zone_type].add(zone.zone_id)
        
        if zone.asset_id not in self._by_asset:
            self._by_asset[zone.asset_id] = set()
        self._by_asset[zone.asset_id].add(zone.zone_id)
        
        self.logger.debug(
            "Zone registered",
            zone_id=zone.zone_id,
            zone_type=zone.zone_type.value,
            asset_id=zone.asset_id,
        )
        
        self._validated = False
        return True
    
    def unregister_zone(self, zone_id: str) -> bool:
        """
        Unregister a zone from the registry.
        
        Args:
            zone_id: ID of zone to unregister
            
        Returns:
            True if unregistered, False if not found
        """
        if zone_id not in self._zones:
            return False
        
        zone = self._zones[zone_id]
        
        # Remove from indices
        self._by_type[zone.zone_type].discard(zone_id)
        if zone.asset_id in self._by_asset:
            self._by_asset[zone.asset_id].discard(zone_id)
        
        # Remove from primary storage
        del self._zones[zone_id]
        
        self.logger.debug("Zone unregistered", zone_id=zone_id)
        return True
    
    def clear(self) -> int:
        """
        Clear all zones from the registry.
        
        Returns:
            Number of zones cleared
        """
        count = len(self._zones)
        self._zones.clear()
        for zone_set in self._by_type.values():
            zone_set.clear()
        self._by_asset.clear()
        self._validated = False
        self._validation_errors.clear()
        
        self.logger.info("Registry cleared", zones_cleared=count)
        return count
    
    # ========================================
    # QUERIES
    # ========================================
    
    def get_zone(self, zone_id: str) -> Optional[Zone]:
        """Get a zone by ID."""
        return self._zones.get(zone_id)
    
    def get_zones_by_type(self, zone_type: ZoneType) -> list[Zone]:
        """Get all zones of a specific type."""
        return [self._zones[zid] for zid in self._by_type[zone_type]]
    
    def get_zones_by_asset(self, asset_id: str) -> list[Zone]:
        """Get all zones belonging to an asset."""
        if asset_id not in self._by_asset:
            return []
        return [self._zones[zid] for zid in self._by_asset[asset_id]]
    
    def get_zones_for_class(
        self,
        vehicle_class: VehicleClass,
        zone_type: Optional[ZoneType] = None,
    ) -> list[Zone]:
        """Get all zones that can accept a vehicle class."""
        result = []
        
        if zone_type:
            zones = self.get_zones_by_type(zone_type)
        else:
            zones = list(self._zones.values())
        
        for zone in zones:
            if zone.can_spawn(vehicle_class):
                result.append(zone)
        
        return result
    
    def get_zone_at_point(self, point: Vector3) -> Optional[Zone]:
        """Get the zone containing a point (first match)."""
        for zone in self._zones.values():
            if zone.contains_point(point):
                return zone
        return None
    
    def get_all_zones_at_point(self, point: Vector3) -> list[Zone]:
        """Get all zones containing a point."""
        return [z for z in self._zones.values() if z.contains_point(point)]
    
    def is_point_in_exclusion(self, point: Vector3) -> bool:
        """Check if a point is inside any exclusion zone."""
        for zone in self.get_zones_by_type(ZoneType.EXCLUSION):
            if zone.contains_point(point):
                return True
        return False
    
    @property
    def zone_count(self) -> int:
        """Total number of registered zones."""
        return len(self._zones)
    
    @property
    def road_zone_count(self) -> int:
        """Number of road zones."""
        return len(self._by_type[ZoneType.ROAD])
    
    @property
    def parking_zone_count(self) -> int:
        """Number of parking zones."""
        return len(self._by_type[ZoneType.PARKING])
    
    @property
    def exclusion_zone_count(self) -> int:
        """Number of exclusion zones."""
        return len(self._by_type[ZoneType.EXCLUSION])
    
    def __iter__(self) -> Iterator[Zone]:
        """Iterate over all zones."""
        return iter(self._zones.values())
    
    def __len__(self) -> int:
        """Number of zones."""
        return len(self._zones)
    
    # ========================================
    # SPAWN ALLOCATION
    # ========================================
    
    def allocate_spawn(
        self,
        vehicle_class: VehicleClass,
        zone_type: Optional[ZoneType] = None,
        preferred_zone_id: Optional[str] = None,
    ) -> SpawnAllocation:
        """
        Allocate a spawn position for a vehicle.
        
        This is the PRIMARY API for spawn position allocation.
        
        Args:
            vehicle_class: Class of vehicle to spawn
            zone_type: Optional filter by zone type
            preferred_zone_id: Optional preferred zone ID
            
        Returns:
            SpawnAllocation with position or failure reason
        """
        # Try preferred zone first
        if preferred_zone_id:
            zone = self.get_zone(preferred_zone_id)
            if zone and zone.can_spawn(vehicle_class):
                return self._allocate_in_zone(zone, vehicle_class)
        
        # Find suitable zones
        suitable = self.get_zones_for_class(vehicle_class, zone_type)
        
        if not suitable:
            return SpawnAllocation(
                success=False,
                failure_reason=f"No zones available for {vehicle_class.value}",
                suggested_fix=f"Add zones that allow {vehicle_class.value} or check zone capacity",
            )
        
        # Try each zone until we find one with capacity
        for zone in suitable:
            result = self._allocate_in_zone(zone, vehicle_class)
            if result.success:
                return result
        
        return SpawnAllocation(
            success=False,
            failure_reason=f"All suitable zones at capacity for {vehicle_class.value}",
            suggested_fix="Increase zone capacity or reduce vehicle count",
        )
    
    def _allocate_in_zone(
        self,
        zone: Zone,
        vehicle_class: VehicleClass,
    ) -> SpawnAllocation:
        """Allocate spawn position within a specific zone."""
        
        if isinstance(zone, ParkingZone):
            return self._allocate_parking_slot(zone, vehicle_class)
        elif isinstance(zone, RoadZone):
            return self._allocate_road_position(zone, vehicle_class)
        else:
            return SpawnAllocation(
                success=False,
                failure_reason=f"Zone type {zone.zone_type.value} does not support spawning",
            )
    
    def _allocate_parking_slot(
        self,
        zone: ParkingZone,
        vehicle_class: VehicleClass,
    ) -> SpawnAllocation:
        """Allocate a parking slot."""
        import uuid
        
        available = zone.get_available_slots(vehicle_class)
        if not available:
            return SpawnAllocation(
                success=False,
                zone=zone,
                failure_reason=f"No available parking slots in {zone.zone_id} for {vehicle_class.value}",
                suggested_fix=f"Increase slot count or allow {vehicle_class.value} in existing slots",
            )
        
        # Allocate first available slot
        slot = available[0]
        instance_id = f"vehicle_{uuid.uuid4().hex[:8]}"
        slot.occupy(instance_id)
        zone.current_vehicle_count += 1
        
        self.logger.debug(
            "Parking slot allocated",
            zone_id=zone.zone_id,
            slot_id=slot.slot_id,
            vehicle_class=vehicle_class.value,
            instance_id=instance_id,
        )
        
        return SpawnAllocation(
            success=True,
            zone=zone,
            slot=slot,
            transform=slot.transform,
        )
    
    def _allocate_road_position(
        self,
        zone: RoadZone,
        vehicle_class: VehicleClass,
    ) -> SpawnAllocation:
        """Allocate a road position (simplified - uses lane centers)."""
        if not zone.lanes:
            return SpawnAllocation(
                success=False,
                zone=zone,
                failure_reason=f"Road zone {zone.zone_id} has no lanes defined",
                suggested_fix="Add lane definitions to road zone",
            )
        
        # For now, return first lane center
        # Full implementation would track lane occupancy
        lane = zone.lanes[0]
        y_offset = lane.get("y_offset", 0.0)
        
        if zone.bounds.center:
            position = Vector3(
                zone.bounds.center.x,
                zone.bounds.center.y + y_offset,
                0.0,  # Ground level
            )
        else:
            position = Vector3(0, y_offset, 0)
        
        yaw = zone.get_lane_yaw(0)
        transform = Transform3D(
            position=position,
            rotation=Rotation3(yaw=yaw),
        )
        
        zone.current_vehicle_count += 1
        
        return SpawnAllocation(
            success=True,
            zone=zone,
            transform=transform,
        )
    
    def release_allocation(
        self,
        zone_id: str,
        slot_id: Optional[str] = None,
    ) -> bool:
        """
        Release a spawn allocation.
        
        Args:
            zone_id: Zone ID
            slot_id: Slot ID (for parking zones)
            
        Returns:
            True if released successfully
        """
        zone = self.get_zone(zone_id)
        if not zone:
            return False
        
        if isinstance(zone, ParkingZone) and slot_id:
            return zone.release_slot(slot_id)
        else:
            zone.current_vehicle_count = max(0, zone.current_vehicle_count - 1)
            return True
    
    def release_all_allocations(self) -> int:
        """
        Release all allocations across all zones.
        
        Returns:
            Total number of allocations released
        """
        count = 0
        
        for zone in self._zones.values():
            if isinstance(zone, ParkingZone):
                count += zone.release_all()
            else:
                count += zone.current_vehicle_count
                zone.current_vehicle_count = 0
        
        self.logger.info("All allocations released", count=count)
        return count
    
    # ========================================
    # VALIDATION
    # ========================================
    
    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate all registered zones.
        
        Checks:
        - All zones have valid bounds
        - No unintended overlaps
        - All parking zones have slots
        - All road zones have lanes
        
        Returns:
            (is_valid, list of error messages)
        """
        self._validation_errors.clear()
        
        for zone in self._zones.values():
            self._validate_zone(zone)
        
        # Check for overlapping zones
        self._check_overlaps()
        
        self._validated = len(self._validation_errors) == 0
        
        if self._validated:
            self.logger.info(
                "Zone validation passed",
                zone_count=len(self._zones),
            )
        else:
            self.logger.error(
                "Zone validation failed",
                error_count=len(self._validation_errors),
                errors=self._validation_errors,
            )
        
        return self._validated, self._validation_errors
    
    def _validate_zone(self, zone: Zone) -> None:
        """Validate a single zone."""
        # Basic validation
        if not zone.zone_id:
            self._validation_errors.append(f"Zone has empty ID: {zone}")
        
        if not zone.bounds:
            self._validation_errors.append(f"Zone {zone.zone_id} has no bounds")
        
        # Type-specific validation
        if isinstance(zone, ParkingZone):
            if not zone.slots and not zone.allow_random_placement:
                self._validation_errors.append(
                    f"Parking zone {zone.zone_id} has no slots and random placement is disabled"
                )
        
        if isinstance(zone, RoadZone):
            if not zone.lanes:
                self._validation_errors.append(
                    f"Road zone {zone.zone_id} has no lanes defined"
                )
    
    def _check_overlaps(self) -> None:
        """Check for problematic zone overlaps."""
        # For now, just check exclusion zones don't overlap spawn zones
        exclusion_zones = self.get_zones_by_type(ZoneType.EXCLUSION)
        spawn_zones = (
            self.get_zones_by_type(ZoneType.ROAD) +
            self.get_zones_by_type(ZoneType.PARKING)
        )
        
        # Full overlap detection would require geometric intersection
        # Simplified version: warn about potential overlaps
        pass  # TODO: Implement geometric overlap detection
    
    # ========================================
    # SERIALIZATION
    # ========================================
    
    def to_dict(self) -> dict:
        """Serialize registry to dictionary."""
        return {
            "zone_count": len(self._zones),
            "zones": [z.to_dict() for z in self._zones.values()],
            "by_type": {
                t.value: list(ids) for t, ids in self._by_type.items()
            },
            "by_asset": {
                aid: list(ids) for aid, ids in self._by_asset.items()
            },
            "validated": self._validated,
        }
    
    def save_to_file(self, path: str | Path) -> bool:
        """Save registry to YAML file."""
        try:
            output = {
                "assets": []
            }
            
            for asset_id, zone_ids in self._by_asset.items():
                asset_zones = [self._zones[zid].to_dict() for zid in zone_ids]
                output["assets"].append({
                    "asset_id": asset_id,
                    "zones": asset_zones,
                })
            
            with open(path, 'w') as f:
                yaml.dump(output, f, default_flow_style=False)
            
            self.logger.info("Registry saved", path=str(path))
            return True
            
        except Exception as e:
            self.logger.error("Failed to save registry", error=str(e))
            return False
    
    # ========================================
    # STATISTICS
    # ========================================
    
    def get_statistics(self) -> dict:
        """Get registry statistics."""
        total_slots = 0
        available_slots = 0
        
        for zone in self.get_zones_by_type(ZoneType.PARKING):
            if isinstance(zone, ParkingZone):
                total_slots += len(zone.slots)
                available_slots += len(zone.get_available_slots(VehicleClass.CAR))
        
        return {
            "total_zones": len(self._zones),
            "road_zones": self.road_zone_count,
            "parking_zones": self.parking_zone_count,
            "exclusion_zones": self.exclusion_zone_count,
            "total_parking_slots": total_slots,
            "available_parking_slots": available_slots,
            "assets_with_zones": len(self._by_asset),
            "validated": self._validated,
        }
