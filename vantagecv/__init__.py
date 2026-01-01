#==============================================================================
# VantageCV - Minimal Vehicle Synthetic Data Generator
#==============================================================================
# File: __init__.py
# Description: Package initialization for VantageCV
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

"""
VantageCV: Research-Grade Synthetic Vehicle Dataset Generator

A minimal, modular system for generating synthetic vehicle detection datasets
using Unreal Engine 5 rendering.

Primary entry point: scripts/generate_v2.py
Configuration: configs/research_v2.yaml

Target classes: car, truck, bus, motorcycle, bicycle
Target tasks: 2D object detection, instance identification
"""

__version__ = "2.0.0"
__author__ = "Evan Petersen"

# Core utilities
from .config import Config
from .ue5_bridge import UE5Bridge

# Research v2 is the primary system
from .research_v2 import (
    ResearchConfig,
    DatasetOrchestrator,
    SceneController,
    VehicleSpawner,
    CameraSystem,
    AnnotationGenerator,
    FrameValidator,
    ResearchLogger,
)

__all__ = [
    # Core
    "Config",
    "UE5Bridge",
    # Research v2 modules
    "ResearchConfig",
    "DatasetOrchestrator",
    "SceneController",
    "VehicleSpawner",
    "CameraSystem",
    "AnnotationGenerator",
    "FrameValidator",
    "ResearchLogger",
]

