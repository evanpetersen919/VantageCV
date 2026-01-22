"""
Diagnostic script - Read all current UE5 rendering settings.
Shows what's actually configured vs. what should be configured.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:30010/remote"
LEVEL_PATH = "/Game/automobileV2.automobileV2:PersistentLevel"

def get_property(object_path: str, property_name: str):
    """Get property value via Remote Control API"""
    try:
        response = requests.put(
            f"{BASE_URL}/object/property",
            json={
                "objectPath": object_path,
                "propertyName": property_name
            },
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("PropertyValue")
    except:
        pass
    return None

def check_postprocess():
    """Check PostProcessVolume settings"""
    print("\n" + "=" * 60)
    print("POST PROCESS VOLUME")
    print("=" * 60)
    
    ppv = f"{LEVEL_PATH}.PostProcessVolume_1"
    
    settings = {
        "bUnbound": ("Infinite Extent", True),
        "Settings.AutoExposureMethod": ("Exposure Method", 0),  # 0 = Manual
        "Settings.AutoExposureBias": ("Exposure Bias", 0.0),
        "Settings.BloomIntensity": ("Bloom Intensity", 0.0),
        "Settings.MotionBlurAmount": ("Motion Blur", 0.0),
        "Settings.DepthOfFieldFstop": ("DOF F-stop", 32.0),
        "Settings.VignetteIntensity": ("Vignette", 0.0),
        "Settings.GrainIntensity": ("Film Grain", 0.0),
    }
    
    issues = []
    for prop, (label, expected) in settings.items():
        actual = get_property(ppv, prop)
        status = "✓" if actual == expected else "✗"
        
        if actual != expected and actual is not None:
            issues.append(f"{label}: {actual} (should be {expected})")
        
        print(f"  {status} {label}: {actual} (expected: {expected})")
    
    return issues

def check_directional_light():
    """Check DirectionalLight settings"""
    print("\n" + "=" * 60)
    print("DIRECTIONAL LIGHT (Sun)")
    print("=" * 60)
    
    light = f"{LEVEL_PATH}.DirectionalLight_4"
    
    intensity = get_property(light, "Intensity")
    color = get_property(light, "LightColor")
    rotation = get_property(light, "Rotation")
    cast_shadows = get_property(light, "CastShadows")
    
    print(f"  Intensity: {intensity} lux (recommended: 10)")
    print(f"  Color: {color}")
    print(f"  Rotation: {rotation}")
    print(f"  Cast Shadows: {cast_shadows}")
    
    issues = []
    if intensity and intensity < 5:
        issues.append(f"DirectionalLight too dim: {intensity} lux (should be ~10)")
    if intensity and intensity > 20:
        issues.append(f"DirectionalLight too bright: {intensity} lux (should be ~10)")
    
    return issues

def check_datacapture():
    """Check DataCapture camera settings"""
    print("\n" + "=" * 60)
    print("DATA CAPTURE CAMERA")
    print("=" * 60)
    
    dc = f"{LEVEL_PATH}.DataCapture_1"
    
    location = get_property(dc, "RootComponent.RelativeLocation")
    rotation = get_property(dc, "RootComponent.RelativeRotation")
    
    print(f"  Location: {location}")
    print(f"  Rotation: {rotation}")
    
    # Try to get capture component settings
    fov = get_property(dc, "CaptureComponent.FOVAngle")
    if fov:
        print(f"  FOV: {fov}°")
    
    return []

def check_common_issues():
    """Check for common rendering problems"""
    print("\n" + "=" * 60)
    print("COMMON ISSUES CHECK")
    print("=" * 60)
    
    issues = []
    
    # Check if fog is enabled (causes dark scenes)
    fog = f"{LEVEL_PATH}.ExponentialHeightFog_1"
    fog_density = get_property(fog, "Component.FogDensity")
    if fog_density and fog_density > 0.01:
        issues.append(f"Fog enabled with density {fog_density} (should be 0.0)")
        print(f"  ✗ Fog Density: {fog_density} (should be 0.0)")
    else:
        print(f"  ✓ Fog Density: {fog_density}")
    
    # Check post process blend weight (0 = use PPV settings)
    dc = f"{LEVEL_PATH}.DataCapture_1"
    blend = get_property(dc, "CaptureComponent.PostProcessBlendWeight")
    if blend:
        if blend > 0.1:
            issues.append(f"DataCapture PostProcessBlendWeight: {blend} (should be 0.0)")
            print(f"  ✗ DataCapture PP Blend: {blend} (should be 0.0)")
        else:
            print(f"  ✓ DataCapture PP Blend: {blend}")
    
    return issues

def main():
    print("=" * 60)
    print("UE5 RENDERING SETTINGS DIAGNOSTIC")
    print("=" * 60)
    print("\nReading current settings from UE5...")
    
    all_issues = []
    
    # Check all systems
    all_issues.extend(check_postprocess())
    all_issues.extend(check_directional_light())
    all_issues.extend(check_datacapture())
    all_issues.extend(check_common_issues())
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if all_issues:
        print(f"\n⚠ FOUND {len(all_issues)} ISSUES:\n")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
        
        print("\n" + "=" * 60)
        print("FIX:")
        print("  Run: python scripts/fix_postprocess_settings.py")
        print("  Run: python scripts/optimize_lighting.py")
        print("=" * 60)
    else:
        print("\n✓ All settings look correct!")
        print("\nIf rendering still looks bad, check:")
        print("  1. Is SkyLight added in UE5? (ambient fill light)")
        print("  2. Is Lumen enabled? (Project Settings > Rendering)")
        print("  3. Did you build lighting? (Build > Lighting Quality > Production)")

if __name__ == "__main__":
    main()
