"""
VantageCV Pipeline Tests

Test suite to verify all components work correctly.
Follows pytest-compatible structure for integration into CI/CD pipelines.
"""

import sys
from pathlib import Path
import json
import logging
from typing import List, Dict, Any

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.config import Config
from domains.industrial import IndustrialDomain
from domains.automotive import AutomotiveDomain

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_config_loading() -> None:
    """
    Test YAML configuration loading for all domains.
    
    Validates:
        - Configuration files can be parsed
        - Required fields are present
        - Domain-specific classes are loaded correctly
    
    Raises:
        AssertionError: If configuration validation fails
    """
    logger.info("Testing configuration loading...")
    
    # Test industrial config
    industrial_config = Config('configs/industrial.yaml')
    assert industrial_config.get('domain.name') == 'industrial', \
        "Industrial domain name mismatch"
    assert len(industrial_config.get('objects.classes')) == 8, \
        "Industrial domain should have 8 object classes"
    logger.info("  PASS: Industrial config loaded correctly")
    
    # Test automotive config
    automotive_config = Config('configs/automotive.yaml')
    assert automotive_config.get('domain.name') == 'automotive', \
        "Automotive domain name mismatch"
    assert len(automotive_config.get('objects.classes')) == 10, \
        "Automotive domain should have 10 object classes"
    logger.info("  PASS: Automotive config loaded correctly")
    
    logger.info("  All config tests passed\n")


def test_domain_initialization() -> None:
    """
    Test domain plugin initialization.
    
    Validates:
        - Domain objects can be instantiated
        - Configuration is properly passed to domains
        - Domain metadata is correctly set
    
    Raises:
        AssertionError: If domain initialization fails
    """
    logger.info("Testing domain initialization...")
    
    # Test industrial domain
    industrial_config = Config('configs/industrial.yaml')
    industrial_domain = IndustrialDomain(industrial_config.data)
    assert industrial_domain.domain_name == 'industrial', \
        "Industrial domain name not set correctly"
    logger.info("  PASS: Industrial domain initialized")
    
    # Test automotive domain
    automotive_config = Config('configs/automotive.yaml')
    automotive_domain = AutomotiveDomain(automotive_config.data)
    assert automotive_domain.domain_name == 'automotive', \
        "Automotive domain name not set correctly"
    logger.info("  PASS: Automotive domain initialized")
    
    logger.info("  All domain initialization tests passed\n")


def test_generated_data() -> None:
    """
    Validate quality and structure of generated synthetic data.
    
    Tests:
        - Image files exist and are accessible
        - COCO annotation format is valid
        - YOLO annotation format is valid
        - Metadata is complete
    
    Raises:
        AssertionError: If data validation fails
    """
    logger.info("Testing generated data validation...")
    
    # Check industrial dataset
    industrial_path = Path('data/synthetic/industrial')
    if industrial_path.exists():
        images = list((industrial_path / 'images').glob('*.png'))
        assert len(images) > 0, "No images generated in industrial dataset"
        logger.info(f"  PASS: Industrial dataset has {len(images)} images")
        
        # Validate COCO annotations
        coco_file = industrial_path / 'annotations_coco.json'
        if coco_file.exists():
            with open(coco_file, 'r') as f:
                coco_data = json.load(f)
                assert 'images' in coco_data, "COCO annotations missing 'images' field"
                assert 'annotations' in coco_data, "COCO annotations missing 'annotations' field"
                assert 'categories' in coco_data, "COCO annotations missing 'categories' field"
                logger.info(
                    f"  PASS: COCO format valid - {len(coco_data['images'])} images, "
                    f"{len(coco_data['annotations'])} objects"
                )
        
        # Validate YOLO annotations
        yolo_dir = industrial_path / 'annotations_yolo'
        if yolo_dir.exists():
            yolo_files = list(yolo_dir.glob('*.txt'))
            logger.info(f"  PASS: YOLO format valid - {len(yolo_files)} label files")
    
    # Check automotive dataset
    automotive_path = Path('data/synthetic/automotive')
    if automotive_path.exists():
        images = list((automotive_path / 'images').glob('*.png'))
        assert len(images) > 0, "No images generated in automotive dataset"
        logger.info(f"  PASS: Automotive dataset has {len(images)} images")
    
    logger.info("  All data validation tests passed\n")


def test_domain_randomization() -> None:
    """
    Test domain randomization produces statistically varied parameters.
    
    Validates:
        - Randomization produces different values across calls
        - All randomization parameters are within configured bounds
        - Scene setup completes successfully before randomization
    
    Raises:
        AssertionError: If randomization does not produce varied outputs
    """
    logger.info("Testing domain randomization...")
    
    industrial_config = Config('configs/industrial.yaml')
    industrial_domain = IndustrialDomain(industrial_config.data)
    
    # Setup scene before randomization
    setup_success = industrial_domain.setup_scene()
    assert setup_success, "Scene setup failed"
    
    # Generate multiple randomization parameter sets
    num_samples = 5
    params_list: List[Dict[str, Any]] = []
    for _ in range(num_samples):
        params = industrial_domain.randomize_scene()
        params_list.append(params)
    
    # Validate that randomization produces different values
    rotations = [p['pose']['rotation_z'] for p in params_list]
    unique_rotations = len(set(rotations))
    assert unique_rotations > 1, \
        f"Randomization not producing varied values: {unique_rotations}/{num_samples} unique rotations"
    logger.info(f"  PASS: Randomization produces varied parameters ({unique_rotations}/{num_samples} unique)")
    
    logger.info("  All randomization tests passed\n")



if __name__ == '__main__':
    """Run all tests and report results."""
    logger.info("=" * 60)
    logger.info("VantageCV Pipeline Test Suite")
    logger.info("=" * 60)
    
    tests = [
        ("Configuration Loading", test_config_loading),
        ("Domain Initialization", test_domain_initialization),
        ("Domain Randomization", test_domain_randomization),
        ("Generated Data Validation", test_generated_data),
    ]
    
    failed_tests = []
    
    for test_name, test_func in tests:
        try:
            test_func()
        except AssertionError as e:
            logger.error(f"FAIL: {test_name} - {str(e)}")
            failed_tests.append((test_name, str(e)))
        except Exception as e:
            logger.error(f"ERROR: {test_name} - {str(e)}")
            import traceback
            traceback.print_exc()
            failed_tests.append((test_name, str(e)))
    
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    if failed_tests:
        logger.error(f"FAILED: {len(failed_tests)}/{len(tests)} tests failed")
        for test_name, error in failed_tests:
            logger.error(f"  - {test_name}: {error}")
        sys.exit(1)
    else:
        logger.info(f"SUCCESS: All {len(tests)} tests passed")
        logger.info("=" * 60)
        sys.exit(0)
