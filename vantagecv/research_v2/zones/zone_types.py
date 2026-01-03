"""
Zone Type Definitions

Strict enumeration of zone types and shapes.
No ambiguity, no fallbacks.
"""

from enum import Enum, auto


class ZoneType(Enum):
    """
    Explicit zone types for vehicle placement.
    
    Each type has distinct spawning semantics:
    - ROAD: Directional, traffic-aligned placement
    - PARKING: Static, slot-based placement
    - EXCLUSION: No vehicles allowed
    """
    ROAD = "road"
    PARKING = "parking"
    EXCLUSION = "exclusion"
    
    @classmethod
    def from_string(cls, value: str) -> "ZoneType":
        """Parse zone type from string (case-insensitive)."""
        normalized = value.lower().strip()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(
            f"Invalid zone type: '{value}'. "
            f"Valid types: {[m.value for m in cls]}"
        )


class ZoneShape(Enum):
    """
    Supported zone shapes.
    
    - BOX: Axis-aligned or oriented bounding box
    - POLYGON: Convex polygon (2D footprint with height)
    """
    BOX = "box"
    POLYGON = "polygon"
    
    @classmethod
    def from_string(cls, value: str) -> "ZoneShape":
        """Parse zone shape from string (case-insensitive)."""
        normalized = value.lower().strip()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(
            f"Invalid zone shape: '{value}'. "
            f"Valid shapes: {[m.value for m in cls]}"
        )


class LaneDirection(Enum):
    """
    Direction of travel for road zones.
    
    FORWARD: +X direction (away from origin)
    BACKWARD: -X direction (toward origin)
    BIDIRECTIONAL: Either direction allowed
    """
    FORWARD = "forward"
    BACKWARD = "backward"
    BIDIRECTIONAL = "bidirectional"
    
    @classmethod
    def from_string(cls, value: str) -> "LaneDirection":
        """Parse lane direction from string (case-insensitive)."""
        normalized = value.lower().strip()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(
            f"Invalid lane direction: '{value}'. "
            f"Valid directions: {[m.value for m in cls]}"
        )


class SlotState(Enum):
    """
    State of a parking slot.
    """
    AVAILABLE = auto()
    OCCUPIED = auto()
    DISABLED = auto()
