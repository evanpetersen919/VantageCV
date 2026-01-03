"""
Zone Configuration

Integration between zone system and main configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .zone_types import ZoneType


@dataclass
class ZoneConfig:
    """
    Zone system configuration.
    
    Controls zone loading, validation, and spawning behavior.
    """
    # Zone manifest path (relative to project root or absolute)
    manifest_path: str = "configs/zones/automobile.zones.yaml"
    
    # Validation settings
    validate_on_load: bool = True
    strict_validation: bool = True  # Fail on any validation error
    
    # Spawning behavior
    default_zone_type: Optional[ZoneType] = None  # None = any zone type
    prefer_parking_zones: bool = False  # Try parking first
    prefer_road_zones: bool = True      # Try road first
    
    # Capacity limits
    max_vehicles_per_zone: int = 10
    max_total_vehicles: int = 50
    
    # Jitter settings
    position_jitter_meters: float = 0.5
    rotation_jitter_degrees: float = 5.0
    
    # Debug visualization
    enable_debug_visualization: bool = False
    debug_duration_seconds: float = 10.0
    
    def get_manifest_path(self, base_dir: Optional[Path] = None) -> Path:
        """Get absolute path to zone manifest."""
        path = Path(self.manifest_path)
        if path.is_absolute():
            return path
        if base_dir:
            return base_dir / path
        return Path.cwd() / path
    
    def to_dict(self) -> dict:
        return {
            "manifest_path": self.manifest_path,
            "validate_on_load": self.validate_on_load,
            "strict_validation": self.strict_validation,
            "default_zone_type": self.default_zone_type.value if self.default_zone_type else None,
            "prefer_parking_zones": self.prefer_parking_zones,
            "prefer_road_zones": self.prefer_road_zones,
            "max_vehicles_per_zone": self.max_vehicles_per_zone,
            "max_total_vehicles": self.max_total_vehicles,
            "position_jitter_meters": self.position_jitter_meters,
            "rotation_jitter_degrees": self.rotation_jitter_degrees,
            "enable_debug_visualization": self.enable_debug_visualization,
            "debug_duration_seconds": self.debug_duration_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ZoneConfig":
        zone_type = data.get("default_zone_type")
        return cls(
            manifest_path=data.get("manifest_path", "data/zones/automobile.zones.yaml"),
            validate_on_load=data.get("validate_on_load", True),
            strict_validation=data.get("strict_validation", True),
            default_zone_type=ZoneType.from_string(zone_type) if zone_type else None,
            prefer_parking_zones=data.get("prefer_parking_zones", False),
            prefer_road_zones=data.get("prefer_road_zones", True),
            max_vehicles_per_zone=data.get("max_vehicles_per_zone", 10),
            max_total_vehicles=data.get("max_total_vehicles", 50),
            position_jitter_meters=data.get("position_jitter_meters", 0.5),
            rotation_jitter_degrees=data.get("rotation_jitter_degrees", 5.0),
            enable_debug_visualization=data.get("enable_debug_visualization", False),
            debug_duration_seconds=data.get("debug_duration_seconds", 10.0),
        )
