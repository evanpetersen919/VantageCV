#==============================================================================
# VantageCV - Annotation Exporter
#==============================================================================
# File: annotator.py
# Description: Exports annotations to COCO and YOLO formats
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class AnnotationExporter:
    """
    Exports annotations to standard computer vision formats.
    
    Supports:
    - COCO JSON (object detection, instance segmentation, keypoints, 6D pose)
    - YOLO TXT (object detection only)
    
    Handles multi-modal annotations:
    - Bounding boxes (detection)
    - Segmentation masks (instance segmentation)
    - 6D poses (rotation + translation for objects)
    """
    
    def __init__(self, class_names: List[str]):
        """
        Initialize annotation exporter.
        
        Args:
            class_names: List of object class names (e.g., ['resistor', 'ic', 'capacitor'])
        """
        self.class_names = class_names
        self.class_to_id = {name: idx for idx, name in enumerate(class_names)}
    
    def export_coco(self, annotations_list: List[Dict[str, Any]], output_path: Path, 
                    image_size: tuple = (1920, 1080)) -> None:
        """
        Export annotations to COCO JSON format.
        
        COCO format structure:
        {
            "images": [...],
            "annotations": [...],
            "categories": [...]
        }
        
        Args:
            annotations_list: List of annotation dicts from generator
            output_path: Path to save COCO JSON file
            image_size: Tuple of (width, height) in pixels
        """
        coco_data = {
            "info": {
                "description": "VantageCV Synthetic Dataset",
                "version": "1.0",
                "year": datetime.now().year,
                "date_created": datetime.now().isoformat()
            },
            "images": [],
            "annotations": [],
            "categories": []
        }
        
        # Create categories
        for idx, class_name in enumerate(self.class_names):
            coco_data["categories"].append({
                "id": idx,
                "name": class_name,
                "supercategory": "object"
            })
        
        annotation_id = 0
        
        # Process each image
        for image_id, ann_data in enumerate(annotations_list):
            # Add image metadata
            image_info = {
                "id": image_id,
                "file_name": ann_data['image_filename'],
                "width": image_size[0],
                "height": image_size[1],
                "date_captured": ann_data.get('timestamp', '')
            }
            coco_data["images"].append(image_info)
            
            # Add object annotations (components)
            components = ann_data.get('components', [])
            for component in components:
                bbox = component['bbox']  # [x, y, width, height]
                class_name = component['class']
                
                if class_name not in self.class_to_id:
                    continue
                
                annotation = {
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": self.class_to_id[class_name],
                    "bbox": bbox,
                    "area": bbox[2] * bbox[3],
                    "iscrowd": 0
                }
                
                # Add segmentation mask if available (polygon or RLE format)
                if 'segmentation' in component:
                    annotation["segmentation"] = component['segmentation']
                
                # Add 6D pose if available (rotation matrix + translation)
                if 'pose' in component:
                    pose = component['pose']
                    annotation["pose"] = {
                        "rotation": pose['rotation'],  # 3x3 matrix as nested list
                        "translation": pose['translation'],  # [x, y, z]
                        "unit": pose.get('unit', 'meters')
                    }
                
                # Add keypoints if available
                if 'keypoints' in component:
                    annotation["keypoints"] = component['keypoints']
                    annotation["num_keypoints"] = len(component['keypoints']) // 3
                
                coco_data["annotations"].append(annotation)
                annotation_id += 1
            
            # Add defect annotations
            defects = ann_data.get('defects', [])
            for defect in defects:
                bbox = defect['bbox']
                
                annotation = {
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": len(self.class_names),  # Defect class
                    "bbox": bbox,
                    "area": bbox[2] * bbox[3],
                    "iscrowd": 0,
                    "defect_type": defect['type'],
                    "severity": defect.get('severity', 0.5)
                }
                
                coco_data["annotations"].append(annotation)
                annotation_id += 1
        
        # Save COCO JSON
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(coco_data, f, indent=2)
        
        logger.info(f"Exported COCO: {len(coco_data['annotations'])} annotations in {len(coco_data['images'])} images")
    
    def export_poses(self, annotations_list: List[Dict[str, Any]], output_path: Path) -> None:
        """
        Export 6D pose annotations to dedicated JSON file.
        
        Format compatible with BOP (Benchmark for 6D Object Pose Estimation) and
        other pose estimation frameworks.
        
        Args:
            annotations_list: List of annotation dicts with pose data
            output_path: Path to save pose JSON file
        """
        pose_data = {
            "info": {
                "description": "VantageCV 6D Pose Annotations",
                "version": "1.0",
                "date_created": datetime.now().isoformat(),
                "unit": "meters",
                "coordinate_system": "camera"
            },
            "images": []
        }
        
        for image_id, ann_data in enumerate(annotations_list):
            image_poses = {
                "image_id": image_id,
                "file_name": ann_data['image_filename'],
                "objects": []
            }
            
            components = ann_data.get('components', [])
            for component in components:
                if 'pose' not in component:
                    continue
                
                pose = component['pose']
                obj_pose = {
                    "class": component['class'],
                    "rotation": pose['rotation'],
                    "translation": pose['translation'],
                    "confidence": pose.get('confidence', 1.0)
                }
                
                image_poses["objects"].append(obj_pose)
            
            if image_poses["objects"]:
                pose_data["images"].append(image_poses)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(pose_data, f, indent=2)
        
        total_poses = sum(len(img["objects"]) for img in pose_data["images"])
        logger.info(f"Exported poses: {total_poses} object poses in {len(pose_data['images'])} images")
    
    def export_yolo(self, annotations_list: List[Dict[str, Any]], output_dir: Path,
                    image_size: tuple = (1920, 1080)) -> None:
        """
        Export annotations to YOLO format.
        
        YOLO format: One .txt file per image
        Each line: class_id center_x center_y width height (normalized 0-1)
        
        Args:
            annotations_list: List of annotation dicts from generator
            output_dir: Directory to save YOLO txt files
            image_size: Tuple of (width, height) in pixels
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        image_width, image_height = image_size
        total_objects = 0
        
        for ann_data in annotations_list:
            image_filename = ann_data['image_filename']
            txt_filename = Path(image_filename).stem + '.txt'
            txt_path = output_dir / txt_filename
            
            yolo_lines = []
            
            # Convert components to YOLO format
            components = ann_data.get('components', [])
            for component in components:
                bbox = component['bbox']  # [x, y, width, height]
                class_name = component['class']
                
                if class_name not in self.class_to_id:
                    continue
                
                # Convert to YOLO format (normalized center x, y, width, height)
                center_x = (bbox[0] + bbox[2] / 2) / image_width
                center_y = (bbox[1] + bbox[3] / 2) / image_height
                norm_width = bbox[2] / image_width
                norm_height = bbox[3] / image_height
                
                class_id = self.class_to_id[class_name]
                yolo_line = f"{class_id} {center_x:.6f} {center_y:.6f} {norm_width:.6f} {norm_height:.6f}"
                yolo_lines.append(yolo_line)
                total_objects += 1
            
            # Convert defects to YOLO format
            defects = ann_data.get('defects', [])
            for defect in defects:
                bbox = defect['bbox']
                
                center_x = (bbox[0] + bbox[2] / 2) / image_width
                center_y = (bbox[1] + bbox[3] / 2) / image_height
                norm_width = bbox[2] / image_width
                norm_height = bbox[3] / image_height
                
                defect_class_id = len(self.class_names)  # Defect is last class
                yolo_line = f"{defect_class_id} {center_x:.6f} {center_y:.6f} {norm_width:.6f} {norm_height:.6f}"
                yolo_lines.append(yolo_line)
                total_objects += 1
            
            # Write YOLO txt file
            with open(txt_path, 'w') as f:
                f.write('\n'.join(yolo_lines))
        
        # Save class names file
        classes_path = output_dir / 'classes.txt'
        with open(classes_path, 'w') as f:
            f.write('\n'.join(self.class_names + ['defect']))
        
        logger.info(f"Exported YOLO: {total_objects} objects in {len(annotations_list)} images")

