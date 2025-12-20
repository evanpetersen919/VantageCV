#==============================================================================
# VantageCV - Base Domain Class
#==============================================================================
# File: base.py
# Description: Abstract base class for all domain implementations
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseDomain(ABC):
    """
    Abstract base class for domain-specific synthetic data generation.
    Each domain (industrial, automotive, etc.) inherits this and implements
    the specific methods for that domain.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize domain with configuration."""
        self.config = config
        self.domain_name = config.get('domain', {}).get('name', 'unknown')
    
    @abstractmethod
    def setup_scene(self) -> bool:
        """
        Set up the UE5 scene for this domain.
        This creates/loads the environment, objects, lighting, etc.
        Returns True if successful.
        """
        pass
    
    @abstractmethod
    def randomize_scene(self) -> Dict[str, Any]:
        """
        Apply domain randomization to the scene.
        This changes lighting, materials, object poses, camera angles, etc.
        Returns metadata about what was randomized.
        """
        pass
    
    @abstractmethod
    def get_annotations(self) -> Dict[str, Any]:
        """
        Extract ground truth annotations from the current scene.
        Returns dict with bounding boxes, masks, poses, etc.
        """
        pass
    
    @abstractmethod
    def validate_scene(self) -> bool:
        """
        Check if scene is valid (objects visible, not occluded, etc.).
        Returns True if scene is good for data generation.
        """
        pass
    
    def get_object_list(self) -> List[str]:
        """Get list of object classes in this domain."""
        return self.config.get('objects', {}).get('classes', [])
    
    def get_camera_config(self) -> Dict[str, Any]:
        """Get camera configuration for this domain."""
        return self.config.get('camera', {})

