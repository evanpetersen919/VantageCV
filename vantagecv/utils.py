#==============================================================================
# VantageCV - Utility Functions
#==============================================================================
# File: utils.py
# Description: Helper functions for validation, file I/O, and conversions
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import json
from pathlib import Path
from typing import List, Tuple, Dict, Any
import numpy as np


def validate_bbox(bbox: List[float], image_width: int, image_height: int) -> bool:
    """
    Validate bounding box coordinates.
    
    Args:
        bbox: [x, y, width, height]
        image_width: Image width in pixels
        image_height: Image height in pixels
        
    Returns:
        True if bbox is valid (within image bounds and has positive size)
    """
    if len(bbox) != 4:
        return False
    
    x, y, w, h = bbox
    
    # Check positive dimensions
    if w <= 0 or h <= 0:
        return False
    
    # Check within image bounds
    if x < 0 or y < 0:
        return False
    
    if x + w > image_width or y + h > image_height:
        return False
    
    return True


def bbox_to_yolo(bbox: List[float], image_width: int, image_height: int) -> List[float]:
    """
    Convert bbox from [x, y, width, height] to YOLO format.
    
    YOLO format: [center_x, center_y, width, height] (all normalized 0-1)
    
    Args:
        bbox: [x, y, width, height] in pixels
        image_width: Image width
        image_height: Image height
        
    Returns:
        [center_x, center_y, width, height] normalized
    """
    x, y, w, h = bbox
    
    center_x = (x + w / 2) / image_width
    center_y = (y + h / 2) / image_height
    norm_w = w / image_width
    norm_h = h / image_height
    
    return [center_x, center_y, norm_w, norm_h]


def yolo_to_bbox(yolo_coords: List[float], image_width: int, image_height: int) -> List[float]:
    """
    Convert YOLO format to bbox [x, y, width, height].
    
    Args:
        yolo_coords: [center_x, center_y, width, height] (normalized)
        image_width: Image width
        image_height: Image height
        
    Returns:
        [x, y, width, height] in pixels
    """
    center_x, center_y, norm_w, norm_h = yolo_coords
    
    w = norm_w * image_width
    h = norm_h * image_height
    x = center_x * image_width - w / 2
    y = center_y * image_height - h / 2
    
    return [x, y, w, h]


def calculate_iou(bbox1: List[float], bbox2: List[float]) -> float:
    """
    Calculate Intersection over Union (IoU) between two bounding boxes.
    
    Args:
        bbox1: [x, y, width, height]
        bbox2: [x, y, width, height]
        
    Returns:
        IoU score (0.0 to 1.0)
    """
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2
    
    # Calculate intersection coordinates
    x_left = max(x1, x2)
    y_top = max(y1, y2)
    x_right = min(x1 + w1, x2 + w2)
    y_bottom = min(y1 + h1, y2 + h2)
    
    # Check if there's intersection
    if x_right < x_left or y_bottom < y_top:
        return 0.0
    
    # Calculate areas
    intersection = (x_right - x_left) * (y_bottom - y_top)
    area1 = w1 * h1
    area2 = w2 * h2
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0.0


def ensure_dir(directory: Path) -> None:
    """
    Ensure directory exists, create if needed.
    
    Args:
        directory: Directory path
    """
    Path(directory).mkdir(parents=True, exist_ok=True)


def load_json(filepath: Path) -> Dict[str, Any]:
    """
    Load JSON file.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Parsed JSON as dictionary
    """
    with open(filepath, 'r') as f:
        return json.load(f)


def save_json(data: Dict[str, Any], filepath: Path, indent: int = 2) -> None:
    """
    Save dictionary to JSON file.
    
    Args:
        data: Data to save
        filepath: Output path
        indent: JSON indentation level
    """
    ensure_dir(filepath.parent)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=indent)

