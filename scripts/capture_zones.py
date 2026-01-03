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
MIN_SIDEWALK_DISTANCE = 1500.0  # Sidewalk corners must be at least 15m apart
MAX_PARKING_ROW_DISTANCE = 800.0  # Parking slots in a row are within 8m of each other


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
    Sidewalk corners should be VERY close in one axis (defining a line) and facing each other.
    """
    # Check if forward vectors are opposite
    dp = dot_product(fwd1, fwd2)
    if dp > -0.9:  # Not opposite enough
        return False
    
    # Check position relationship - should be aligned VERY closely in one axis
    delta_x = abs(pos2[0] - pos1[0])
    delta_y = abs(pos2[1] - pos1[1])
    
    # Sidewalk corners: VERY close in one axis (<100cm), far in other (>3000)
    # This defines a narrow strip/boundary
    if (delta_x < 100 and delta_y > 3000) or (delta_y < 100 and delta_x > 3000):
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
    # STEP 1: Find SIDEWALK pairs (arrows pointing TOWARD each other, dot ≈ -1.0)
    # Must be far apart to define a region (> MIN_SIDEWALK_DISTANCE)
    # ========================================================================
    print(f"\n--- Pass 1: Finding SIDEWALK pairs (dot ≈ -1.0, dist > {MIN_SIDEWALK_DISTANCE:.0f}) ---")
    
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
            
            print(f"  ✓ SIDEWALK: {anchor_a.name} <-> {anchor_b.name} (dot={best_dot:.4f}, dist={best_distance:.1f})")
    
    # ========================================================================
    # STEP 2: Find ROAD/LANE pairs (arrows pointing SAME direction, dot ≈ +1.0)
    # Must be far apart to define a lane segment (> MIN_LANE_DISTANCE)
    # ========================================================================
    print(f"\n--- Pass 2: Finding ROAD pairs (dot ≈ +1.0, dist > {MIN_LANE_DISTANCE:.0f}) ---")
    
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
            
            print(f"  ✓ ROAD: {anchor_a.name} -> {anchor_b.name} (dot={best_dot:.4f}, dist={best_distance:.1f})")
    
    # ========================================================================
    # STEP 3: Remaining anchors are PARKING slots
    # ========================================================================
    print(f"\n--- Pass 3: Remaining anchors -> PARKING ---")
    
    parking_zones = []
    for i in range(n):
        if i in used_indices:
            continue
        
        anchor = anchors[i]
        anchor.zone_type = ZoneType.PARKING
        
        zone = ClassifiedZone(
            zone_type=ZoneType.PARKING,
            anchors=[anchor],
            dot_product=None
        )
        parking_zones.append(zone)
        
        print(f"  ✓ PARKING: {anchor.name}")
    
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
            print(f"  ✗ Failed to get transform: {e}")
            return None
    
    def discover_eligible_anchors(self) -> Tuple[List[AnchorActor], List[Tuple[str, List[float]]]]:
        """
        Discover all StaticMeshActors and filter by scale.
        
        Returns:
            - List of eligible AnchorActor objects
            - List of ignored actors (name, scale) for logging
        """
        print(f"\n{'='*60}")
        print("ANCHOR DISCOVERY")
        print(f"{'='*60}")
        print(f"Required scale: {REQUIRED_SCALE}")
        print(f"Scale tolerance: {SCALE_TOLERANCE}")
        
        all_actors = self.get_all_static_mesh_actors()
        print(f"\nTotal StaticMeshActors in level: {len(all_actors)}")
        
        eligible: List[AnchorActor] = []
        ignored: List[Tuple[str, List[float]]] = []
        
        for actor_path in sorted(all_actors):
            # Extract name from path
            name = actor_path.split('.')[-1].split(':')[-1]
            
            transform = self.get_actor_transform_full(actor_path)
            if transform is None:
                print(f"  ✗ {name}: Failed to get transform")
                continue
            
            # Check scale eligibility
            if scale_matches_required(transform.scale):
                anchor = AnchorActor(name=name, transform=transform)
                eligible.append(anchor)
            else:
                ignored.append((name, transform.scale))
        
        # Log eligible anchors
        print(f"\n--- ELIGIBLE ANCHORS ({len(eligible)}) ---")
        for anchor in eligible:
            t = anchor.transform
            fwd = t.forward_vector
            print(f"  ✓ {anchor.name:25}")
            print(f"      Scale: ({t.scale[0]:.2f}, {t.scale[1]:.2f}, {t.scale[2]:.2f})")
            print(f"      Pos:   ({t.position[0]:8.1f}, {t.position[1]:8.1f}, {t.position[2]:8.1f})")
            print(f"      Yaw:   {t.rotation[1]:.1f}°")
            print(f"      Fwd:   ({fwd[0]:.3f}, {fwd[1]:.3f}, {fwd[2]:.3f})")
        
        # Log ignored anchors
        if ignored:
            print(f"\n--- IGNORED ACTORS ({len(ignored)}) [wrong scale] ---")
            for name, scale in ignored[:20]:  # Limit output
                print(f"  ✗ {name:25} Scale: ({scale[0]:.2f}, {scale[1]:.2f}, {scale[2]:.2f})")
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
        
        # Step 2: Classify zones
        zones, _ = classify_anchors(eligible)
        
        if args.list_only:
            print(f"\n✓ Classification complete. Use --output to generate YAML.")
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
