"""
Research v2 - Configuration Module

Single source of truth for all pipeline parameters.
Designed for reproducibility and easy debugging.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
import json
import yaml


class VehicleClass(Enum):
    """Supported vehicle classes for detection."""
    CAR = "car"
    TRUCK = "truck"
    BUS = "bus"
    MOTORCYCLE = "motorcycle"
    BICYCLE = "bicycle"
    
    @classmethod
    def get_id(cls, vehicle_class: "VehicleClass") -> int:
        """Get COCO-style category ID (1-indexed)."""
        return list(cls).index(vehicle_class) + 1
    
    @classmethod
    def from_id(cls, category_id: int) -> "VehicleClass":
        """Get vehicle class from category ID."""
        return list(cls)[category_id - 1]
    
    @classmethod
    def all_classes(cls) -> list[str]:
        """Get all class names."""
        return [v.value for v in cls]


class TimeOfDay(Enum):
    """Supported lighting conditions."""
    DAY = "day"
    NIGHT = "night"


@dataclass
class SceneConfig:
    """
    MODULE 1 - Scene Controller Configuration
    
    Single straight road environment.
    """
    # Road parameters
    road_length: float = 200.0  # meters
    road_width: float = 12.0    # meters (3 lanes @ 4m each)
    lane_width: float = 4.0     # meters
    num_lanes: int = 3
    
    # Lane positions (center Y offsets from road center)
    lane_positions: list[float] = field(default_factory=lambda: [-4.0, 0.0, 4.0])
    
    # Environment
    time_of_day: TimeOfDay = TimeOfDay.DAY
    
    # UE5 paths (straight road level)
    level_path: str = "/Game/automobile"
    
    def __post_init__(self):
        """Validate and compute derived values."""
        if len(self.lane_positions) != self.num_lanes:
            self.lane_positions = [
                (i - self.num_lanes // 2) * self.lane_width
                for i in range(self.num_lanes)
            ]


@dataclass
class VehicleSpawnerConfig:
    """
    MODULE 2 - Vehicle Spawner Configuration
    
    Controls vehicle placement and distribution.
    """
    # Vehicle count distribution (fixed for v1)
    count_distribution: dict[str, float] = field(default_factory=lambda: {
        "1": 0.20,      # 20% single vehicle
        "2-4": 0.50,    # 50% 2-4 vehicles
        "5-6": 0.30,    # 30% 5-6 vehicles
    })
    
    # Class distribution (uniform by default)
    class_weights: dict[str, float] = field(default_factory=lambda: {
        "car": 0.35,
        "truck": 0.25,
        "bus": 0.15,
        "motorcycle": 0.15,
        "bicycle": 0.10,
    })
    
    # Spawn bounds (X = forward, Y = lateral)
    spawn_x_min: float = 10.0    # meters from camera
    spawn_x_max: float = 100.0   # meters from camera
    
    # Per-vehicle randomization
    scale_jitter: float = 0.05   # ±5% scale variation
    position_jitter: float = 0.5  # meters lateral jitter within lane
    
    # Collision avoidance
    min_spacing: float = 5.0     # minimum meters between vehicles
    
    # UE5 pre-placed actor names (visibility-based spawning)
    # These are actors already in the level that we hide/show and reposition
    vehicle_actors: dict[str, list[str]] = field(default_factory=lambda: {
        "car": ["StaticMeshActor_4", "StaticMeshActor_7", "StaticMeshActor_13", 
                "StaticMeshActor_18", "StaticMeshActor_19", "StaticMeshActor_23",
                "StaticMeshActor_26", "StaticMeshActor_29", "StaticMeshActor_33",
                "StaticMeshActor_34", "StaticMeshActor_39"],
        "truck": ["StaticMeshActor_25", "StaticMeshActor_27", "StaticMeshActor_31", "StaticMeshActor_41"],
        "bus": ["StaticMeshActor_9", "StaticMeshActor_11"],
        "motorcycle": ["StaticMeshActor_2", "StaticMeshActor_8", "SkeletalMeshActor_5"],
        "bicycle": ["StaticMeshActor_1", "StaticMeshActor_3", "StaticMeshActor_5"],
    })


@dataclass 
class CameraConfig:
    """
    MODULE 3 - Camera System Configuration
    
    Fixed forward-facing dashcam.
    """
    # Position (relative to scene origin)
    height: float = 1.5          # meters
    x_position: float = 0.0      # meters (at origin)
    y_position: float = 0.0      # meters (centered)
    
    # Orientation
    pitch: float = 0.0           # degrees (level)
    yaw: float = 0.0             # degrees (forward)
    roll: float = 0.0            # degrees (no tilt)
    
    # Lens
    fov: float = 90.0            # degrees
    fov_jitter: float = 2.0      # ±degrees variation
    
    # Resolution
    width: int = 1920
    height_px: int = 1080
    
    # Intrinsics (computed from FOV and resolution)
    @property
    def focal_length_px(self) -> float:
        """Focal length in pixels (assuming square pixels)."""
        import math
        return self.width / (2 * math.tan(math.radians(self.fov / 2)))
    
    @property
    def intrinsics(self) -> dict:
        """Camera intrinsic matrix as dict."""
        fx = fy = self.focal_length_px
        cx = self.width / 2
        cy = self.height_px / 2
        return {
            "fx": fx, "fy": fy,
            "cx": cx, "cy": cy,
            "width": self.width,
            "height": self.height_px,
        }


@dataclass
class RenderConfig:
    """
    MODULE 4 - Render & Capture Configuration
    """
    # Output format
    image_format: str = "png"
    jpeg_quality: int = 95
    
    # Anti-aliasing samples
    aa_samples: int = 4
    
    # Capture settings
    capture_delay_frames: int = 2  # frames to wait after scene setup


@dataclass
class AnnotationConfig:
    """
    MODULE 5 - Annotation Generator Configuration
    """
    # Format
    format: str = "coco"  # Only COCO supported in v1
    
    # Bounding box constraints
    min_bbox_area: int = 100      # pixels^2
    min_bbox_dimension: int = 10  # pixels
    max_truncation: float = 0.8   # 80% max out-of-frame
    
    # Instance tracking
    track_occlusion: bool = True


@dataclass
class ValidationConfig:
    """
    MODULE 6 - Validation Configuration
    """
    # Frame rejection criteria
    reject_zero_vehicles: bool = True
    reject_all_truncated: bool = True
    reject_all_occluded: bool = False  # v1: allow fully occluded
    
    # Bbox validity
    require_positive_area: bool = True
    require_in_frame: bool = True


@dataclass
class OutputConfig:
    """
    Output directory structure configuration.
    """
    base_dir: Path = field(default_factory=lambda: Path("data/research_v2"))
    
    # Subdirectories
    images_subdir: str = "images"
    annotations_subdir: str = "annotations"
    logs_subdir: str = "logs"
    metadata_subdir: str = "metadata"
    
    @property
    def images_dir(self) -> Path:
        return self.base_dir / self.images_subdir
    
    @property
    def annotations_dir(self) -> Path:
        return self.base_dir / self.annotations_subdir
    
    @property
    def logs_dir(self) -> Path:
        return self.base_dir / self.logs_subdir
    
    @property
    def metadata_dir(self) -> Path:
        return self.base_dir / self.metadata_subdir
    
    def create_directories(self) -> None:
        """Create all output directories."""
        for dir_path in [self.images_dir, self.annotations_dir, 
                         self.logs_dir, self.metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


@dataclass
class ResearchConfig:
    """
    Master configuration for Research v2 pipeline.
    
    Single source of truth for all parameters.
    """
    # Pipeline identification
    experiment_name: str = "research_v2"
    random_seed: int = 42
    
    # Dataset size
    num_images: int = 1000
    
    # Module configurations
    scene: SceneConfig = field(default_factory=SceneConfig)
    vehicles: VehicleSpawnerConfig = field(default_factory=VehicleSpawnerConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    annotation: AnnotationConfig = field(default_factory=AnnotationConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    # UE5 connection
    ue5_host: str = "localhost"
    ue5_port: int = 9998
    
    def __post_init__(self):
        """Initialize derived values."""
        # Update output base dir with experiment name
        if self.output.base_dir == Path("data/research_v2"):
            self.output.base_dir = Path(f"data/{self.experiment_name}")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        def convert(obj):
            if isinstance(obj, Enum):
                return obj.value
            elif isinstance(obj, Path):
                return str(obj)
            elif hasattr(obj, "__dataclass_fields__"):
                return {k: convert(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(v) for v in obj]
            return obj
        return convert(self)
    
    def save(self, path: Path) -> None:
        """Save configuration to YAML file."""
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def load(cls, path: Path) -> "ResearchConfig":
        """Load configuration from YAML file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ResearchConfig":
        """Create config from dictionary."""
        # Convert nested dicts to dataclasses
        scene_data = data.get("scene", {})
        if "time_of_day" in scene_data:
            scene_data["time_of_day"] = TimeOfDay(scene_data["time_of_day"])
        
        output_data = data.get("output", {})
        if "base_dir" in output_data:
            output_data["base_dir"] = Path(output_data["base_dir"])
        
        return cls(
            experiment_name=data.get("experiment_name", "research_v2"),
            random_seed=data.get("random_seed", 42),
            num_images=data.get("num_images", 1000),
            scene=SceneConfig(**scene_data) if scene_data else SceneConfig(),
            vehicles=VehicleSpawnerConfig(**data.get("vehicles", {})),
            camera=CameraConfig(**data.get("camera", {})),
            render=RenderConfig(**data.get("render", {})),
            annotation=AnnotationConfig(**data.get("annotation", {})),
            validation=ValidationConfig(**data.get("validation", {})),
            output=OutputConfig(**output_data) if output_data else OutputConfig(),
            ue5_host=data.get("ue5_host", "localhost"),
            ue5_port=data.get("ue5_port", 9998),
        )
    
    def validate(self) -> list[str]:
        """
        Validate configuration, return list of issues.
        
        Returns empty list if valid.
        """
        issues = []
        
        # Scene validation
        if self.scene.num_lanes < 1:
            issues.append("Scene must have at least 1 lane")
        if self.scene.road_length < 50:
            issues.append("Road length should be at least 50m for vehicle variety")
        
        # Vehicle validation
        total_weight = sum(self.vehicles.class_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            issues.append(f"Vehicle class weights must sum to 1.0, got {total_weight}")
        
        # Camera validation
        if self.camera.fov < 30 or self.camera.fov > 150:
            issues.append(f"Camera FOV {self.camera.fov} is outside reasonable range [30, 150]")
        
        # Output validation
        if self.num_images < 1:
            issues.append("Must generate at least 1 image")
        
        return issues


def create_default_config() -> ResearchConfig:
    """Create default research configuration."""
    return ResearchConfig()


def load_or_create_config(config_path: Optional[Path] = None) -> ResearchConfig:
    """Load config from file or create default."""
    if config_path and Path(config_path).exists():
        return ResearchConfig.load(config_path)
    return create_default_config()
