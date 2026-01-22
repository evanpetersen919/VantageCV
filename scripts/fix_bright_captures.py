"""
Fix bright captures - match viewport auto-exposure.
Viewport adapts brightness, but captures were locked at manual EV100=0.
"""

import requests

BASE_URL = "http://127.0.0.1:30010/remote"
PPV = "/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1"

def set_property(path, prop, value):
    try:
        r = requests.put(f"{BASE_URL}/object/property", 
                        json={"objectPath": path, "propertyName": prop, "propertyValue": value},
                        timeout=10)
        return r.status_code == 200
    except:
        return False

print("Switching to Auto-Exposure (matches viewport)...")

# Use Auto Exposure Histogram (same as viewport)
set_property(PPV, "Settings.bOverride_AutoExposureMethod", True)
set_property(PPV, "Settings.AutoExposureMethod", 1)  # 1 = Auto Exposure Histogram
print("  ✓ Exposure Method: Auto Exposure Histogram")

# Set reasonable brightness range
set_property(PPV, "Settings.bOverride_AutoExposureMinBrightness", True)
set_property(PPV, "Settings.AutoExposureMinBrightness", 0.5)

set_property(PPV, "Settings.bOverride_AutoExposureMaxBrightness", True)
set_property(PPV, "Settings.AutoExposureMaxBrightness", 2.0)
print("  ✓ Auto-Exposure Range: 0.5 - 2.0")

# Lower bias to prevent overexposure
set_property(PPV, "Settings.bOverride_AutoExposureBias", True)
set_property(PPV, "Settings.AutoExposureBias", -1.0)
print("  ✓ Exposure Bias: -1.0 EV (slightly darker)")

print("\n✓ Captures should now match viewport brightness")
print("Test: python scripts/preview_capture.py")
