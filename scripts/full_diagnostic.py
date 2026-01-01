#!/usr/bin/env python3
"""
VantageCV - Complete Diagnostic Test Suite
===========================================
Exhaustive test of every component that can affect image brightness.
Run this to identify exactly what's wrong.

Author: VantageCV Team
Date: December 2025
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
UE5_HOST = "http://localhost:30010"
TIMEOUT = 15
OUTPUT_DIR = Path("data/synthetic/diagnostic")

# Test results
class TestResult:
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    WARN = "⚠️ WARN"
    SKIP = "⏭️ SKIP"
    INFO = "ℹ️ INFO"

results: List[Tuple[str, str, str]] = []

def log_result(test_name: str, status: str, message: str = ""):
    """Log a test result."""
    results.append((test_name, status, message))
    print(f"  {status} {test_name}")
    if message:
        print(f"       {message}")

def call_ue5(endpoint: str, body: dict = None, method: str = "PUT") -> Tuple[int, dict]:
    """Make a request to UE5 Remote Control API."""
    url = f"{UE5_HOST}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=TIMEOUT)
        else:
            resp = requests.put(url, json=body or {}, timeout=TIMEOUT)
        try:
            data = resp.json() if resp.text else {}
        except:
            data = {"raw": resp.text[:500]}
        return resp.status_code, data
    except requests.exceptions.ConnectionError:
        return 0, {"error": "Connection refused - UE5 not running?"}
    except requests.exceptions.Timeout:
        return 0, {"error": "Request timed out"}
    except Exception as e:
        return 0, {"error": str(e)}

def get_property(object_path: str, property_name: str) -> Tuple[bool, Any]:
    """Get a property value from UE5 object."""
    status, data = call_ue5("/remote/object/property", {
        "objectPath": object_path,
        "propertyName": property_name
    })
    if status == 200:
        return True, data.get(property_name, data)
    return False, data.get("errorMessage", str(data))

def set_property(object_path: str, property_name: str, value: Any) -> bool:
    """Set a property value on UE5 object."""
    status, _ = call_ue5("/remote/object/property", {
        "objectPath": object_path,
        "propertyName": property_name,
        "propertyValue": value
    })
    return status == 200

def call_function(object_path: str, function_name: str, params: dict = None) -> Tuple[bool, Any]:
    """Call a function on UE5 object."""
    status, data = call_ue5("/remote/object/call", {
        "objectPath": object_path,
        "functionName": function_name,
        "parameters": params or {}
    })
    return status == 200, data


# =============================================================================
# TEST SECTIONS
# =============================================================================

def test_ue5_connection():
    """Test 1: Basic UE5 Connection"""
    print("\n" + "="*70)
    print("TEST 1: UE5 CONNECTION")
    print("="*70)
    
    # 1.1 Remote Control API reachable
    status, data = call_ue5("/remote/info", method="GET")
    if status == 200:
        log_result("Remote Control API", TestResult.PASS, f"Connected to {UE5_HOST}")
    else:
        log_result("Remote Control API", TestResult.FAIL, f"Cannot connect: {data}")
        return False
    
    # 1.2 Check API version
    if "HttpRoutes" in str(data):
        log_result("API Routes Available", TestResult.PASS)
    else:
        log_result("API Routes", TestResult.WARN, "Unexpected response format")
    
    # 1.3 Test batch endpoint
    status, _ = call_ue5("/remote/batch", {"Requests": []})
    if status == 200:
        log_result("Batch Endpoint", TestResult.PASS)
    else:
        log_result("Batch Endpoint", TestResult.WARN, "Batch requests may not work")
    
    return True


def test_level_and_actors():
    """Test 2: Level and Required Actors"""
    print("\n" + "="*70)
    print("TEST 2: LEVEL AND ACTORS")
    print("="*70)
    
    # 2.1 Find all actors in level
    status, data = call_ue5("/remote/search/assets", {
        "Query": "automobile",
        "Limit": 200
    })
    
    if status != 200:
        log_result("Level Search", TestResult.FAIL, "Cannot search for actors")
        return {}
    
    actors = data.get("Assets", [])
    log_result("Actor Search", TestResult.PASS, f"Found {len(actors)} assets")
    
    # Parse actor paths
    actor_paths = {}
    automobile_actors = [a for a in actors if "automobile" in a.get("Path", "").lower()]
    
    # 2.2 Check for DataCapture
    data_captures = [a for a in automobile_actors if "DataCapture" in a.get("Name", "") or "DataCapture" in a.get("Class", "")]
    if data_captures:
        actor_paths["DataCapture"] = data_captures[0]["Path"]
        log_result("DataCapture Actor", TestResult.PASS, data_captures[0]["Path"])
    else:
        log_result("DataCapture Actor", TestResult.FAIL, "NOT FOUND - This is required!")
    
    # 2.3 Check for DirectionalLight
    lights = [a for a in automobile_actors if "DirectionalLight" in a.get("Name", "")]
    if lights:
        actor_paths["DirectionalLight"] = lights[0]["Path"] if "PersistentLevel" in lights[0].get("Path", "") else f"/Game/automobile.automobile:PersistentLevel.{lights[0]['Name']}"
        log_result("DirectionalLight", TestResult.PASS, actor_paths["DirectionalLight"])
    else:
        log_result("DirectionalLight", TestResult.WARN, "No directional light found")
    
    # 2.4 Check for SkyLight
    skylights = [a for a in automobile_actors if "SkyLight" in a.get("Name", "")]
    if skylights:
        actor_paths["SkyLight"] = skylights[0]["Path"] if "PersistentLevel" in skylights[0].get("Path", "") else f"/Game/automobile.automobile:PersistentLevel.{skylights[0]['Name']}"
        log_result("SkyLight", TestResult.PASS)
    else:
        log_result("SkyLight", TestResult.WARN, "No sky light found - may cause dark shadows")
    
    # 2.5 Check for PostProcessVolume
    ppvs = [a for a in automobile_actors if "PostProcess" in a.get("Name", "")]
    if ppvs:
        actor_paths["PostProcessVolume"] = ppvs[0]["Path"] if "PersistentLevel" in ppvs[0].get("Path", "") else f"/Game/automobile.automobile:PersistentLevel.{ppvs[0]['Name']}"
        log_result("PostProcessVolume", TestResult.PASS)
    else:
        log_result("PostProcessVolume", TestResult.WARN, "No PostProcessVolume - exposure may be wrong")
    
    # 2.6 Check for SceneController
    controllers = [a for a in automobile_actors if "SceneController" in a.get("Name", "")]
    if controllers:
        actor_paths["SceneController"] = controllers[0]["Path"] if "PersistentLevel" in controllers[0].get("Path", "") else f"/Game/automobile.automobile:PersistentLevel.{controllers[0]['Name']}"
        log_result("SceneController", TestResult.PASS)
    else:
        log_result("SceneController", TestResult.INFO, "No SceneController (optional)")
    
    # 2.7 Check for DomainRandomization
    dr = [a for a in automobile_actors if "DomainRandomization" in a.get("Name", "")]
    if dr:
        actor_paths["DomainRandomization"] = dr[0]["Path"] if "PersistentLevel" in dr[0].get("Path", "") else f"/Game/automobile.automobile:PersistentLevel.{dr[0]['Name']}"
        log_result("DomainRandomization", TestResult.PASS)
    else:
        log_result("DomainRandomization", TestResult.INFO, "No DomainRandomization (optional)")
    
    return actor_paths


def test_lighting_settings(actor_paths: dict):
    """Test 3: Lighting Configuration"""
    print("\n" + "="*70)
    print("TEST 3: LIGHTING SETTINGS")
    print("="*70)
    
    # 3.1 Directional Light Intensity
    if "DirectionalLight" in actor_paths:
        path = actor_paths["DirectionalLight"]
        
        # Get light component
        success, intensity = get_property(path, "Intensity")
        if success:
            val = intensity if isinstance(intensity, (int, float)) else 0
            if val >= 5.0:
                log_result("DirectionalLight Intensity", TestResult.PASS, f"{val} lux")
            elif val >= 1.0:
                log_result("DirectionalLight Intensity", TestResult.WARN, f"{val} lux - Consider increasing to 10+")
            else:
                log_result("DirectionalLight Intensity", TestResult.FAIL, f"{val} lux - TOO LOW! Set to 10-15")
        else:
            # Try via LightComponent
            success2, data = get_property(path, "LightComponent")
            log_result("DirectionalLight Intensity", TestResult.WARN, f"Could not read directly: {intensity}")
    else:
        log_result("DirectionalLight Check", TestResult.SKIP, "No DirectionalLight actor")
    
    # 3.2 SkyLight
    if "SkyLight" in actor_paths:
        path = actor_paths["SkyLight"]
        success, intensity = get_property(path, "Intensity")
        if success and isinstance(intensity, (int, float)):
            if intensity >= 0.5:
                log_result("SkyLight Intensity", TestResult.PASS, f"{intensity}")
            else:
                log_result("SkyLight Intensity", TestResult.WARN, f"{intensity} - Consider 1.0+")
        else:
            log_result("SkyLight Intensity", TestResult.WARN, "Could not read")
    else:
        log_result("SkyLight Check", TestResult.SKIP, "No SkyLight")


def test_postprocess_settings(actor_paths: dict):
    """Test 4: Post-Process Volume Settings"""
    print("\n" + "="*70)
    print("TEST 4: POST-PROCESS VOLUME SETTINGS")
    print("="*70)
    
    if "PostProcessVolume" not in actor_paths:
        log_result("PostProcessVolume", TestResult.SKIP, "No PostProcessVolume found")
        return
    
    path = actor_paths["PostProcessVolume"]
    
    # 4.1 Check if Unbound
    success, unbound = get_property(path, "bUnbound")
    if success:
        if unbound:
            log_result("Infinite Extent (Unbound)", TestResult.PASS, "Global volume")
        else:
            log_result("Infinite Extent (Unbound)", TestResult.WARN, "Not global - may not affect capture")
    
    # 4.2 Get Settings subobject path
    settings_props = [
        ("AutoExposureMethod", "bOverride_AutoExposureMethod", "Should be Histogram or Basic"),
        ("AutoExposureBias", "bOverride_AutoExposureBias", "Should be 3.0-5.0 for bright"),
        ("AutoExposureMinBrightness", "bOverride_AutoExposureMinBrightness", "Should be 0.5-1.0"),
        ("AutoExposureMaxBrightness", "bOverride_AutoExposureMaxBrightness", "Should be 8.0-10.0"),
    ]
    
    for prop, override_prop, hint in settings_props:
        success, value = get_property(path, prop)
        if success:
            log_result(f"PPV {prop}", TestResult.INFO, f"{value} ({hint})")
        else:
            log_result(f"PPV {prop}", TestResult.WARN, f"Could not read - {hint}")


def test_datacapture_actor(actor_paths: dict):
    """Test 5: DataCapture Actor Functionality"""
    print("\n" + "="*70)
    print("TEST 5: DATACAPTURE ACTOR")
    print("="*70)
    
    if "DataCapture" not in actor_paths:
        log_result("DataCapture", TestResult.FAIL, "No DataCapture actor - CRITICAL!")
        return False
    
    path = actor_paths["DataCapture"]
    
    # 5.1 Check actor exists and responds
    success, data = get_property(path, "RootComponent")
    if not success:
        log_result("DataCapture Exists", TestResult.FAIL, f"Actor not accessible: {data}")
        return False
    log_result("DataCapture Exists", TestResult.PASS)
    
    # 5.2 Test SetResolution function
    success, result = call_function(path, "SetResolution", {"Width": 1280, "Height": 720})
    if success:
        log_result("SetResolution(1280x720)", TestResult.PASS)
    else:
        log_result("SetResolution", TestResult.FAIL, f"Function call failed: {result}")
        return False
    
    # 5.3 Get actor location
    success, location = get_property(path, "ActorLocation")
    if success:
        log_result("Actor Location", TestResult.INFO, str(location)[:60])
    
    return True


def test_capture_brightness(actor_paths: dict):
    """Test 6: Actual Capture and Brightness Analysis"""
    print("\n" + "="*70)
    print("TEST 6: CAPTURE BRIGHTNESS ANALYSIS")
    print("="*70)
    
    if "DataCapture" not in actor_paths:
        log_result("Capture Test", TestResult.SKIP, "No DataCapture")
        return
    
    path = actor_paths["DataCapture"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 6.1 Capture test image
    test_path = str((OUTPUT_DIR / "brightness_test.png").absolute()).replace("\\", "/")
    print(f"  Capturing to: {test_path}")
    
    success, result = call_function(path, "CaptureFrame", {
        "OutputPath": test_path,
        "Width": 1280,
        "Height": 720
    })
    
    if not success:
        log_result("CaptureFrame Call", TestResult.FAIL, f"{result}")
        return
    
    return_value = result.get("ReturnValue", False)
    if return_value:
        log_result("CaptureFrame Call", TestResult.PASS)
    else:
        log_result("CaptureFrame Call", TestResult.FAIL, "Function returned false")
        return
    
    # Wait for file
    time.sleep(1)
    
    # 6.2 Check file exists
    output_file = OUTPUT_DIR / "brightness_test.png"
    if not output_file.exists():
        log_result("Image File Created", TestResult.FAIL, "File not found!")
        return
    
    file_size = output_file.stat().st_size
    log_result("Image File Created", TestResult.PASS, f"{file_size:,} bytes")
    
    # 6.3 Analyze brightness
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(output_file)
        img_array = np.array(img)
        
        mean_brightness = img_array.mean()
        max_val = img_array.max()
        min_val = img_array.min()
        
        # Per-channel
        if len(img_array.shape) == 3:
            r_mean = img_array[:,:,0].mean()
            g_mean = img_array[:,:,1].mean()
            b_mean = img_array[:,:,2].mean()
            
            log_result("Image Dimensions", TestResult.INFO, f"{img.width}x{img.height}")
            log_result("Pixel Range", TestResult.INFO, f"Min={min_val}, Max={max_val}")
            log_result("R Channel Mean", TestResult.INFO, f"{r_mean:.1f}")
            log_result("G Channel Mean", TestResult.INFO, f"{g_mean:.1f}")
            log_result("B Channel Mean", TestResult.INFO, f"{b_mean:.1f}")
            
            # Brightness verdict
            if mean_brightness < 10:
                log_result("BRIGHTNESS", TestResult.FAIL, f"Mean={mean_brightness:.1f} - COMPLETELY BLACK!")
            elif mean_brightness < 30:
                log_result("BRIGHTNESS", TestResult.FAIL, f"Mean={mean_brightness:.1f} - VERY DARK!")
            elif mean_brightness < 60:
                log_result("BRIGHTNESS", TestResult.WARN, f"Mean={mean_brightness:.1f} - TOO DARK")
            elif mean_brightness < 120:
                log_result("BRIGHTNESS", TestResult.WARN, f"Mean={mean_brightness:.1f} - Slightly dark")
            elif mean_brightness < 200:
                log_result("BRIGHTNESS", TestResult.PASS, f"Mean={mean_brightness:.1f} - GOOD!")
            else:
                log_result("BRIGHTNESS", TestResult.WARN, f"Mean={mean_brightness:.1f} - Possibly overexposed")
            
            # Check for all-black
            if max_val < 5:
                log_result("BLACK IMAGE CHECK", TestResult.FAIL, "Image is completely black - render target issue?")
            
            # Check for clipping
            white_pixels = np.sum(img_array > 250) / img_array.size * 100
            black_pixels = np.sum(img_array < 5) / img_array.size * 100
            
            if black_pixels > 50:
                log_result("Black Pixel %", TestResult.WARN, f"{black_pixels:.1f}% - Too many dark pixels")
            else:
                log_result("Black Pixel %", TestResult.INFO, f"{black_pixels:.1f}%")
            
            if white_pixels > 20:
                log_result("White Pixel %", TestResult.WARN, f"{white_pixels:.1f}% - Clipping/overexposure")
            else:
                log_result("White Pixel %", TestResult.INFO, f"{white_pixels:.1f}%")
        
    except ImportError:
        log_result("Brightness Analysis", TestResult.SKIP, "Install PIL: pip install Pillow")
    except Exception as e:
        log_result("Brightness Analysis", TestResult.FAIL, str(e))


def test_config_files():
    """Test 7: Configuration Files"""
    print("\n" + "="*70)
    print("TEST 7: CONFIGURATION FILES")
    print("="*70)
    
    # 7.1 Check research.yaml
    research_yaml = Path("configs/research.yaml")
    if research_yaml.exists():
        log_result("configs/research.yaml", TestResult.PASS, "Exists")
        
        try:
            import yaml
            with open(research_yaml) as f:
                config = yaml.safe_load(f)
            
            # Check UE5 section
            ue5 = config.get("ue5", {})
            if ue5.get("data_capture_path"):
                log_result("data_capture_path", TestResult.PASS, ue5["data_capture_path"])
            else:
                log_result("data_capture_path", TestResult.FAIL, "Missing!")
            
            if ue5.get("host"):
                log_result("UE5 host", TestResult.INFO, ue5["host"])
            
        except Exception as e:
            log_result("Parse research.yaml", TestResult.FAIL, str(e))
    else:
        log_result("configs/research.yaml", TestResult.FAIL, "File not found")
    
    # 7.2 Check automotive.yaml
    auto_yaml = Path("configs/automotive.yaml")
    if auto_yaml.exists():
        log_result("configs/automotive.yaml", TestResult.PASS, "Exists")
    else:
        log_result("configs/automotive.yaml", TestResult.WARN, "Not found")


def test_plugin_compilation():
    """Test 8: Plugin DLL Status"""
    print("\n" + "="*70)
    print("TEST 8: PLUGIN COMPILATION STATUS")
    print("="*70)
    
    dll_path = Path("F:/Unreal Editor/VantageCV_Project/Plugins/VantageCV/Binaries/Win64/UnrealEditor-VantageCV.dll")
    
    if dll_path.exists():
        mtime = datetime.fromtimestamp(dll_path.stat().st_mtime)
        size = dll_path.stat().st_size
        log_result("Plugin DLL Exists", TestResult.PASS)
        log_result("DLL Last Modified", TestResult.INFO, mtime.strftime("%Y-%m-%d %H:%M:%S"))
        log_result("DLL Size", TestResult.INFO, f"{size:,} bytes")
        
        # Check if recently modified
        age_minutes = (datetime.now() - mtime).total_seconds() / 60
        if age_minutes < 10:
            log_result("Recently Compiled", TestResult.PASS, f"{age_minutes:.0f} minutes ago")
        elif age_minutes < 60:
            log_result("Compilation Age", TestResult.INFO, f"{age_minutes:.0f} minutes ago")
        else:
            log_result("Compilation Age", TestResult.WARN, f"{age_minutes/60:.1f} hours ago - Consider rebuilding")
    else:
        log_result("Plugin DLL", TestResult.FAIL, "Not found - Need to compile!")
    
    # Check source file
    source_path = Path("f:/vscode/VantageCV/ue5_plugin/Source/VantageCV/Private/DataCapture.cpp")
    if source_path.exists():
        src_mtime = datetime.fromtimestamp(source_path.stat().st_mtime)
        log_result("Source Last Modified", TestResult.INFO, src_mtime.strftime("%Y-%m-%d %H:%M:%S"))
        
        if dll_path.exists():
            dll_mtime = datetime.fromtimestamp(dll_path.stat().st_mtime)
            if src_mtime > dll_mtime:
                log_result("SOURCE NEWER THAN DLL", TestResult.FAIL, "NEED TO REBUILD! Close UE5 and reopen")


def test_python_environment():
    """Test 9: Python Environment"""
    print("\n" + "="*70)
    print("TEST 9: PYTHON ENVIRONMENT")
    print("="*70)
    
    log_result("Python Version", TestResult.INFO, sys.version.split()[0])
    log_result("Python Executable", TestResult.INFO, sys.executable[:50])
    
    # Check required packages
    packages = ["requests", "numpy", "PIL", "yaml"]
    for pkg in packages:
        try:
            if pkg == "PIL":
                import PIL
                log_result(f"Package: Pillow", TestResult.PASS, PIL.__version__)
            elif pkg == "yaml":
                import yaml
                log_result(f"Package: PyYAML", TestResult.PASS)
            else:
                mod = __import__(pkg)
                ver = getattr(mod, "__version__", "unknown")
                log_result(f"Package: {pkg}", TestResult.PASS, ver)
        except ImportError:
            log_result(f"Package: {pkg}", TestResult.FAIL, "Not installed")


def test_file_permissions():
    """Test 10: File System Permissions"""
    print("\n" + "="*70)
    print("TEST 10: FILE SYSTEM PERMISSIONS")
    print("="*70)
    
    # Test write to output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    test_file = OUTPUT_DIR / "permission_test.txt"
    
    try:
        test_file.write_text("test")
        test_file.unlink()
        log_result("Write to output dir", TestResult.PASS, str(OUTPUT_DIR))
    except Exception as e:
        log_result("Write to output dir", TestResult.FAIL, str(e))
    
    # Check UE5 project access
    ue5_project = Path("F:/Unreal Editor/VantageCV_Project")
    if ue5_project.exists():
        log_result("UE5 Project Folder", TestResult.PASS, "Accessible")
    else:
        log_result("UE5 Project Folder", TestResult.WARN, "Not found or not accessible")


def print_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY")
    print("="*70)
    
    passes = sum(1 for _, status, _ in results if status == TestResult.PASS)
    fails = sum(1 for _, status, _ in results if status == TestResult.FAIL)
    warns = sum(1 for _, status, _ in results if status == TestResult.WARN)
    
    print(f"\n  {TestResult.PASS}: {passes}")
    print(f"  {TestResult.FAIL}: {fails}")
    print(f"  {TestResult.WARN}: {warns}")
    
    if fails > 0:
        print("\n" + "-"*70)
        print("FAILURES (Must Fix):")
        print("-"*70)
        for name, status, msg in results:
            if status == TestResult.FAIL:
                print(f"  • {name}: {msg}")
    
    if warns > 0:
        print("\n" + "-"*70)
        print("WARNINGS (Should Check):")
        print("-"*70)
        for name, status, msg in results:
            if status == TestResult.WARN:
                print(f"  • {name}: {msg}")
    
    # Specific recommendations
    print("\n" + "="*70)
    print("RECOMMENDED ACTIONS")
    print("="*70)
    
    fail_names = [name for name, status, _ in results if status == TestResult.FAIL]
    
    if "BRIGHTNESS" in str(fail_names) or any("DARK" in str(msg) for _, _, msg in results):
        print("""
  🔧 DARK IMAGE FIX:
     1. In UE5, select PostProcessVolume_1
     2. Set Exposure Compensation to 5.0
     3. Set Min Brightness to 1.0
     4. Set Max Brightness to 10.0
     5. Make sure 'Infinite Extent (Unbound)' is CHECKED
     6. Close UE5 and reopen to rebuild plugin
     7. Run this diagnostic again
        """)
    
    if any("SOURCE NEWER" in name for name, _, _ in results):
        print("""
  🔧 REBUILD REQUIRED:
     1. Close UE5 completely
     2. Reopen the VantageCV_Project.uproject
     3. Wait for compilation to finish
     4. Run this diagnostic again
        """)
    
    if not any(status == TestResult.FAIL for _, status, _ in results):
        print("\n  ✅ All critical tests passed!")


def main():
    """Run all diagnostic tests."""
    print("\n" + "="*70)
    print("VantageCV COMPLETE DIAGNOSTIC TEST SUITE")
    print("="*70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output: {OUTPUT_DIR}")
    print("="*70)
    
    # Run tests
    if not test_ue5_connection():
        print("\n❌ Cannot connect to UE5 - is it running with Remote Control enabled?")
        print("   Start UE5, open the automobile level, and try again.")
        return
    
    actor_paths = test_level_and_actors()
    test_lighting_settings(actor_paths)
    test_postprocess_settings(actor_paths)
    test_datacapture_actor(actor_paths)
    test_capture_brightness(actor_paths)
    test_config_files()
    test_plugin_compilation()
    test_python_environment()
    test_file_permissions()
    
    print_summary()
    
    # Open the test image
    test_img = OUTPUT_DIR / "brightness_test.png"
    if test_img.exists():
        print(f"\n  Opening test image: {test_img}")
        import subprocess
        subprocess.run(["explorer", str(test_img)], shell=True)


if __name__ == "__main__":
    main()
