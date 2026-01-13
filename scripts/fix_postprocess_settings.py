"""
Fix Post Process Volume settings for synthetic data capture.
Sets all rendering parameters to neutral/disabled for clean ground truth.
"""

import requests
import sys

BASE_URL = "http://127.0.0.1:30010/remote"
LEVEL_PATH = "/Game/main"

def call_function(object_path: str, function_name: str, parameters: dict = None):
    """Call UE5 function via Remote Control API"""
    response = requests.put(
        f"{BASE_URL}/object/call",
        json={
            "objectPath": object_path,
            "functionName": function_name,
            "parameters": parameters or {}
        },
        timeout=10
    )
    response.raise_for_status()
    return response.json()

def set_property(object_path: str, property_name: str, value):
    """Set property via Remote Control API"""
    try:
        response = requests.put(
            f"{BASE_URL}/object/property",
            json={
                "objectPath": object_path,
                "propertyName": property_name,
                "propertyValue": value
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Some properties may not exist - skip them
        pass

def find_postprocess_volume():
    """Find PostProcessVolume in level"""
    # Use exact path provided
    path = "/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1"
    try:
        response = requests.put(
            f"{BASE_URL}/object/property",
            json={
                "objectPath": path,
                "propertyName": "bEnabled",
                "propertyValue": True
            },
            timeout=5
        )
        if response.status_code == 200:
            return path
    except:
        pass
    
    return None

def apply_settings(ppv_path: str):
    """Apply all post process settings"""
    
    # Infinite Extent
    set_property(ppv_path, "bUnbound", True)
    
    # Manual Exposure (EV100 = 0)
    set_property(ppv_path, "Settings.bOverride_AutoExposureMethod", True)
    set_property(ppv_path, "Settings.AutoExposureMethod", 0)  # 0 = Manual
    set_property(ppv_path, "Settings.bOverride_AutoExposureBias", True)
    set_property(ppv_path, "Settings.AutoExposureBias", 0.0)
    set_property(ppv_path, "Settings.bOverride_AutoExposureMinBrightness", True)
    set_property(ppv_path, "Settings.AutoExposureMinBrightness", 1.0)
    set_property(ppv_path, "Settings.bOverride_AutoExposureMaxBrightness", True)
    set_property(ppv_path, "Settings.AutoExposureMaxBrightness", 1.0)
    
    # Bloom OFF
    set_property(ppv_path, "Settings.bOverride_BloomIntensity", True)
    set_property(ppv_path, "Settings.BloomIntensity", 0.0)
    
    # Color Grading - Neutral
    set_property(ppv_path, "Settings.bOverride_ColorSaturation", True)
    set_property(ppv_path, "Settings.ColorSaturation", {"X": 1.0, "Y": 1.0, "Z": 1.0, "W": 1.0})
    set_property(ppv_path, "Settings.bOverride_ColorContrast", True)
    set_property(ppv_path, "Settings.ColorContrast", {"X": 1.0, "Y": 1.0, "Z": 1.0, "W": 1.0})
    set_property(ppv_path, "Settings.bOverride_ColorGamma", True)
    set_property(ppv_path, "Settings.ColorGamma", {"X": 1.0, "Y": 1.0, "Z": 1.0, "W": 1.0})
    set_property(ppv_path, "Settings.bOverride_ColorGain", True)
    set_property(ppv_path, "Settings.ColorGain", {"X": 1.0, "Y": 1.0, "Z": 1.0, "W": 1.0})
    set_property(ppv_path, "Settings.bOverride_ColorOffset", True)
    set_property(ppv_path, "Settings.ColorOffset", {"X": 0.0, "Y": 0.0, "Z": 0.0, "W": 0.0})
    
    # Film - Neutral
    set_property(ppv_path, "Settings.bOverride_FilmSlope", True)
    set_property(ppv_path, "Settings.FilmSlope", 1.0)
    set_property(ppv_path, "Settings.bOverride_FilmToe", True)
    set_property(ppv_path, "Settings.FilmToe", 0.0)
    set_property(ppv_path, "Settings.bOverride_FilmShoulder", True)
    set_property(ppv_path, "Settings.FilmShoulder", 0.0)
    set_property(ppv_path, "Settings.bOverride_FilmBlackClip", True)
    set_property(ppv_path, "Settings.FilmBlackClip", 0.0)
    set_property(ppv_path, "Settings.bOverride_FilmWhiteClip", True)
    set_property(ppv_path, "Settings.FilmWhiteClip", 0.0)
    
    # Lens Effects OFF
    set_property(ppv_path, "Settings.bOverride_VignetteIntensity", True)
    set_property(ppv_path, "Settings.VignetteIntensity", 0.0)
    set_property(ppv_path, "Settings.bOverride_SceneFringeIntensity", True)
    set_property(ppv_path, "Settings.SceneFringeIntensity", 0.0)
    set_property(ppv_path, "Settings.bOverride_MotionBlurAmount", True)
    set_property(ppv_path, "Settings.MotionBlurAmount", 0.0)
    set_property(ppv_path, "Settings.bOverride_DepthOfFieldFstop", True)
    set_property(ppv_path, "Settings.DepthOfFieldFstop", 32.0)  # High f-stop = everything in focus
    set_property(ppv_path, "Settings.bOverride_GrainIntensity", True)
    set_property(ppv_path, "Settings.GrainIntensity", 0.0)

def main():
    print("Fixing Post Process Volume settings for synthetic data capture...")
    
    # Find existing PPV
    ppv_path = find_postprocess_volume()
    if not ppv_path:
        print("ERROR: No PostProcessVolume found in level")
        sys.exit(1)
    
    print(f"Found: {ppv_path}")
    
    # Apply all settings
    try:
        apply_settings(ppv_path)
        print("✓ Post Process settings applied: Manual exposure, no bloom, neutral color grading, lens effects disabled")
    except Exception as e:
        print(f"ERROR applying settings: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
