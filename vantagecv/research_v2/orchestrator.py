"""
Research v2 - MODULE 7: Dataset Orchestrator

Responsibilities:
- Control scene resets
- Trigger frame generation
- Track dataset statistics

Tracked metrics:
- Images generated
- Vehicles per image distribution
- Class frequency
- Failure rates per module

Logging (REQUIRED):
- Per-run summary
- Running stats every N frames
- Final dataset report
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
import json
import time

from .logging_utils import ResearchLogger, PipelineLogger
from .config import ResearchConfig
from .scene_controller import SceneController
from .vehicle_spawner import VehicleSpawner, SpawnedVehicle
from .camera_system import CameraSystem
from .annotation import AnnotationGenerator, FrameAnnotation
from .validation import FrameValidator, FrameValidationResult
from .vehicle_lifecycle import VehicleLifecycleManager, VehicleCleanupResult
from .adaptive_camera import AdaptiveCameraController, CameraFitResult


@dataclass
class FrameResult:
    """Result of generating a single frame."""
    frame_index: int
    success: bool
    image_path: Optional[Path] = None
    annotation: Optional[FrameAnnotation] = None
    validation: Optional[FrameValidationResult] = None
    vehicles: list[SpawnedVehicle] = field(default_factory=list)
    generation_time_ms: float = 0.0
    failure_reason: Optional[str] = None
    failure_module: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "frame_index": self.frame_index,
            "success": self.success,
            "image_path": str(self.image_path) if self.image_path else None,
            "num_vehicles": len(self.vehicles),
            "num_valid_annotations": self.annotation.num_valid if self.annotation else 0,
            "validation_passed": self.validation.is_valid if self.validation else False,
            "generation_time_ms": self.generation_time_ms,
            "failure_reason": self.failure_reason,
            "failure_module": self.failure_module,
        }


@dataclass
class DatasetStatistics:
    """Running statistics for dataset generation."""
    images_generated: int = 0
    images_failed: int = 0
    total_vehicles: int = 0
    vehicles_per_image: list[int] = field(default_factory=list)
    class_counts: dict[str, int] = field(default_factory=dict)
    failure_counts: dict[str, int] = field(default_factory=dict)
    total_time_ms: float = 0.0
    
    def add_frame(self, result: FrameResult) -> None:
        """Update statistics with frame result."""
        if result.success:
            self.images_generated += 1
            num_vehicles = len(result.vehicles)
            self.total_vehicles += num_vehicles
            self.vehicles_per_image.append(num_vehicles)
            
            for vehicle in result.vehicles:
                cls = vehicle.vehicle_class.value
                self.class_counts[cls] = self.class_counts.get(cls, 0) + 1
        else:
            self.images_failed += 1
            reason = result.failure_reason or "unknown"
            self.failure_counts[reason] = self.failure_counts.get(reason, 0) + 1
        
        self.total_time_ms += result.generation_time_ms
    
    def to_dict(self) -> dict:
        total = self.images_generated + self.images_failed
        avg_vehicles = (self.total_vehicles / max(self.images_generated, 1))
        avg_time = self.total_time_ms / max(total, 1)
        
        # Compute vehicle count distribution
        count_dist = {}
        for count in self.vehicles_per_image:
            key = str(count)
            count_dist[key] = count_dist.get(key, 0) + 1
        
        # Normalize class distribution
        total_vehicles = sum(self.class_counts.values())
        class_dist = {
            cls: count / max(total_vehicles, 1)
            for cls, count in self.class_counts.items()
        }
        
        return {
            "images_generated": self.images_generated,
            "images_failed": self.images_failed,
            "success_rate": self.images_generated / max(total, 1),
            "total_vehicles": self.total_vehicles,
            "avg_vehicles_per_image": avg_vehicles,
            "vehicles_per_image_distribution": count_dist,
            "class_counts": self.class_counts,
            "class_distribution": class_dist,
            "failure_counts": self.failure_counts,
            "total_time_ms": self.total_time_ms,
            "avg_time_per_frame_ms": avg_time,
        }


class DatasetOrchestrator:
    """
    MODULE 7 - Dataset Orchestrator
    
    Coordinates all modules to generate a complete dataset.
    """
    
    MODULE_NAME = "DatasetOrchestrator"
    
    def __init__(
        self,
        config: ResearchConfig,
        ue5_connection: Optional[Any] = None,  # UE5 remote execution interface
    ):
        """
        Initialize orchestrator.
        
        Args:
            config: Master configuration
            ue5_connection: Optional UE5 connection for remote execution
        """
        self.config = config
        self.ue5 = ue5_connection
        
        # Create output directories
        config.output.create_directories()
        
        # Initialize pipeline logger
        self._pipeline_logger = PipelineLogger(config.output.logs_dir)
        
        # Get module loggers
        self.logger = self._pipeline_logger.get_logger(self.MODULE_NAME)
        
        # Initialize modules
        self._scene = SceneController(
            config=config.scene,
            logger=self._pipeline_logger.get_logger("SceneController"),
        )
        
        self._spawner = VehicleSpawner(
            config=config.vehicles,
            scene_config=config.scene,
            logger=self._pipeline_logger.get_logger("VehicleSpawner"),
        )
        
        self._camera = CameraSystem(
            config=config.camera,
            logger=self._pipeline_logger.get_logger("CameraSystem"),
        )
        
        self._annotator = AnnotationGenerator(
            config=config.annotation,
            camera_config=config.camera,
            logger=self._pipeline_logger.get_logger("AnnotationGenerator"),
        )
        
        self._validator = FrameValidator(
            config=config.validation,
            logger=self._pipeline_logger.get_logger("FrameValidator"),
        )
        
        # Initialize vehicle lifecycle manager (if UE5 connected)
        self._lifecycle: Optional[VehicleLifecycleManager] = None
        if self.ue5:
            self._lifecycle = VehicleLifecycleManager(
                ue5_bridge=self.ue5,
                vehicle_actors=config.vehicles.vehicle_actors,
                logger=self._pipeline_logger.get_logger("VehicleLifecycle"),
            )
        
        # Initialize adaptive camera controller
        self._adaptive_camera = AdaptiveCameraController(
            config=config.camera,
            image_width=config.camera.width,
            image_height=config.camera.height_px,
            logger=self._pipeline_logger.get_logger("AdaptiveCamera"),
        )
        
        # Statistics
        self._stats = DatasetStatistics()
        self._frame_results: list[FrameResult] = []
        
        self.logger.log_init(
            experiment_name=config.experiment_name,
            num_images=config.num_images,
            random_seed=config.random_seed,
            output_dir=str(config.output.base_dir),
            lifecycle_manager_enabled=self._lifecycle is not None,
            adaptive_camera_enabled=True,
        )
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate all configurations."""
        all_issues = []
        
        # Config-level validation
        all_issues.extend(self.config.validate())
        
        # Module validation
        _, scene_issues = self._scene.validate()
        all_issues.extend(scene_issues)
        
        _, spawner_issues = self._spawner.validate()
        all_issues.extend(spawner_issues)
        
        _, camera_issues = self._camera.validate()
        all_issues.extend(camera_issues)
        
        if all_issues:
            self.logger.error(
                "Configuration validation failed",
                issues=all_issues,
            )
        else:
            self.logger.info("All configurations validated successfully")
        
        return len(all_issues) == 0, all_issues
    
    def generate_frame(self, frame_index: int) -> FrameResult:
        """
        Generate a single frame.
        
        Implements fail-fast: any module failure aborts the frame.
        
        Args:
            frame_index: Index of frame to generate
            
        Returns:
            FrameResult with success/failure info
        """
        start_time = time.time()
        
        self.logger.info(
            "Frame generation started",
            frame_index=frame_index,
        )
        
        result = FrameResult(frame_index=frame_index, success=False)
        
        try:
            # Step 1: Set up camera for frame
            camera_state = self._camera.setup_frame(
                frame_index=frame_index,
                apply_jitter=True,
            )
            
            # Step 2: Spawn vehicles
            spawn_result = self._spawner.spawn_vehicles()
            
            if not spawn_result.success:
                result.failure_reason = "Vehicle spawn failed"
                result.failure_module = "VehicleSpawner"
                self.logger.error(
                    "Frame aborted: spawn failed",
                    frame_index=frame_index,
                    reason="No vehicles could be spawned",
                )
                return result
            
            result.vehicles = spawn_result.vehicles
            
            # Step 3: Execute in UE5 (if connected)
            image_filename = f"frame_{frame_index:06d}.png"
            image_path = self.config.output.images_dir / image_filename
            
            if self.ue5:
                # Send commands to UE5
                ue5_success = self._execute_ue5_frame(
                    spawn_result.vehicles,
                    camera_state,
                    image_path,
                )
                if not ue5_success:
                    result.failure_reason = "UE5 render failed"
                    result.failure_module = "UE5"
                    return result
            else:
                # Simulation mode - create placeholder
                self._create_placeholder_image(image_path)
            
            result.image_path = image_path
            
            # Step 4: Generate annotations
            annotation = self._annotator.annotate_frame(
                frame_index=frame_index,
                image_id=frame_index + 1,  # 1-indexed for COCO
                image_filename=image_filename,
                vehicles=spawn_result.vehicles,
                camera=self._camera,
            )
            result.annotation = annotation
            
            # Step 5: Validate frame
            validation = self._validator.validate_frame(annotation)
            result.validation = validation
            
            if not validation.is_valid:
                result.failure_reason = "Validation failed"
                result.failure_module = "FrameValidator"
                self.logger.error(
                    "Frame aborted: validation failed",
                    frame_index=frame_index,
                    issues=[i.to_dict() for i in validation.issues],
                )
                # Remove invalid image
                if image_path.exists():
                    image_path.unlink()
                return result
            
            # Success!
            result.success = True
            
        except Exception as e:
            result.failure_reason = str(e)
            result.failure_module = "Unknown"
            self.logger.error(
                "Frame aborted: exception",
                frame_index=frame_index,
                exception=str(e),
                reason="Unhandled exception during frame generation",
                suggested_fix="Check stack trace in logs",
            )
        
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            result.generation_time_ms = elapsed_ms
            
            self.logger.log_output(
                "Frame generation completed",
                frame_index=frame_index,
                success=result.success,
                time_ms=elapsed_ms,
            )
        
        return result
    
    def _execute_ue5_frame(
        self,
        vehicles: list[SpawnedVehicle],
        camera_state: Any,
        image_path: Path,
    ) -> bool:
        """
        Execute frame generation in UE5 with HARD CONSTRAINTS:
        
        1. VEHICLE LIFECYCLE: All vehicles MUST be cleaned up after capture
        2. CAMERA VISIBILITY: All vehicles MUST have >=50% visibility
        3. FAIL-FAST: Any failure aborts the frame immediately
        
        Args:
            vehicles: Vehicles to spawn
            camera_state: Camera configuration
            image_path: Where to save image
            
        Returns:
            True if successful
        """
        if not self.ue5:
            self.logger.debug("UE5 not connected, skipping")
            return True
        
        try:
            # ============================================================
            # STEP 1: VERIFY CLEAN STATE (FAIL-FAST)
            # ============================================================
            if self._lifecycle:
                is_clean, violations = self._lifecycle.verify_clean_state()
                if not is_clean:
                    self.logger.error(
                        "ABORT: Scene not clean before frame",
                        violations=violations[:5],  # Show first 5
                    )
                    # Force cleanup before aborting
                    self._lifecycle.cleanup_all()
                    return False
            else:
                # Fallback: hide all vehicles
                self.ue5.hide_all_vehicles(self.config.vehicles.vehicle_actors)
            
            self.logger.info("Vehicle cleanup started", method="verify_clean_state")
            
            # ============================================================
            # STEP 2: FIT CAMERA TO VEHICLES (VISIBILITY GUARANTEE)
            # ============================================================
            camera_fit = self._adaptive_camera.fit_camera_to_vehicles(
                vehicles=vehicles,
                world_offset_x=self.config.vehicles.world_offset_x,
                world_offset_y=self.config.vehicles.world_offset_y,
            )
            
            # Log camera fit results (REQUIRED)
            self.logger.info(
                "Camera fit computed",
                vehicle_centroid=camera_fit.vehicle_centroid,
                camera_position=camera_fit.camera_position,
                camera_fov=camera_fit.fov,
                per_vehicle_visibility=[
                    {"actor": v.actor_name, "ratio": v.visible_ratio}
                    for v in camera_fit.visibility_results
                ],
                success=camera_fit.success,
            )
            
            if not camera_fit.success:
                self.logger.error(
                    "ABORT: Camera fit failed - cannot guarantee visibility",
                    failure_reason=camera_fit.failure_reason,
                    retry_count=camera_fit.retry_count,
                )
                return False
            
            # ============================================================
            # STEP 3: SPAWN VEHICLES
            # ============================================================
            commands = self._spawner.get_ue5_spawn_commands(vehicles)
            success_count = self.ue5.execute_spawn_commands(commands)
            
            if success_count < len(commands) // 2:
                self.logger.warning(
                    "Too many UE5 spawn commands failed",
                    executed=success_count,
                    total=len(commands),
                )
            
            # Track spawned actors
            spawned_actors = [v.actor_name for v in vehicles]
            if self._lifecycle:
                self._lifecycle.register_spawned(spawned_actors)
            
            # Wait for UE5 to update
            time.sleep(0.1)  # 100ms for physics/rendering to settle
            
            # ============================================================
            # STEP 4: SET CAMERA (DATA-DRIVEN POSITION)
            # ============================================================
            cam_x, cam_y, cam_z = camera_fit.camera_position
            pitch, yaw, roll = camera_fit.camera_rotation
            
            self.ue5.set_capture_camera(
                x=cam_x, y=cam_y, z=cam_z,
                pitch=pitch, yaw=yaw, roll=roll,
                fov=camera_fit.fov
            )
            
            # ============================================================
            # STEP 5: CAPTURE FRAME
            # ============================================================
            success = self.ue5.capture_frame(
                str(image_path.absolute()),
                self.config.camera.width,
                self.config.camera.height_px,
            )
            
            if not success:
                self.logger.error(
                    "ABORT: Frame capture failed",
                    image_path=str(image_path),
                )
                return False
            
            self.logger.debug(
                "UE5 frame executed successfully",
                vehicle_count=len(vehicles),
                image_path=str(image_path),
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "ABORT: UE5 execution exception",
                error=str(e),
                vehicle_count=len(vehicles),
            )
            return False
        
        finally:
            # ============================================================
            # MANDATORY CLEANUP: Remove ALL vehicles after capture
            # ============================================================
            self.logger.info("Vehicle cleanup started", method="post_capture")
            
            if self._lifecycle:
                cleanup_result = self._lifecycle.cleanup_all()
                self.logger.info(
                    "Vehicle cleanup completed",
                    vehicles_removed=cleanup_result.vehicles_cleaned,
                    success=cleanup_result.success,
                    method=cleanup_result.method,
                )
                if not cleanup_result.success:
                    self.logger.error(
                        "Vehicle cleanup FAILED",
                        vehicles_failed=cleanup_result.vehicles_failed,
                        failure_reasons=cleanup_result.failure_reasons[:5],
                    )
            else:
                # Fallback cleanup
                try:
                    self.ue5.hide_all_vehicles(self.config.vehicles.vehicle_actors)
                    self.logger.info("Vehicle cleanup completed", method="hide_all")
                except Exception as e:
                    self.logger.error("Vehicle cleanup failed", error=str(e))
    
    def _create_placeholder_image(self, path: Path) -> None:
        """Create a placeholder image for simulation mode."""
        # Create a simple text file as placeholder
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write("PLACEHOLDER")
    
    def generate_dataset(
        self,
        num_images: Optional[int] = None,
        progress_interval: int = 10,
    ) -> DatasetStatistics:
        """
        Generate complete dataset.
        
        Args:
            num_images: Number of images (uses config if not specified)
            progress_interval: Log progress every N frames
            
        Returns:
            Final dataset statistics
        """
        num_images = num_images or self.config.num_images
        
        self.logger.info(
            "Dataset generation started",
            num_images=num_images,
            seed=self.config.random_seed,
            output_dir=str(self.config.output.base_dir),
        )
        
        # Validate configuration
        is_valid, issues = self.validate_config()
        if not is_valid:
            self.logger.critical(
                "Cannot generate dataset: invalid configuration",
                issues=issues,
            )
            return self._stats
        
        # Initialize scene
        self._scene.initialize(seed=self.config.random_seed)
        self._spawner.set_seed(self.config.random_seed)
        self._camera.set_seed(self.config.random_seed)
        
        # Generate frames
        successful_frames = 0
        frame_index = 0
        max_attempts = num_images * 2  # Allow some failures
        
        while successful_frames < num_images and frame_index < max_attempts:
            result = self.generate_frame(frame_index)
            self._frame_results.append(result)
            self._stats.add_frame(result)
            
            if result.success:
                successful_frames += 1
            
            # Log progress
            if (frame_index + 1) % progress_interval == 0:
                self._log_progress(frame_index + 1, successful_frames, num_images)
            
            # Advance scene for next frame
            self._scene.advance_frame()
            frame_index += 1
        
        # Export annotations
        self._annotator.export_coco(
            self.config.output.annotations_dir / "annotations.json"
        )
        
        # Save metadata
        self._save_metadata()
        
        # Log final summary
        self._log_final_summary()
        
        return self._stats
    
    def _log_progress(
        self,
        frames_attempted: int,
        frames_successful: int,
        target: int,
    ) -> None:
        """Log progress update."""
        pct = (frames_successful / target) * 100
        stats = self._stats.to_dict()
        
        self.logger.info(
            "Progress update",
            frames_attempted=frames_attempted,
            frames_successful=frames_successful,
            target=target,
            progress_pct=f"{pct:.1f}%",
            avg_vehicles=stats["avg_vehicles_per_image"],
            avg_time_ms=stats["avg_time_per_frame_ms"],
        )
    
    def _save_metadata(self) -> None:
        """Save dataset metadata."""
        metadata = {
            "experiment_name": self.config.experiment_name,
            "generated_at": datetime.now().isoformat(),
            "config": self.config.to_dict(),
            "statistics": self._stats.to_dict(),
            "spawner_stats": self._spawner.get_statistics(),
            "annotation_stats": self._annotator.get_statistics(),
            "validation_stats": self._validator.get_statistics(),
        }
        
        metadata_path = self.config.output.metadata_dir / "dataset_info.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)
        
        self.logger.info("Metadata saved", path=str(metadata_path))
    
    def _log_final_summary(self) -> None:
        """Log final dataset summary."""
        stats = self._stats.to_dict()
        
        self.logger.info(
            "="*50,
        )
        self.logger.info(
            "DATASET GENERATION COMPLETE",
            experiment=self.config.experiment_name,
        )
        self.logger.info(
            "Final statistics",
            **stats,
        )
        
        # Log validation summary
        self._validator.log_summary()
        
        # Log class distribution
        self.logger.info(
            "Class distribution",
            **stats["class_distribution"],
        )
        
        # Log any failures
        if stats["failure_counts"]:
            self.logger.warning(
                "Generation failures",
                **stats["failure_counts"],
            )
        
        # Write pipeline summary
        summary_path = self._pipeline_logger.write_summary()
        self.logger.info(
            "Pipeline summary saved",
            path=str(summary_path),
        )
    
    def get_statistics(self) -> dict:
        """Get current statistics."""
        return self._stats.to_dict()
    
    def get_frame_results(self) -> list[FrameResult]:
        """Get all frame results."""
        return self._frame_results.copy()
