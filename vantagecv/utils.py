#==============================================================================
# VantageCV - Utility Functions
#==============================================================================
# File: utils.py
# Description: Helper functions for file I/O, image processing, and validation
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

"""Utility functions for VantageCV."""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging for VantageCV.
    
    Args:
        level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
    """
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def load_image(image_path: Path) -> Optional[np.ndarray]:
    """
    Load image from file.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Image as numpy array (BGR format) or None if failed
    """
    if not image_path.exists():
        logger.error(f"Image not found: {image_path}")
        return None
    
    image = cv2.imread(str(image_path))
    if image is None:
        logger.error(f"Failed to load image: {image_path}")
    
    return image


def save_image(image: np.ndarray, output_path: Path) -> bool:
    """
    Save image to file.
    
    Args:
        image: Image as numpy array
        output_path: Output file path
        
    Returns:
        True if successful
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    success = cv2.imwrite(str(output_path), image)
    if success:
        logger.debug(f"Saved image to {output_path}")
    else:
        logger.error(f"Failed to save image to {output_path}")
    
    return success


def resize_image(image: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
    """
    Resize image to target size.
    
    Args:
        image: Input image
        target_size: (width, height) tuple
        
    Returns:
        Resized image
    """
    return cv2.resize(image, target_size, interpolation=cv2.INTER_LINEAR)


def validate_bbox(bbox: Tuple[float, float, float, float], 
                  image_width: int, image_height: int) -> bool:
    """
    Validate bounding box coordinates.
    
    Args:
        bbox: (x, y, width, height) tuple
        image_width: Image width
        image_height: Image height
        
    Returns:
        True if bbox is valid
    """
    x, y, w, h = bbox
    
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        return False
    
    if x + w > image_width or y + h > image_height:
        return False
    
    return True


def ensure_dir(directory: Path) -> None:
    """
    Ensure directory exists, create if it doesn't.
    
    Args:
        directory: Directory path
    """
    directory.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {directory}")

