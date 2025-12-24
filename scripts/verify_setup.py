#!/usr/bin/env python
"""
VantageCV Setup Verification

Comprehensive environment and dependency verification tool.
Validates that all prerequisites are correctly installed and configured
before running the VantageCV synthetic data generation pipeline.

Usage:
    python scripts/verify_setup.py

Exit Codes:
    0 - All checks passed
    1 - One or more checks failed
"""

import sys
import logging
from pathlib import Path
from typing import Tuple, List, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def check_python_version() -> bool:
    """
    Verify Python version meets minimum requirements.
    
    Returns:
        bool: True if Python >= 3.9, False otherwise
    """
    logger.info("Checking Python version...")
    version = sys.version_info
    
    if version.major == 3 and version.minor >= 9:
        logger.info(f"  PASS: Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        logger.error(
            f"  FAIL: Python {version.major}.{version.minor} detected "
            f"(requires Python >= 3.9)"
        )
        return False


def check_dependencies() -> bool:
    """
    Verify required Python packages are installed.
    
    Returns:
        bool: True if all required packages are available, False if any are missing
    """
    logger.info("\nChecking dependencies...")
    
    required_packages = [
        ('torch', 'torch'),
        ('torchvision', 'torchvision'), 
        ('numpy', 'numpy'),
        ('cv2', 'opencv-python'),
        ('PIL', 'Pillow'),
        ('yaml', 'PyYAML'),
        ('onnx', 'onnx'),
    ]
    
    optional_packages = [
        ('albumentations', 'albumentations'),
        ('onnxruntime', 'onnxruntime-gpu'),
    ]
    
    missing_packages = []
    
    # Check required packages
    for import_name, package_name in required_packages:
        try:
            if import_name == 'cv2':
                import cv2
            elif import_name == 'PIL':
                from PIL import Image
            elif import_name == 'yaml':
                import yaml
            else:
                __import__(import_name)
            logger.info(f"  PASS: {package_name}")
        except ImportError:
            logger.error(f"  FAIL: {package_name} (not installed)")
            missing_packages.append(package_name)
        except Exception as e:
            logger.warning(f"  WARN: {package_name} (import error: {str(e)[:60]})")
    
    # Check optional packages (non-blocking)
    for import_name, package_name in optional_packages:
        try:
            __import__(import_name)
            logger.info(f"  PASS: {package_name} (optional)")
        except Exception:
            logger.warning(f"  WARN: {package_name} (optional - may have compatibility issues)")
    
    if missing_packages:
        logger.error(f"\nInstall missing packages:")
        logger.error(f"  pip install {' '.join(missing_packages)}")
        return False
    
    return True


def check_project_structure() -> bool:
    """
    Verify all required project directories exist.
    
    Returns:
        bool: True if all required directories exist, False otherwise
    """
    logger.info("\nChecking project structure...")
    
    required_dirs = [
        'vantagecv',
        'domains',
        'configs',
        'scripts',
        'ue5_plugin',
        'cpp',
        'notebooks'
    ]
    
    all_exist = True
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists() and dir_path.is_dir():
            logger.info(f"  PASS: {dir_name}/")
        else:
            logger.error(f"  FAIL: {dir_name}/ (missing or not a directory)")
            all_exist = False
    
    return all_exist


def check_configs() -> bool:
    """
    Verify all required configuration files exist and are readable.
    
    Returns:
        bool: True if all configuration files exist, False otherwise
    """
    logger.info("\nChecking configuration files...")
    
    required_configs = [
        'configs/industrial.yaml',
        'configs/automotive.yaml'
    ]
    
    all_exist = True
    for config_path in required_configs:
        path = Path(config_path)
        if path.exists() and path.is_file():
            logger.info(f"  PASS: {config_path}")
        else:
            logger.error(f"  FAIL: {config_path} (missing or not a file)")
            all_exist = False
    
    return all_exist


def check_gpu() -> bool:
    """
    Check for CUDA GPU availability and report specifications.
    
    Returns:
        bool: Always returns True (GPU is optional, not required)
    """
    logger.info("\nChecking GPU availability...")
    
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info(f"  PASS: {gpu_name}")
            logger.info(f"  PASS: {gpu_memory:.1f} GB VRAM")
        else:
            logger.warning("  WARN: No CUDA GPU detected (will use CPU mode)")
    except Exception as e:
        logger.warning(f"  WARN: Could not check GPU availability: {str(e)}")
    
    return True  # GPU is optional, not a hard requirement


def run_quick_test() -> bool:
    """
    Run quick functionality test of core components.
    
    Tests basic functionality:
        - Configuration loading
        - Domain initialization
        - Scene setup
        - Randomization
    
    Returns:
        bool: True if all functionality tests pass, False otherwise
    """
    logger.info("\nRunning quick functionality test...")
    
    try:
        sys.path.insert(0, '.')
        from vantagecv.config import Config
        from domains.industrial import IndustrialDomain
        
        # Test config loading
        config = Config('configs/industrial.yaml')
        logger.info("  PASS: Config loading works")
        
        # Test domain initialization
        domain = IndustrialDomain(config.data)
        logger.info("  PASS: Domain initialization works")
        
        # Test scene setup
        setup_result = domain.setup_scene()
        if not setup_result:
            raise RuntimeError("Scene setup returned False")
        logger.info("  PASS: Scene setup works")
        
        # Test randomization
        params = domain.randomize_scene()
        if not isinstance(params, dict) or not params:
            raise RuntimeError("Randomization did not return valid parameters")
        logger.info("  PASS: Randomization works")
        
        return True
        
    except Exception as e:
        logger.error(f"  FAIL: Functionality test failed - {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main() -> int:
    """
    Main entry point for setup verification.
    
    Runs all verification checks and reports results.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    logger.info("=" * 60)
    logger.info("VantageCV Setup Verification")
    logger.info("=" * 60)
    
    checks: List[Tuple[str, Callable[[], bool]]] = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Project Structure", check_project_structure),
        ("Configuration Files", check_configs),
        ("GPU", check_gpu),
        ("Functionality", run_quick_test)
    ]
    
    results: List[Tuple[str, bool]] = []
    for check_name, check_func in checks:
        result = check_func()
        results.append((check_name, result))
    
    logger.info("\n" + "=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    
    all_passed = True
    for check_name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info(f"{status:10} {check_name}")
        if not result:
            all_passed = False
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("\nAll checks passed. VantageCV is ready to use.")
        logger.info("\nQuick start:")
        logger.info("  python scripts/generate.py --config configs/industrial.yaml --num-images 100")
        return 0
    else:
        logger.error("\nSome checks failed. Please fix the issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
