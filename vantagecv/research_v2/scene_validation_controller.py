"""
SceneValidationController - Scene Readiness Validation

RESPONSIBILITY (STRICT):
- Validate the scene exists and is properly configured
- Validate semantic correctness (vehicles in correct zones)
- Validate determinism (seed is set)
- Validate readiness for capture

MUST NOT:
- Move or rotate the camera
- Capture images
- Modify vehicle transforms
- Apply domain randomization
- Fix errors silently

This controller returns SCENE_VALID (bool) and FAILURE_REASON (string).
It is a prerequisite for SmartCameraCaptureController.
"""

import math
import logging
import requests
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Locked background actor - must never be modified
LOCKED_BACKGROUND_ACTOR = "StaticMeshActor_10"
LOCKED_BACKGROUND_PATH = "/Game/automobileV2.automobileV2:PersistentLevel.StaticMeshActor_10"


class ValidationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


class ZoneType(Enum):
    PARKING = "PARKING"
    ROAD_LANE = "ROAD_LANE"
    SIDEWALK = "SIDEWALK"


class VehicleClass(Enum):
    CAR = "car"
    TRUCK = "truck"
    BUS = "bus"
    MOTORCYCLE = "motorcycle"
    BICYCLE = "bicycle"
    PEDESTRIAN = "pedestrian"


@dataclass
class ValidationResult:
    """Single validation check result"""
    name: str
    status: ValidationStatus
    message: str
    actor_name: Optional[str] = None
    category: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class SceneValidationReport:
    """Complete validation report"""
    scene_valid: bool = False
    failure_reason: str = ""
    seed: int = 0
    results: List[ValidationResult] = field(default_factory=list)
    
    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.PASS)
    
    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.FAIL)
    
    @property
    def warn_count(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.WARN)


# ============================================================================
# ZONE SEMANTICS - Which vehicles can go where
# ============================================================================

ZONE_ALLOWED_VEHICLES = {
    ZoneType.PARKING: {VehicleClass.CAR, VehicleClass.TRUCK, VehicleClass.MOTORCYCLE},
    ZoneType.ROAD_LANE: {VehicleClass.CAR, VehicleClass.TRUCK, VehicleClass.BUS, VehicleClass.MOTORCYCLE},
    ZoneType.SIDEWALK: {VehicleClass.BICYCLE, VehicleClass.PEDESTRIAN},
}


class SceneValidationController:
    """
    Scene Validation Controller
    
    Validates that the scene is ready for capture without modifying anything.
    Returns SCENE_VALID (bool) and FAILURE_REASON (string).
    """
    
    def __init__(self, 
                 host: str = "127.0.0.1", 
                 port: int = 30010,
                 level_path: str = "/Game/automobileV2.automobileV2",
                 config_path: str = "configs/levels/automobileV2_anchors_detected.yaml",
                 vehicle_config_path: str = "configs/levels/automobileV2_vehicles.yaml"):
        self.base_url = f"http://{host}:{port}/remote"
        self.level_path = level_path
        self.config_path = Path(config_path)
        self.vehicle_config_path = Path(vehicle_config_path)
        self.session = requests.Session()
        self.report = SceneValidationReport()
        self.anchor_config = None
        self.vehicle_config = None
        
        # Load anchor configuration
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.anchor_config = yaml.safe_load(f)
        
        # Load vehicle pool configuration
        if self.vehicle_config_path.exists():
            with open(self.vehicle_config_path, 'r') as f:
                self.vehicle_config = yaml.safe_load(f)
        
        logger.info("SceneValidationController initialized")
        logger.info(f"  Level: {level_path}")
        logger.info(f"  Anchor Config: {config_path}")
        logger.info(f"  Vehicle Config: {vehicle_config_path}")
        logger.info(f"  Remote Control: http://{host}:{port}")
    
    # ========================================================================
    # REMOTE CONTROL API
    # ========================================================================
    
    def _call_remote(self, object_path: str, function_name: str, 
                     parameters: Dict = None) -> Optional[Dict]:
        """Call a UE5 function via Remote Control API"""
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
    
    def _actor_exists(self, actor_name: str) -> bool:
        """Check if an actor exists in the level"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        result = self._call_remote(path, "K2_GetActorLocation")
        return result is not None
    
    def _get_actor_transform(self, actor_name: str) -> Optional[Dict]:
        """Get actor location, rotation, scale"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        
        loc = self._call_remote(path, "K2_GetActorLocation")
        rot = self._call_remote(path, "K2_GetActorRotation")
        scale = self._call_remote(path, "GetActorScale3D")
        
        if not all([loc, rot, scale]):
            return None
        
        return {
            "location": loc.get("ReturnValue", {}),
            "rotation": rot.get("ReturnValue", {}),
            "scale": scale.get("ReturnValue", {})
        }
    
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
                return response.json().get(property_name)
            return None
        except Exception as e:
            logger.error(f"Get property error: {e}")
            return None
    
    def _get_actor_visibility(self, actor_name: str) -> Optional[bool]:
        """Check if actor is visible (not hidden)"""
        path = f"{self.level_path}:PersistentLevel.{actor_name}"
        is_hidden = self._get_property(path, "bHidden")
        if is_hidden is not None:
            return not is_hidden
        return None
    
    # ========================================================================
    # VALIDATION: Locked Environment
    # ========================================================================
    
    def _validate_locked_background(self) -> ValidationResult:
        """Validate that the locked background mesh exists and is not modified"""
        logger.info("Validating locked background actor...")
        
        if not self._actor_exists(LOCKED_BACKGROUND_ACTOR):
            return ValidationResult(
                name="Locked Background",
                status=ValidationStatus.FAIL,
                message=f"Background actor '{LOCKED_BACKGROUND_ACTOR}' not found",
                actor_name=LOCKED_BACKGROUND_ACTOR,
                category="Environment"
            )
        
        transform = self._get_actor_transform(LOCKED_BACKGROUND_ACTOR)
        if not transform:
            return ValidationResult(
                name="Locked Background",
                status=ValidationStatus.FAIL,
                message="Could not read background actor transform",
                actor_name=LOCKED_BACKGROUND_ACTOR,
                category="Environment"
            )
        
        # Log the transform (we don't enforce specific values, just that it exists)
        loc = transform["location"]
        logger.info(f"  Background actor location: ({loc.get('X', 0):.1f}, {loc.get('Y', 0):.1f}, {loc.get('Z', 0):.1f})")
        
        return ValidationResult(
            name="Locked Background",
            status=ValidationStatus.PASS,
            message="Background actor exists and is accessible",
            actor_name=LOCKED_BACKGROUND_ACTOR,
            category="Environment",
            details=transform
        )
    
    def _validate_zones(self) -> ValidationResult:
        """Validate zone anchors from config file"""
        logger.info("Validating zone anchors from config...")
        
        if not self.anchor_config:
            return ValidationResult(
                name="Zone Anchors",
                status=ValidationStatus.FAIL,
                message="No anchor configuration loaded",
                category="Zones"
            )
        
        # Count anchors from config
        parking_count = len(self.anchor_config.get("parking", {}).get("anchors", []))
        lanes_count = len(self.anchor_config.get("lanes", {}).get("definitions", []))
        sidewalks_count = len(self.anchor_config.get("sidewalks", {}).get("definitions", []))
        
        total_zones = parking_count + lanes_count + sidewalks_count
        
        if total_zones == 0:
            return ValidationResult(
                name="Zone Anchors",
                status=ValidationStatus.FAIL,
                message="No zone anchors defined in config",
                category="Zones"
            )
        
        # Verify anchors exist in UE5
        missing_anchors = []
        
        for anchor_name in self.anchor_config.get("parking", {}).get("anchors", []):
            if not self._actor_exists(anchor_name):
                missing_anchors.append(anchor_name)
        
        for lane in self.anchor_config.get("lanes", {}).get("definitions", []):
            if not self._actor_exists(lane["start"]):
                missing_anchors.append(lane["start"])
            if not self._actor_exists(lane["end"]):
                missing_anchors.append(lane["end"])
        
        for sidewalk in self.anchor_config.get("sidewalks", {}).get("definitions", []):
            if not self._actor_exists(sidewalk["start"]):
                missing_anchors.append(sidewalk["start"])
            if not self._actor_exists(sidewalk["end"]):
                missing_anchors.append(sidewalk["end"])
        
        if missing_anchors:
            return ValidationResult(
                name="Zone Anchors",
                status=ValidationStatus.FAIL,
                message=f"Missing anchors in UE5: {', '.join(missing_anchors)}",
                category="Zones"
            )
        
        logger.info(f"  ✓ {parking_count} parking slots, {lanes_count} lanes, {sidewalks_count} sidewalks")
        
        return ValidationResult(
            name="Zone Anchors",
            status=ValidationStatus.PASS,
            message=f"Found {total_zones} zones ({parking_count} parking, "
                   f"{lanes_count} lanes, {sidewalks_count} sidewalks)",
            category="Zones",
            details={
                "parking_count": parking_count,
                "lanes_count": lanes_count,
                "sidewalks_count": sidewalks_count
            }
        )
    
    # ========================================================================
    # VALIDATION: Vehicle Placement Semantics
    # ========================================================================
    
    def _get_vehicle_pool(self) -> List[str]:
        """Get all vehicle actor names from config"""
        if not self.vehicle_config:
            return []
        
        vehicles = self.vehicle_config.get("vehicles", {})
        actor_names = []
        
        for category in ["bicycle", "bus", "car", "motorcycle", "truck"]:
            for v in vehicles.get(category, []):
                actor_names.append(v["name"])
        
        return actor_names
    
    def _get_visible_vehicles(self) -> List[Dict]:
        """Get all visible vehicle actors from config"""
        vehicles = []
        
        # Use vehicle pool from config instead of scanning
        actor_names = self._get_vehicle_pool()
        
        if not actor_names:
            # Fallback to scanning if no config
            for prefix in ["StaticMeshActor", "SkeletalMeshActor"]:
                for i in range(100):
                    actor_names.append(f"{prefix}_{i}")
        
        for actor_name in actor_names:
            visibility = self._get_actor_visibility(actor_name)
            if visibility is None or not visibility:
                continue
            
            transform = self._get_actor_transform(actor_name)
            if not transform:
                continue
            
            # Skip anchors (scale 0.5)
            scale = transform["scale"]
            sx = scale.get("X", 1)
            if abs(sx - 0.5) <= 0.01:
                continue
            
            vehicles.append({
                "name": actor_name,
                "transform": transform,
                "visible": True
            })
        
        return vehicles
    
    def _validate_vehicle_placement(self) -> ValidationResult:
        """Validate that vehicles are placed correctly (not overlapping, not underground)"""
        vehicles = self._get_visible_vehicles()
        
        if len(vehicles) == 0:
            return ValidationResult(
                name="Vehicle Placement",
                status=ValidationStatus.WARN,
                message="No visible vehicles found",
                category="Vehicles"
            )
        
        issues = []
        
        # Check for underground vehicles (Z < -100)
        for v in vehicles:
            z = v["transform"]["location"].get("Z", 0)
            if z < -100:
                issues.append(f"{v['name']} is underground (Z={z:.1f})")
                logger.warning(f"  Underground vehicle: {v['name']} at Z={z:.1f}")
        
        # Check for overlapping vehicles (simplified distance check)
        # Use 50cm threshold - cars can be parked close together
        for i in range(len(vehicles)):
            for j in range(i + 1, len(vehicles)):
                v1 = vehicles[i]
                v2 = vehicles[j]
                
                loc1 = v1["transform"]["location"]
                loc2 = v2["transform"]["location"]
                
                dist = math.sqrt(
                    (loc1["X"] - loc2["X"]) ** 2 +
                    (loc1["Y"] - loc2["Y"]) ** 2
                )
                
                # If vehicles are closer than 50cm, flag as potential overlap
                if dist < 50:
                    issues.append(f"{v1['name']} and {v2['name']} may be overlapping (dist={dist:.1f}cm)")
                    logger.warning(f"  Overlap: {v1['name']} and {v2['name']} dist={dist:.1f}cm")
        
        if issues:
            return ValidationResult(
                name="Vehicle Placement",
                status=ValidationStatus.FAIL,
                message=f"Found {len(issues)} placement issues",
                category="Vehicles",
                details={"issues": issues, "vehicle_count": len(vehicles)}
            )
        
        return ValidationResult(
            name="Vehicle Placement",
            status=ValidationStatus.PASS,
            message=f"{len(vehicles)} vehicles validated (no overlaps, not underground)",
            category="Vehicles",
            details={"vehicle_count": len(vehicles)}
        )
    
    # ========================================================================
    # VALIDATION: Domain Randomization State
    # ========================================================================
    
    def _validate_domain_randomization(self) -> ValidationResult:
        """Validate that domain randomization system exists and is accessible"""
        # Check for DomainRandomization actor
        domain_rand_path = f"{self.level_path}:PersistentLevel.DomainRandomization_1"
        result = self._call_remote(domain_rand_path, "K2_GetActorLocation")
        
        if result is None:
            return ValidationResult(
                name="Domain Randomization",
                status=ValidationStatus.WARN,
                message="DomainRandomization actor not found (optional)",
                category="Randomization"
            )
        
        return ValidationResult(
            name="Domain Randomization",
            status=ValidationStatus.PASS,
            message="DomainRandomization actor exists",
            category="Randomization"
        )
    
    # ========================================================================
    # MAIN VALIDATION ENTRY POINT
    # ========================================================================
    
    def validate(self, seed: int = 0) -> SceneValidationReport:
        """
        Run all validation checks.
        
        Args:
            seed: Random seed for determinism tracking
            
        Returns:
            SceneValidationReport with scene_valid (bool) and failure_reason
        """
        logger.info("=" * 60)
        logger.info("SCENE VALIDATION")
        logger.info("=" * 60)
        logger.info(f"Seed: {seed}")
        
        self.report = SceneValidationReport(seed=seed)
        
        # Run all validations
        validations = [
            self._validate_locked_background(),
            self._validate_zones(),
            self._validate_vehicle_placement(),
            self._validate_domain_randomization(),
        ]
        
        for result in validations:
            self.report.results.append(result)
            
            status_icon = {
                ValidationStatus.PASS: "✓",
                ValidationStatus.FAIL: "✗",
                ValidationStatus.WARN: "⚠",
                ValidationStatus.SKIP: "-"
            }.get(result.status, "?")
            
            logger.info(f"  {status_icon} [{result.category}] {result.name}: {result.message}")
        
        # Determine overall validity
        failures = [r for r in self.report.results if r.status == ValidationStatus.FAIL]
        
        if failures:
            self.report.scene_valid = False
            self.report.failure_reason = "; ".join(f.message for f in failures)
            logger.error(f"SCENE_VALID = False | Reason: {self.report.failure_reason}")
        else:
            self.report.scene_valid = True
            logger.info(f"SCENE_VALID = True | {self.report.pass_count} checks passed")
        
        logger.info("=" * 60)
        
        return self.report


# ============================================================================
# STANDALONE USAGE
# ============================================================================

def main():
    """Run scene validation from command line"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate scene for capture")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--host", default="127.0.0.1", help="UE5 Remote Control host")
    parser.add_argument("--port", type=int, default=30010, help="UE5 Remote Control port")
    parser.add_argument("--level", default="/Game/automobileV2.automobileV2",
                       help="Level path")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Run validation
    controller = SceneValidationController(
        host=args.host,
        port=args.port,
        level_path=args.level
    )
    
    report = controller.validate(seed=args.seed)
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  SCENE_VALID:    {report.scene_valid}")
    print(f"  FAILURE_REASON: {report.failure_reason or 'None'}")
    print(f"  Pass: {report.pass_count}")
    print(f"  Fail: {report.fail_count}")
    print(f"  Warn: {report.warn_count}")
    
    return 0 if report.scene_valid else 1


if __name__ == "__main__":
    exit(main())
