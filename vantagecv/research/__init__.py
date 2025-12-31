#==============================================================================
# VantageCV Research - Academic-Grade Synthetic Data Generation
#==============================================================================
# Research-grade synthetic data generation for vehicle perception
# Designed for: academic publication, sim-to-real transfer, long-tail robustness
#==============================================================================

from .generator import ResearchDataGenerator
from .scene_sampler import SceneSampler, VehicleDistribution
from .occlusion import OcclusionAnalyzer
from .scenarios import ScenarioGenerator, EdgeCaseType
from .annotations import AnnotationExporter, COCOExporter, KITTIExporter
from .metadata import MetadataTracker

__all__ = [
    'ResearchDataGenerator',
    'SceneSampler',
    'VehicleDistribution', 
    'OcclusionAnalyzer',
    'ScenarioGenerator',
    'EdgeCaseType',
    'AnnotationExporter',
    'COCOExporter',
    'KITTIExporter',
    'MetadataTracker'
]
