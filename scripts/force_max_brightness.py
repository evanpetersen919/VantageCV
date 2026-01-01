"""Force maximum brightness in UE5 scene and test capture."""
import requests
import time
from PIL import Image
import numpy as np

UE5_URL = "http://localhost:30010"

def set_property(object_path, property_name, value):
    """Set property on UE5 object."""
    resp = requests.put(
        f"{UE5_URL}/remote/object/property",
        json={
            "objectPath": object_path,
            "propertyName": property_name,
            "propertyValue": {property_name: value}
        }
    )
    print(f"Set {property_name} = {value}: {resp.status_code}")
    return resp

def call_function(object_path, function_name, **parameters):
    """Call function on UE5 object."""
    resp = requests.put(
        f"{UE5_URL}/remote/object/call",
        json={
            "objectPath": object_path,
            "functionName": function_name,
            "parameters": parameters
        }
    )
    return resp

# Force MAXIMUM brightness settings
print("=" * 60)
print("FORCING MAXIMUM BRIGHTNESS")
print("=" * 60)

# DirectionalLight - EXTREME intensity
light_path = "/Game/automobile.automobile:PersistentLevel.DirectionalLight_4"
print("\n1. DirectionalLight settings:")
set_property(light_path, "Intensity", 50.0)  # 5x normal max
set_property(light_path, "LightColor", {"R": 255, "G": 255, "B": 255, "A": 255})

# SkyLight - MAX intensity
sky_path = "/Game/automobile.automobile:PersistentLevel.SkyLight_2"
print("\n2. SkyLight settings:")
set_property(sky_path, "Intensity", 10.0)  # Very high

# PostProcessVolume - EXTREME exposure
ppv_path = "/Game/automobile.automobile:PersistentLevel.PostProcessVolume_1"
print("\n3. PostProcessVolume settings:")
set_property(ppv_path, "AutoExposureBias", 15.0)  # 32x brighter
set_property(ppv_path, "AutoExposureMinBrightness", 5.0)
set_property(ppv_path, "AutoExposureMaxBrightness", 50.0)

# DataCapture - Force EXTREME overrides
capture_path = "/Game/automobile.automobile:PersistentLevel.DataCapture_1"
print("\n4. DataCapture exposure (via constructor call):")

# Wait for settings to apply
time.sleep(2)

# Capture frame
print("\n5. Capturing frame...")
resp = call_function(capture_path, "CaptureFrame")
print(f"Capture result: {resp.json()}")

# Wait for file write
time.sleep(2)

# Analyze brightness
print("\n" + "=" * 60)
print("BRIGHTNESS ANALYSIS")
print("=" * 60)

img_path = "data/synthetic/test/images/frame_000000.png"
try:
    img = Image.open(img_path)
    arr = np.array(img)
    
    mean = arr.mean()
    print(f"Mean brightness: {mean:.1f}/255")
    print(f"Min: {arr.min()}, Max: {arr.max()}")
    print(f"RGB means: R={arr[:,:,0].mean():.1f}, G={arr[:,:,1].mean():.1f}, B={arr[:,:,2].mean():.1f}")
    
    if mean > 120:
        print("\n✓✓✓ SUCCESS! Image is BRIGHT! ✓✓✓")
    elif mean > 80:
        print("\n⚠ MODERATE - Getting better but still need more brightness")
    else:
        print("\n✗✗✗ STILL DARK - Scene lighting issue ✗✗✗")
        
except Exception as e:
    print(f"Error analyzing image: {e}")

print("\n" + "=" * 60)
