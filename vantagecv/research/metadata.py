#==============================================================================
# VantageCV Research - Metadata Tracking
#==============================================================================
# Comprehensive metadata tracking for research reproducibility
# Supports ablation studies and dataset distribution analysis
#==============================================================================

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Snapshot of generation configuration for reproducibility."""
    seed: Optional[int] = None
    num_images: int = 0
    image_width: int = 1920
    image_height: int = 1080
    domain: str = "automotive"
    config_file: str = ""
    config_hash: str = ""


@dataclass
class DistributionStats:
    """Statistics for dataset distribution analysis."""
    # Vehicle count distribution
    vehicle_count_histogram: Dict[str, int] = field(default_factory=dict)
    vehicle_count_by_bucket: Dict[str, int] = field(default_factory=dict)
    
    # Class distribution
    class_counts: Dict[str, int] = field(default_factory=dict)
    class_percentages: Dict[str, float] = field(default_factory=dict)
    
    # Scene parameter distributions
    environment_counts: Dict[str, int] = field(default_factory=dict)
    time_of_day_counts: Dict[str, int] = field(default_factory=dict)
    weather_counts: Dict[str, int] = field(default_factory=dict)
    
    # Occlusion statistics
    occlusion_ratio_mean: float = 0.0
    occlusion_ratio_std: float = 0.0
    occluded_instance_ratio: float = 0.0
    truncated_instance_ratio: float = 0.0
    
    # Scenario statistics
    scenario_counts: Dict[str, int] = field(default_factory=dict)
    edge_case_ratio: float = 0.0


@dataclass
class DatasetMetadata:
    """
    Complete dataset metadata for research documentation.
    
    Includes all information needed for:
    - Reproducibility
    - Distribution analysis
    - Ablation study design
    - Publication documentation
    """
    # Dataset identification
    dataset_name: str = "VantageCV Synthetic Dataset"
    dataset_version: str = "1.0"
    creation_date: str = ""
    
    # Generation parameters
    generation_config: GenerationConfig = field(default_factory=GenerationConfig)
    
    # Statistics
    total_images: int = 0
    total_instances: int = 0
    distribution_stats: DistributionStats = field(default_factory=DistributionStats)
    
    # Timing
    generation_duration_seconds: float = 0.0
    images_per_second: float = 0.0
    
    # File paths
    output_directory: str = ""
    annotation_files: Dict[str, str] = field(default_factory=dict)
    
    # Research metadata
    research_notes: str = ""
    ablation_tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export."""
        return asdict(self)


class MetadataTracker:
    """
    Research-grade metadata tracking system.
    
    Tracks all aspects of dataset generation for:
    - Full reproducibility
    - Distribution monitoring
    - Quality assurance
    - Research documentation
    """
    
    def __init__(self, output_dir: str, config: Dict = None):
        """
        Initialize metadata tracker.
        
        Args:
            output_dir: Output directory for metadata files
            config: Generation configuration dictionary
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = config or {}
        self.metadata = DatasetMetadata()
        self.metadata.creation_date = datetime.now().isoformat()
        self.metadata.output_directory = str(output_dir)
        
        # Per-frame tracking
        self.frame_metadata: List[Dict] = []
        
        # Running statistics
        self._vehicle_counts: List[int] = []
        self._class_counts: Dict[str, int] = defaultdict(int)
        self._environment_counts: Dict[str, int] = defaultdict(int)
        self._time_counts: Dict[str, int] = defaultdict(int)
        self._weather_counts: Dict[str, int] = defaultdict(int)
        self._scenario_counts: Dict[str, int] = defaultdict(int)
        self._occlusion_ratios: List[float] = []
        self._occluded_count: int = 0
        self._truncated_count: int = 0
        self._total_instances: int = 0
        
        # Timing
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
    
    def set_generation_config(self, 
                               seed: Optional[int] = None,
                               num_images: int = 0,
                               image_size: tuple = (1920, 1080),
                               domain: str = "automotive",
                               config_file: str = ""):
        """Set generation configuration."""
        self.metadata.generation_config = GenerationConfig(
            seed=seed,
            num_images=num_images,
            image_width=image_size[0],
            image_height=image_size[1],
            domain=domain,
            config_file=config_file
        )
    
    def start_generation(self):
        """Mark start of generation."""
        self._start_time = datetime.now()
        logger.info(f"Generation started at {self._start_time.isoformat()}")
    
    def end_generation(self):
        """Mark end of generation."""
        self._end_time = datetime.now()
        if self._start_time:
            duration = (self._end_time - self._start_time).total_seconds()
            self.metadata.generation_duration_seconds = duration
            self.metadata.images_per_second = (
                self.metadata.total_images / duration if duration > 0 else 0
            )
        logger.info(f"Generation completed at {self._end_time.isoformat()}")
    
    def record_frame(self, 
                     frame_id: int,
                     image_filename: str,
                     scene_params: Dict,
                     instances: List[Dict],
                     scenario_id: Optional[str] = None):
        """
        Record metadata for a single frame.
        
        Args:
            frame_id: Unique frame identifier
            image_filename: Image filename
            scene_params: Scene parameters used
            instances: List of instance annotations
            scenario_id: Edge case scenario ID if applicable
        """
        # Update frame count
        self.metadata.total_images += 1
        
        # Track vehicle count
        vehicle_count = len(instances)
        self._vehicle_counts.append(vehicle_count)
        
        # Track per-instance statistics
        for inst in instances:
            self._total_instances += 1
            
            # Class counts
            class_name = inst.get('class_name', 'unknown')
            self._class_counts[class_name] += 1
            
            # Occlusion tracking
            occlusion_ratio = inst.get('occlusion_ratio', 1.0)
            self._occlusion_ratios.append(occlusion_ratio)
            
            if inst.get('is_occluded', False):
                self._occluded_count += 1
            if inst.get('is_truncated', False):
                self._truncated_count += 1
        
        # Track scene parameters
        environment = scene_params.get('environment', 'unknown')
        self._environment_counts[environment] += 1
        
        time_of_day = scene_params.get('time_of_day', 'unknown')
        self._time_counts[time_of_day] += 1
        
        weather = scene_params.get('weather', {}).get('condition', 'unknown')
        self._weather_counts[weather] += 1
        
        # Track scenario
        if scenario_id:
            self._scenario_counts[scenario_id] += 1
        
        # Store frame metadata
        self.frame_metadata.append({
            'frame_id': frame_id,
            'image_filename': image_filename,
            'vehicle_count': vehicle_count,
            'scene_params': scene_params,
            'scenario_id': scenario_id,
            'instance_count': len(instances)
        })
    
    def compute_statistics(self):
        """Compute final statistics from recorded data."""
        import numpy as np
        
        stats = self.metadata.distribution_stats
        
        # Vehicle count distribution
        if self._vehicle_counts:
            for count in self._vehicle_counts:
                key = str(count)
                stats.vehicle_count_histogram[key] = (
                    stats.vehicle_count_histogram.get(key, 0) + 1
                )
            
            # Bucket counts
            for count in self._vehicle_counts:
                if count == 1:
                    bucket = "single"
                elif 2 <= count <= 4:
                    bucket = "medium"
                elif 5 <= count <= 10:
                    bucket = "high"
                else:
                    bucket = "very_high"
                stats.vehicle_count_by_bucket[bucket] = (
                    stats.vehicle_count_by_bucket.get(bucket, 0) + 1
                )
        
        # Class distribution
        total_instances = sum(self._class_counts.values())
        stats.class_counts = dict(self._class_counts)
        if total_instances > 0:
            stats.class_percentages = {
                k: v / total_instances 
                for k, v in self._class_counts.items()
            }
        
        # Scene parameter distributions
        stats.environment_counts = dict(self._environment_counts)
        stats.time_of_day_counts = dict(self._time_counts)
        stats.weather_counts = dict(self._weather_counts)
        
        # Occlusion statistics
        if self._occlusion_ratios:
            stats.occlusion_ratio_mean = float(np.mean(self._occlusion_ratios))
            stats.occlusion_ratio_std = float(np.std(self._occlusion_ratios))
        
        if self._total_instances > 0:
            stats.occluded_instance_ratio = self._occluded_count / self._total_instances
            stats.truncated_instance_ratio = self._truncated_count / self._total_instances
        
        # Scenario statistics
        stats.scenario_counts = dict(self._scenario_counts)
        if self.metadata.total_images > 0:
            edge_case_count = sum(self._scenario_counts.values())
            stats.edge_case_ratio = edge_case_count / self.metadata.total_images
        
        self.metadata.total_instances = self._total_instances
    
    def save(self, filename: str = "metadata.json") -> str:
        """
        Save metadata to JSON file.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        self.compute_statistics()
        
        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(self.metadata.to_dict(), f, indent=2)
        
        logger.info(f"Saved metadata to {output_path}")
        return str(output_path)
    
    def save_per_frame_metadata(self, filename: str = "frames_metadata.json") -> str:
        """
        Save per-frame metadata for detailed analysis.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(self.frame_metadata, f, indent=2)
        
        logger.info(f"Saved per-frame metadata to {output_path}")
        return str(output_path)
    
    def print_summary(self):
        """Print generation summary to console."""
        self.compute_statistics()
        stats = self.metadata.distribution_stats
        
        print("\n" + "=" * 60)
        print("DATASET GENERATION SUMMARY")
        print("=" * 60)
        print(f"Total images: {self.metadata.total_images}")
        print(f"Total instances: {self.metadata.total_instances}")
        print(f"Generation time: {self.metadata.generation_duration_seconds:.1f}s")
        print(f"Rate: {self.metadata.images_per_second:.2f} img/s")
        
        print("\n--- Vehicle Count Distribution ---")
        for bucket, count in stats.vehicle_count_by_bucket.items():
            pct = count / max(1, self.metadata.total_images) * 100
            print(f"  {bucket}: {count} ({pct:.1f}%)")
        
        print("\n--- Class Distribution ---")
        for class_name, count in sorted(stats.class_counts.items(), 
                                        key=lambda x: -x[1]):
            pct = stats.class_percentages.get(class_name, 0) * 100
            print(f"  {class_name}: {count} ({pct:.1f}%)")
        
        print("\n--- Occlusion Statistics ---")
        print(f"  Mean visibility: {stats.occlusion_ratio_mean:.2f}")
        print(f"  Occluded instances: {stats.occluded_instance_ratio * 100:.1f}%")
        print(f"  Truncated instances: {stats.truncated_instance_ratio * 100:.1f}%")
        
        if stats.scenario_counts:
            print("\n--- Edge Case Scenarios ---")
            for scenario_id, count in stats.scenario_counts.items():
                pct = count / max(1, self.metadata.total_images) * 100
                print(f"  {scenario_id}: {count} ({pct:.1f}%)")
        
        print("=" * 60 + "\n")
    
    def add_research_notes(self, notes: str):
        """Add research notes to metadata."""
        self.metadata.research_notes = notes
    
    def add_ablation_tags(self, tags: List[str]):
        """Add ablation study tags."""
        self.metadata.ablation_tags.extend(tags)
