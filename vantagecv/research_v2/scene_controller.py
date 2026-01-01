"""
Research v2 - MODULE 1: Scene Controller

Responsibilities:
- Initialize a single straight-road scene
- Place static infrastructure (road, lane markings, barriers)
- Ensure deterministic scene reset capability

Logging (REQUIRED):
- Scene initialized (scene_id)
- Environment parameters
- Random seed used
"""

from dataclasses import dataclass
from typing import Optional
import random

from .logging_utils import ResearchLogger
from .config import SceneConfig, TimeOfDay


@dataclass
class SceneState:
    """Current state of the scene."""
    scene_id: str
    is_initialized: bool = False
    time_of_day: TimeOfDay = TimeOfDay.DAY
    random_seed: int = 0
    frame_index: int = 0
    
    def to_dict(self) -> dict:
        """Serialize state to dictionary."""
        return {
            "scene_id": self.scene_id,
            "is_initialized": self.is_initialized,
            "time_of_day": self.time_of_day.value,
            "random_seed": self.random_seed,
            "frame_index": self.frame_index,
        }


class SceneController:
    """
    MODULE 1 - Scene Controller
    
    Manages the straight-road scene environment.
    Provides deterministic scene setup and reset.
    """
    
    MODULE_NAME = "SceneController"
    
    def __init__(
        self,
        config: SceneConfig,
        logger: Optional[ResearchLogger] = None,
    ):
        """
        Initialize scene controller.
        
        Args:
            config: Scene configuration
            logger: Optional logger (creates own if not provided)
        """
        self.config = config
        self.logger = logger or ResearchLogger(self.MODULE_NAME)
        self._state: Optional[SceneState] = None
        self._rng = random.Random()
        
        self.logger.log_init(
            road_length=config.road_length,
            road_width=config.road_width,
            num_lanes=config.num_lanes,
            lane_positions=config.lane_positions,
            time_of_day=config.time_of_day.value,
            level_path=config.level_path,
        )
    
    def initialize(self, seed: int, scene_id: Optional[str] = None) -> bool:
        """
        Initialize the scene with given seed.
        
        Args:
            seed: Random seed for reproducibility
            scene_id: Optional scene identifier (auto-generated if not provided)
            
        Returns:
            True if initialization successful
        """
        self.logger.info("Initializing scene", seed=seed)
        
        # Set random state
        self._rng.seed(seed)
        
        # Generate scene ID if not provided
        if scene_id is None:
            scene_id = f"scene_{seed:08d}"
        
        # Create scene state
        self._state = SceneState(
            scene_id=scene_id,
            is_initialized=True,
            time_of_day=self.config.time_of_day,
            random_seed=seed,
            frame_index=0,
        )
        
        self.logger.info(
            "Scene initialized successfully",
            scene_id=scene_id,
            environment={
                "road_length": self.config.road_length,
                "road_width": self.config.road_width,
                "num_lanes": self.config.num_lanes,
                "lane_positions": self.config.lane_positions,
                "time_of_day": self.config.time_of_day.value,
            },
            random_seed=seed,
        )
        
        return True
    
    def reset(self, new_seed: Optional[int] = None) -> bool:
        """
        Reset scene to initial state.
        
        Args:
            new_seed: Optional new seed (uses increment of current if not provided)
            
        Returns:
            True if reset successful
        """
        if self._state is None:
            self.logger.error(
                "Cannot reset uninitialized scene",
                reason="Scene was never initialized",
                suggested_fix="Call initialize() before reset()",
            )
            return False
        
        # Determine new seed
        if new_seed is None:
            new_seed = self._state.random_seed + 1
        
        self.logger.info(
            "Resetting scene",
            previous_scene_id=self._state.scene_id,
            previous_frame_index=self._state.frame_index,
            new_seed=new_seed,
        )
        
        # Re-initialize with new seed
        return self.initialize(new_seed)
    
    def advance_frame(self) -> int:
        """
        Advance to next frame.
        
        Returns:
            New frame index
        """
        if self._state is None:
            self.logger.error(
                "Cannot advance frame in uninitialized scene",
                reason="Scene was never initialized",
                suggested_fix="Call initialize() first",
            )
            return -1
        
        self._state.frame_index += 1
        
        self.logger.debug(
            "Frame advanced",
            frame_index=self._state.frame_index,
            scene_id=self._state.scene_id,
        )
        
        return self._state.frame_index
    
    def get_lane_position(self, lane_index: int) -> float:
        """
        Get Y position for a lane.
        
        Args:
            lane_index: Lane index (0 to num_lanes-1)
            
        Returns:
            Y coordinate of lane center
        """
        if lane_index < 0 or lane_index >= self.config.num_lanes:
            self.logger.warning(
                "Lane index out of bounds",
                lane_index=lane_index,
                num_lanes=self.config.num_lanes,
            )
            lane_index = max(0, min(lane_index, self.config.num_lanes - 1))
        
        return self.config.lane_positions[lane_index]
    
    def sample_lane(self) -> tuple[int, float]:
        """
        Sample a random lane.
        
        Returns:
            Tuple of (lane_index, y_position)
        """
        lane_index = self._rng.randint(0, self.config.num_lanes - 1)
        y_position = self.get_lane_position(lane_index)
        return lane_index, y_position
    
    def set_time_of_day(self, time_of_day: TimeOfDay) -> None:
        """
        Set lighting condition.
        
        Args:
            time_of_day: DAY or NIGHT
        """
        previous = self.config.time_of_day
        self.config.time_of_day = time_of_day
        
        if self._state:
            self._state.time_of_day = time_of_day
        
        self.logger.info(
            "Time of day changed",
            previous=previous.value,
            current=time_of_day.value,
        )
    
    def sample_time_of_day(self, day_probability: float = 0.7) -> TimeOfDay:
        """
        Randomly sample time of day.
        
        Args:
            day_probability: Probability of daytime (default 70%)
            
        Returns:
            Sampled time of day
        """
        time = TimeOfDay.DAY if self._rng.random() < day_probability else TimeOfDay.NIGHT
        self.set_time_of_day(time)
        return time
    
    @property
    def state(self) -> Optional[SceneState]:
        """Get current scene state."""
        return self._state
    
    @property
    def is_initialized(self) -> bool:
        """Check if scene is initialized."""
        return self._state is not None and self._state.is_initialized
    
    @property
    def frame_index(self) -> int:
        """Get current frame index."""
        return self._state.frame_index if self._state else -1
    
    @property
    def scene_id(self) -> Optional[str]:
        """Get current scene ID."""
        return self._state.scene_id if self._state else None
    
    def get_spawn_bounds(self) -> dict:
        """
        Get spawn bounds for vehicles.
        
        Returns:
            Dictionary with x_min, x_max, y_min, y_max
        """
        half_width = self.config.road_width / 2
        return {
            "x_min": 0.0,
            "x_max": self.config.road_length,
            "y_min": -half_width,
            "y_max": half_width,
        }
    
    def get_ue5_commands(self) -> list[dict]:
        """
        Get UE5 commands to set up scene.
        
        Returns:
            List of command dictionaries for UE5 execution
        """
        commands = []
        
        # Load level
        commands.append({
            "type": "load_level",
            "path": self.config.level_path,
        })
        
        # Set time of day (lighting)
        if self._state:
            commands.append({
                "type": "set_time_of_day",
                "time": self._state.time_of_day.value,
            })
        
        return commands
    
    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate scene configuration.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        if self.config.num_lanes < 1:
            issues.append("Must have at least 1 lane")
        
        if self.config.road_length < 20:
            issues.append("Road length must be at least 20m")
        
        if self.config.lane_width < 2.5:
            issues.append("Lane width should be at least 2.5m")
        
        if len(self.config.lane_positions) != self.config.num_lanes:
            issues.append(f"Lane positions count ({len(self.config.lane_positions)}) "
                         f"doesn't match num_lanes ({self.config.num_lanes})")
        
        is_valid = len(issues) == 0
        
        if not is_valid:
            for issue in issues:
                self.logger.warning("Scene validation issue", issue=issue)
        else:
            self.logger.info("Scene configuration validated successfully")
        
        return is_valid, issues
