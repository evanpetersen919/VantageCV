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

A hybrid synthetic data platform combining Unreal Engine 5's photorealistic
rendering with optimized machine learning workflows.
"""

__version__ = "0.1.0"
__author__ = "Evan Petersen"

# Import core modules for convenient access
from .config import load_config
from .generator import SyntheticDataGenerator
from .annotator import AnnotationGenerator

__all__ = [
    "load_config",
    "SyntheticDataGenerator",
    "AnnotationGenerator",
]

