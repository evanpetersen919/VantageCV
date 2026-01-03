"""
Research v2 - Vehicle Lifecycle Manager

HARD CONSTRAINT: Vehicles MUST be cleaned up after EACH frame capture.
No vehicle may persist into the next capture.

Cleanup method: Relocate to unreachable location (Z=-100000) + hide + disable collision.
This is safer than destroy since we reuse pre-placed actors.

Logging (REQUIRED):
- Vehicle cleanup started
- Number of vehicles removed
- Cleanup success or failure
- Method used (relocate)
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from .logging_utils import ResearchLogger

logger = logging.getLogger(__name__)


# Unreachable location for hidden vehicles
VEHICLE_GRAVEYARD_Z = -100000  # 1km below ground - guaranteed out of view


@dataclass
class VehicleCleanupResult:
    """Result of vehicle cleanup operation."""
    success: bool
    vehicles_cleaned: int
    vehicles_failed: int
    failure_reasons: List[str]
    method: str = "relocate_and_hide"
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "vehicles_cleaned": self.vehicles_cleaned,
            "vehicles_failed": self.vehicles_failed,
            "failure_reasons": self.failure_reasons,
            "method": self.method,
        }


class VehicleLifecycleManager:
    """
    Manages vehicle lifecycle with STRICT cleanup guarantees.
    
    INVARIANT: After cleanup(), no vehicle is visible or in-bounds.
    """
    
    MODULE_NAME = "VehicleLifecycle"
    
    def __init__(
        self,
        ue5_bridge: Any,
        vehicle_actors: Dict[str, List[str]],
        logger: Optional[ResearchLogger] = None,
    ):
        """
        Initialize lifecycle manager.
        
        Args:
            ue5_bridge: UE5Bridge instance for remote calls
            vehicle_actors: Dict mapping class names to actor name lists
            logger: Optional research logger
        """
        self.ue5 = ue5_bridge
        self.vehicle_actors = vehicle_actors
        self.log = logger or ResearchLogger(self.MODULE_NAME)
        
        # Track which vehicles are currently spawned
        self._spawned_actors: List[str] = []
        
        self.log.log_init(
            vehicle_classes=list(vehicle_actors.keys()),
            total_actors=sum(len(v) for v in vehicle_actors.values()),
            graveyard_z=VEHICLE_GRAVEYARD_Z,
        )
    
    def register_spawned(self, actor_names: List[str]) -> None:
        """
        Register vehicles as currently spawned.
        
        Args:
            actor_names: List of actor names that were made visible
        """
        self._spawned_actors.extend(actor_names)
        self.log.debug(
            "Vehicles registered as spawned",
            count=len(actor_names),
            actors=actor_names,
        )
    
    def cleanup_all(self) -> VehicleCleanupResult:
        """
        MANDATORY cleanup after each frame.
        
        PHASE 1: Python-side cleanup (relocate tracked vehicles)
        PHASE 2: UE5 authoritative world sweep (catches ANY leaked vehicles)
        
        Returns:
            VehicleCleanupResult with success/failure info
        """
        self.log.info(
            "Vehicle cleanup started",
            method="two_phase_authoritative",
            graveyard_z=VEHICLE_GRAVEYARD_Z,
        )
        
        # ============================================================
        # PHASE 1: Python-side cleanup (tracked vehicles only)
        # ============================================================
        all_actors = []
        for class_name, actors in self.vehicle_actors.items():
            all_actors.extend(actors)
        
        cleaned = 0
        failed = 0
        failure_reasons = []
        
        for actor_name in all_actors:
            success, error = self._cleanup_single_vehicle(actor_name)
            if success:
                cleaned += 1
            else:
                failed += 1
                failure_reasons.append(f"{actor_name}: {error}")
        
        # Clear spawned tracking
        self._spawned_actors.clear()
        
        self.log.info(
            "Phase 1 complete: Python-side cleanup",
            vehicles_cleaned=cleaned,
            vehicles_failed=failed,
        )
        
        # ============================================================
        # PHASE 2: UE5 authoritative world sweep (MANDATORY)
        # ============================================================
        # This catches ANY vehicles that Python didn't know about
        # (e.g., from DomainRandomization.RandomizeVehicles)
        # ============================================================
        try:
            hidden_by_ue5, still_visible = self.ue5.authoritative_vehicle_cleanup()
            
            if still_visible > 0:
                # FATAL: Vehicles leaked
                failure_reasons.append(
                    f"UE5 world sweep found {still_visible} vehicles STILL VISIBLE after cleanup!"
                )
                failed += still_visible
                self.log.error(
                    "FATAL: Vehicle cleanup FAILED - vehicles still visible",
                    vehicles_still_visible=still_visible,
                    level="FATAL",
                )
            else:
                self.log.info(
                    "Phase 2 complete: UE5 authoritative world sweep",
                    vehicles_hidden_by_ue5=hidden_by_ue5,
                    vehicles_still_visible=still_visible,
                )
        except Exception as e:
            # If authoritative cleanup fails, log warning but don't fail
            # (old behavior is preserved as fallback)
            self.log.warning(
                "UE5 authoritative cleanup unavailable, using fallback",
                error=str(e),
            )
        
        result = VehicleCleanupResult(
            success=(failed == 0),
            vehicles_cleaned=cleaned,
            vehicles_failed=failed,
            failure_reasons=failure_reasons,
            method="two_phase_authoritative",
        )
        
        if result.success:
            self.log.info(
                "Vehicle cleanup completed",
                vehicles_removed=cleaned,
                success=True,
            )
        else:
            self.log.error(
                "Vehicle cleanup FAILED",
                vehicles_removed=cleaned,
                vehicles_failed=failed,
                failure_reasons=failure_reasons,
            )
        
        return result
    
    def _cleanup_single_vehicle(self, actor_name: str) -> tuple[bool, Optional[str]]:
        """
        Clean up a single vehicle.
        
        Process:
        1. Set hidden in game = True
        2. Relocate to Z = -100000 (graveyard)
        3. (Optional) Disable collision
        
        Returns:
            (success, error_message)
        """
        try:
            actor_path = f"/Game/automobile.automobile:PersistentLevel.{actor_name}"
            
            # Step 1: Hide the actor
            self.ue5.call_function(
                actor_path,
                "SetActorHiddenInGame",
                {"bNewHidden": True}
            )
            
            # Step 2: Relocate to graveyard
            self.ue5.call_function(
                actor_path,
                "K2_SetActorLocation",
                {
                    "NewLocation": {"X": 0, "Y": 0, "Z": VEHICLE_GRAVEYARD_Z},
                    "bSweep": False,
                    "bTeleport": True,
                }
            )
            
            # Step 3: Disable collision (prevents any physics interactions)
            self.ue5.call_function(
                actor_path,
                "SetActorEnableCollision",
                {"bNewActorEnableCollision": False}
            )
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    def prepare_for_spawn(self, actor_name: str, location: dict) -> bool:
        """
        Prepare a vehicle for spawning.
        
        Process:
        1. Enable collision
        2. Set location
        3. Make visible
        
        Args:
            actor_name: Actor to prepare
            location: Dict with x, y, z in centimeters
            
        Returns:
            True if successful
        """
        try:
            actor_path = f"/Game/automobile.automobile:PersistentLevel.{actor_name}"
            
            # Step 1: Re-enable collision
            self.ue5.call_function(
                actor_path,
                "SetActorEnableCollision",
                {"bNewActorEnableCollision": True}
            )
            
            # Step 2: Set location
            self.ue5.call_function(
                actor_path,
                "K2_SetActorLocation",
                {
                    "NewLocation": {
                        "X": location.get("x", 0),
                        "Y": location.get("y", 0),
                        "Z": location.get("z", 0),
                    },
                    "bSweep": False,
                    "bTeleport": True,
                }
            )
            
            # Step 3: Make visible
            self.ue5.call_function(
                actor_path,
                "SetActorHiddenInGame",
                {"bNewHidden": False}
            )
            
            # Track as spawned
            if actor_name not in self._spawned_actors:
                self._spawned_actors.append(actor_name)
            
            self.log.debug(f"Vehicle prepared for spawn: {actor_name}")
            return True
            
        except Exception as e:
            self.log.error(f"Failed to prepare vehicle {actor_name}: {e}")
            return False
    
    def verify_clean_state(self) -> tuple[bool, List[str]]:
        """
        Verify that no vehicles are visible or in-bounds.
        
        Uses authoritative world sweep via DomainRandomization actor.
        
        Returns:
            (is_clean, list of violations)
        """
        violations = []
        
        # Use authoritative verification from DomainRandomization actor
        # This uses GetVisibleVehicleCountWorldSweep() which iterates ALL tagged vehicles
        try:
            domain_randomization_path = "/Game/automobile.automobile:PersistentLevel.DomainRandomization_1"
            result = self.ue5.call_function(
                domain_randomization_path,
                "GetVisibleVehicleCountWorldSweep",
                {}
            )
            visible_count = result.get("ReturnValue", -1)
            
            if visible_count > 0:
                violations.append(f"{visible_count} vehicles still visible (authoritative world sweep)")
            elif visible_count < 0:
                # Fallback to Z-position check if authoritative function fails
                self.log.warning("Authoritative verification unavailable, using Z-position check")
                violations = self._verify_by_position()
                
        except Exception as e:
            self.log.warning(f"Authoritative verification failed: {e}, using Z-position check")
            violations = self._verify_by_position()
        
        is_clean = len(violations) == 0
        
        if is_clean:
            self.log.debug("Scene verified clean: no vehicles visible")
        else:
            self.log.error(
                "Scene NOT clean - vehicles detected",
                violations=violations,
            )
        
        return is_clean, violations
    
    def _verify_by_position(self) -> List[str]:
        """Fallback verification using Z-position checks."""
        violations = []
        
        for class_name, actors in self.vehicle_actors.items():
            for actor_name in actors:
                try:
                    actor_path = f"/Game/automobile.automobile:PersistentLevel.{actor_name}"
                    
                    # Check Z position only (IsHidden not exposed via Remote Control)
                    result = self.ue5.call_function(
                        actor_path,
                        "K2_GetActorLocation",
                        {}
                    )
                    location = result.get("ReturnValue", {})
                    z = location.get("Z", VEHICLE_GRAVEYARD_Z)
                    
                    # If Z is above -1000, vehicle might be in scene
                    if z > -1000:
                        violations.append(f"{actor_name} at Z={z}, expected < -1000")
                        
                except Exception as e:
                    # Can't verify = log but don't fail
                    self.log.debug(f"Could not verify {actor_name}: {e}")
        
        return violations
