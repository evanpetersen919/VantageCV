#==============================================================================
# VantageCV Research - Research Data Generator
#==============================================================================
# Academic-grade synthetic data generation orchestrator
# Designed for publication-quality datasets and ablation studies
#==============================================================================

import time
import json
import random
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import numpy as np

from .scene_sampler import SceneSampler, VehicleDistribution, create_sampler_from_config
from .occlusion import OcclusionAnalyzer, BoundingBox2D
from .scenarios import ScenarioGenerator, EdgeCaseType, SCENARIO_APPLICATORS
from .annotations import (
    FrameAnnotation, InstanceAnnotation, BoundingBox2D as AnnBBox2D,
    ResearchExporter
)
from .metadata import MetadataTracker

logger = logging.getLogger(__name__)


class ResearchDataGenerator:
    """
    Research-grade synthetic data generator.
    
    Designed for academic publication and professional-grade training data
    with support for:
    - Distributional vehicle counts (not fixed)
    - Comprehensive scene randomization
    - Occlusion-aware annotations
    - Edge case scenario generation
    - Multi-format export (COCO, KITTI, YOLO)
    - Full metadata tracking for reproducibility
    
    Architecture:
        UE5 Remote Control API → Scene Sampling → Capture → 
        Occlusion Analysis → Annotation Export → Metadata
    """
    
    # Vehicle classes with IDs
    VEHICLE_CLASSES = ['car', 'truck', 'bus', 'motorcycle', 'bicycle']
    CLASS_TO_ID = {name: i for i, name in enumerate(VEHICLE_CLASSES)}
    
    def __init__(self,
                 config: Dict,
                 output_dir: str,
                 ue5_host: str = "localhost",
                 ue5_port: int = 30010,
                 seed: Optional[int] = None):
        """
        Initialize research data generator.
        
        Args:
            config: Configuration dictionary
            output_dir: Output directory for dataset
            ue5_host: UE5 Remote Control API host
            ue5_port: UE5 Remote Control API port
            seed: Random seed for reproducibility
        """
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set random seed for reproducibility
        self.seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            logger.info(f"Random seed set to {seed}")
        
        # Initialize UE5 bridge
        self.ue5_bridge = None
        try:
            from vantagecv.ue5_bridge import UE5Bridge
            ue5_config = config.get('ue5', {})
            self.ue5_bridge = UE5Bridge(
                host=ue5_host,
                port=ue5_port,
                scene_controller_path=ue5_config.get('scene_controller_path'),
                data_capture_path=ue5_config.get('data_capture_path')
            )
            logger.info(f"Connected to UE5 at {ue5_host}:{ue5_port}")
        except Exception as e:
            logger.error(f"Failed to connect to UE5: {e}")
            raise
        
        # Setup perfect lighting once at start
        try:
            scene_controller = ue5_config.get('scene_controller_path')
            if scene_controller:
                self.ue5_bridge.call_function(scene_controller, 'SetupPerfectLighting')
                logger.info("Perfect lighting configured - bright uniform illumination")
        except Exception as e:
            logger.warning(f"Could not setup lighting: {e}")
        
        # Get image dimensions
        self.image_width = config.get('image_width', 1920)
        self.image_height = config.get('image_height', 1080)
        
        # Initialize components
        self.scene_sampler = create_sampler_from_config(config, seed)
        
        self.occlusion_analyzer = OcclusionAnalyzer(
            image_width=self.image_width,
            image_height=self.image_height,
            min_occlusion_threshold=config.get('occlusion_threshold', 0.3),
            target_occluded_ratio=config.get('target_occlusion_ratio', 0.35)
        )
        
        # Edge case scenarios
        enabled_scenarios = config.get('enabled_scenarios', None)
        if enabled_scenarios:
            enabled_types = [EdgeCaseType(s) for s in enabled_scenarios]
        else:
            enabled_types = None
        self.scenario_generator = ScenarioGenerator(enabled_scenarios=enabled_types)
        
        # Metadata tracker
        self.metadata_tracker = MetadataTracker(str(output_dir), config)
        
        # Annotation storage
        self.annotations: List[FrameAnnotation] = []
        
        # UE5 actor paths from config
        self.domain_rand_path = config.get('ue5', {}).get('domain_randomization_path')
        self.scene_controller_path = config.get('ue5', {}).get('scene_controller_path')
        self.data_capture_path = config.get('ue5', {}).get('data_capture_path')
    
    def generate(self, num_images: int) -> Dict:
        """
        Generate research-grade synthetic dataset.
        
        Args:
            num_images: Number of images to generate
            
        Returns:
            Dict with generation statistics and paths
        """
        logger.info(f"Starting research-grade generation of {num_images} images")
        
        # Setup metadata
        self.metadata_tracker.set_generation_config(
            seed=self.seed,
            num_images=num_images,
            image_size=(self.image_width, self.image_height),
            domain=self.config.get('domain', 'automotive'),
            config_file=self.config.get('config_file', '')
        )
        self.metadata_tracker.start_generation()
        
        # Create output directories
        images_dir = self.output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        # Generation loop
        generated = 0
        rejected = 0
        
        print(f"\n{'='*60}")
        print("VantageCV Research - Synthetic Data Generation")
        print(f"{'='*60}")
        print(f"Target: {num_images} images")
        print(f"Output: {self.output_dir}")
        print(f"Seed: {self.seed if self.seed else 'random'}")
        print(f"{'='*60}\n")
        
        while generated < num_images:
            try:
                # 1. Sample scene parameters
                scene_params = self.scene_sampler.sample_scene()
                
                # 2. Check for edge case scenario
                is_edge_case, edge_case_type = self.scenario_generator.should_generate_edge_case()
                scenario_id = None
                
                if is_edge_case and edge_case_type:
                    scenario_params = self.scenario_generator.generate_scenario(edge_case_type)
                    scenario_id = scenario_params.get('scenario_id')
                    
                    # Apply scenario modifications
                    if edge_case_type in SCENARIO_APPLICATORS:
                        scene_params = SCENARIO_APPLICATORS[edge_case_type](
                            scene_params, scenario_params
                        )
                    
                    logger.debug(f"Generating edge case: {edge_case_type.value}")
                
                # 3. Apply scene randomization to UE5
                vehicle_count = scene_params['vehicle_count']
                self._apply_scene_randomization(scene_params)
                
                # 4. Capture frame
                image_filename = f"frame_{generated:06d}.png"
                image_path = images_dir / image_filename
                
                success = self._capture_frame(str(image_path))
                if not success:
                    rejected += 1
                    logger.warning(f"Frame capture failed, retrying...")
                    continue
                
                # 5. Get annotations from UE5 (mock for now - we'll use Python-side tracking)
                # TODO: Implement GetVisibleAnnotations in DataCapture C++
                instances = self._get_mock_annotations(scene_params['vehicle_count'])
                
                # 6. Compute occlusion metrics
                bboxes = [
                    BoundingBox2D(
                        x=inst['bbox'][0],
                        y=inst['bbox'][1],
                        width=inst['bbox'][2],
                        height=inst['bbox'][3],
                        instance_id=inst['instance_id'],
                        class_name=inst['class_name'],
                        depth=inst.get('depth', 1000.0)
                    )
                    for inst in instances
                ]
                
                occlusion_metrics = self.occlusion_analyzer.analyze_occlusions(bboxes)
                
                # 7. Build frame annotation
                frame_annotation = self._build_frame_annotation(
                    frame_id=generated,
                    image_filename=image_filename,
                    scene_params=scene_params,
                    instances=instances,
                    occlusion_metrics=occlusion_metrics,
                    scenario_id=scenario_id
                )
                
                self.annotations.append(frame_annotation)
                
                # 8. Record metadata
                instance_dicts = [
                    {
                        'class_name': inst.class_name,
                        'occlusion_ratio': inst.occlusion_ratio,
                        'is_occluded': inst.is_occluded,
                        'is_truncated': inst.is_truncated
                    }
                    for inst in frame_annotation.instances
                ]
                
                self.metadata_tracker.record_frame(
                    frame_id=generated,
                    image_filename=image_filename,
                    scene_params=scene_params,
                    instances=instance_dicts,
                    scenario_id=scenario_id
                )
                
                generated += 1
                
                # Progress update
                if generated % 10 == 0 or generated == num_images:
                    elapsed = (datetime.now() - self.metadata_tracker._start_time).total_seconds()
                    rate = generated / elapsed if elapsed > 0 else 0
                    eta = (num_images - generated) / rate if rate > 0 else 0
                    print(f"  Progress: {generated}/{num_images} | "
                          f"Rate: {rate:.1f} img/s | "
                          f"Rejected: {rejected} | "
                          f"ETA: {eta:.0f}s", end='\r')
                
            except Exception as e:
                logger.error(f"Error generating frame: {e}")
                rejected += 1
                if rejected > num_images * 0.5:
                    logger.error("Too many rejections, aborting")
                    break
        
        print()  # New line after progress
        
        # Finalize
        self.metadata_tracker.end_generation()
        
        # Export annotations
        print("\nExporting annotations...")
        export_paths = self._export_annotations()
        
        # Save metadata
        print("Saving metadata...")
        self.metadata_tracker.save()
        self.metadata_tracker.save_per_frame_metadata()
        self.metadata_tracker.print_summary()
        
        return {
            'generated': generated,
            'rejected': rejected,
            'output_dir': str(self.output_dir),
            'annotation_paths': export_paths
        }
    
    def _apply_scene_randomization(self, scene_params: Dict):
        """Apply scene randomization to UE5."""
        dr_config = self.config.get('domain_randomization', {})
        
        # NOTE: Sun angle setting removed - was causing API errors
        # Lighting is controlled by UE5 level setup
        
        # 1. Apply domain randomization
        if self.domain_rand_path:
            try:
                self.ue5_bridge.call_function(
                    self.domain_rand_path,
                    "ApplyRandomization",
                    {}
                )
            except Exception as e:
                logger.warning(f"Domain randomization failed: {e}")
        
        # 2. Randomize lighting based on scene params
        # FIXED: Use proper intensity values (50-100), NOT shadow_intensity (0-1)!
        if self.scene_controller_path:
            try:
                lighting = scene_params.get('lighting', {})
                self.ue5_bridge.call_function(
                    self.scene_controller_path,
                    "RandomizeLighting",
                    {
                        "MinIntensity": 50.0,  # BRIGHT minimum - was shadow_intensity * 0.8 (bug!)
                        "MaxIntensity": 100.0,  # BRIGHT maximum - was shadow_intensity * 1.2 (bug!)
                        "MinTemperature": 4500.0 if lighting.get('time_of_day') == 'noon' else 3500.0,
                        "MaxTemperature": 7500.0 if lighting.get('time_of_day') == 'noon' else 5500.0
                    }
                )
            except Exception as e:
                logger.warning(f"Lighting randomization failed: {e}")
        
        # 3. Adaptive camera zoom based on vehicle count
        if self.data_capture_path:
            try:
                vehicle_count = scene_params.get('vehicle_count', 3)
                camera = scene_params.get('camera', {})
                
                # Adaptive distance: more vehicles = wider shot
                base_distance_range = dr_config.get('camera_distance_range', [2000.0, 6000.0])
                
                if vehicle_count <= 1:
                    min_dist = base_distance_range[0]
                    max_dist = base_distance_range[0] + 1000.0
                elif vehicle_count >= 10:
                    min_dist = base_distance_range[1] - 500.0
                    max_dist = base_distance_range[1]
                else:
                    t = (vehicle_count - 1) / 9.0
                    min_dist = base_distance_range[0] + t * (base_distance_range[1] - base_distance_range[0] - 1500.0)
                    max_dist = min_dist + 1000.0
                
                fov = camera.get('fov', 75.0)
                
                self.ue5_bridge.call_function(
                    self.data_capture_path,
                    "RandomizeCamera",
                    {
                        "MinDistance": min_dist,
                        "MaxDistance": max_dist,
                        "MinFOV": max(60.0, fov - 10.0),
                        "MaxFOV": min(120.0, fov + 10.0)
                    }
                )
            except Exception as e:
                logger.warning(f"Camera randomization failed: {e}")
    
    def _capture_frame(self, output_path: str) -> bool:
        """Capture frame from UE5."""
        try:
            # Use absolute path
            abs_path = str(Path(output_path).resolve())
            
            if self.data_capture_path:
                result = self.ue5_bridge.call_function(
                    self.data_capture_path,
                    "CaptureFrame",
                    {
                        "OutputPath": abs_path,
                        "Width": self.image_width,
                        "Height": self.image_height
                    }
                )
                
                # Check return value
                success = result.get("ReturnValue", False) if result else False
                
                if not success:
                    logger.warning(f"CaptureFrame returned false for {abs_path}")
                    return False
            
            # Wait for file
            import time
            for _ in range(20):  # Increased wait time
                if Path(output_path).exists():
                    logger.debug(f"Frame captured successfully: {output_path}")
                    return True
                time.sleep(0.2)
            
            logger.warning(f"Frame file not found after capture: {output_path}")
            return False
            
        except Exception as e:
            logger.error(f"Capture failed: {e}")
            return False
    
    def _get_mock_annotations(self, vehicle_count: int) -> List[Dict]:
        """
        Generate mock annotations for now.
        
        TODO: Implement GetVisibleAnnotations in DataCapture.cpp to get real data.
        For now, generate reasonable mock data based on vehicle count.
        """
        import random
        instances = []
        
        for i in range(vehicle_count):
            # Random class weighted by distribution
            class_name = random.choices(
                self.VEHICLE_CLASSES,
                weights=[0.45, 0.20, 0.15, 0.12, 0.08],  # car, truck, bus, motorcycle, bicycle
                k=1
            )[0]
            
            # Random bbox (reasonable sizes)
            if class_name == 'bicycle':
                w, h = random.randint(30, 60), random.randint(50, 90)
            elif class_name == 'motorcycle':
                w, h = random.randint(50, 90), random.randint(70, 120)
            elif class_name == 'car':
                w, h = random.randint(100, 200), random.randint(80, 150)
            elif class_name == 'truck':
                w, h = random.randint(120, 250), random.randint(100, 180)
            else:  # bus
                w, h = random.randint(150, 300), random.randint(120, 200)
            
            x = random.randint(0, self.image_width - w)
            y = random.randint(int(self.image_height * 0.3), self.image_height - h)
            
            instances.append({
                'instance_id': i,
                'class_name': class_name,
                'class_id': self.CLASS_TO_ID[class_name],
                'bbox': [x, y, w, h],
                'depth': random.uniform(500.0, 5000.0)
            })
        
        return instances
    
    def _get_instance_annotations(self) -> List[Dict]:
        """Get instance annotations from UE5."""
        instances = []
        
        try:
            if self.data_capture_path:
                result = self.ue5_bridge.call_function(
                    self.data_capture_path,
                    "GetVisibleAnnotations",
                    {}
                )
                
                if result and 'Annotations' in result:
                    for ann in result['Annotations']:
                        instances.append({
                            'instance_id': ann.get('InstanceId', len(instances)),
                            'class_name': ann.get('ClassName', 'car'),
                            'class_id': self.CLASS_TO_ID.get(ann.get('ClassName', 'car'), 0),
                            'bbox': [
                                ann.get('BboxX', 0),
                                ann.get('BboxY', 0),
                                ann.get('BboxWidth', 100),
                                ann.get('BboxHeight', 100)
                            ],
                            'depth': ann.get('Depth', 1000.0)
                        })
        except Exception as e:
            logger.warning(f"Failed to get annotations: {e}")
        
        return instances
    
    def _build_frame_annotation(self,
                                 frame_id: int,
                                 image_filename: str,
                                 scene_params: Dict,
                                 instances: List[Dict],
                                 occlusion_metrics: Dict,
                                 scenario_id: Optional[str]) -> FrameAnnotation:
        """Build complete frame annotation."""
        
        instance_annotations = []
        
        for inst in instances:
            inst_id = inst['instance_id']
            metrics = occlusion_metrics.get(inst_id)
            
            bbox = AnnBBox2D(
                x=inst['bbox'][0],
                y=inst['bbox'][1],
                width=inst['bbox'][2],
                height=inst['bbox'][3]
            )
            
            instance_annotations.append(InstanceAnnotation(
                instance_id=inst_id,
                class_name=inst['class_name'],
                class_id=inst['class_id'],
                bbox_2d=bbox,
                occlusion_ratio=metrics.occlusion_ratio if metrics else 1.0,
                is_occluded=metrics.is_occluded if metrics else False,
                is_truncated=metrics.is_truncated if metrics else False,
                truncation_ratio=metrics.truncation_ratio if metrics else 0.0,
                occlusion_source=metrics.occlusion_source.value if metrics else "none",
                area=bbox.width * bbox.height,
                visible_area=metrics.visible_area if metrics else bbox.width * bbox.height
            ))
        
        frame = FrameAnnotation(
            frame_id=frame_id,
            image_filename=image_filename,
            image_width=self.image_width,
            image_height=self.image_height,
            instances=instance_annotations,
            scene_params=scene_params,
            scenario_id=scenario_id,
            scenario_type=scene_params.get('scenario_type')
        )
        
        frame.compute_statistics()
        
        return frame
    
    def _export_annotations(self) -> Dict[str, str]:
        """Export annotations in multiple formats."""
        
        export_formats = self.config.get('export_formats', ['coco', 'yolo'])
        
        exporter = ResearchExporter(
            output_dir=str(self.output_dir),
            class_names=self.VEHICLE_CLASSES,
            formats=export_formats
        )
        
        return exporter.export_all(self.annotations)
