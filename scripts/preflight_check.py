#!/usr/bin/env python3
"""
VantageCV - Pre-Flight Check Script

File: preflight_check.py
Description: Comprehensive validation before dataset generation. Tests all
             components to ensure successful bulk generation without wasted time.
Author: Evan Petersen
Date: December 2025

Usage:
    python scripts/preflight_check.py --config configs/automotive.yaml
    python scripts/preflight_check.py --config configs/industrial.yaml --quick
"""

import sys
import json
import time
import hashlib
import argparse
import requests
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.config import Config


class TestStatus(Enum):
    PASS = "✓"
    FAIL = "✗"
    WARN = "⚠"
    SKIP = "○"


@dataclass
class TestResult:
    name: str
    status: TestStatus
    message: str
    details: Optional[str] = None


@dataclass
class PreflightReport:
    config_path: str
    domain: str
    tests: List[TestResult] = field(default_factory=list)
    
    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.PASS)
    
    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.FAIL)
    
    @property
    def warnings(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.WARN)
    
    @property
    def success(self) -> bool:
        return self.failed == 0


class PreflightChecker:
    """
    Comprehensive pre-flight validation for VantageCV pipeline.
    
    Tests:
    1. Configuration validity
    2. UE5 connection
    3. Actor paths (DataCapture, SceneController, DomainRandomization)
    4. Camera capture functionality
    5. Image uniqueness (not static)
    6. Randomization (lighting, materials, camera)
    7. File system permissions
    8. Annotation generation
    """
    
    def __init__(self, config_path: str, quick_mode: bool = False):
        self.config_path = config_path
        self.quick_mode = quick_mode
        self.config: Optional[Config] = None
        self.ue5_config: Dict[str, Any] = {}
        self.base_url: str = ""
        self.report = PreflightReport(config_path=config_path, domain="unknown")
        self.temp_dir = Path("data/preflight_test")
        
    def run_all_tests(self) -> PreflightReport:
        """Run all pre-flight tests and return report."""
        print("\n" + "="*70)
        print("VantageCV Pre-Flight Check")
        print("="*70)
        print(f"Config: {self.config_path}")
        print(f"Mode: {'Quick' if self.quick_mode else 'Full'}")
        print("="*70 + "\n")
        
        # Test sequence (order matters - later tests depend on earlier ones)
        self._test_config_loading()
        self._test_ue5_connection()
        self._test_actor_paths()
        self._test_camera_capture()
        
        if not self.quick_mode:
            self._test_image_uniqueness()
            self._test_randomization()
            self._test_annotations()
        
        self._test_filesystem()
        self._cleanup()
        
        self._print_report()
        return self.report
    
    def _add_result(self, name: str, status: TestStatus, message: str, 
                    details: Optional[str] = None):
        """Add a test result to the report."""
        result = TestResult(name=name, status=status, message=message, details=details)
        self.report.tests.append(result)
        
        # Print immediately
        status_char = status.value
        color = {
            TestStatus.PASS: "\033[92m",  # Green
            TestStatus.FAIL: "\033[91m",  # Red
            TestStatus.WARN: "\033[93m",  # Yellow
            TestStatus.SKIP: "\033[90m",  # Gray
        }.get(status, "")
        reset = "\033[0m"
        
        print(f"  {color}{status_char}{reset} {name}: {message}")
        if details and status == TestStatus.FAIL:
            for line in details.split('\n'):
                print(f"      {line}")
    
    # =========================================================================
    # Test 1: Configuration Loading
    # =========================================================================
    def _test_config_loading(self):
        """Test that configuration file loads correctly."""
        print("\n[1/8] Configuration")
        print("-" * 40)
        
        try:
            self.config = Config(self.config_path)
            self.report.domain = self.config.get('domain.name', 'unknown')
            self._add_result(
                "Config file loads",
                TestStatus.PASS,
                f"Loaded {self.config_path}"
            )
        except FileNotFoundError:
            self._add_result(
                "Config file loads",
                TestStatus.FAIL,
                f"File not found: {self.config_path}"
            )
            return
        except Exception as e:
            self._add_result(
                "Config file loads",
                TestStatus.FAIL,
                f"Parse error: {e}"
            )
            return
        
        # Check required UE5 config
        self.ue5_config = self.config.get('ue5', {})
        
        required_keys = ['remote_control_port', 'data_capture_path']
        missing = [k for k in required_keys if k not in self.ue5_config]
        
        if missing:
            self._add_result(
                "UE5 config complete",
                TestStatus.FAIL,
                f"Missing keys: {missing}"
            )
        else:
            self._add_result(
                "UE5 config complete",
                TestStatus.PASS,
                f"Port: {self.ue5_config['remote_control_port']}"
            )
        
        # Check object classes
        classes = self.config.get('objects.classes', [])
        if classes:
            self._add_result(
                "Object classes defined",
                TestStatus.PASS,
                f"{len(classes)} classes: {', '.join(classes[:5])}{'...' if len(classes) > 5 else ''}"
            )
        else:
            self._add_result(
                "Object classes defined",
                TestStatus.WARN,
                "No object classes defined"
            )
    
    # =========================================================================
    # Test 2: UE5 Connection
    # =========================================================================
    def _test_ue5_connection(self):
        """Test connection to UE5 Remote Control API."""
        print("\n[2/8] UE5 Connection")
        print("-" * 40)
        
        if not self.ue5_config:
            self._add_result(
                "Remote Control API",
                TestStatus.SKIP,
                "No UE5 config"
            )
            return
        
        port = self.ue5_config.get('remote_control_port', 30010)
        self.base_url = f"http://localhost:{port}"
        
        try:
            response = requests.get(f"{self.base_url}/remote/info", timeout=5)
            if response.status_code == 200:
                self._add_result(
                    "Remote Control API",
                    TestStatus.PASS,
                    f"Connected on port {port}"
                )
            else:
                self._add_result(
                    "Remote Control API",
                    TestStatus.FAIL,
                    f"Status {response.status_code}"
                )
        except requests.exceptions.ConnectionError:
            self._add_result(
                "Remote Control API",
                TestStatus.FAIL,
                "Connection refused - is UE5 running?",
                details="Start UE5 Editor with your level loaded and Remote Control enabled"
            )
        except Exception as e:
            self._add_result(
                "Remote Control API",
                TestStatus.FAIL,
                str(e)
            )
    
    # =========================================================================
    # Test 3: Actor Paths
    # =========================================================================
    def _test_actor_paths(self):
        """Test that all required actors exist in the level."""
        print("\n[3/8] Actor Paths")
        print("-" * 40)
        
        if not self.base_url:
            self._add_result("Actor validation", TestStatus.SKIP, "No UE5 connection")
            return
        
        actors_to_check = [
            ('data_capture_path', 'DataCapture'),
            ('scene_controller_path', 'SceneController'),
            ('domain_randomization_path', 'DomainRandomization'),
        ]
        
        for config_key, actor_name in actors_to_check:
            actor_path = self.ue5_config.get(config_key)
            
            if not actor_path:
                self._add_result(
                    f"{actor_name} path",
                    TestStatus.WARN,
                    f"Not configured in ue5.{config_key}"
                )
                continue
            
            # Try to describe the actor
            try:
                response = requests.put(
                    f"{self.base_url}/remote/object/describe",
                    json={"objectPath": actor_path},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    class_name = data.get('Class', 'Unknown')
                    self._add_result(
                        f"{actor_name} exists",
                        TestStatus.PASS,
                        f"Found: {class_name.split('.')[-1]}"
                    )
                else:
                    # Extract level name from path for helpful message
                    level_hint = actor_path.split('.')[0] if '.' in actor_path else "unknown"
                    self._add_result(
                        f"{actor_name} exists",
                        TestStatus.FAIL,
                        f"Not found at configured path",
                        details=f"Path: {actor_path}\nIs the correct level loaded? (Expected: {level_hint})"
                    )
            except Exception as e:
                self._add_result(
                    f"{actor_name} exists",
                    TestStatus.FAIL,
                    str(e)
                )
    
    # =========================================================================
    # Test 4: Camera Capture
    # =========================================================================
    def _test_camera_capture(self):
        """Test that camera can capture an image."""
        print("\n[4/8] Camera Capture")
        print("-" * 40)
        
        data_capture_path = self.ue5_config.get('data_capture_path')
        if not data_capture_path or not self.base_url:
            self._add_result("Camera capture", TestStatus.SKIP, "No DataCapture actor")
            return
        
        # Create temp directory
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        test_image = self.temp_dir / "preflight_test_001.png"
        
        resolution = self.ue5_config.get('default_resolution', [1920, 1080])
        
        try:
            start_time = time.time()
            response = requests.put(
                f"{self.base_url}/remote/object/call",
                json={
                    "objectPath": data_capture_path,
                    "functionName": "CaptureFrame",
                    "parameters": {
                        "OutputPath": str(test_image.resolve()),
                        "Width": resolution[0],
                        "Height": resolution[1]
                    }
                },
                timeout=30
            )
            capture_time = time.time() - start_time
            
            if response.status_code != 200:
                self._add_result(
                    "CaptureFrame call",
                    TestStatus.FAIL,
                    f"HTTP {response.status_code}: {response.text[:100]}"
                )
                return
            
            result = response.json()
            success = result.get('ReturnValue', False)
            
            if not success:
                self._add_result(
                    "CaptureFrame call",
                    TestStatus.FAIL,
                    "Function returned false"
                )
                return
            
            self._add_result(
                "CaptureFrame call",
                TestStatus.PASS,
                f"Completed in {capture_time:.2f}s"
            )
            
            # Wait for file to be written
            time.sleep(0.5)
            
            # Check if file exists and has content
            if test_image.exists():
                size_kb = test_image.stat().st_size / 1024
                if size_kb > 10:  # At least 10KB (not empty)
                    self._add_result(
                        "Image file created",
                        TestStatus.PASS,
                        f"{size_kb:.1f} KB at {resolution[0]}x{resolution[1]}"
                    )
                else:
                    self._add_result(
                        "Image file created",
                        TestStatus.FAIL,
                        f"File too small ({size_kb:.1f} KB) - likely empty"
                    )
            else:
                self._add_result(
                    "Image file created",
                    TestStatus.FAIL,
                    f"File not found: {test_image}",
                    details="Check UE5 Output Log for errors"
                )
                
        except Exception as e:
            self._add_result(
                "Camera capture",
                TestStatus.FAIL,
                str(e)
            )
    
    # =========================================================================
    # Test 5: Image Uniqueness (detect static/noise)
    # =========================================================================
    def _test_image_uniqueness(self):
        """Test that captured images are unique (not static noise)."""
        print("\n[5/8] Image Uniqueness")
        print("-" * 40)
        
        data_capture_path = self.ue5_config.get('data_capture_path')
        if not data_capture_path or not self.base_url:
            self._add_result("Image uniqueness", TestStatus.SKIP, "No capture capability")
            return
        
        resolution = self.ue5_config.get('default_resolution', [1920, 1080])
        test_images = []
        hashes = []
        
        # Capture 3 images
        for i in range(3):
            test_image = self.temp_dir / f"preflight_unique_{i:03d}.png"
            test_images.append(test_image)
            
            try:
                response = requests.put(
                    f"{self.base_url}/remote/object/call",
                    json={
                        "objectPath": data_capture_path,
                        "functionName": "CaptureFrame",
                        "parameters": {
                            "OutputPath": str(test_image.resolve()),
                            "Width": resolution[0],
                            "Height": resolution[1]
                        }
                    },
                    timeout=30
                )
                time.sleep(0.3)  # Small delay between captures
                
            except Exception as e:
                self._add_result(
                    "Multi-capture test",
                    TestStatus.FAIL,
                    f"Capture {i+1} failed: {e}"
                )
                return
        
        # Calculate hashes
        time.sleep(0.5)  # Ensure files are written
        for img_path in test_images:
            if img_path.exists():
                with open(img_path, 'rb') as f:
                    hashes.append(hashlib.md5(f.read()).hexdigest())
            else:
                hashes.append(None)
        
        valid_hashes = [h for h in hashes if h is not None]
        
        if len(valid_hashes) < 2:
            self._add_result(
                "Image files valid",
                TestStatus.FAIL,
                f"Only {len(valid_hashes)}/3 images captured"
            )
            return
        
        # Check if all hashes are the same (static image problem)
        unique_hashes = set(valid_hashes)
        
        if len(unique_hashes) == 1:
            self._add_result(
                "Images are unique",
                TestStatus.WARN,
                "All 3 images are identical - camera may be static",
                details="This is OK if scene hasn't changed. Randomization test will verify."
            )
        else:
            self._add_result(
                "Images are unique",
                TestStatus.PASS,
                f"{len(unique_hashes)} unique images from 3 captures"
            )
    
    # =========================================================================
    # Test 6: Randomization
    # =========================================================================
    def _test_randomization(self):
        """Test that scene randomization works."""
        print("\n[6/8] Randomization")
        print("-" * 40)
        
        scene_controller_path = self.ue5_config.get('scene_controller_path')
        domain_rand_path = self.ue5_config.get('domain_randomization_path')
        data_capture_path = self.ue5_config.get('data_capture_path')
        
        # Test lighting randomization
        if scene_controller_path:
            try:
                response = requests.put(
                    f"{self.base_url}/remote/object/call",
                    json={
                        "objectPath": scene_controller_path,
                        "functionName": "RandomizeLighting",
                        "parameters": {
                            "MinIntensity": 3.0,
                            "MaxIntensity": 10.0,
                            "MinTemperature": 4000.0,
                            "MaxTemperature": 7000.0
                        }
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    self._add_result(
                        "Lighting randomization",
                        TestStatus.PASS,
                        "SceneController.RandomizeLighting works"
                    )
                else:
                    self._add_result(
                        "Lighting randomization",
                        TestStatus.WARN,
                        f"HTTP {response.status_code}"
                    )
            except Exception as e:
                self._add_result(
                    "Lighting randomization",
                    TestStatus.WARN,
                    str(e)
                )
        else:
            self._add_result(
                "Lighting randomization",
                TestStatus.SKIP,
                "No SceneController configured"
            )
        
        # Test domain randomization
        if domain_rand_path:
            try:
                response = requests.put(
                    f"{self.base_url}/remote/object/call",
                    json={
                        "objectPath": domain_rand_path,
                        "functionName": "ApplyRandomization",
                        "parameters": {}
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    self._add_result(
                        "Domain randomization",
                        TestStatus.PASS,
                        "DomainRandomization.ApplyRandomization works"
                    )
                else:
                    self._add_result(
                        "Domain randomization",
                        TestStatus.WARN,
                        f"HTTP {response.status_code}"
                    )
            except Exception as e:
                self._add_result(
                    "Domain randomization",
                    TestStatus.WARN,
                    str(e)
                )
        else:
            self._add_result(
                "Domain randomization",
                TestStatus.SKIP,
                "No DomainRandomization configured"
            )
        
        # Test camera randomization
        if data_capture_path:
            try:
                response = requests.put(
                    f"{self.base_url}/remote/object/call",
                    json={
                        "objectPath": data_capture_path,
                        "functionName": "RandomizeCamera",
                        "parameters": {
                            "MinDistance": 300.0,
                            "MaxDistance": 800.0,
                            "MinFOV": 60.0,
                            "MaxFOV": 90.0
                        }
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    self._add_result(
                        "Camera randomization",
                        TestStatus.PASS,
                        "DataCapture.RandomizeCamera works"
                    )
                else:
                    self._add_result(
                        "Camera randomization",
                        TestStatus.WARN,
                        f"HTTP {response.status_code}"
                    )
            except Exception as e:
                self._add_result(
                    "Camera randomization",
                    TestStatus.WARN,
                    str(e)
                )
        
        # Capture images after randomization to verify visual difference
        if data_capture_path and domain_rand_path:
            hashes = []
            resolution = self.ue5_config.get('default_resolution', [1920, 1080])
            
            for i in range(2):
                # Apply randomization
                requests.put(
                    f"{self.base_url}/remote/object/call",
                    json={
                        "objectPath": domain_rand_path,
                        "functionName": "ApplyRandomization",
                        "parameters": {}
                    },
                    timeout=10
                )
                
                # Capture
                test_image = self.temp_dir / f"preflight_rand_{i:03d}.png"
                requests.put(
                    f"{self.base_url}/remote/object/call",
                    json={
                        "objectPath": data_capture_path,
                        "functionName": "CaptureFrame",
                        "parameters": {
                            "OutputPath": str(test_image.resolve()),
                            "Width": resolution[0],
                            "Height": resolution[1]
                        }
                    },
                    timeout=30
                )
                time.sleep(0.5)
                
                if test_image.exists():
                    with open(test_image, 'rb') as f:
                        hashes.append(hashlib.md5(f.read()).hexdigest())
            
            if len(hashes) == 2 and hashes[0] != hashes[1]:
                self._add_result(
                    "Randomization produces different images",
                    TestStatus.PASS,
                    "Images differ after ApplyRandomization"
                )
            elif len(hashes) == 2:
                self._add_result(
                    "Randomization produces different images",
                    TestStatus.WARN,
                    "Images identical - randomization may not be visible"
                )
    
    # =========================================================================
    # Test 7: Annotations
    # =========================================================================
    def _test_annotations(self):
        """Test annotation generation."""
        print("\n[7/8] Annotations")
        print("-" * 40)
        
        data_capture_path = self.ue5_config.get('data_capture_path')
        if not data_capture_path or not self.base_url:
            self._add_result("Annotations", TestStatus.SKIP, "No DataCapture")
            return
        
        # Get object classes from config
        classes = self.config.get('objects.classes', [])
        
        try:
            response = requests.put(
                f"{self.base_url}/remote/object/call",
                json={
                    "objectPath": data_capture_path,
                    "functionName": "GenerateBoundingBoxes",
                    "parameters": {
                        "TargetTags": classes
                    }
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                json_str = result.get('ReturnValue', '{}')
                
                try:
                    annotations = json.loads(json_str)
                    num_annotations = len(annotations.get('annotations', []))
                    
                    if num_annotations > 0:
                        self._add_result(
                            "Bounding box generation",
                            TestStatus.PASS,
                            f"Found {num_annotations} annotations"
                        )
                    else:
                        self._add_result(
                            "Bounding box generation",
                            TestStatus.WARN,
                            "No objects found - check vehicle tags match config",
                            details=f"Looking for tags: {classes}"
                        )
                except json.JSONDecodeError:
                    self._add_result(
                        "Bounding box generation",
                        TestStatus.WARN,
                        "Invalid JSON response"
                    )
            else:
                self._add_result(
                    "Bounding box generation",
                    TestStatus.FAIL,
                    f"HTTP {response.status_code}"
                )
                
        except Exception as e:
            self._add_result(
                "Bounding box generation",
                TestStatus.FAIL,
                str(e)
            )
    
    # =========================================================================
    # Test 8: Filesystem
    # =========================================================================
    def _test_filesystem(self):
        """Test filesystem permissions and paths."""
        print("\n[8/8] Filesystem")
        print("-" * 40)
        
        # Check output directory
        domain = self.config.get('domain.name', 'unknown') if self.config else 'unknown'
        output_dir = Path(f"data/synthetic/{domain}")
        
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            test_file = output_dir / ".preflight_test"
            test_file.write_text("test")
            test_file.unlink()
            
            self._add_result(
                "Output directory writable",
                TestStatus.PASS,
                str(output_dir)
            )
        except PermissionError:
            self._add_result(
                "Output directory writable",
                TestStatus.FAIL,
                f"Permission denied: {output_dir}"
            )
        except Exception as e:
            self._add_result(
                "Output directory writable",
                TestStatus.FAIL,
                str(e)
            )
        
        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(output_dir.anchor)
            free_gb = free / (1024**3)
            
            if free_gb > 50:
                self._add_result(
                    "Disk space",
                    TestStatus.PASS,
                    f"{free_gb:.1f} GB free"
                )
            elif free_gb > 10:
                self._add_result(
                    "Disk space",
                    TestStatus.WARN,
                    f"Only {free_gb:.1f} GB free (recommend 50+ GB for large datasets)"
                )
            else:
                self._add_result(
                    "Disk space",
                    TestStatus.FAIL,
                    f"Low disk space: {free_gb:.1f} GB"
                )
        except Exception as e:
            self._add_result(
                "Disk space",
                TestStatus.WARN,
                f"Could not check: {e}"
            )
    
    # =========================================================================
    # Cleanup and Report
    # =========================================================================
    def _cleanup(self):
        """Clean up temporary test files."""
        if self.temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
    
    def _print_report(self):
        """Print final summary report."""
        print("\n" + "="*70)
        print("PRE-FLIGHT CHECK SUMMARY")
        print("="*70)
        print(f"Domain: {self.report.domain}")
        print(f"Config: {self.report.config_path}")
        print("-"*70)
        print(f"  ✓ Passed:   {self.report.passed}")
        print(f"  ✗ Failed:   {self.report.failed}")
        print(f"  ⚠ Warnings: {self.report.warnings}")
        print("-"*70)
        
        if self.report.success:
            print("\n  🚀 ALL CRITICAL TESTS PASSED - Ready for dataset generation!\n")
            print("  Recommended command:")
            print(f"    python scripts/generate.py --config {self.config_path} --num-images 1000 --use-ue5\n")
        else:
            print("\n  ❌ CRITICAL FAILURES DETECTED - Fix issues before generating\n")
            print("  Failed tests:")
            for test in self.report.tests:
                if test.status == TestStatus.FAIL:
                    print(f"    - {test.name}: {test.message}")
            print()
        
        print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="VantageCV Pre-Flight Check - Validate pipeline before generation"
    )
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to domain configuration file'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick mode: skip lengthy randomization and uniqueness tests'
    )
    
    args = parser.parse_args()
    
    checker = PreflightChecker(args.config, quick_mode=args.quick)
    report = checker.run_all_tests()
    
    # Exit with error code if failed
    sys.exit(0 if report.success else 1)


if __name__ == "__main__":
    main()
