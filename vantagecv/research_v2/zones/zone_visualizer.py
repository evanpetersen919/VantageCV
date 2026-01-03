"""
Zone Visualization

Debug visualization for zones in UE5.
Generates DrawDebugBox / DrawDebugLine commands.
"""

from dataclasses import dataclass
from typing import Optional

from .zone_types import ZoneType, ZoneShape
from .zone_data import Zone, RoadZone, ParkingZone, ExclusionZone, Vector3
from .zone_registry import ZoneRegistry
from ..logging_utils import ResearchLogger


@dataclass
class DebugColor:
    """RGBA color for debug visualization."""
    r: float
    g: float
    b: float
    a: float = 1.0
    
    def to_ue5_dict(self) -> dict:
        """Convert to UE5 FLinearColor format."""
        return {"R": self.r, "G": self.g, "B": self.b, "A": self.a}


# Default colors for each zone type
ZONE_COLORS = {
    ZoneType.ROAD: DebugColor(0.0, 0.5, 1.0, 0.5),      # Blue
    ZoneType.PARKING: DebugColor(0.0, 1.0, 0.0, 0.5),   # Green
    ZoneType.EXCLUSION: DebugColor(1.0, 0.0, 0.0, 0.5), # Red
}

# Slot colors
SLOT_COLOR_AVAILABLE = DebugColor(0.0, 1.0, 0.5, 0.7)   # Cyan
SLOT_COLOR_OCCUPIED = DebugColor(1.0, 0.5, 0.0, 0.7)    # Orange


class ZoneVisualizer:
    """
    Generates debug visualization commands for zones.
    
    Visualization includes:
    - Zone boundaries (boxes or polygons)
    - Parking slots
    - Zone labels
    - Directional arrows for road zones
    
    Usage:
        visualizer = ZoneVisualizer(registry)
        commands = visualizer.generate_debug_commands()
        # Send commands to UE5 via Remote Control API
    """
    
    MODULE_NAME = "ZoneVisualizer"
    
    def __init__(
        self,
        registry: ZoneRegistry,
        logger: Optional[ResearchLogger] = None,
    ):
        """
        Initialize visualizer.
        
        Args:
            registry: Zone registry to visualize
            logger: Optional logger
        """
        self.registry = registry
        self.logger = logger or ResearchLogger(self.MODULE_NAME)
        
        # Visualization settings
        self.line_thickness = 5.0
        self.box_thickness = 3.0
        self.arrow_size = 50.0  # cm
        self.debug_duration = 10.0  # seconds
        
    def generate_debug_commands(
        self,
        show_zones: bool = True,
        show_slots: bool = True,
        show_arrows: bool = True,
        show_labels: bool = True,
        zone_filter: Optional[ZoneType] = None,
    ) -> list[dict]:
        """
        Generate debug draw commands for all zones.
        
        Args:
            show_zones: Draw zone boundaries
            show_slots: Draw parking slots
            show_arrows: Draw direction arrows on road zones
            show_labels: Draw zone labels (text)
            zone_filter: Only show zones of this type
            
        Returns:
            List of UE5 debug draw commands
        """
        commands = []
        
        for zone in self.registry:
            if zone_filter and zone.zone_type != zone_filter:
                continue
            
            if show_zones:
                commands.extend(self._draw_zone_bounds(zone))
            
            if show_slots and isinstance(zone, ParkingZone):
                commands.extend(self._draw_parking_slots(zone))
            
            if show_arrows and isinstance(zone, RoadZone):
                commands.extend(self._draw_road_arrows(zone))
            
            if show_labels:
                commands.extend(self._draw_zone_label(zone))
        
        self.logger.debug(
            "Debug commands generated",
            command_count=len(commands),
            zone_count=self.registry.zone_count,
        )
        
        return commands
    
    def _draw_zone_bounds(self, zone: Zone) -> list[dict]:
        """Draw zone boundary."""
        commands = []
        color = ZONE_COLORS.get(zone.zone_type, DebugColor(1, 1, 1, 0.5))
        
        bounds = zone.bounds
        
        if bounds.shape == ZoneShape.BOX and bounds.center and bounds.size:
            # Draw box
            center = bounds.center
            size = bounds.size
            
            commands.append({
                "type": "debug_draw",
                "function": "DrawDebugBox",
                "params": {
                    "Center": {
                        "X": center.x * 100,  # Convert to cm
                        "Y": center.y * 100,
                        "Z": center.z * 100,
                    },
                    "Extent": {
                        "X": size.x * 100 / 2,
                        "Y": size.y * 100 / 2,
                        "Z": size.z * 100 / 2,
                    },
                    "LineColor": color.to_ue5_dict(),
                    "Duration": self.debug_duration,
                    "Thickness": self.box_thickness,
                },
            })
            
        elif bounds.shape == ZoneShape.POLYGON and bounds.vertices:
            # Draw polygon edges
            vertices = bounds.vertices
            n = len(vertices)
            
            for i in range(n):
                x1, y1 = vertices[i]
                x2, y2 = vertices[(i + 1) % n]
                
                # Draw vertical lines at corners
                for x, y in [(x1, y1), (x2, y2)]:
                    commands.append({
                        "type": "debug_draw",
                        "function": "DrawDebugLine",
                        "params": {
                            "LineStart": {"X": x * 100, "Y": y * 100, "Z": bounds.z_min * 100},
                            "LineEnd": {"X": x * 100, "Y": y * 100, "Z": bounds.z_max * 100},
                            "LineColor": color.to_ue5_dict(),
                            "Duration": self.debug_duration,
                            "Thickness": self.line_thickness,
                        },
                    })
                
                # Draw horizontal edges at top and bottom
                for z in [bounds.z_min, bounds.z_max]:
                    commands.append({
                        "type": "debug_draw",
                        "function": "DrawDebugLine",
                        "params": {
                            "LineStart": {"X": x1 * 100, "Y": y1 * 100, "Z": z * 100},
                            "LineEnd": {"X": x2 * 100, "Y": y2 * 100, "Z": z * 100},
                            "LineColor": color.to_ue5_dict(),
                            "Duration": self.debug_duration,
                            "Thickness": self.line_thickness,
                        },
                    })
        
        return commands
    
    def _draw_parking_slots(self, zone: ParkingZone) -> list[dict]:
        """Draw parking slots."""
        commands = []
        
        for slot in zone.slots:
            from .zone_types import SlotState
            
            if slot.state == SlotState.OCCUPIED:
                color = SLOT_COLOR_OCCUPIED
            else:
                color = SLOT_COLOR_AVAILABLE
            
            pos = slot.transform.position
            
            # Draw slot as small box (2m x 4m x 0.1m)
            commands.append({
                "type": "debug_draw",
                "function": "DrawDebugBox",
                "params": {
                    "Center": {
                        "X": pos.x * 100,
                        "Y": pos.y * 100,
                        "Z": pos.z * 100 + 5,  # Slightly above ground
                    },
                    "Extent": {
                        "X": 200,  # 2m half-length
                        "Y": 100,  # 1m half-width
                        "Z": 5,    # 0.1m half-height
                    },
                    "LineColor": color.to_ue5_dict(),
                    "Duration": self.debug_duration,
                    "Thickness": self.line_thickness,
                },
            })
            
            # Draw forward direction arrow
            yaw = slot.transform.rotation.yaw
            import math
            dx = math.cos(math.radians(yaw)) * self.arrow_size
            dy = math.sin(math.radians(yaw)) * self.arrow_size
            
            commands.append({
                "type": "debug_draw",
                "function": "DrawDebugDirectionalArrow",
                "params": {
                    "LineStart": {
                        "X": pos.x * 100,
                        "Y": pos.y * 100,
                        "Z": pos.z * 100 + 10,
                    },
                    "LineEnd": {
                        "X": pos.x * 100 + dx,
                        "Y": pos.y * 100 + dy,
                        "Z": pos.z * 100 + 10,
                    },
                    "ArrowSize": 20,
                    "LineColor": color.to_ue5_dict(),
                    "Duration": self.debug_duration,
                    "Thickness": self.line_thickness / 2,
                },
            })
        
        return commands
    
    def _draw_road_arrows(self, zone: RoadZone) -> list[dict]:
        """Draw direction arrows for road zones."""
        commands = []
        
        if not zone.bounds.center or not zone.bounds.size:
            return commands
        
        center = zone.bounds.center
        size = zone.bounds.size
        
        from .zone_types import LaneDirection
        import math
        
        # Draw arrow along road direction
        if zone.direction == LaneDirection.FORWARD:
            yaw = 0
        elif zone.direction == LaneDirection.BACKWARD:
            yaw = 180
        else:
            yaw = 0  # Draw forward for bidirectional
        
        dx = math.cos(math.radians(yaw)) * (size.x * 100 / 3)
        dy = math.sin(math.radians(yaw)) * (size.x * 100 / 3)
        
        color = ZONE_COLORS[ZoneType.ROAD]
        
        commands.append({
            "type": "debug_draw",
            "function": "DrawDebugDirectionalArrow",
            "params": {
                "LineStart": {
                    "X": center.x * 100 - dx / 2,
                    "Y": center.y * 100,
                    "Z": center.z * 100 + 50,
                },
                "LineEnd": {
                    "X": center.x * 100 + dx / 2,
                    "Y": center.y * 100,
                    "Z": center.z * 100 + 50,
                },
                "ArrowSize": 50,
                "LineColor": color.to_ue5_dict(),
                "Duration": self.debug_duration,
                "Thickness": self.line_thickness,
            },
        })
        
        return commands
    
    def _draw_zone_label(self, zone: Zone) -> list[dict]:
        """Draw zone label (text)."""
        commands = []
        
        # Text rendering requires special handling in UE5
        # For now, we'll use DrawDebugString if available
        
        if zone.bounds.center:
            center = zone.bounds.center
            
            commands.append({
                "type": "debug_draw",
                "function": "DrawDebugString",
                "params": {
                    "TextLocation": {
                        "X": center.x * 100,
                        "Y": center.y * 100,
                        "Z": center.z * 100 + 200,  # Above zone
                    },
                    "Text": f"{zone.zone_id} ({zone.zone_type.value})",
                    "TextColor": {"R": 255, "G": 255, "B": 255, "A": 255},
                    "Duration": self.debug_duration,
                },
            })
        
        return commands
    
    def generate_summary(self) -> str:
        """Generate text summary of zones for logging."""
        lines = [
            "=== ZONE VISUALIZATION SUMMARY ===",
            f"Total Zones: {self.registry.zone_count}",
            f"  Road Zones: {self.registry.road_zone_count}",
            f"  Parking Zones: {self.registry.parking_zone_count}",
            f"  Exclusion Zones: {self.registry.exclusion_zone_count}",
            "",
        ]
        
        for zone in self.registry:
            lines.append(f"[{zone.zone_type.value.upper()}] {zone.zone_id}")
            lines.append(f"  Asset: {zone.asset_id}")
            lines.append(f"  Enabled: {zone.enabled}")
            lines.append(f"  Allowed Classes: {[c.value for c in zone.allowed_classes]}")
            
            if isinstance(zone, ParkingZone):
                lines.append(f"  Slots: {len(zone.slots)}")
                available = sum(1 for s in zone.slots if s.state.name == "AVAILABLE")
                lines.append(f"  Available: {available}")
            
            if isinstance(zone, RoadZone):
                lines.append(f"  Lanes: {len(zone.lanes)}")
                lines.append(f"  Direction: {zone.direction.value}")
            
            lines.append("")
        
        return "\n".join(lines)


def create_test_zones() -> ZoneRegistry:
    """
    Create a test zone configuration for debugging.
    
    Returns:
        ZoneRegistry with sample zones
    """
    from .zone_data import ZoneBounds, Transform3D, Rotation3
    
    registry = ZoneRegistry()
    
    # Create a simple road zone
    road_zone = RoadZone(
        zone_id="test_road_01",
        asset_id="test_level",
        zone_type=ZoneType.ROAD,
        bounds=ZoneBounds(
            shape=ZoneShape.BOX,
            center=Vector3(50.0, 0.0, 0.0),
            size=Vector3(100.0, 12.0, 5.0),
        ),
        allowed_classes=frozenset([
            VehicleClass.CAR,
            VehicleClass.TRUCK,
            VehicleClass.BUS,
            VehicleClass.MOTORCYCLE,
            VehicleClass.BICYCLE,
        ]),
        lanes=[
            {"y_offset": -4.0, "width": 4.0},
            {"y_offset": 0.0, "width": 4.0},
            {"y_offset": 4.0, "width": 4.0},
        ],
    )
    registry.register_zone(road_zone)
    
    # Create a parking zone with slots
    from .zone_data import ParkingSlot
    
    slots = []
    for i in range(6):
        slot = ParkingSlot(
            slot_id=f"slot_{i:02d}",
            transform=Transform3D(
                position=Vector3(-20.0, -10.0 + i * 4.0, 0.0),
                rotation=Rotation3(yaw=90.0),
            ),
            allowed_classes=frozenset([VehicleClass.CAR, VehicleClass.MOTORCYCLE]),
        )
        slots.append(slot)
    
    parking_zone = ParkingZone(
        zone_id="test_parking_01",
        asset_id="test_level",
        zone_type=ZoneType.PARKING,
        bounds=ZoneBounds(
            shape=ZoneShape.BOX,
            center=Vector3(-20.0, 0.0, 0.0),
            size=Vector3(10.0, 30.0, 5.0),
        ),
        allowed_classes=frozenset([VehicleClass.CAR, VehicleClass.MOTORCYCLE]),
        slots=slots,
    )
    registry.register_zone(parking_zone)
    
    # Create an exclusion zone
    exclusion_zone = ExclusionZone(
        zone_id="test_exclusion_01",
        asset_id="test_level",
        zone_type=ZoneType.EXCLUSION,
        bounds=ZoneBounds(
            shape=ZoneShape.BOX,
            center=Vector3(0.0, 20.0, 0.0),
            size=Vector3(20.0, 10.0, 10.0),
        ),
        allowed_classes=frozenset(),
        reason="Building footprint",
    )
    registry.register_zone(exclusion_zone)
    
    return registry


# Import VehicleClass for test zones
from ..config import VehicleClass
