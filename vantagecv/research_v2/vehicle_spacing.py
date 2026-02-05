"""
Vehicle Spacing and Collision Prevention

RESPONSIBILITY:
- Prevent vehicle overlaps using boundary mesh exclusion volumes
- Check vehicle-to-vehicle spacing before spawning
- Support deterministic placement with random seeds

BOUNDARY RULES:
- Cars/Trucks/Buses: Front and back boundary meshes define exclusion volume
- Bikes: Front, back, left, right boundary meshes define exclusion volume
- Parking spots: Spacing checks are SKIPPED (overlap allowed in parking)
- Lane/sidewalk spawns: STRICT collision checking (no overlaps allowed)

NO OVERLAP POLICY:
- If any boundary overlap detected → REJECT spawn
- No fallback placement that allows overlap
- Uncertainty → DO NOT PLACE
"""

import math
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class VehicleOffsets:
    """Boundary mesh offsets relative to vehicle origin (in vehicle's local space)"""
    front: Optional[Dict[str, float]] = None  # Local offset to front boundary
    back: Optional[Dict[str, float]] = None   # Local offset to back boundary
    left: Optional[Dict[str, float]] = None   # Local offset to left boundary (bikes)
    right: Optional[Dict[str, float]] = None  # Local offset to right boundary (bikes)


@dataclass
class VehicleBounds:
    """Vehicle boundary volume defined by mesh positions"""
    vehicle_name: str
    category: str  # "car", "truck", "bus", "bicycle", "motorcycle"
    location: Dict[str, float]  # {"X": ..., "Y": ..., "Z": ...}
    rotation: Dict[str, float]  # {"Pitch": ..., "Yaw": ..., "Roll": ...}
    
    # Boundary mesh positions (world coordinates)
    front_boundary: Optional[Dict[str, float]] = None
    back_boundary: Optional[Dict[str, float]] = None
    left_boundary: Optional[Dict[str, float]] = None  # Bikes only
    right_boundary: Optional[Dict[str, float]] = None  # Bikes only
    
    # Zone information
    in_parking_spot: bool = False  # If True, skip collision checks


class VehicleSpacingChecker:
    """
    Check vehicle spacing and prevent overlaps using boundary meshes.
    
    Usage:
        checker = VehicleSpacingChecker(host="127.0.0.1", port=30010)
        
        # Before spawning a new vehicle
        if checker.can_place_vehicle(vehicle_info, location, rotation, existing_vehicles):
            # Safe to spawn
            pass
        else:
            # Collision detected - try different position
            pass
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 30010,
                 level_path: str = "/Game/automobileV2.automobileV2"):
        self.base_url = f"http://{host}:{port}/remote"
        self.level_path = level_path
        self.session = requests.Session()
        
        # Cache of boundary offsets (relative to vehicle origin)
        # Key: vehicle_name, Value: VehicleOffsets
        self.boundary_offsets: Dict[str, VehicleOffsets] = {}
    
    def can_place_vehicle(self,
                          vehicle_name: str,
                          category: str,
                          location: Dict[str, float],
                          rotation: Dict[str, float],
                          existing_vehicles: List[VehicleBounds],
                          in_parking_spot: bool = False) -> bool:
        """
        Check if a vehicle can be placed without overlapping existing vehicles.
        
        Args:
            vehicle_name: Name of vehicle to place
            category: Vehicle category ("car", "truck", "bus", "bicycle", "motorcycle")
            location: Proposed spawn location {"X": ..., "Y": ..., "Z": ...}
            rotation: Proposed spawn rotation {"Pitch": ..., "Yaw": ..., "Roll": ...}
            existing_vehicles: List of already-placed vehicles with their bounds
            in_parking_spot: If True, skip collision checks (parking exception)
        
        Returns:
            True if vehicle can be placed safely, False if collision detected
        """
        # PARKING SPOT EXCEPTION: Skip checks if in parking
        if in_parking_spot:
            return True
        
        # Get boundary meshes for proposed vehicle
        proposed_bounds = self.get_vehicle_bounds(
            vehicle_name, category, location, rotation, in_parking_spot
        )
        
        if not proposed_bounds:
            # Cannot determine bounds - reject for safety
            return False
        
        # Check against all existing vehicles
        for existing in existing_vehicles:
            # Skip if existing vehicle is in parking (parking exception)
            if existing.in_parking_spot:
                continue
            
            if self._check_collision(proposed_bounds, existing):
                # Collision detected
                return False
        
        # No collisions detected
        return True
    
    def get_vehicle_bounds(self,
                           vehicle_name: str,
                           category: str,
                           location: Dict[str, float],
                           rotation: Dict[str, float],
                           in_parking_spot: bool = False) -> Optional[VehicleBounds]:
        """
        Get vehicle boundary volume from boundary meshes.
        
        IMPORTANT: This method computes boundary positions at the PROPOSED location,
        not the current location. It uses cached offsets to transform boundaries.
        
        Args:
            vehicle_name: Vehicle actor name
            category: Vehicle category
            location: PROPOSED vehicle location (where it will be spawned)
            rotation: PROPOSED vehicle rotation (how it will be oriented)
            in_parking_spot: Whether vehicle is in parking spot
        
        Returns:
            VehicleBounds with boundary mesh positions, or None if failed
        """
        # Ensure we have cached boundary offsets for this vehicle
        if vehicle_name not in self.boundary_offsets:
            if not self._cache_boundary_offsets(vehicle_name, category):
                # Failed to cache offsets - cannot determine bounds
                return None
        
        offsets = self.boundary_offsets[vehicle_name]
        
        # Create bounds object
        bounds = VehicleBounds(
            vehicle_name=vehicle_name,
            category=category,
            location=location,
            rotation=rotation,
            in_parking_spot=in_parking_spot
        )
        
        # Compute world positions by transforming offsets
        if category in ["car", "truck", "bus"]:
            # Cars/Trucks/Buses: Front and back boundaries
            if offsets.front and offsets.back:
                bounds.front_boundary = self._transform_offset(offsets.front, location, rotation)
                bounds.back_boundary = self._transform_offset(offsets.back, location, rotation)
            else:
                return None
        
        elif category in ["bicycle", "motorcycle"]:
            # Bikes: Front, back, left, right boundaries
            if all([offsets.front, offsets.back, offsets.left, offsets.right]):
                bounds.front_boundary = self._transform_offset(offsets.front, location, rotation)
                bounds.back_boundary = self._transform_offset(offsets.back, location, rotation)
                bounds.left_boundary = self._transform_offset(offsets.left, location, rotation)
                bounds.right_boundary = self._transform_offset(offsets.right, location, rotation)
            else:
                return None
        else:
            # Unknown category
            return None
        
        return bounds
    
    def _cache_boundary_offsets(self, vehicle_name: str, category: str) -> bool:
        """
        Cache boundary mesh offsets relative to vehicle origin.
        
        Queries Cube components attached to vehicle and determines which is
        Front/Back/Left/Right based on their relative offsets.
        
        Args:
            vehicle_name: Vehicle actor name
            category: Vehicle category
        
        Returns:
            True if offsets cached successfully, False if failed
        """
        # Get all Cube component locations
        cube_offsets = self._get_cube_component_offsets(vehicle_name)
        
        if not cube_offsets or len(cube_offsets) < 2:
            # No cube boundaries found - fall back to default dimensions
            print(f"  [SPACING] No cube boundaries for {vehicle_name}, using defaults")
            DEFAULT_LENGTHS = {
                "car": 450.0,      # 4.5m
                "truck": 700.0,    # 7.0m
                "bus": 1200.0,     # 12.0m
                "motorcycle": 220.0,  # 2.2m
                "bicycle": 180.0,  # 1.8m
            }
            DEFAULT_WIDTHS = {
                "car": 180.0,      # 1.8m
                "truck": 250.0,    # 2.5m
                "bus": 250.0,      # 2.5m
                "motorcycle": 80.0,   # 0.8m
                "bicycle": 60.0,   # 0.6m
            }
            
            length = DEFAULT_LENGTHS.get(category, 450.0)
            width = DEFAULT_WIDTHS.get(category, 180.0)
            half_length = length / 2.0
            half_width = width / 2.0
            
            offsets = VehicleOffsets()
            offsets.front = {"X": half_length, "Y": 0.0, "Z": 0.0}
            offsets.back = {"X": -half_length, "Y": 0.0, "Z": 0.0}
            if category in ["bicycle", "motorcycle"]:
                offsets.left = {"X": 0.0, "Y": -half_width, "Z": 0.0}
                offsets.right = {"X": 0.0, "Y": half_width, "Z": 0.0}
            
            self.boundary_offsets[vehicle_name] = offsets
            return True
        
        # Classify cubes by offset direction
        # Front: largest positive X, Back: largest negative X
        # Right: largest positive Y, Left: largest negative Y
        front_cube = None
        back_cube = None
        left_cube = None
        right_cube = None
        
        for name, offset in cube_offsets.items():
            x, y = offset["X"], offset["Y"]
            
            # Check if this is primarily X-direction (front/back)
            if abs(x) > abs(y) * 2:  # X dominant
                if x > 0:
                    if front_cube is None or x > front_cube[1]["X"]:
                        front_cube = (name, offset)
                else:
                    if back_cube is None or x < back_cube[1]["X"]:
                        back_cube = (name, offset)
            # Check if this is primarily Y-direction (left/right)
            elif abs(y) > abs(x) * 2:  # Y dominant
                if y > 0:
                    if right_cube is None or y > right_cube[1]["Y"]:
                        right_cube = (name, offset)
                else:
                    if left_cube is None or y < left_cube[1]["Y"]:
                        left_cube = (name, offset)
            else:
                # Mixed - assign to most extreme direction
                if abs(x) >= abs(y):
                    if x > 0 and (front_cube is None or x > front_cube[1]["X"]):
                        front_cube = (name, offset)
                    elif x < 0 and (back_cube is None or x < back_cube[1]["X"]):
                        back_cube = (name, offset)
                else:
                    if y > 0 and (right_cube is None or y > right_cube[1]["Y"]):
                        right_cube = (name, offset)
                    elif y < 0 and (left_cube is None or y < left_cube[1]["Y"]):
                        left_cube = (name, offset)
        
        offsets = VehicleOffsets()
        
        if front_cube:
            offsets.front = front_cube[1]
        if back_cube:
            offsets.back = back_cube[1]
        if left_cube:
            offsets.left = left_cube[1]
        if right_cube:
            offsets.right = right_cube[1]
        
        # Validate we have at least front and back
        if not offsets.front or not offsets.back:
            print(f"  [SPACING] Incomplete boundaries for {vehicle_name}: front={offsets.front}, back={offsets.back}")
            return False
        
        self.boundary_offsets[vehicle_name] = offsets
        return True
    
    def _get_cube_component_offsets(self, vehicle_name: str) -> Dict[str, Dict[str, float]]:
        """
        Get offsets of boundary marker components relative to vehicle in LOCAL space.
        
        Boundary markers can be named:
        - Cube, Cube0-9 (common naming)
        - StaticMeshComponent_NNN (numbered components with offset from center)
        
        IMPORTANT: Components are queried in world space, then rotated into the vehicle's
        local space using the inverse of the vehicle's current rotation.
        
        Returns:
            Dict mapping component name to LOCAL offset {"X": ..., "Y": ..., "Z": ...}
        """
        veh_path = f"{self.level_path}:PersistentLevel.{vehicle_name}"
        
        try:
            # Get vehicle location
            response = self.session.put(
                f"{self.base_url}/object/call",
                json={"objectPath": veh_path, "functionName": "K2_GetActorLocation"},
                timeout=2.0
            )
            if response.status_code != 200:
                return {}
            veh_loc = response.json().get("ReturnValue", {})
            
            # Get vehicle rotation
            response = self.session.put(
                f"{self.base_url}/object/call",
                json={"objectPath": veh_path, "functionName": "K2_GetActorRotation"},
                timeout=2.0
            )
            if response.status_code != 200:
                return {}
            veh_rot = response.json().get("ReturnValue", {})
        except:
            return {}
        
        if not veh_loc or not veh_rot:
            return {}
        
        # Prepare inverse rotation for local space conversion
        veh_yaw = veh_rot.get("Yaw", 0.0)
        inv_yaw_rad = math.radians(-veh_yaw)
        cos_inv = math.cos(inv_yaw_rad)
        sin_inv = math.sin(inv_yaw_rad)
        
        offsets = {}
        
        # Method 1: Try Cube naming convention first (faster)
        cube_names = ["Cube", "Cube0", "Cube1", "Cube2", "Cube3", "Cube4", "Cube5"]
        for cube_name in cube_names:
            comp_path = f"{self.level_path}:PersistentLevel.{vehicle_name}.{cube_name}"
            try:
                response = self.session.put(
                    f"{self.base_url}/object/call",
                    json={"objectPath": comp_path, "functionName": "K2_GetComponentLocation"},
                    timeout=1.0
                )
                if response.status_code == 200:
                    cube_loc = response.json().get("ReturnValue")
                    if cube_loc:
                        world_dx = cube_loc["X"] - veh_loc["X"]
                        world_dy = cube_loc["Y"] - veh_loc["Y"]
                        world_dz = cube_loc["Z"] - veh_loc["Z"]
                        
                        # Only include if it has significant offset (boundary marker)
                        if abs(world_dx) > 50 or abs(world_dy) > 50:
                            local_x = world_dx * cos_inv - world_dy * sin_inv
                            local_y = world_dx * sin_inv + world_dy * cos_inv
                            offsets[cube_name] = {"X": local_x, "Y": local_y, "Z": world_dz}
            except:
                continue
        
        # If we found cube components, return them
        if len(offsets) >= 2:
            return offsets
        
        # Method 2: Get ALL StaticMeshComponents and find boundary markers
        try:
            response = self.session.put(
                f"{self.base_url}/object/call",
                json={
                    "objectPath": veh_path,
                    "functionName": "GetComponentsByClass",
                    "parameters": {"ComponentClass": "/Script/Engine.StaticMeshComponent"}
                },
                timeout=3.0
            )
            if response.status_code != 200:
                return offsets
            
            components = response.json().get("ReturnValue", [])
            
            for comp_path in components:
                # Extract component name from full path
                comp_name = comp_path.split(".")[-1] if "." in comp_path else comp_path
                
                # Skip the main mesh component (no offset)
                if comp_name == "StaticMeshComponent0":
                    continue
                
                try:
                    response = self.session.put(
                        f"{self.base_url}/object/call",
                        json={"objectPath": comp_path, "functionName": "K2_GetComponentLocation"},
                        timeout=1.0
                    )
                    if response.status_code == 200:
                        comp_loc = response.json().get("ReturnValue")
                        if comp_loc:
                            world_dx = comp_loc["X"] - veh_loc["X"]
                            world_dy = comp_loc["Y"] - veh_loc["Y"]
                            world_dz = comp_loc["Z"] - veh_loc["Z"]
                            
                            # Only include if it has significant offset (boundary marker)
                            if abs(world_dx) > 50 or abs(world_dy) > 50:
                                local_x = world_dx * cos_inv - world_dy * sin_inv
                                local_y = world_dx * sin_inv + world_dy * cos_inv
                                offsets[comp_name] = {"X": local_x, "Y": local_y, "Z": world_dz}
                except:
                    continue
        except:
            pass
        
        return offsets
    
    def _transform_offset(self, local_offset: Dict[str, float],
                         vehicle_loc: Dict[str, float],
                         vehicle_rot: Dict[str, float]) -> Dict[str, float]:
        """
        Transform local offset to world position.
        
        Args:
            local_offset: Offset in vehicle's local space
            vehicle_loc: Vehicle world location
            vehicle_rot: Vehicle world rotation
        
        Returns:
            World position {"X": ..., "Y": ..., "Z": ...}
        """
        # Rotate offset from local space to world space
        yaw_rad = math.radians(vehicle_rot["Yaw"])
        cos_yaw = math.cos(yaw_rad)
        sin_yaw = math.sin(yaw_rad)
        
        world_dx = local_offset["X"] * cos_yaw - local_offset["Y"] * sin_yaw
        world_dy = local_offset["X"] * sin_yaw + local_offset["Y"] * cos_yaw
        world_dz = local_offset["Z"]  # Z unchanged
        
        # Add to vehicle position
        return {
            "X": vehicle_loc["X"] + world_dx,
            "Y": vehicle_loc["Y"] + world_dy,
            "Z": vehicle_loc["Z"] + world_dz
        }
    
    def _get_actor_location(self, actor_name: str) -> Optional[Dict[str, float]]:
        """Get world location of an actor."""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        
        try:
            response = self.session.put(
                f"{self.base_url}/object/call",
                json={
                    "objectPath": path,
                    "functionName": "K2_GetActorLocation"
                },
                timeout=2.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("ReturnValue")
        except:
            pass
        
        return None
    
    def _get_actor_rotation(self, actor_name: str) -> Optional[Dict[str, float]]:
        """Get world rotation of an actor."""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        
        try:
            response = self.session.put(
                f"{self.base_url}/object/call",
                json={
                    "objectPath": path,
                    "functionName": "K2_GetActorRotation"
                },
                timeout=2.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("ReturnValue")
        except:
            pass
        
        return None
    
    def _check_collision(self, proposed: VehicleBounds, existing: VehicleBounds) -> bool:
        """
        Check if proposed vehicle collides with existing vehicle.
        
        Uses oriented bounding box (OBB) overlap test.
        
        Args:
            proposed: Proposed vehicle bounds
            existing: Existing vehicle bounds
        
        Returns:
            True if collision detected, False if safe
        """
        # Get all corners of both vehicles' bounding boxes
        proposed_corners = self._get_vehicle_corners(proposed)
        existing_corners = self._get_vehicle_corners(existing)
        
        if not proposed_corners or not existing_corners:
            # Missing boundaries - check distance fallback
            dist = math.sqrt(
                (proposed.location["X"] - existing.location["X"]) ** 2 +
                (proposed.location["Y"] - existing.location["Y"]) ** 2
            )
            # Use conservative minimum distance
            MIN_SAFE_DIST = 500.0  # 5m minimum for safety
            return dist < MIN_SAFE_DIST
        
        # Use Separating Axis Theorem (SAT) for OBB collision
        # If we can find a separating axis, boxes don't overlap
        
        # Get axes to test (normals of each box's edges)
        axes = []
        
        # Proposed vehicle's axes (perpendicular to front-back and left-right)
        if proposed.front_boundary and proposed.back_boundary:
            dx = proposed.front_boundary["X"] - proposed.back_boundary["X"]
            dy = proposed.front_boundary["Y"] - proposed.back_boundary["Y"]
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0.01:
                # Forward axis and perpendicular (side) axis
                axes.append((dx/length, dy/length))
                axes.append((-dy/length, dx/length))
        
        # Existing vehicle's axes
        if existing.front_boundary and existing.back_boundary:
            dx = existing.front_boundary["X"] - existing.back_boundary["X"]
            dy = existing.front_boundary["Y"] - existing.back_boundary["Y"]
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0.01:
                axes.append((dx/length, dy/length))
                axes.append((-dy/length, dx/length))
        
        # If no axes found, use fallback
        if not axes:
            dist = math.sqrt(
                (proposed.location["X"] - existing.location["X"]) ** 2 +
                (proposed.location["Y"] - existing.location["Y"]) ** 2
            )
            return dist < 500.0
        
        # Test each axis - if we find separation on any axis, no collision
        for axis in axes:
            p_min, p_max = self._project_corners(proposed_corners, axis)
            e_min, e_max = self._project_corners(existing_corners, axis)
            
            # Add small safety margin (50cm)
            MARGIN = 50.0
            p_min -= MARGIN
            p_max += MARGIN
            
            # Check for separation
            if p_max < e_min or e_max < p_min:
                return False  # Separated on this axis - no collision
        
        # No separating axis found - boxes overlap
        return True
    
    def _get_vehicle_corners(self, bounds: VehicleBounds) -> Optional[List[Tuple[float, float]]]:
        """Get 4 corners of vehicle's bounding box in world coordinates."""
        if bounds.category in ["bicycle", "motorcycle"]:
            # Bikes have all 4 boundaries
            if all([bounds.front_boundary, bounds.back_boundary,
                   bounds.left_boundary, bounds.right_boundary]):
                # Use actual boundaries - compute 4 corners
                fx, fy = bounds.front_boundary["X"], bounds.front_boundary["Y"]
                bx, by = bounds.back_boundary["X"], bounds.back_boundary["Y"]
                lx, ly = bounds.left_boundary["X"], bounds.left_boundary["Y"]
                rx, ry = bounds.right_boundary["X"], bounds.right_boundary["Y"]
                
                # Compute half-width from left/right boundaries
                center_x = (fx + bx) / 2
                center_y = (fy + by) / 2
                half_width_l = math.sqrt((lx - center_x)**2 + (ly - center_y)**2)
                half_width_r = math.sqrt((rx - center_x)**2 + (ry - center_y)**2)
                
                # Get direction perpendicular to front-back
                dx = fx - bx
                dy = fy - by
                length = math.sqrt(dx*dx + dy*dy) if (dx*dx + dy*dy) > 0.01 else 1.0
                px, py = -dy/length, dx/length  # Perpendicular
                
                half_width = max(half_width_l, half_width_r, 40.0)  # At least 40cm for bikes
                
                return [
                    (fx + px * half_width, fy + py * half_width),
                    (fx - px * half_width, fy - py * half_width),
                    (bx + px * half_width, by + py * half_width),
                    (bx - px * half_width, by - py * half_width),
                ]
        
        # Cars/trucks/buses - compute corners from front/back + width
        if bounds.front_boundary and bounds.back_boundary:
            fx, fy = bounds.front_boundary["X"], bounds.front_boundary["Y"]
            bx, by = bounds.back_boundary["X"], bounds.back_boundary["Y"]
            
            # Get vehicle direction vector
            dx = fx - bx
            dy = fy - by
            length = math.sqrt(dx*dx + dy*dy)
            
            if length < 0.01:
                return None
            
            # Normalize
            dx /= length
            dy /= length
            
            # Perpendicular vector (for width)
            px, py = -dy, dx
            
            # Determine half-width from left/right boundaries if available
            if bounds.left_boundary and bounds.right_boundary:
                center_x = (fx + bx) / 2
                center_y = (fy + by) / 2
                half_width_l = math.sqrt(
                    (bounds.left_boundary["X"] - center_x)**2 + 
                    (bounds.left_boundary["Y"] - center_y)**2
                )
                half_width_r = math.sqrt(
                    (bounds.right_boundary["X"] - center_x)**2 + 
                    (bounds.right_boundary["Y"] - center_y)**2
                )
                half_width = max(half_width_l, half_width_r, 90.0)
            else:
                # Estimate half-width based on category (realistic values)
                # These are HALF-widths, so total width = 2 * half_width
                HALF_WIDTHS = {
                    "car": 110.0,     # 1.1m half-width (2.2m total)
                    "truck": 140.0,   # 1.4m half-width (2.8m total)
                    "bus": 150.0,     # 1.5m half-width (3.0m total) - buses are wide!
                }
                half_width = HALF_WIDTHS.get(bounds.category, 110.0)
            
            # 4 corners: front-left, front-right, back-left, back-right
            return [
                (fx + px * half_width, fy + py * half_width),
                (fx - px * half_width, fy - py * half_width),
                (bx + px * half_width, by + py * half_width),
                (bx - px * half_width, by - py * half_width),
            ]
        
        return None
    
    def _project_corners(self, corners: List[Tuple[float, float]], 
                        axis: Tuple[float, float]) -> Tuple[float, float]:
        """Project corners onto axis and return min/max values."""
        projections = [c[0] * axis[0] + c[1] * axis[1] for c in corners]
        return min(projections), max(projections)
