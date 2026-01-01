"""
VantageCV Research v2 - Minimal Research-Grade Synthetic Vehicle Dataset Generator

A clean, modular implementation prioritizing:
- Correctness over completeness
- Observability over features  
- Controlled scope over realism

Target classes: car, truck, bus, motorcycle, bicycle
Target tasks: 2D object detection, instance identification
"""

__version__ = "2.0.0"
__author__ = "VantageCV Research"

from .logging_utils import ResearchLogger, LogLevel
from .config import ResearchConfig
from .scene_controller import SceneController
from .vehicle_spawner import VehicleSpawner
from .camera_system import CameraSystem
from .annotation import AnnotationGenerator
from .validation import FrameValidator
from .orchestrator import DatasetOrchestrator

__all__ = [
    "ResearchLogger",
    "LogLevel", 
    "ResearchConfig",
    "SceneController",
    "VehicleSpawner",
    "CameraSystem",
    "AnnotationGenerator",
    "FrameValidator",
    "DatasetOrchestrator",
]
