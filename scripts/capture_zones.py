"""
Zone Capture Tool - Automatic Zone Classification from UE5 Level

AUTOMATIC CLASSIFICATION RULES:
================================

1. ELIGIBILITY: Only StaticMeshActors with scale EXACTLY (0.5, 0.5, 0.5)
   - All other actors are IGNORED and logged

2. ZONE TYPE BY FORWARD VECTOR (Red Arrow):
   - SIDEWALK: Two anchors with arrows pointing TOWARD each other (dot ≈ -1.0)
   - ROAD/LANE: Two anchors with arrows pointing SAME direction (dot ≈ +1.0)
   - PARKING: Single anchor (unpaired or no valid match)

3. PAIRING LOGIC:
   - Uses dot product of forward vectors
   - Tolerance: 0.1 for pairing threshold
   - Each anchor can only belong to ONE zone

Usage:
------
# Auto-classify all eligible anchors:
python scripts/capture_zones.py --auto --output zones.yaml

# List all eligible anchors without generating YAML:
python scripts/capture_zones.py --auto --list-only

# Legacy mode with pattern matching:
python scripts/capture_zones.py --pattern "StaticMeshActor_*" --list-only
"""

import argparse
import math
import requests
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

REQUIRED_SCALE = (0.3, 0.3, 0.3)
SCALE_TOLERANCE = 0.001
DOT_PRODUCT_TOLERANCE = 0.1  # For pairing classification
FORWARD_VECTOR_MIN_LENGTH = 0.9  # Safety check for valid forward vector

# Distance constraints for pairing
MIN_LANE_DISTANCE = 1500.0  # Lanes must be at least 15m apart
MIN_SIDEWALK_DISTANCE = 500.0  # Sidewalk corners must be at least 5m apart
MAX_PARKING_ROW_DISTANCE = 800.0  # Parking slots in a row are within 8m of each other

# ============================================================================
# MULTI-LOCATION SUPPORT
# ============================================================================

# Global X bounds for zone detection
X_MIN_GLOBAL = 5000.0
X_MAX_GLOBAL = 30000.0

# Y range configuration for locations
Y_RANGE_SIZE = 20000.0 - 400.0  # 19600 units per location
Y_START_BASE = 400.0

# Number of locations to support
NUM_LOCATIONS = 7

# Generate location Y bounds dynamically
LOCATION_Y_BOUNDS = [
    (Y_START_BASE + i * Y_RANGE_SIZE, Y_START_BASE + (i + 1) * Y_RANGE_SIZE)
    for i in range(NUM_LOCATIONS)
]

# Vehicle capacity calculation
CAPACITY_UNITS_PER_500 = 1  # +1 vehicle per 500 units
BUS_CAPACITY_COST = 2       # Bus consumes 2 capacity units


class ZoneType(Enum):
    PARKING = "PARKING"
    SIDEWALK = "SIDEWALK"
    ROAD = "ROAD"


@dataclass
class Transform:
    position: List[float]  # [x, y, z]
    rotation: List[float]  # [pitch, yaw, roll]
    scale: List[float] = None
    forward_vector: List[float] = None  # Computed from rotation


@dataclass
class AnchorActor:
    """Single anchor actor with full transform data"""
    name: str
    transform: Transform
    zone_type: ZoneType = None
    paired_with: str = None  # Name of paired anchor (if any)


@dataclass
class ClassifiedZone:
    """A classified zone (parking slot, lane, or sidewalk)"""
    zone_type: ZoneType
    anchors: List[AnchorActor]
    dot_product: float = None  # For paired zones


# ============================================================================
# VECTOR MATH UTILITIES
# ============================================================================

def is_within_global_bounds(position: List[float]) -> bool:
    """Check if position is within global X bounds"""
    x = position[0]
    return X_MIN_GLOBAL <= x <= X_MAX_GLOBAL


def get_location_index(position: List[float]) -> Optional[int]:
    """
    Determine which location (1-7) a position belongs to based on Y coordinate.
    Returns None if position is outside all location bounds or global X bounds.
    """
    if not is_within_global_bounds(position):
        return None
    
    y = position[1]
    for idx, (y_min, y_max) in enumerate(LOCATION_Y_BOUNDS):
        if y_min <= y < y_max:
            return idx + 1  # 1-indexed locations
    
    return None


def calculate_lane_distance(pos1: List[float], pos2: List[float]) -> float:
    """Calculate world-space distance between lane endpoints (2D horizontal distance)"""
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    return math.sqrt(dx * dx + dy * dy)


def calculate_vehicle_capacity(distance: float) -> int:
    """
    Calculate vehicle capacity based on distance.
    Formula: +1 vehicle per 500 units of distance
    """
    return int(distance / 500.0)


def yaw_to_forward_vector(yaw_degrees: float) -> List[float]:
    """
    Convert yaw rotation to unit forward vector.
    UE5: Yaw is rotation around Z-axis, 0° = +X direction
    """
    yaw_rad = math.radians(yaw_degrees)
    return [
        math.cos(yaw_rad),  # X
        math.sin(yaw_rad),  # Y
        0.0                 # Z (horizontal)
    ]


def vector_length(v: List[float]) -> float:
    """Compute vector magnitude"""
    return math.sqrt(sum(c * c for c in v))


def distance_3d(pos1: List[float], pos2: List[float]) -> float:
    """Compute 3D distance between two positions"""
    return math.sqrt(
        (pos2[0] - pos1[0]) ** 2 +
        (pos2[1] - pos1[1]) ** 2 +
        (pos2[2] - pos1[2]) ** 2
    )


def are_sidewalk_corners(pos1: List[float], pos2: List[float], fwd1: List[float], fwd2: List[float]) -> bool:
    """
    Check if two anchors define sidewalk corners (opposite directions, aligned perpendicularly).
    Sidewalk corners should be aligned along one axis (defining a boundary).
    CRITICAL: Arrows must point TOWARD each other, not just have opposite directions.
    """
    # Check if forward vectors are opposite
    dp = dot_product(fwd1, fwd2)
    if dp > -0.9:  # Not opposite enough
        return False
    
    # CRITICAL CHECK: Verify arrows point TOWARD each other's positions
    # Direction from pos1 to pos2
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    dist = (dx**2 + dy**2)**0.5
    if dist < MIN_SIDEWALK_DISTANCE:
        return False
    
    # Normalize direction vector
    dir_to_2 = [dx / dist, dy / dist, 0.0]
    dir_to_1 = [-dx / dist, -dy / dist, 0.0]
    
    # Check if fwd1 points toward pos2 and fwd2 points toward pos1
    # Both dot products should be positive (pointing toward each other)
    dot_fwd1_to2 = dot_product(fwd1, dir_to_2)
    dot_fwd2_to1 = dot_product(fwd2, dir_to_1)
    
    if dot_fwd1_to2 < 0.7 or dot_fwd2_to1 < 0.7:
        # Arrows don't point toward each other - just parking spots with opposite yaw
        return False
    
    # Check position relationship - should be aligned along one axis
    delta_x = abs(dx)
    delta_y = abs(dy)
    
    # Sidewalk corners: aligned primarily along one axis
    # Either delta_x is much larger than delta_y, or vice versa
    max_delta = max(delta_x, delta_y)
    min_delta = min(delta_x, delta_y)
    
    # If max delta is at least 3x the min delta, they're aligned along an axis
    if min_delta < 300 or max_delta > 3 * min_delta:
        return True
    
    return False


def are_aligned_along_direction(pos1: List[float], pos2: List[float], direction: List[float], tolerance: float = 0.3) -> bool:
    """
    Check if two positions are aligned along a direction vector.
    For lanes: anchors should be positioned along the lane direction.
    """
    # Vector from pos1 to pos2
    delta = [pos2[0] - pos1[0], pos2[1] - pos1[1], 0]  # Ignore Z
    delta_length = math.sqrt(delta[0]**2 + delta[1]**2)
    
    if delta_length < 100:  # Too close
        return False
    
    # Normalize delta
    delta_norm = [delta[0] / delta_length, delta[1] / delta_length, 0]
    
    # Dot product with direction (should be close to ±1 if aligned)
    alignment = abs(dot_product(delta_norm, direction))
    
    return alignment > (1.0 - tolerance)


def dot_product(v1: List[float], v2: List[float]) -> float:
    """Compute dot product of two vectors"""
    return sum(a * b for a, b in zip(v1, v2))


def is_valid_forward_vector(v: List[float]) -> bool:
    """Check if forward vector has valid magnitude (~1.0)"""
    length = vector_length(v)
    return length >= FORWARD_VECTOR_MIN_LENGTH


def scale_matches_required(scale: List[float]) -> bool:
    """Check if scale matches REQUIRED_SCALE within tolerance"""
    if scale is None or len(scale) != 3:
        return False
    return all(
        abs(scale[i] - REQUIRED_SCALE[i]) <= SCALE_TOLERANCE
        for i in range(3)
    )


# ============================================================================
# ZONE CLASSIFICATION ENGINE
# ============================================================================

def classify_anchors(anchors: List[AnchorActor]) -> Tuple[List[ClassifiedZone], List[AnchorActor]]:
    """
    Centralized zone classification based on forward vector dot products.
    
    Returns:
        - List of ClassifiedZone objects
        - List of unpaired anchors (fallback to PARKING)
    """
    zones: List[ClassifiedZone] = []
    used_indices = set()
    n = len(anchors)
    
    print(f"\n{'='*60}")
    print("ZONE CLASSIFICATION ENGINE")
    print(f"{'='*60}")
    print(f"Eligible anchors: {n}")
    
    # ========================================================================
    # STEP 1: Find ROAD/LANE pairs (arrows pointing SAME direction, dot ≈ +1.0)
    # Must be far apart to define a lane segment (> MIN_LANE_DISTANCE)
    # ========================================================================
    print(f"\n--- Pass 1: Finding ROAD pairs (dot ~= +1.0, dist > {MIN_LANE_DISTANCE:.0f}) ---")
    
    for i in range(n):
        if i in used_indices:
            continue
        
        anchor_a = anchors[i]
        fwd_a = anchor_a.transform.forward_vector
        
        if not is_valid_forward_vector(fwd_a):
            continue
        
        best_match = None
        best_dot = None
        best_distance = None
        
        for j in range(i + 1, n):
            if j in used_indices:
                continue
            
            anchor_b = anchors[j]
            fwd_b = anchor_b.transform.forward_vector
            
            if not is_valid_forward_vector(fwd_b):
                continue
            
            dp = dot_product(fwd_a, fwd_b)
            dist = distance_3d(anchor_a.transform.position, anchor_b.transform.position)
            
            # ROAD: arrows point SAME direction (dot ≈ +1.0) AND far apart AND aligned along direction
            if dp > (1.0 - DOT_PRODUCT_TOLERANCE) and dist >= MIN_LANE_DISTANCE:
                # Check if the two anchors are aligned along the forward direction
                if are_aligned_along_direction(anchor_a.transform.position, anchor_b.transform.position, fwd_a):
                    if best_match is None or dp > best_dot:
                        best_match = j
                        best_dot = dp
                        best_distance = dist
        
        if best_match is not None:
            anchor_b = anchors[best_match]
            
            # Mark both as used
            used_indices.add(i)
            used_indices.add(best_match)
            
            # Classify as ROAD
            anchor_a.zone_type = ZoneType.ROAD
            anchor_a.paired_with = anchor_b.name
            anchor_b.zone_type = ZoneType.ROAD
            anchor_b.paired_with = anchor_a.name
            
            zone = ClassifiedZone(
                zone_type=ZoneType.ROAD,
                anchors=[anchor_a, anchor_b],
                dot_product=best_dot
            )
            zones.append(zone)
            
            print(f"  [ROAD] {anchor_a.name} -> {anchor_b.name} (dot={best_dot:.4f}, dist={best_distance:.1f})")
    
    # ========================================================================
    # STEP 2: Find SIDEWALK pairs (arrows pointing TOWARD each other, dot ≈ -1.0)
    # Must be far apart to define a region (> MIN_SIDEWALK_DISTANCE)
    # ========================================================================
    print(f"\n--- Pass 2: Finding SIDEWALK pairs (dot ~= -1.0, dist > {MIN_SIDEWALK_DISTANCE:.0f}) ---")
    
    for i in range(n):
        if i in used_indices:
            continue
        
        anchor_a = anchors[i]
        fwd_a = anchor_a.transform.forward_vector
        
        if not is_valid_forward_vector(fwd_a):
            print(f"  ⚠️  {anchor_a.name}: Invalid forward vector, skipping pair search")
            continue
        
        best_match = None
        best_dot = None
        best_distance = None
        
        for j in range(i + 1, n):
            if j in used_indices:
                continue
            
            anchor_b = anchors[j]
            fwd_b = anchor_b.transform.forward_vector
            
            if not is_valid_forward_vector(fwd_b):
                continue
            
            dp = dot_product(fwd_a, fwd_b)
            dist = distance_3d(anchor_a.transform.position, anchor_b.transform.position)
            
            # SIDEWALK: arrows point TOWARD each other (dot ≈ -1.0) AND define corner bounds
            if dp < (-1.0 + DOT_PRODUCT_TOLERANCE) and dist >= MIN_SIDEWALK_DISTANCE:
                # Check if these are sidewalk corners (aligned perpendicularly)
                if are_sidewalk_corners(anchor_a.transform.position, anchor_b.transform.position, fwd_a, fwd_b):
                    if best_match is None or dp < best_dot:
                        best_match = j
                        best_dot = dp
                        best_distance = dist
        
        if best_match is not None:
            anchor_b = anchors[best_match]
            
            # Mark both as used
            used_indices.add(i)
            used_indices.add(best_match)
            
            # Classify as SIDEWALK
            anchor_a.zone_type = ZoneType.SIDEWALK
            anchor_a.paired_with = anchor_b.name
            anchor_b.zone_type = ZoneType.SIDEWALK
            anchor_b.paired_with = anchor_a.name
            
            zone = ClassifiedZone(
                zone_type=ZoneType.SIDEWALK,
                anchors=[anchor_a, anchor_b],
                dot_product=best_dot
            )
            zones.append(zone)
            
            print(f"  [SIDEWALK] {anchor_a.name} <-> {anchor_b.name} (dot={best_dot:.4f}, dist={best_distance:.1f})")
    
    # ========================================================================
    # STEP 3: Remaining anchors are PARKING slots
    # CRITICAL: Parking spots must have arrows pointing to EMPTY SPACE, not toward other anchors
    # ========================================================================
    print(f"\n--- Pass 3: Remaining anchors -> PARKING ---")
    
    parking_zones = []
    for i in range(n):
        if i in used_indices:
            continue
        
        anchor = anchors[i]
        
        # VALIDATION: Check if this anchor's arrow points toward any other anchor
        # If it does, it's likely a lane/sidewalk start that couldn't pair, not true parking
        pos_a = anchor.transform.position
        fwd_a = anchor.transform.forward_vector
        points_to_anchor = False
        
        for j in range(n):
            if i == j:
                continue
            
            pos_b = anchors[j].transform.position
            
            # Calculate direction from anchor to other anchor
            dx = pos_b[0] - pos_a[0]
            dy = pos_b[1] - pos_a[1]
            dist = (dx**2 + dy**2)**0.5
            
            if dist < 100:  # Too close, skip
                continue
            
            # Normalize direction
            dir_to_b = [dx / dist, dy / dist, 0.0]
            
            # Check if arrow points toward this other anchor
            dot_to_b = dot_product(fwd_a, dir_to_b)
            
            # If arrow points strongly toward another anchor (within reasonable distance)
            if dot_to_b > 0.85 and dist < 5000:
                points_to_anchor = True
                break
        
        # Only classify as parking if arrow points to empty space
        if not points_to_anchor:
            anchor.zone_type = ZoneType.PARKING
            
            zone = ClassifiedZone(
                zone_type=ZoneType.PARKING,
                anchors=[anchor],
                dot_product=None
            )
            parking_zones.append(zone)
            
            print(f"  [PARKING] {anchor.name}")
        else:
            print(f"  [SKIP] {anchor.name} (arrow points toward another anchor)")
    
    zones.extend(parking_zones)
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    sidewalk_count = sum(1 for z in zones if z.zone_type == ZoneType.SIDEWALK)
    road_count = sum(1 for z in zones if z.zone_type == ZoneType.ROAD)
    parking_count = sum(1 for z in zones if z.zone_type == ZoneType.PARKING)
    
    print(f"\n{'='*60}")
    print("CLASSIFICATION SUMMARY")
    print(f"{'='*60}")
    print(f"  SIDEWALK zones: {sidewalk_count} (paired)")
    print(f"  ROAD zones:     {road_count} (paired)")
    print(f"  PARKING slots:  {parking_count} (singles)")
    print(f"  TOTAL zones:    {len(zones)}")
    
    return zones, [anchors[i] for i in range(n) if i not in used_indices]


# ============================================================================
# UE5 REMOTE CONTROL CLIENT
# ============================================================================

class ZoneCaptureClient:
    """UE5 Remote Control API client for capturing zone data"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 30010):
        self.base_url = f"http://{host}:{port}/remote/object"
        self.session = requests.Session()
    
    def get_all_static_mesh_actors(self) -> List[str]:
        """Get all StaticMeshActor instances in the level"""
        # Remote Control API's GetAllActorsOfClass doesn't work reliably
        # Instead, we'll scan common actor name patterns
        print("  Scanning for StaticMeshActor patterns...")
        
        found_actors = []
        
        # Try common naming patterns: StaticMeshActor_0 to StaticMeshActor_500
        for i in range(500):
            actor_name = f"StaticMeshActor_{i}"
            actor_path = f"PersistentLevel.{actor_name}"
            
            # Quick check: try to get location
            response = self.session.put(
                f"{self.base_url}/call",
                json={
                    "objectPath": actor_path,
                    "functionName": "K2_GetActorLocation"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if "ReturnValue" in data:
                    # Actor exists!
                    found_actors.append(actor_path)
        
        print(f"  Found {len(found_actors)} actors via pattern scan")
        return found_actors
    
    def get_actor_transform_full(self, actor_path: str) -> Optional[Transform]:
        """Get full transform (location, rotation, scale) of an actor"""
        try:
            # Get location
            loc_response = self.session.put(
                f"{self.base_url}/call",
                json={
                    "objectPath": actor_path,
                    "functionName": "K2_GetActorLocation"
                }
            )
            
            # Get rotation
            rot_response = self.session.put(
                f"{self.base_url}/call",
                json={
                    "objectPath": actor_path,
                    "functionName": "K2_GetActorRotation"
                }
            )
            
            # Get scale
            scale_response = self.session.put(
                f"{self.base_url}/call",
                json={
                    "objectPath": actor_path,
                    "functionName": "GetActorScale3D"
                }
            )
            
            if any(r.status_code != 200 for r in [loc_response, rot_response, scale_response]):
                return None
            
            location = loc_response.json().get("ReturnValue", {})
            rotation = rot_response.json().get("ReturnValue", {})
            scale = scale_response.json().get("ReturnValue", {})
            
            position = [location.get("X", 0), location.get("Y", 0), location.get("Z", 0)]
            rot = [rotation.get("Pitch", 0), rotation.get("Yaw", 0), rotation.get("Roll", 0)]
            sc = [scale.get("X", 1), scale.get("Y", 1), scale.get("Z", 1)]
            
            # Compute forward vector from yaw
            forward = yaw_to_forward_vector(rot[1])  # Yaw is index 1
            
            return Transform(
                position=position,
                rotation=rot,
                scale=sc,
                forward_vector=forward
            )
        except Exception as e:
            print(f"  [ERROR] Failed to get transform: {e}")
            return None
    
    def discover_eligible_anchors(self) -> Tuple[List[AnchorActor], List[Tuple[str, List[float]]]]:
        """
        Discover all StaticMeshActors and filter by scale and location bounds.
        
        Returns:
            - List of eligible AnchorActor objects (within bounds)
            - List of ignored actors (name, scale) for logging
        """
        print(f"\n{'='*60}")
        print("ANCHOR DISCOVERY")
        print(f"{'='*60}")
        print(f"Required scale: {REQUIRED_SCALE}")
        print(f"Scale tolerance: {SCALE_TOLERANCE}")
        print(f"Global X bounds: [{X_MIN_GLOBAL:.0f}, {X_MAX_GLOBAL:.0f}]")
        print(f"Locations: {NUM_LOCATIONS}")
        for idx, (y_min, y_max) in enumerate(LOCATION_Y_BOUNDS):
            print(f"  Location {idx + 1}: Y in [{y_min:.0f}, {y_max:.0f}]")
        
        all_actors = self.get_all_static_mesh_actors()
        print(f"\nTotal StaticMeshActors in level: {len(all_actors)}")
        
        eligible: List[AnchorActor] = []
        ignored: List[Tuple[str, List[float]]] = []
        
        for actor_path in sorted(all_actors):
            # Extract name from path
            name = actor_path.split('.')[-1].split(':')[-1]
            
            transform = self.get_actor_transform_full(actor_path)
            if transform is None:
                print(f"  [ERROR] {name}: Failed to get transform")
                continue
            
            # Check location bounds (X and Y)
            location_idx = get_location_index(transform.position)
            if location_idx is None:
                # Outside all location bounds - ignore
                continue
            
            # Check scale eligibility
            if scale_matches_required(transform.scale):
                anchor = AnchorActor(name=name, transform=transform)
                eligible.append(anchor)
            else:
                ignored.append((name, transform.scale))
        
        # Log eligible anchors
        print(f"\n--- ELIGIBLE ANCHORS ({len(eligible)}) [within bounds] ---")
        for anchor in eligible:
            t = anchor.transform
            fwd = t.forward_vector
            loc_idx = get_location_index(t.position)
            print(f"  + {anchor.name:25} [Location {loc_idx}]")
            print(f"      Scale: ({t.scale[0]:.2f}, {t.scale[1]:.2f}, {t.scale[2]:.2f})")
            print(f"      Pos:   ({t.position[0]:8.1f}, {t.position[1]:8.1f}, {t.position[2]:8.1f})")
            print(f"      Yaw:   {t.rotation[1]:.1f}°")
            print(f"      Fwd:   ({fwd[0]:.3f}, {fwd[1]:.3f}, {fwd[2]:.3f})")
        
        # Log ignored anchors
        if ignored:
            print(f"\n--- IGNORED ACTORS ({len(ignored)}) [wrong scale or out of bounds] ---")
            for name, scale in ignored[:20]:  # Limit output
                print(f"  - {name:25} Scale: ({scale[0]:.2f}, {scale[1]:.2f}, {scale[2]:.2f})")
            if len(ignored) > 20:
                print(f"  ... and {len(ignored) - 20} more")
        
        return eligible, ignored


# ============================================================================
# MANIFEST GENERATION
# ============================================================================

def generate_classified_manifest(
    zones: List[ClassifiedZone],
    level_name: str = None
) -> Dict[str, Any]:
    """Generate YAML manifest from classified zones"""
    
    parking_anchors = []
    lanes = []
    sidewalks = []
    
    for zone in zones:
        if zone.zone_type == ZoneType.PARKING:
            anchor = zone.anchors[0]
            parking_anchors.append({
                "name": anchor.name,
                "position": [round(p, 2) for p in anchor.transform.position],
                "yaw": round(anchor.transform.rotation[1], 2)
            })
        
        elif zone.zone_type == ZoneType.ROAD:
            # First anchor = start, second = end (based on discovery order)
            anchor_a, anchor_b = zone.anchors
            lanes.append({
                "id": f"lane_{len(lanes) + 1}",
                "start_anchor": anchor_a.name,
                "end_anchor": anchor_b.name,
                "start_position": [round(p, 2) for p in anchor_a.transform.position],
                "end_position": [round(p, 2) for p in anchor_b.transform.position],
                "dot_product": round(zone.dot_product, 4)
            })
        
        elif zone.zone_type == ZoneType.SIDEWALK:
            anchor_a, anchor_b = zone.anchors
            sidewalks.append({
                "id": f"sidewalk_{len(sidewalks) + 1}",
                "anchor_1": anchor_a.name,
                "anchor_2": anchor_b.name,
                "position_1": [round(p, 2) for p in anchor_a.transform.position],
                "position_2": [round(p, 2) for p in anchor_b.transform.position],
                "dot_product": round(zone.dot_product, 4)
            })
    
    manifest = {
        "manifest_version": 2,
        "classification_mode": "automatic",
        "level_name": level_name or "AutoClassifiedLevel",
        "eligibility_scale": list(REQUIRED_SCALE),
        "dot_product_tolerance": DOT_PRODUCT_TOLERANCE,
        
        "parking": {
            "count": len(parking_anchors),
            "anchors": parking_anchors
        },
        
        "lanes": {
            "count": len(lanes),
            "definitions": lanes
        },
        
        "sidewalks": {
            "count": len(sidewalks),
            "definitions": sidewalks
        }
    }
    
    return manifest


# ============================================================================
# VALIDATION SUMMARY
# ============================================================================

def print_validation_summary(zones: List[ClassifiedZone]):
    """
    Print comprehensive validation summary for all locations.
    Includes counts per location and capacity calculations.
    """
    print(f"\n{'='*70}")
    print("VALIDATION SUMMARY - MULTI-LOCATION ZONE ANALYSIS")
    print(f"{'='*70}")
    
    # Initialize location tracking
    location_data = {
        i: {"parking": 0, "lanes": [], "sidewalks": []}
        for i in range(1, NUM_LOCATIONS + 1)
    }
    
    # Classify zones by location
    for zone in zones:
        if zone.zone_type == ZoneType.PARKING:
            # Single anchor
            pos = zone.anchors[0].transform.position
            loc_idx = get_location_index(pos)
            if loc_idx:
                location_data[loc_idx]["parking"] += 1
        
        elif zone.zone_type == ZoneType.ROAD:
            # Paired anchors (lane)
            pos1 = zone.anchors[0].transform.position
            pos2 = zone.anchors[1].transform.position
            # Both anchors must be in the same location
            loc_idx1 = get_location_index(pos1)
            loc_idx2 = get_location_index(pos2)
            
            if loc_idx1 and loc_idx1 == loc_idx2:
                # Only count if both anchors are in the same location
                distance = calculate_lane_distance(pos1, pos2)
                capacity = calculate_vehicle_capacity(distance)
                location_data[loc_idx1]["lanes"].append({
                    "name": f"{zone.anchors[0].name} -> {zone.anchors[1].name}",
                    "distance": distance,
                    "capacity": capacity
                })
        
        elif zone.zone_type == ZoneType.SIDEWALK:
            # Paired anchors (sidewalk)
            pos1 = zone.anchors[0].transform.position
            pos2 = zone.anchors[1].transform.position
            # Both anchors must be in the same location
            loc_idx1 = get_location_index(pos1)
            loc_idx2 = get_location_index(pos2)
            
            if loc_idx1 and loc_idx1 == loc_idx2:
                # Only count if both anchors are in the same location
                distance = calculate_lane_distance(pos1, pos2)
                capacity = int(distance / 500)
                location_data[loc_idx1]["sidewalks"].append({
                    "name": f"{zone.anchors[0].name} -> {zone.anchors[1].name}",
                    "distance": distance,
                    "capacity": capacity
                })
    
    # Print summary for each location
    for loc_idx in range(1, NUM_LOCATIONS + 1):
        data = location_data[loc_idx]
        y_min, y_max = LOCATION_Y_BOUNDS[loc_idx - 1]
        
        print(f"\nLOCATION {loc_idx} | Y ∈ [{y_min:.0f}, {y_max:.0f}]")
        print(f"{'-'*70}")
        
        # Counts
        print(f"  Parking Spots:  {data['parking']}")
        print(f"  Lanes:          {len(data['lanes'])}")
        print(f"  Sidewalks:      {len(data['sidewalks'])}")
        
        # Lane details
        if data['lanes']:
            print(f"\n  Lane Details:")
            for lane in data['lanes']:
                print(f"    • {lane['name']}")
                print(f"      Distance: {lane['distance']:.1f} units")
                print(f"      Capacity: {lane['capacity']} vehicles (+{lane['capacity']*2} if all buses)")
        
        # Sidewalk details
        if data['sidewalks']:
            print(f"\n  Sidewalk Details:")
            for sidewalk in data['sidewalks']:
                print(f"    • {sidewalk['name']}")
                print(f"      Distance: {sidewalk['distance']:.1f} units")
                print(f"      Capacity: {sidewalk['capacity']} vehicles")
    
    # Global summary
    print(f"\n{'='*70}")
    print("GLOBAL SUMMARY")
    print(f"{'='*70}")
    total_parking = sum(loc["parking"] for loc in location_data.values())
    total_lanes = sum(len(loc["lanes"]) for loc in location_data.values())
    total_sidewalks = sum(len(loc["sidewalks"]) for loc in location_data.values())
    
    print(f"  Total Parking Spots:  {total_parking}")
    print(f"  Total Lanes:          {total_lanes}")
    print(f"  Total Sidewalks:      {total_sidewalks}")
    print(f"  Total Zones:          {len(zones)}")
    
    print(f"\nCapacity Calculation Formula:")
    print(f"  • +{CAPACITY_UNITS_PER_500} vehicle per 500 units of distance")
    print(f"  • Bus consumes {BUS_CAPACITY_COST} capacity units")
    print(f"{'='*70}\n")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Capture and auto-classify zone anchors from UE5 level",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-classify all eligible anchors (scale 0.5, 0.5, 0.5):
  python scripts/capture_zones.py --auto --list-only
  
  # Generate YAML manifest:
  python scripts/capture_zones.py --auto --output my_level.yaml
  
  # Legacy pattern mode:
  python scripts/capture_zones.py --pattern "StaticMeshActor_*" --list-only
        """
    )
    
    parser.add_argument("--auto", action="store_true",
                        help="Auto-discover and classify all eligible anchors")
    parser.add_argument("--pattern", help="Legacy: Actor name pattern")
    parser.add_argument("--actors", help="Legacy: Comma-separated actor names")
    parser.add_argument("--output", help="Output YAML file path")
    parser.add_argument("--level-name", help="Level name for manifest")
    parser.add_argument("--host", default="127.0.0.1", help="UE5 Remote Control host")
    parser.add_argument("--port", type=int, default=30010, help="UE5 Remote Control port")
    parser.add_argument("--list-only", action="store_true", help="List only, don't generate YAML")
    
    args = parser.parse_args()
    
    # Validate input
    if not args.auto and not args.pattern and not args.actors:
        print("❌ ERROR: Must provide --auto, --pattern, or --actors")
        parser.print_help()
        return 1
    
    client = ZoneCaptureClient(host=args.host, port=args.port)
    
    # ========================================================================
    # AUTO-CLASSIFICATION MODE
    # ========================================================================
    if args.auto:
        print("\n" + "="*60)
        print("AUTOMATIC ZONE CLASSIFICATION")
        print("="*60)
        
        # Step 1: Discover eligible anchors
        eligible, ignored = client.discover_eligible_anchors()
        
        if not eligible:
            print("\n❌ No eligible anchors found!")
            print(f"   Required scale: {REQUIRED_SCALE}")
            print(f"   Place StaticMeshActors with scale (0.5, 0.5, 0.5) to use as anchors")
            return 1
        
        # Step 2: Group anchors by location
        print("\n" + "="*60)
        print("LOCATION-BASED GROUPING")
        print("="*60)
        
        location_anchors = {i: [] for i in range(1, NUM_LOCATIONS + 1)}
        for anchor in eligible:
            loc_idx = get_location_index(anchor.transform.position)
            if loc_idx:
                location_anchors[loc_idx].append(anchor)
        
        # Print grouping summary
        for loc_idx in range(1, NUM_LOCATIONS + 1):
            count = len(location_anchors[loc_idx])
            print(f"  Location {loc_idx}: {count} anchors")
        
        # Step 3: Classify zones within each location independently
        print("\n" + "="*60)
        print("PER-LOCATION ZONE CLASSIFICATION")
        print("="*60)
        
        all_zones = []
        for loc_idx in range(1, NUM_LOCATIONS + 1):
            anchors = location_anchors[loc_idx]
            if not anchors:
                continue
            
            print(f"\n--- Location {loc_idx} ---")
            zones, _ = classify_anchors(anchors)
            
            # Count zone types
            parking_count = sum(1 for z in zones if z.zone_type == ZoneType.PARKING)
            lane_count = sum(1 for z in zones if z.zone_type == ZoneType.ROAD)
            sidewalk_count = sum(1 for z in zones if z.zone_type == ZoneType.SIDEWALK)
            
            print(f"  Parking: {parking_count}, Lanes: {lane_count}, Sidewalks: {sidewalk_count}")
            all_zones.extend(zones)
        
        zones = all_zones
        
        # Step 2.5: Print validation summary
        print_validation_summary(zones)
        
        if args.list_only:
            print(f"\n[DONE] Classification complete. Use --output to generate YAML.")
            return 0
        
        if not args.output:
            print("\n❌ --output required when not using --list-only")
            return 1
        
        # Step 3: Generate manifest
        manifest = generate_classified_manifest(zones, level_name=args.level_name)
        
        # Write to file
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False, width=120)
        
        print(f"\n✅ Zone manifest saved to: {output_path}")
        return 0
    
    # ========================================================================
    # LEGACY MODE (pattern or actors)
    # ========================================================================
    print("\n⚠️  Legacy mode - consider using --auto for automatic classification")
    
    # Legacy code path preserved for backward compatibility
    # ... (original pattern/actors code would go here)
    print("Legacy mode not fully implemented. Use --auto instead.")
    return 1


if __name__ == "__main__":
    exit(main())
