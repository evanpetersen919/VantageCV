#==============================================================================
# VantageCV - Core Package Initialization
#==============================================================================
# File: __init__.py
# Description: Package initialization for VantageCV core modules
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

"""
VantageCV: Synthetic Data Generation for Computer Vision

A hybrid Python/C++ platform combining Unreal Engine 5's photorealistic
rendering with optimized ML workflows for synthetic training data generation.
"""

__version__ = "0.1.0"
__author__ = "Evan Petersen"

# Import core modules for convenient access
from .config import Config
from .generator import SyntheticDataGenerator
from .annotator import AnnotationExporter

__all__ = [
    "Config",
    "SyntheticDataGenerator",
    "AnnotationExporter",
]

