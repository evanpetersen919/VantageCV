"""
PropZoneController - Prop Spawning Based on Anchor Scale Detection

RESPONSIBILITY:
- Detecting prop anchors by SCALE
- Capturing anchor transforms and directions
- Spawning props from existing content folders
- Logging all actions

ANCHOR DETECTION:
(0.2, 0.2, 0.2) → Barrier anchors (paired sets)
(0.4, 0.4, 0.4) → Vegetation anchors
(0.5, 0.5, 0.5) → Sign anchors
(0.6, 0.6, 0.6) → Furniture anchors (range-based sets)

ASSET SOURCES (DYNAMIC):
/Game/Environments/Props/
- Barriers/
- Vegetation/
- Signs/
- Furniture/

Author: Evan Petersen
Date: January 2026
"""

import math
import random
import logging
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AnchorInfo:
    """Detected anchor information"""
    name: str
    location: Dict[str, float]
    rotation: Dict[str, float]
    scale: Dict[str, float]
    anchor_type: str  # barrier, vegetation, sign, furniture
    forward_direction: Dict[str, float]  # Red arrow (X-axis)
    right_direction: Dict[str, float]    # Green arrow (Y-axis)


@dataclass
class SpawnedProp:
    """Information about a spawned prop"""
    prop_name: str
    asset_path: str
    location: Dict[str, float]
    rotation: Dict[str, float]
    scale: Dict[str, float]
    anchor_name: str
    prop_type: str


@dataclass
class PropSpawnResult:
    """Result of prop spawning operation"""
    success: bool
    spawned_props: List[SpawnedProp] = field(default_factory=list)
    failure_reason: Optional[str] = None


# =============================================================================
# ANCHOR SCALE DEFINITIONS
# =============================================================================

ANCHOR_SCALES = {
    "barrier": {"X": 0.2, "Y": 0.2, "Z": 0.2},
    "vegetation": {"X": 0.4, "Y": 0.4, "Z": 0.4},
    "sign": {"X": 0.5, "Y": 0.5, "Z": 0.5},
    "furniture": {"X": 0.6, "Y": 0.6, "Z": 0.6},
    "roadtrash": {"X": 0.7, "Y": 0.7, "Z": 0.7},  # RoadTrash anchors
}

SCALE_TOLERANCE = 0.001  # Exact match required

# Asset folder paths (relative to /Game/)
ASSET_PATHS = {
    "barrier": "/Game/Enviroments/Props/Barriers/",
    "vegetation": "/Game/Enviroments/Props/Vegetation/",
    "sign": "/Game/Enviroments/Props/Signs/",
    "furniture": "/Game/Enviroments/Props/Furniture/",
    "roadtrash": "/Game/Enviroments/Props/Trash/",
}

# =============================================================================
# PROP POOL CLASSIFICATION BY X-COORDINATE
# =============================================================================
# Prop pool actors placed at specific X coordinates for classification

PROP_POOL_X_COORDINATES = {
    -1880: "barrier",
    -3500: "furniture",
    -5100: "sign",
    -6800: "vegetation",
    -8100: "roadtrash",
}


# =============================================================================
# PROP ZONE CONTROLLER
# =============================================================================

class PropZoneController:
    """
    Controller for detecting prop anchors and spawning props.
    
    Anchors are detected by their world scale:
    - 0.2: Barrier (paired sets)
    - 0.4: Vegetation (independent)
    - 0.5: Signs (independent)
    - 0.6: Furniture (range-based sets)
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 30010,
                 level_path: str = "/Game/automobileV2.automobileV2"):
        """
        Initialize PropZoneController.
        
        Args:
            host: UE5 Remote Control host
            port: UE5 Remote Control port
            level_path: Path to the level asset
        """
        self.host = host
        self.port = port
        self.level_path = level_path
        self.base_url = f"http://{host}:{port}/remote"
        
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Cached data
        self.detected_anchors: Dict[str, List[AnchorInfo]] = {
            "barrier": [],
            "vegetation": [],
            "sign": [],
            "furniture": [],
            "roadtrash": [],
        }
        self.spawned_props: List[SpawnedProp] = []
        self.available_assets: Dict[str, List[str]] = {}
        
        # Prop pool actors (detected by X-coordinate)
        self.prop_pool: Dict[str, List[str]] = {
            "barrier": [],
            "vegetation": [],
            "sign": [],
            "furniture": [],
            "roadtrash": [],
        }
        
        # Original prop pool positions (for reset)
        self.prop_pool_original_transforms: Dict[str, Dict] = {}
        
        # Track which props are currently spawned (to prevent duplicates)
        self.props_in_use: Set[str] = set()
        
        # Spawn tracking for reporting
        self.spawn_counts: Dict[str, int] = {
            "barrier": 0,
            "vegetation": 0,
            "sign": 0,
            "furniture": 0,
            "roadtrash": 0,
        }
        
        logger.info("PropZoneController initialized")
        logger.info(f"  Level: {level_path}")
        logger.info(f"  Remote Control: {self.base_url}")
    
    # =========================================================================
    # REMOTE CONTROL API
    # =========================================================================
    
    def _call_remote(self, object_path: str, function_name: str,
                     parameters: Dict = None) -> Optional[Dict]:
        """Call a remote function on UE5 actor"""
        try:
            payload = {
                "objectPath": object_path,
                "functionName": function_name
            }
            if parameters:
                payload["parameters"] = parameters
            
            response = self.session.put(
                f"{self.base_url}/object/call",
                json=payload,
                timeout=5.0
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Remote call error: {e}")
            return None
    
    def _get_property(self, object_path: str, property_name: str) -> Optional[Any]:
        """Get a property from an actor"""
        try:
            response = self.session.put(
                f"{self.base_url}/object/property",
                json={
                    "objectPath": object_path,
                    "propertyName": property_name
                },
                timeout=5.0
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("PropertyValue") or result.get(property_name)
            return None
        except Exception as e:
            logger.error(f"Get property error: {e}")
            return None
    
    def _set_property(self, object_path: str, property_name: str, value: Any) -> bool:
        """Set a property on an actor"""
        try:
            response = self.session.put(
                f"{self.base_url}/object/property",
                json={
                    "objectPath": object_path,
                    "propertyName": property_name,
                    "propertyValue": value
                },
                timeout=5.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Set property error: {e}")
            return False
    
    # =========================================================================
    # ANCHOR DETECTION
    # =========================================================================
    
    def _scale_matches(self, scale: Dict[str, float], target: Dict[str, float]) -> bool:
        """Check if scale matches target within tolerance"""
        return (
            abs(scale.get("X", 0) - target["X"]) < SCALE_TOLERANCE and
            abs(scale.get("Y", 0) - target["Y"]) < SCALE_TOLERANCE and
            abs(scale.get("Z", 0) - target["Z"]) < SCALE_TOLERANCE
        )
    
    def _get_actor_transform(self, actor_name: str) -> Optional[Dict]:
        """Get full transform (location, rotation, scale) for an actor"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        
        loc = self._call_remote(path, "K2_GetActorLocation")
        rot = self._call_remote(path, "K2_GetActorRotation")
        scale = self._call_remote(path, "GetActorScale3D")
        
        if not loc or not rot or not scale:
            return None
        
        return {
            "location": loc.get("ReturnValue", {}),
            "rotation": rot.get("ReturnValue", {}),
            "scale": scale.get("ReturnValue", {})
        }
    
    def _compute_directions(self, rotation: Dict[str, float]) -> Tuple[Dict, Dict]:
        """
        Compute forward (red arrow) and right (green arrow) directions from rotation.
        
        Forward = X-axis direction (red arrow in UE5)
        Right = Y-axis direction (green arrow in UE5)
        """
        yaw = math.radians(rotation.get("Yaw", 0))
        pitch = math.radians(rotation.get("Pitch", 0))
        
        # Forward direction (X-axis, red arrow)
        forward = {
            "X": math.cos(yaw) * math.cos(pitch),
            "Y": math.sin(yaw) * math.cos(pitch),
            "Z": math.sin(pitch)
        }
        
        # Right direction (Y-axis, green arrow)
        right = {
            "X": math.sin(yaw),
            "Y": -math.cos(yaw),
            "Z": 0
        }
        
        return forward, right
    
    def detect_anchors(self) -> Dict[str, List[AnchorInfo]]:
        """
        Scan level for all prop anchors by detecting StaticMeshActors with specific scales.
        
        Returns:
            Dict mapping anchor type to list of detected anchors
        """
        logger.info("=" * 60)
        logger.info("ANCHOR DETECTION")
        logger.info("=" * 60)
        
        # Clear previous detections
        self.detected_anchors = {k: [] for k in ANCHOR_SCALES.keys()}
        
        # Get all actors in level - scan StaticMeshActor_* naming pattern
        # We'll scan a reasonable range (increased to 200 to catch all anchors)
        for i in range(1, 200):
            actor_name = f"StaticMeshActor_{i}"
            transform = self._get_actor_transform(actor_name)
            
            if not transform:
                continue
            
            scale = transform["scale"]
            
            # Check if scale matches any anchor type
            for anchor_type, target_scale in ANCHOR_SCALES.items():
                if self._scale_matches(scale, target_scale):
                    forward, right = self._compute_directions(transform["rotation"])
                    
                    anchor = AnchorInfo(
                        name=actor_name,
                        location=transform["location"],
                        rotation=transform["rotation"],
                        scale=scale,
                        anchor_type=anchor_type,
                        forward_direction=forward,
                        right_direction=right
                    )
                    
                    self.detected_anchors[anchor_type].append(anchor)
                    
                    logger.info(f"  ✓ Detected {anchor_type.upper()} anchor: {actor_name}")
                    logger.info(f"      Location: ({transform['location']['X']:.1f}, {transform['location']['Y']:.1f}, {transform['location']['Z']:.1f})")
                    logger.info(f"      Rotation: Yaw={transform['rotation']['Yaw']:.1f}°")
                    logger.info(f"      Scale: ({scale['X']:.2f}, {scale['Y']:.2f}, {scale['Z']:.2f})")
                    break
        
        # Log summary
        logger.info("-" * 40)
        logger.info("DETECTION SUMMARY:")
        for anchor_type, anchors in self.detected_anchors.items():
            logger.info(f"  {anchor_type.capitalize()}: {len(anchors)} anchors")
        
        return self.detected_anchors
    
    # =========================================================================
    # PROP POOL DETECTION (BY X-COORDINATE)
    # =========================================================================
    
    def detect_prop_pool(self) -> Dict[str, List[str]]:
        """
        Scan level for prop pool actors by detecting StaticMeshActors at specific X-coordinates.
        
        Classification rule (EXACT match):
        X == -1880 → Barrier
        X == -3500 → Furniture
        X == -5100 → Sign
        X == -6800 → Vegetation
        X == -8100 → RoadTrash
        
        Returns:
            Dict mapping prop class to list of actor names
        """
        logger.info("=" * 60)
        logger.info("PROP POOL DETECTION (BY X-COORDINATE)")
        logger.info("=" * 60)
        
        # Clear previous detections
        self.prop_pool = {k: [] for k in PROP_POOL_X_COORDINATES.values()}
        
        # Scan StaticMeshActor_* naming pattern
        for i in range(1, 500):
            actor_name = f"StaticMeshActor_{i}"
            transform = self._get_actor_transform(actor_name)
            
            if not transform:
                continue
            
            x_coord = transform["location"].get("X", 0)
            
            # Check if X matches any prop pool classification (exact match)
            for target_x, prop_class in PROP_POOL_X_COORDINATES.items():
                if abs(x_coord - target_x) < 1.0:  # Allow 1 unit tolerance for floating point
                    self.prop_pool[prop_class].append(actor_name)
                    
                    # Store original transform for reset
                    self.prop_pool_original_transforms[actor_name] = {
                        "location": transform["location"].copy(),
                        "rotation": transform["rotation"].copy(),
                        "scale": transform["scale"].copy()
                    }
                    
                    logger.info(f"  ✓ Detected {prop_class.upper()} prop: {actor_name}")
                    logger.info(f"      X-Coordinate: {x_coord:.1f} (target: {target_x})")
                    break
        
        # Log summary
        logger.info("-" * 40)
        logger.info("PROP POOL SUMMARY:")
        total_props = 0
        for prop_class, actors in self.prop_pool.items():
            logger.info(f"  {prop_class.capitalize()}: {len(actors)} props available")
            total_props += len(actors)
        logger.info(f"  TOTAL: {total_props} props in pool")
        
        return self.prop_pool

    # =========================================================================
    # ASSET DISCOVERY
    # =========================================================================
    
    def _discover_assets(self, folder_path: str) -> List[str]:
        """
        Discover available assets in a content folder.
        
        Uses UE5 Asset Registry to find all assets in the specified folder.
        """
        # Try to get assets via remote control
        # This uses the GetAssetsByPath function
        try:
            response = self.session.put(
                f"{self.base_url}/object/call",
                json={
                    "objectPath": "/Script/Engine.Default__AssetRegistryHelpers",
                    "functionName": "GetAssetsByPath",
                    "parameters": {
                        "PackagePath": folder_path,
                        "bRecursive": True
                    }
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                assets = result.get("ReturnValue", [])
                return [a.get("ObjectPath", "") for a in assets if a.get("ObjectPath")]
        except Exception as e:
            logger.warning(f"Asset discovery failed for {folder_path}: {e}")
        
        # Fallback: Return empty and let spawn functions handle it
        return []
    
    def discover_all_assets(self) -> Dict[str, List[str]]:
        """Discover all available prop assets"""
        logger.info("Discovering available assets...")
        
        for prop_type, folder_path in ASSET_PATHS.items():
            assets = self._discover_assets(folder_path)
            self.available_assets[prop_type] = assets
            logger.info(f"  {prop_type.capitalize()}: {len(assets)} assets found")
        
        return self.available_assets
    
    # =========================================================================
    # SPAWN UTILITIES
    # =========================================================================
    
    def _spawn_actor(self, asset_path: str, location: Dict, rotation: Dict, 
                     scale: Dict) -> Optional[str]:
        """
        Spawn a new actor from an asset at specified transform.
        
        Returns the spawned actor name or None on failure.
        """
        # Use UE5's SpawnActorFromClass or similar
        try:
            response = self.session.put(
                f"{self.base_url}/object/call",
                json={
                    "objectPath": "/Script/Engine.Default__GameplayStatics",
                    "functionName": "SpawnActorFromClass",
                    "parameters": {
                        "WorldContextObject": self.level_path,
                        "ActorClass": asset_path,
                        "Location": location,
                        "Rotation": rotation
                    }
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                actor_path = result.get("ReturnValue")
                if actor_path:
                    # Set scale
                    self._call_remote(actor_path, "SetActorScale3D", {"NewScale3D": scale})
                    return actor_path
        except Exception as e:
            logger.error(f"Spawn actor error: {e}")
        
        return None
    
    def _set_actor_hidden(self, actor_name: str, hidden: bool) -> bool:
        """Set actor visibility"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        result = self._call_remote(path, "SetActorHiddenInGame", {"bNewHidden": hidden})
        return result is not None
    
    def _teleport_actor(self, actor_name: str, location: Dict, rotation: Dict) -> bool:
        """Teleport actor to new transform"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        
        loc_result = self._call_remote(path, "K2_SetActorLocation", {
            "NewLocation": location,
            "bSweep": False,
            "bTeleport": True
        })
        
        rot_result = self._call_remote(path, "K2_SetActorRotation", {
            "NewRotation": rotation,
            "bTeleportPhysics": True
        })
        
        return loc_result is not None and rot_result is not None
    
    def _check_overlap(self, location: Dict, min_distance: float = 100.0) -> bool:
        """Check if location overlaps with any spawned prop"""
        for prop in self.spawned_props:
            dx = location["X"] - prop.location["X"]
            dy = location["Y"] - prop.location["Y"]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < min_distance:
                return True
        return False
    
    # =========================================================================
    # BARRIER SPAWNING (0.2 scale)
    # =========================================================================
    
    def spawn_barriers(self, seed: int, spawn_chance: float = 0.2) -> PropSpawnResult:
        """
        Spawn barriers at paired anchor sets.
        
        Rules:
        - Barriers are defined in PAIRS (consecutive anchors)
        - Each pair has spawn_chance probability to spawn
        - If spawned, BOTH barriers use same model
        - If multiple pairs spawn, ALL use same model
        - Align rotation to green arrow
        """
        random.seed(seed)
        logger.info("=" * 60)
        logger.info("BARRIER SPAWNING")
        logger.info(f"  Seed: {seed}")
        logger.info(f"  Spawn Chance: {spawn_chance:.0%}")
        logger.info("=" * 60)
        
        anchors = self.detected_anchors.get("barrier", [])
        if not anchors:
            logger.info("  No barrier anchors detected")
            return PropSpawnResult(success=True, spawned_props=[])
        
        # Group anchors into pairs by proximity (not by detection order)
        # Sort anchors by location first
        import math
        sorted_anchors = sorted(anchors, key=lambda a: (a.location["X"], a.location["Y"]))
        
        pairs = []
        used = set()
        
        for anchor in sorted_anchors:
            if anchor.name in used:
                continue
                
            # Find closest anchor not yet paired
            closest = None
            min_dist = float('inf')
            
            for other in sorted_anchors:
                if other.name == anchor.name or other.name in used:
                    continue
                    
                dx = anchor.location["X"] - other.location["X"]
                dy = anchor.location["Y"] - other.location["Y"]
                dist = math.sqrt(dx * dx + dy * dy)
                
                if dist < min_dist:
                    min_dist = dist
                    closest = other
            
            if closest:
                pairs.append((anchor, closest))
                used.add(anchor.name)
                used.add(closest.name)
            else:
                # Odd anchor - spawn it alone
                pairs.append((anchor,))
                used.add(anchor.name)
        
        logger.info(f"  Found {len(pairs)} barrier pair(s) ({len(anchors)} total anchors)")
        
        # Decide which pairs spawn
        spawning_pairs = []
        for i, pair in enumerate(pairs):
            roll = random.random()
            if roll < spawn_chance:
                spawning_pairs.append(pair)
                logger.info(f"  Pair {i+1}: SPAWN (roll={roll:.3f})")
            else:
                logger.info(f"  Pair {i+1}: SKIP (roll={roll:.3f})")
        
        if not spawning_pairs:
            logger.info("  No barriers spawned this seed")
            return PropSpawnResult(success=True, spawned_props=[])
        
        # Get barrier pool and group by original location (each style has 4 stacked at same spot)
        barrier_pool = self.prop_pool.get("barrier", [])
        if not barrier_pool:
            logger.warning("  No barrier props in pool")
            return PropSpawnResult(success=True, spawned_props=[])
        
        # Group barriers by their original Y coordinate (each style stack has same Y)
        barrier_styles = {}
        for prop_name in barrier_pool:
            if prop_name in self.prop_pool_original_transforms:
                orig_y = round(self.prop_pool_original_transforms[prop_name]["location"]["Y"], 0)
                if orig_y not in barrier_styles:
                    barrier_styles[orig_y] = []
                barrier_styles[orig_y].append(prop_name)
        
        logger.info(f"  Found {len(barrier_styles)} barrier styles, {len(barrier_pool)} total props")
        
        # Pick ONE random style (all barriers in scene must be same style)
        if not barrier_styles:
            logger.warning("  No barrier styles detected")
            return PropSpawnResult(success=True, spawned_props=[])
        
        chosen_style_y = random.choice(list(barrier_styles.keys()))
        style_barriers = barrier_styles[chosen_style_y]
        logger.info(f"  Selected style at Y={chosen_style_y} with {len(style_barriers)} barriers")
        
        # Count how many barriers we need
        total_needed = sum(len(pair) for pair in spawning_pairs)
        if total_needed > len(style_barriers):
            logger.warning(f"  Need {total_needed} barriers but only {len(style_barriers)} available in style")
        
        spawned = []
        barrier_index = 0
        for pair_idx, pair in enumerate(spawning_pairs, 1):
            logger.info(f"  Spawning pair {pair_idx} ({len(pair)} anchor(s)):")
            for anchor in pair:
                # Use green arrow (right direction) for facing
                yaw = math.degrees(math.atan2(anchor.right_direction["Y"], 
                                               anchor.right_direction["X"]))
                
                rotation = {
                    "Pitch": anchor.rotation["Pitch"],
                    "Yaw": yaw + 90,  # Rotate +90 degrees
                    "Roll": 0
                }
                
                # Note: No overlap check for barriers - both in a pair must spawn together
                
                # Use next barrier from the chosen style (cycling if needed)
                if barrier_index >= len(style_barriers):
                    logger.warning(f"    Ran out of barriers in style, cycling")
                    barrier_index = 0
                
                chosen_prop = style_barriers[barrier_index]
                barrier_index += 1
                self.props_in_use.add(chosen_prop)
                
                logger.info(f"    [{anchor.name}] Using {chosen_prop}")
                
                # Teleport prop to anchor location
                self._teleport_actor(chosen_prop, anchor.location, rotation)
                self._set_actor_hidden(chosen_prop, False)
                
                prop = SpawnedProp(
                    prop_name=f"Barrier_{chosen_prop}",
                    asset_path=chosen_prop,
                    location=anchor.location.copy(),
                    rotation=rotation,
                    scale={"X": 1.0, "Y": 1.0, "Z": 1.0},
                    anchor_name=anchor.name,
                    prop_type="barrier"
                )
                
                spawned.append(prop)
                self.spawned_props.append(prop)
                
                logger.info(f"        ✓ Location: ({anchor.location['X']:.1f}, {anchor.location['Y']:.1f}, {anchor.location['Z']:.1f})")
                logger.info(f"        ✓ Rotation: Yaw={yaw + 90:.1f}°")
        
        logger.info(f"  Total barriers spawned: {len(spawned)}")
        return PropSpawnResult(success=True, spawned_props=spawned)
    
    # =========================================================================
    # VEGETATION SPAWNING (0.4 scale)
    # =========================================================================
    
    def spawn_vegetation(self, seed: int, spawn_chance: float = 0.2) -> PropSpawnResult:
        """
        Spawn vegetation at independent anchors.
        
        Rules:
        - Each anchor independent
        - spawn_chance probability per anchor
        - Random tree/bush model
        - Random yaw rotation
        - Realistic random scale (0.8-1.2)
        """
        random.seed(seed)
        logger.info("=" * 60)
        logger.info("VEGETATION SPAWNING")
        logger.info(f"  Seed: {seed}")
        logger.info(f"  Spawn Chance: {spawn_chance:.0%}")
        logger.info("=" * 60)
        
        anchors = self.detected_anchors.get("vegetation", [])
        if not anchors:
            logger.info("  No vegetation anchors detected")
            return PropSpawnResult(success=True, spawned_props=[])
        
        spawned = []
        for anchor in anchors:
            roll = random.random()
            if roll >= spawn_chance:
                logger.info(f"  {anchor.name}: SKIP (roll={roll:.3f})")
                continue
            
            logger.info(f"  {anchor.name}: SPAWN (roll={roll:.3f})")
            
            # Check overlap
            if self._check_overlap(anchor.location, min_distance=200.0):
                logger.warning(f"    REJECTED: Overlap detected")
                continue
            
            # Use prop from pool
            veg_pool = self.prop_pool.get("vegetation", [])
            available_props = [p for p in veg_pool if p not in self.props_in_use]
            if not available_props:
                logger.warning(f"    SKIP: No available vegetation props in pool")
                continue
            
            # Choose random prop from available pool
            chosen_prop = random.choice(available_props)
            self.props_in_use.add(chosen_prop)
            
            # Random yaw
            random_yaw = random.uniform(0, 360)
            rotation = {
                "Pitch": 0,
                "Yaw": random_yaw,
                "Roll": 0
            }
            
            # Random realistic scale
            scale_factor = random.uniform(0.8, 1.2)
            
            # Teleport prop to anchor location
            self._teleport_actor(chosen_prop, anchor.location, rotation)
            self._set_actor_hidden(chosen_prop, False)
            self._call_remote(f"{self.level_path}:PersistentLevel.{chosen_prop}", 
                            "SetActorScale3D", 
                            {"NewScale3D": {"X": scale_factor, "Y": scale_factor, "Z": scale_factor}})
            
            scale = {"X": scale_factor, "Y": scale_factor, "Z": scale_factor}
            
            prop = SpawnedProp(
                prop_name=f"Veg_{chosen_prop}",
                asset_path=chosen_prop,
                location=anchor.location.copy(),
                rotation=rotation,
                scale=scale,
                anchor_name=anchor.name,
                prop_type="vegetation"
            )
            
            spawned.append(prop)
            self.spawned_props.append(prop)
            
            logger.info(f"    ✓ {chosen_prop}")
            logger.info(f"      Yaw: {random_yaw:.1f}°, Scale: {scale_factor:.2f}")
        
        logger.info(f"  Total vegetation spawned: {len(spawned)}")
        return PropSpawnResult(success=True, spawned_props=spawned)
    
    # =========================================================================
    # SIGN SPAWNING (0.5 scale)
    # =========================================================================
    
    def spawn_signs(self, seed: int, spawn_chance: float = 0.2) -> PropSpawnResult:
        """
        Spawn signs at independent anchors.
        
        Rules:
        - Each anchor independent
        - spawn_chance probability per anchor
        - Random sign model
        - Align to RED arrow direction (forward)
        - Fixed scale
        """
        random.seed(seed)
        logger.info("=" * 60)
        logger.info("SIGN SPAWNING")
        logger.info(f"  Seed: {seed}")
        logger.info(f"  Spawn Chance: {spawn_chance:.0%}")
        logger.info("=" * 60)
        
        anchors = self.detected_anchors.get("sign", [])
        if not anchors:
            logger.info("  No sign anchors detected")
            return PropSpawnResult(success=True, spawned_props=[])
        
        spawned = []
        for anchor in anchors:
            roll = random.random()
            if roll >= spawn_chance:
                logger.info(f"  {anchor.name}: SKIP (roll={roll:.3f})")
                continue
            
            logger.info(f"  {anchor.name}: SPAWN (roll={roll:.3f})")
            
            # Check overlap
            if self._check_overlap(anchor.location, min_distance=100.0):
                logger.warning(f"    REJECTED: Overlap detected")
                continue
            
            # Use prop from pool
            sign_pool = self.prop_pool.get("sign", [])
            available_props = [p for p in sign_pool if p not in self.props_in_use]
            if not available_props:
                logger.warning(f"    SKIP: No available sign props in pool")
                continue
            
            # Choose random prop from available pool
            chosen_prop = random.choice(available_props)
            self.props_in_use.add(chosen_prop)
            
            # Align to RED arrow (forward direction)
            yaw = math.degrees(math.atan2(anchor.forward_direction["Y"],
                                           anchor.forward_direction["X"]))
            rotation = {
                "Pitch": 0,
                "Yaw": yaw,
                "Roll": 0
            }
            
            # Teleport prop to anchor location
            self._teleport_actor(chosen_prop, anchor.location, rotation)
            self._set_actor_hidden(chosen_prop, False)
            
            # Fixed scale
            scale = {"X": 1.0, "Y": 1.0, "Z": 1.0}
            
            prop = SpawnedProp(
                prop_name=f"Sign_{chosen_prop}",
                asset_path=chosen_prop,
                location=anchor.location.copy(),
                rotation=rotation,
                scale=scale,
                anchor_name=anchor.name,
                prop_type="sign"
            )
            
            spawned.append(prop)
            self.spawned_props.append(prop)
            
            logger.info(f"    ✓ {chosen_prop}")
            logger.info(f"      Facing Yaw: {yaw:.1f}°")
        
        logger.info(f"  Total signs spawned: {len(spawned)}")
        return PropSpawnResult(success=True, spawned_props=spawned)
    
    # =========================================================================
    # FURNITURE SPAWNING (0.6 scale)
    # =========================================================================
    
    def spawn_furniture(self, seed: int, spawn_chance: float = 0.2) -> PropSpawnResult:
        """
        Spawn furniture in range-based sets.
        
        Rules:
        - Anchors define SETS (paired anchors define spawn range)
        - Red arrow defines spawn range direction
        - Green arrow defines facing direction
        - Per set: 20% spawn 1, 20% spawn 2, 20% spawn 3
        - All spawned items face green arrow
        - Slight position jitter allowed
        """
        random.seed(seed)
        logger.info("=" * 60)
        logger.info("FURNITURE SPAWNING")
        logger.info(f"  Seed: {seed}")
        logger.info(f"  Spawn Chance: {spawn_chance:.0%}")
        logger.info("=" * 60)
        
        anchors = self.detected_anchors.get("furniture", [])
        if not anchors:
            logger.info("  No furniture anchors detected")
            return PropSpawnResult(success=True, spawned_props=[])
        
        # Group anchors into sets (pairs define range)
        sets = []
        for i in range(0, len(anchors) - 1, 2):
            sets.append((anchors[i], anchors[i + 1]))
        
        logger.info(f"  Found {len(sets)} furniture sets")
        
        spawned = []
        for set_idx, (anchor_a, anchor_b) in enumerate(sets):
            # Determine spawn count (0, 1, 2, or 3)
            roll = random.random()
            if roll < spawn_chance:
                spawn_count = 1
            elif roll < spawn_chance * 2:
                spawn_count = 2
            elif roll < spawn_chance * 3:
                spawn_count = 3
            else:
                spawn_count = 0
            
            logger.info(f"  Set {set_idx + 1}: Spawn {spawn_count} items (roll={roll:.3f})")
            
            if spawn_count == 0:
                continue
            
            # Compute spawn range along red arrow
            range_dx = anchor_b.location["X"] - anchor_a.location["X"]
            range_dy = anchor_b.location["Y"] - anchor_a.location["Y"]
            range_length = math.sqrt(range_dx * range_dx + range_dy * range_dy)
            
            # Use green arrow for facing direction
            facing_yaw = math.degrees(math.atan2(anchor_a.right_direction["Y"],
                                                  anchor_a.right_direction["X"]))
            
            for item_idx in range(spawn_count):
                # Position along range with some spacing
                t = (item_idx + 1) / (spawn_count + 1)
                
                location = {
                    "X": anchor_a.location["X"] + t * range_dx + random.uniform(-20, 20),
                    "Y": anchor_a.location["Y"] + t * range_dy + random.uniform(-20, 20),
                    "Z": anchor_a.location["Z"]
                }
                
                # Check overlap
                if self._check_overlap(location, min_distance=80.0):
                    logger.warning(f"    Item {item_idx + 1}: REJECTED (overlap)")
                    continue
                
                # Use prop from pool
                furn_pool = self.prop_pool.get("furniture", [])
                available_props = [p for p in furn_pool if p not in self.props_in_use]
                if not available_props:
                    logger.warning(f"    Item {item_idx + 1}: SKIP (no available furniture in pool)")
                    continue
                
                # Choose random prop from available pool
                chosen_prop = random.choice(available_props)
                self.props_in_use.add(chosen_prop)
                
                rotation = {
                    "Pitch": 0,
                    "Yaw": facing_yaw + 90 + random.uniform(-5, 5),  # +90 degrees rotation with slight jitter
                    "Roll": 0
                }
                
                # Teleport prop to location
                self._teleport_actor(chosen_prop, location, rotation)
                self._set_actor_hidden(chosen_prop, False)
                
                scale = {"X": 1.0, "Y": 1.0, "Z": 1.0}
                
                prop = SpawnedProp(
                    prop_name=f"Furn_{chosen_prop}_{item_idx}",
                    asset_path=chosen_prop,
                    location=location,
                    rotation=rotation,
                    scale=scale,
                    anchor_name=anchor_a.name,
                    prop_type="furniture"
                )
                
                spawned.append(prop)
                self.spawned_props.append(prop)
                
                logger.info(f"    ✓ Item {item_idx + 1}: {chosen_prop}")
                logger.info(f"        Location: ({location['X']:.1f}, {location['Y']:.1f})")
        
        logger.info(f"  Total furniture spawned: {len(spawned)}")
        return PropSpawnResult(success=True, spawned_props=spawned)
    
    # =========================================================================
    # ROADTRASH SPAWNING
    # =========================================================================
    
    def spawn_roadtrash(self, seed: int, road_segments: List[Dict] = None) -> PropSpawnResult:
        """
        Spawn road trash on road surfaces.
        
        Rules:
        - Spawn 3-8 objects per scene
        - Positions randomized along road segments
        - Avoid parking slots and sidewalks
        - Random yaw rotation
        - Small positional jitter
        - Prevent overlaps with vehicles and other props
        
        Args:
            seed: Random seed for determinism
            road_segments: List of road segment definitions (Y ranges on road surface).
                           If None, uses default road area.
        
        Returns:
            PropSpawnResult with spawned trash items
        """
        random.seed(seed)
        logger.info("=" * 60)
        logger.info("ROADTRASH SPAWNING")
        logger.info(f"  Seed: {seed}")
        logger.info("=" * 60)
        
        # Check if we have roadtrash props in pool
        roadtrash_pool = self.prop_pool.get("roadtrash", [])
        if not roadtrash_pool:
            logger.warning("  No roadtrash props available in pool")
            logger.warning("  RoadTrash spawning SKIPPED - no props at X=-8100")
            return PropSpawnResult(success=True, spawned_props=[], 
                                   failure_reason="No roadtrash props in pool")
        
        # Check road surface data
        if road_segments is None:
            # Default road area (based on level layout)
            # These are Y-ranges where roads exist
            road_segments = [
                {"y_min": 6000, "y_max": 10000, "x_min": 8000, "x_max": 14000, "z": 40},
            ]
            logger.info("  Using default road segments (no road data provided)")
        
        if not road_segments:
            logger.error("  ERROR: No road surface data available")
            logger.error("  RoadTrash spawning SKIPPED safely")
            return PropSpawnResult(success=False, spawned_props=[], 
                                   failure_reason="No road surface data")
        
        logger.info(f"  Road segments: {len(road_segments)}")
        logger.info(f"  Roadtrash pool: {len(roadtrash_pool)} props available")
        
        # Determine spawn count (3-8)
        spawn_count = random.randint(3, 8)
        logger.info(f"  Target spawn count: {spawn_count}")
        
        spawned = []
        attempts = 0
        max_attempts = spawn_count * 5  # Allow multiple attempts per desired spawn
        
        while len(spawned) < spawn_count and attempts < max_attempts:
            attempts += 1
            
            # Choose a random road segment
            segment = random.choice(road_segments)
            
            # Generate random position within road segment
            location = {
                "X": random.uniform(segment["x_min"], segment["x_max"]),
                "Y": random.uniform(segment["y_min"], segment["y_max"]),
                "Z": segment.get("z", 0) + random.uniform(0, 5)  # Slight Z jitter
            }
            
            # Add positional jitter
            location["X"] += random.uniform(-50, 50)
            location["Y"] += random.uniform(-50, 50)
            
            # Check overlap with existing props and vehicles
            if self._check_overlap(location, min_distance=100.0):
                logger.debug(f"    Attempt {attempts}: REJECTED (overlap)")
                continue
            
            # Choose random prop from available pool
            available_props = [p for p in roadtrash_pool if p not in self.props_in_use]
            if not available_props:
                logger.warning(f"    Attempt {attempts}: SKIP (no available roadtrash props)")
                break  # No more available props
            
            chosen_prop = random.choice(available_props)
            self.props_in_use.add(chosen_prop)
            
            # Random yaw rotation
            random_yaw = random.uniform(0, 360)
            rotation = {
                "Pitch": 0,
                "Yaw": random_yaw,
                "Roll": 0
            }
            
            # Teleport the prop to location
            self._teleport_actor(chosen_prop, location, rotation)
            self._set_actor_hidden(chosen_prop, False)
            
            prop = SpawnedProp(
                prop_name=f"RoadTrash_{len(spawned)}",
                asset_path=chosen_prop,
                location=location.copy(),
                rotation=rotation,
                scale={"X": 1.0, "Y": 1.0, "Z": 1.0},
                anchor_name=chosen_prop,
                prop_type="roadtrash"
            )
            
            spawned.append(prop)
            self.spawned_props.append(prop)
            
            # Log spawn details
            logger.info(f"    ✓ Spawned: {chosen_prop}")
            logger.info(f"        Seed: {seed}")
            logger.info(f"        Location: ({location['X']:.1f}, {location['Y']:.1f}, {location['Z']:.1f})")
            logger.info(f"        Rotation: Yaw={random_yaw:.1f}°")
            logger.info(f"        Road segment: Y=[{segment['y_min']}, {segment['y_max']}]")
        
        # Update spawn count tracking
        self.spawn_counts["roadtrash"] = len(spawned)
        
        logger.info(f"  Total roadtrash spawned: {len(spawned)}")
        return PropSpawnResult(success=True, spawned_props=spawned)
    
    # =========================================================================
    # MAIN SPAWN INTERFACE
    # =========================================================================
    
    def spawn_all(self, seed: int, spawn_chance: float = 0.2) -> PropSpawnResult:
        """
        Spawn all prop types with given seed.
        
        Args:
            seed: Random seed for determinism
            spawn_chance: Probability for each spawn roll (default 20%)
        
        Returns:
            Combined result of all spawn operations
        """
        logger.info("=" * 60)
        logger.info(f"PROP ZONE SPAWNING (Seed: {seed})")
        logger.info("=" * 60)
        
        # Clear previous spawns
        self.spawned_props.clear()
        logger.debug(f"Clearing props_in_use (was: {len(self.props_in_use)} props)")
        self.props_in_use.clear()
        logger.debug(f"Props in use after clear: {len(self.props_in_use)}")
        
        # Detect anchors if not already done
        if not any(self.detected_anchors.values()):
            self.detect_anchors()
        
        # Discover assets if not already done
        if not self.available_assets:
            self.discover_all_assets()
        
        # Spawn each type with offset seeds for independence
        barrier_result = self.spawn_barriers(seed, spawn_chance)
        vegetation_result = self.spawn_vegetation(seed + 1000, 0.3)  # Vegetation at 30%
        sign_result = self.spawn_signs(seed + 2000, spawn_chance)
        furniture_result = self.spawn_furniture(seed + 3000, spawn_chance)
        roadtrash_result = self.spawn_roadtrash(seed + 4000)
        
        # Update spawn counts for reporting
        self.spawn_counts["barrier"] = len(barrier_result.spawned_props)
        self.spawn_counts["vegetation"] = len(vegetation_result.spawned_props)
        self.spawn_counts["sign"] = len(sign_result.spawned_props)
        self.spawn_counts["furniture"] = len(furniture_result.spawned_props)
        self.spawn_counts["roadtrash"] = len(roadtrash_result.spawned_props)
        
        # Combine results
        all_spawned = (
            barrier_result.spawned_props +
            vegetation_result.spawned_props +
            sign_result.spawned_props +
            furniture_result.spawned_props +
            roadtrash_result.spawned_props
        )
        
        # Log quantity report
        self._log_quantity_report()
        
        return PropSpawnResult(success=True, spawned_props=all_spawned)
    
    def _log_quantity_report(self) -> None:
        """
        Log detailed quantity report after scanning + spawning.
        
        Reports:
        - Total anchors scanned
        - Count per PropClass detected
        - Count per PropClass spawned
        """
        logger.info("=" * 60)
        logger.info("PROP SCAN SUMMARY")
        logger.info("=" * 60)
        
        total_anchors = sum(len(anchors) for anchors in self.detected_anchors.values())
        total_pool = sum(len(props) for props in self.prop_pool.values())
        total_spawned = sum(self.spawn_counts.values())
        
        logger.info(f"  Total anchors scanned: {total_anchors}")
        logger.info(f"  Total props in pool: {total_pool}")
        logger.info("")
        
        for prop_class in ["barrier", "vegetation", "sign", "furniture", "roadtrash"]:
            detected = len(self.detected_anchors.get(prop_class, []))
            pool = len(self.prop_pool.get(prop_class, []))
            spawned = self.spawn_counts.get(prop_class, 0)
            
            if prop_class == "roadtrash":
                # RoadTrash uses pool, not anchors
                logger.info(f"  {prop_class.capitalize():12}: {pool} in pool / {spawned} spawned")
            else:
                logger.info(f"  {prop_class.capitalize():12}: {detected} detected / {spawned} spawned")
        
        logger.info("")
        logger.info(f"  TOTAL SPAWNED: {total_spawned}")
        logger.info("=" * 60)
    
    def reset_all(self) -> bool:
        """
        Remove all spawned props and reset state.
        Note: Anchor meshes are never touched - they are only used for location detection.
        """
        logger.info("Resetting all spawned props...")
        
        # Hide all prop pool actors and reset to original positions
        for prop_class, props in self.prop_pool.items():
            for prop_name in props:
                self._set_actor_hidden(prop_name, True)
                
                # Teleport back to original position
                if prop_name in self.prop_pool_original_transforms:
                    original = self.prop_pool_original_transforms[prop_name]
                    self._teleport_actor(prop_name, original["location"], original["rotation"])
                    self._call_remote(f"{self.level_path}:PersistentLevel.{prop_name}", 
                                    "SetActorScale3D", 
                                    {"NewScale3D": original["scale"]})
        
        # Clear the in-use tracking
        self.props_in_use.clear()
        
        # Reset spawn counts
        for key in self.spawn_counts:
            self.spawn_counts[key] = 0
        
        # Clear tracking
        count = len(self.spawned_props)
        self.spawned_props.clear()
        
        logger.info(f"  Reset {sum(len(p) for p in self.prop_pool.values())} props to pool locations")
        return True


# =============================================================================
# TEST / DEMO
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    controller = PropZoneController()
    
    # Detect anchors (by scale)
    controller.detect_anchors()
    
    # Detect prop pool (by X-coordinate)
    controller.detect_prop_pool()
    
    # Discover assets
    controller.discover_all_assets()
    
    # Spawn all props with seed
    result = controller.spawn_all(seed=42)
    
    print(f"\nSpawned {len(result.spawned_props)} props total")
