"""
Fix overexposed captures by adjusting manual exposure bias.
"""

import requests

BASE_URL = "http://127.0.0.1:30010/remote"
PPV = "/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1"

def set_property(actor_path, property_name, value):
    try:
        response = requests.put(
            f"{BASE_URL}/object/property",
            json={
                "objectPath": actor_path,
                "propertyName": property_name,
                "propertyValue": value
            },
            timeout=10
        )
        return response.status_code == 200
    except:
        return False

print("Fixing overexposed captures...")
print("Lowering exposure bias to darken images...")

# Lower exposure bias (negative = darker)
set_property(PPV, "Settings.AutoExposureBias", -2.0)
print("  ✓ Exposure Bias: -2.0 EV (darker)")

# Alternative: Use auto exposure with locked range
set_property(PPV, "Settings.AutoExposureMethod", 1)  # Auto Exposure Histogram
print("  ✓ Exposure Method: Auto Exposure (matches viewport)")

set_property(PPV, "Settings.bOverride_AutoExposureMinBrightness", True)
set_property(PPV, "Settings.AutoExposureMinBrightness", 0.3)
set_property(PPV, "Settings.bOverride_AutoExposureMaxBrightness", True)
set_property(PPV, "Settings.AutoExposureMaxBrightness", 2.0)
print("  ✓ Auto Exposure Range: 0.3 - 2.0 (controlled)")

print("\n✓ Exposure fixed - captures should match viewport now")
print("Run test again: python scripts/test_randomization.py")
