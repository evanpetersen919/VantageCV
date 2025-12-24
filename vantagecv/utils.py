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
from typing import List, Tuple, Dict, Any, Optional, Union
import numpy as np
from PIL import Image


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


def polygon_to_rle(polygon: List[List[float]], height: int, width: int) -> Dict[str, Any]:
    """
    Convert polygon segmentation to COCO RLE format.
    
    RLE (Run Length Encoding) is more compact for complex shapes.
    
    Args:
        polygon: List of [x1,y1,x2,y2,...] coordinates
        height: Image height in pixels
        width: Image width in pixels
        
    Returns:
        RLE-encoded mask in COCO format
    """
    from pycocotools import mask as mask_utils
    
    # Create binary mask from polygon
    rles = mask_utils.frPyObjects([polygon], height, width)
    rle = mask_utils.merge(rles)
    
    return {
        'size': [height, width],
        'counts': rle['counts'].decode('utf-8') if isinstance(rle['counts'], bytes) else rle['counts']
    }


def mask_to_polygon(mask: np.ndarray, tolerance: float = 2.0) -> List[List[float]]:
    """
    Convert binary mask to polygon format.
    
    Args:
        mask: Binary mask array (H x W)
        tolerance: Douglas-Peucker tolerance for polygon simplification
        
    Returns:
        List of polygons, each as [x1,y1,x2,y2,...]
    """
    import cv2
    
    # Find contours
    contours, _ = cv2.findContours(
        mask.astype(np.uint8),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )
    
    polygons = []
    for contour in contours:
        # Simplify contour
        epsilon = tolerance
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        # Convert to flat list [x1,y1,x2,y2,...]
        if len(approx) >= 3:  # Valid polygon needs at least 3 points
            polygon = approx.flatten().tolist()
            polygons.append(polygon)
    
    return polygons


def validate_mask(mask: np.ndarray, image_width: int, image_height: int) -> bool:
    """
    Validate segmentation mask.
    
    Args:
        mask: Binary mask array
        image_width: Image width
        image_height: Image height
        
    Returns:
        True if mask is valid
    """
    if mask.shape[0] != image_height or mask.shape[1] != image_width:
        return False
    
    if mask.dtype != np.uint8 and mask.dtype != bool:
        return False
    
    # Check if mask has any foreground pixels
    if not np.any(mask):
        return False
    
    return True


def rotation_matrix_to_euler(R: np.ndarray) -> Tuple[float, float, float]:
    """
    Convert rotation matrix to Euler angles (ZYX convention).
    
    Args:
        R: 3x3 rotation matrix
        
    Returns:
        (roll, pitch, yaw) in radians
    """
    sy = np.sqrt(R[0, 0]**2 + R[1, 0]**2)
    
    singular = sy < 1e-6
    
    if not singular:
        roll = np.arctan2(R[2, 1], R[2, 2])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = np.arctan2(R[1, 0], R[0, 0])
    else:
        roll = np.arctan2(-R[1, 2], R[1, 1])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = 0
    
    return roll, pitch, yaw


def euler_to_rotation_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """
    Convert Euler angles to rotation matrix (ZYX convention).
    
    Args:
        roll: Rotation around X axis (radians)
        pitch: Rotation around Y axis (radians)
        yaw: Rotation around Z axis (radians)
        
    Returns:
        3x3 rotation matrix
    """
    # Rotation around X
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(roll), -np.sin(roll)],
        [0, np.sin(roll), np.cos(roll)]
    ])
    
    # Rotation around Y
    Ry = np.array([
        [np.cos(pitch), 0, np.sin(pitch)],
        [0, 1, 0],
        [-np.sin(pitch), 0, np.cos(pitch)]
    ])
    
    # Rotation around Z
    Rz = np.array([
        [np.cos(yaw), -np.sin(yaw), 0],
        [np.sin(yaw), np.cos(yaw), 0],
        [0, 0, 1]
    ])
    
    # Combined rotation: R = Rz * Ry * Rx
    R = Rz @ Ry @ Rx
    return R


def validate_pose(rotation: np.ndarray, translation: np.ndarray) -> bool:
    """
    Validate 6D pose (rotation + translation).
    
    Args:
        rotation: 3x3 rotation matrix or 4 quaternion values
        translation: 3D translation vector [x, y, z]
        
    Returns:
        True if pose is valid
    """
    # Validate translation
    if translation.shape != (3,):
        return False
    
    if not np.all(np.isfinite(translation)):
        return False
    
    # Validate rotation matrix
    if rotation.shape == (3, 3):
        # Check orthogonality: R^T * R = I
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6):
            return False
        
        # Check determinant = 1 (proper rotation, not reflection)
        if not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-6):
            return False
    
    elif rotation.shape == (4,):
        # Quaternion: check unit norm
        if not np.isclose(np.linalg.norm(rotation), 1.0, atol=1e-6):
            return False
    else:
        return False
    
    return True

