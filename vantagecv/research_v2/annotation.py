"""
Research v2 - MODULE 5: Annotation Generator

Responsibilities:
- Project 3D vehicle bounds to 2D
- Compute tight 2D bounding boxes
- Assign class labels
- Assign instance IDs

Annotation format:
- COCO-style JSON (images, annotations, categories)

Per-instance fields:
- bbox (x, y, w, h)
- class_id
- instance_id
- truncation flag (out of frame)
- occlusion flag (binary, v1)

Logging (REQUIRED):
- Annotation pass started
- Per-instance projection success / failure
- Bounding box validity check
- Annotation file written
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json

from .logging_utils import ResearchLogger
from .config import AnnotationConfig, VehicleClass, CameraConfig
from .vehicle_spawner import SpawnedVehicle
from .camera_system import CameraSystem, CameraState


# Vehicle dimensions for bounding box computation (length, width, height in meters)
VEHICLE_DIMENSIONS_3D = {
    VehicleClass.CAR: (4.5, 1.8, 1.5),
    VehicleClass.TRUCK: (6.0, 2.2, 2.5),
    VehicleClass.BUS: (12.0, 2.5, 3.0),
    VehicleClass.MOTORCYCLE: (2.2, 0.8, 1.2),
    VehicleClass.BICYCLE: (1.8, 0.6, 1.0),
}


@dataclass
class BoundingBox2D:
    """2D bounding box in image coordinates."""
    x: float      # Left edge (pixels)
    y: float      # Top edge (pixels)
    width: float  # Width (pixels)
    height: float # Height (pixels)
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def x2(self) -> float:
        """Right edge."""
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        """Bottom edge."""
        return self.y + self.height
    
    def to_coco(self) -> list[float]:
        """Return [x, y, width, height] format."""
        return [self.x, self.y, self.width, self.height]
    
    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "area": self.area,
        }
    
    def clip_to_image(self, img_width: int, img_height: int) -> "BoundingBox2D":
        """Clip bbox to image bounds, return new bbox."""
        new_x = max(0, self.x)
        new_y = max(0, self.y)
        new_x2 = min(img_width, self.x2)
        new_y2 = min(img_height, self.y2)
        
        return BoundingBox2D(
            x=new_x,
            y=new_y,
            width=max(0, new_x2 - new_x),
            height=max(0, new_y2 - new_y),
        )
    
    def compute_truncation(self, original: "BoundingBox2D") -> float:
        """Compute truncation ratio (0 = fully visible, 1 = fully truncated)."""
        if original.area <= 0:
            return 1.0
        return 1.0 - (self.area / original.area)


@dataclass
class InstanceAnnotation:
    """Annotation for a single vehicle instance."""
    instance_id: str
    category_id: int
    category_name: str
    bbox: BoundingBox2D
    area: float
    truncation: float      # 0 = visible, 1 = fully truncated
    is_occluded: bool      # Binary occlusion flag
    is_valid: bool         # Whether annotation passed validation
    validation_issues: list[str] = field(default_factory=list)
    
    def to_coco_annotation(self, annotation_id: int, image_id: int) -> dict:
        """Convert to COCO annotation format."""
        return {
            "id": annotation_id,
            "image_id": image_id,
            "category_id": self.category_id,
            "bbox": self.bbox.to_coco(),
            "area": self.area,
            "iscrowd": 0,
            # Custom fields
            "instance_id": self.instance_id,
            "truncation": self.truncation,
            "is_occluded": self.is_occluded,
        }
    
    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "bbox": self.bbox.to_dict(),
            "area": self.area,
            "truncation": self.truncation,
            "is_occluded": self.is_occluded,
            "is_valid": self.is_valid,
            "validation_issues": self.validation_issues,
        }


@dataclass
class FrameAnnotation:
    """Annotations for a single frame."""
    frame_index: int
    image_id: int
    image_filename: str
    image_width: int
    image_height: int
    instances: list[InstanceAnnotation] = field(default_factory=list)
    
    @property
    def valid_instances(self) -> list[InstanceAnnotation]:
        """Get only valid instances."""
        return [i for i in self.instances if i.is_valid]
    
    @property
    def num_valid(self) -> int:
        return len(self.valid_instances)
    
    def to_coco_image(self) -> dict:
        """Convert to COCO image entry."""
        return {
            "id": self.image_id,
            "file_name": self.image_filename,
            "width": self.image_width,
            "height": self.image_height,
        }
    
    def to_dict(self) -> dict:
        return {
            "frame_index": self.frame_index,
            "image_id": self.image_id,
            "image_filename": self.image_filename,
            "image_size": (self.image_width, self.image_height),
            "num_instances": len(self.instances),
            "num_valid": self.num_valid,
            "instances": [i.to_dict() for i in self.instances],
        }


class AnnotationGenerator:
    """
    MODULE 5 - Annotation Generator
    
    Generates COCO-format annotations from 3D vehicle data.
    """
    
    MODULE_NAME = "AnnotationGenerator"
    
    def __init__(
        self,
        config: AnnotationConfig,
        camera_config: CameraConfig,
        logger: Optional[ResearchLogger] = None,
    ):
        """
        Initialize annotation generator.
        
        Args:
            config: Annotation configuration
            camera_config: Camera configuration for image dimensions
            logger: Optional logger
        """
        self.config = config
        self.camera_config = camera_config
        self.logger = logger or ResearchLogger(self.MODULE_NAME)
        
        self._annotation_id_counter = 0
        self._frame_annotations: list[FrameAnnotation] = []
        
        # Statistics
        self._total_instances = 0
        self._valid_instances = 0
        self._projection_failures = 0
        
        self.logger.log_init(
            format=config.format,
            min_bbox_area=config.min_bbox_area,
            min_bbox_dimension=config.min_bbox_dimension,
            max_truncation=config.max_truncation,
            image_size=(camera_config.width, camera_config.height_px),
        )
    
    def annotate_frame(
        self,
        frame_index: int,
        image_id: int,
        image_filename: str,
        vehicles: list[SpawnedVehicle],
        camera: CameraSystem,
    ) -> FrameAnnotation:
        """
        Generate annotations for a frame.
        
        Args:
            frame_index: Current frame index
            image_id: Unique image ID for COCO
            image_filename: Filename for the image
            vehicles: List of spawned vehicles
            camera: Camera system for projection
            
        Returns:
            FrameAnnotation with all instance annotations
        """
        self.logger.info(
            "Annotation pass started",
            frame_index=frame_index,
            image_id=image_id,
            num_vehicles=len(vehicles),
        )
        
        frame_annotation = FrameAnnotation(
            frame_index=frame_index,
            image_id=image_id,
            image_filename=image_filename,
            image_width=self.camera_config.width,
            image_height=self.camera_config.height_px,
        )
        
        for vehicle in vehicles:
            instance = self._annotate_vehicle(vehicle, camera)
            frame_annotation.instances.append(instance)
            
            self._total_instances += 1
            if instance.is_valid:
                self._valid_instances += 1
        
        self._frame_annotations.append(frame_annotation)
        
        self.logger.log_output(
            "Annotation pass completed",
            frame_index=frame_index,
            total_instances=len(vehicles),
            valid_instances=frame_annotation.num_valid,
        )
        
        return frame_annotation
    
    def _annotate_vehicle(
        self,
        vehicle: SpawnedVehicle,
        camera: CameraSystem,
    ) -> InstanceAnnotation:
        """
        Generate annotation for a single vehicle.
        
        Args:
            vehicle: Vehicle to annotate
            camera: Camera system for projection
            
        Returns:
            InstanceAnnotation
        """
        # Get vehicle dimensions from the vehicle instance (actual UE5 dimensions)
        length = vehicle.dimensions.length
        width = vehicle.dimensions.width
        height = vehicle.dimensions.height
        
        # Project 3D bbox to 2D
        x = vehicle.transform.x
        y = vehicle.transform.y
        z = vehicle.transform.z
        
        bbox_result = camera.project_bbox_3d_to_2d(
            x=x, y=y, z=z,
            length=length, width=width, height=height,
        )
        
        if bbox_result is None:
            # Projection failed
            self._projection_failures += 1
            
            self.logger.warning(
                "Projection failed",
                instance_id=vehicle.instance_id,
                vehicle_class=vehicle.vehicle_class.value,
                reason="Vehicle behind camera or not visible",
            )
            
            return InstanceAnnotation(
                instance_id=vehicle.instance_id,
                category_id=VehicleClass.get_id(vehicle.vehicle_class),
                category_name=vehicle.vehicle_class.value,
                bbox=BoundingBox2D(0, 0, 0, 0),
                area=0,
                truncation=1.0,
                is_occluded=False,
                is_valid=False,
                validation_issues=["Projection failed - vehicle not visible"],
            )
        
        # Create original bbox
        bx, by, bw, bh = bbox_result
        original_bbox = BoundingBox2D(x=bx, y=by, width=bw, height=bh)
        
        # Clip to image bounds
        clipped_bbox = original_bbox.clip_to_image(
            self.camera_config.width,
            self.camera_config.height_px,
        )
        
        # Compute truncation
        truncation = clipped_bbox.compute_truncation(original_bbox)
        
        # Validate bbox
        is_valid, validation_issues = self._validate_bbox(clipped_bbox, truncation)
        
        # Log instance result
        if is_valid:
            self.logger.debug(
                "Instance annotated",
                instance_id=vehicle.instance_id,
                vehicle_class=vehicle.vehicle_class.value,
                bbox=clipped_bbox.to_dict(),
                truncation=truncation,
            )
        else:
            self.logger.warning(
                "Instance annotation invalid",
                instance_id=vehicle.instance_id,
                vehicle_class=vehicle.vehicle_class.value,
                issues=validation_issues,
            )
        
        return InstanceAnnotation(
            instance_id=vehicle.instance_id,
            category_id=VehicleClass.get_id(vehicle.vehicle_class),
            category_name=vehicle.vehicle_class.value,
            bbox=clipped_bbox,
            area=clipped_bbox.area,
            truncation=truncation,
            is_occluded=False,  # v1: no occlusion detection
            is_valid=is_valid,
            validation_issues=validation_issues,
        )
    
    def _validate_bbox(
        self,
        bbox: BoundingBox2D,
        truncation: float,
    ) -> tuple[bool, list[str]]:
        """
        Validate a bounding box.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check minimum area
        if bbox.area < self.config.min_bbox_area:
            issues.append(f"Area {bbox.area:.1f} below minimum {self.config.min_bbox_area}")
        
        # Check minimum dimensions
        if bbox.width < self.config.min_bbox_dimension:
            issues.append(f"Width {bbox.width:.1f} below minimum {self.config.min_bbox_dimension}")
        
        if bbox.height < self.config.min_bbox_dimension:
            issues.append(f"Height {bbox.height:.1f} below minimum {self.config.min_bbox_dimension}")
        
        # Check truncation
        if truncation > self.config.max_truncation:
            issues.append(f"Truncation {truncation:.2f} exceeds maximum {self.config.max_truncation}")
        
        # Check if completely outside image
        if bbox.x >= self.camera_config.width or bbox.y >= self.camera_config.height_px:
            issues.append("Bbox completely outside image")
        
        if bbox.x + bbox.width <= 0 or bbox.y + bbox.height <= 0:
            issues.append("Bbox completely outside image (negative)")
        
        return len(issues) == 0, issues
    
    def get_coco_categories(self) -> list[dict]:
        """Get COCO category definitions."""
        return [
            {
                "id": VehicleClass.get_id(cls),
                "name": cls.value,
                "supercategory": "vehicle",
            }
            for cls in VehicleClass
        ]
    
    def export_coco(self, output_path: Path) -> Path:
        """
        Export all annotations to COCO JSON format.
        
        Args:
            output_path: Path to write annotations.json
            
        Returns:
            Path to written file
        """
        output_path = Path(output_path)
        
        self.logger.info("Exporting COCO annotations", output_path=str(output_path))
        
        # Build COCO structure
        coco_data = {
            "info": {
                "description": "VantageCV Research v2 Dataset",
                "version": "2.0.0",
                "year": 2024,
                "contributor": "VantageCV",
            },
            "licenses": [],
            "categories": self.get_coco_categories(),
            "images": [],
            "annotations": [],
        }
        
        annotation_id = 1
        
        for frame_ann in self._frame_annotations:
            # Add image entry
            coco_data["images"].append(frame_ann.to_coco_image())
            
            # Add valid annotations
            for instance in frame_ann.valid_instances:
                ann = instance.to_coco_annotation(
                    annotation_id=annotation_id,
                    image_id=frame_ann.image_id,
                )
                coco_data["annotations"].append(ann)
                annotation_id += 1
        
        # Write file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(coco_data, f, indent=2)
        
        self.logger.info(
            "COCO annotations written",
            output_path=str(output_path),
            num_images=len(coco_data["images"]),
            num_annotations=len(coco_data["annotations"]),
        )
        
        return output_path
    
    def get_statistics(self) -> dict:
        """Get annotation statistics."""
        class_counts = {cls.value: 0 for cls in VehicleClass}
        
        for frame_ann in self._frame_annotations:
            for inst in frame_ann.valid_instances:
                class_counts[inst.category_name] += 1
        
        return {
            "total_frames": len(self._frame_annotations),
            "total_instances": self._total_instances,
            "valid_instances": self._valid_instances,
            "projection_failures": self._projection_failures,
            "class_distribution": class_counts,
            "validity_rate": self._valid_instances / max(self._total_instances, 1),
        }
    
    def reset(self) -> None:
        """Reset annotation state."""
        self._frame_annotations.clear()
        self._annotation_id_counter = 0
        self._total_instances = 0
        self._valid_instances = 0
        self._projection_failures = 0
        self.logger.info("Annotation state reset")
