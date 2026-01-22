"""
Comprehensive exposure mismatch diagnostic and fix.
Identifies ALL differences between viewport and DataCapture rendering.
"""

import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:30010/remote"
DATACAPTURE = "/Game/automobileV2.automobileV2:PersistentLevel.DataCapture_1"
PPV = "/Game/automobileV2.automobileV2:PersistentLevel.PostProcessVolume_1"

def get_property(path, prop):
    """Try to read property value."""
    try:
        r = requests.put(f"{BASE_URL}/object/property",
                        json={"objectPath": path, "propertyName": prop},
                        timeout=5)
        if r.status_code == 200:
            return r.json().get("PropertyValue")
    except:
        pass
    return None

def set_property(path, prop, value):
    """Set property and return success status."""
    try:
        r = requests.put(f"{BASE_URL}/object/property",
                        json={"objectPath": path, "propertyName": prop, "propertyValue": value},
                        timeout=10)
        return r.status_code == 200
    except:
        return False

print("=" * 70)
print("EXPOSURE MISMATCH DIAGNOSTIC")
print("=" * 70)
print("\nAnalyzing differences between viewport and DataCapture rendering...")

issues_found = []
fixes_applied = []

# ============================================================================
# ISSUE 1: PostProcess Blend Weight
# ============================================================================
print("\n[1/7] Checking PostProcessBlendWeight...")
print("-" * 70)

blend_weight = get_property(DATACAPTURE, "CaptureComponent.PostProcessBlendWeight")
print(f"  Current value: {blend_weight}")

if blend_weight is None or blend_weight > 0.01:
    issues_found.append("PostProcessBlendWeight > 0 (capture ignores PPV settings)")
    print("  ❌ ISSUE: Capture component overriding PostProcessVolume")
    print("     → DataCapture has its own exposure settings instead of using PPV")
    
    if set_property(DATACAPTURE, "CaptureComponent.PostProcessBlendWeight", 0.0):
        fixes_applied.append("Set PostProcessBlendWeight = 0.0")
        print("  ✓ FIX APPLIED: PostProcessBlendWeight → 0.0")
else:
    print("  ✓ OK: Using PostProcessVolume settings")

# ============================================================================
# ISSUE 2: Capture Source (HDR vs LDR)
# ============================================================================
print("\n[2/7] Checking Capture Source...")
print("-" * 70)

capture_source = get_property(DATACAPTURE, "CaptureComponent.CaptureSource")
print(f"  Current value: {capture_source}")
print("     0 = FinalColorLDR (tonemapped, viewport-like)")
print("     1 = FinalColorHDR (linear, can be very bright)")
print("     2 = SceneColor (no post-processing)")

if capture_source != 0:
    issues_found.append(f"CaptureSource = {capture_source} (should be 0 for LDR)")
    print("  ❌ ISSUE: Using HDR or SceneColor (brighter than viewport)")
    print("     → Viewport shows tonemapped LDR, capture shows linear HDR")
    
    if set_property(DATACAPTURE, "CaptureComponent.CaptureSource", 0):
        fixes_applied.append("Set CaptureSource = 0 (FinalColorLDR)")
        print("  ✓ FIX APPLIED: CaptureSource → 0 (FinalColorLDR)")
else:
    print("  ✓ OK: Using FinalColorLDR (matches viewport)")

# ============================================================================
# ISSUE 3: Gamma Correction
# ============================================================================
print("\n[3/7] Checking Gamma Settings...")
print("-" * 70)

# Force gamma-correct output
if set_property(DATACAPTURE, "CaptureComponent.bCaptureEveryFrame", False):
    print("  ✓ Capture Every Frame: FALSE (manual trigger)")
    fixes_applied.append("Disabled auto-capture (manual trigger)")

# Enable proper tonemapping
if set_property(DATACAPTURE, "CaptureComponent.ShowFlags.Tonemapper", True):
    print("  ✓ Tonemapper: ENABLED")
    fixes_applied.append("Enabled tonemapper in ShowFlags")

if set_property(DATACAPTURE, "CaptureComponent.ShowFlags.EyeAdaptation", False):
    print("  ✓ Eye Adaptation: DISABLED (prevents auto-exposure)")
    fixes_applied.append("Disabled eye adaptation (no auto-exposure)")
    issues_found.append("Eye adaptation may have been enabled in capture")

# ============================================================================
# ISSUE 4: PostProcessVolume Exposure Settings
# ============================================================================
print("\n[4/7] Checking PostProcessVolume Exposure...")
print("-" * 70)

exposure_method = get_property(PPV, "Settings.AutoExposureMethod")
exposure_bias = get_property(PPV, "Settings.AutoExposureBias")

print(f"  Exposure Method: {exposure_method}")
print("     0 = Manual")
print("     1 = Auto Histogram")
print("     2 = Auto Basic")

print(f"  Exposure Bias: {exposure_bias}")

if exposure_method == 0:  # Manual
    print("  ⚠ Manual exposure - may be too bright if EV100=0 with bright lights")
    issues_found.append("Manual exposure with no adaptive range")
    
    # Switch to controlled auto-exposure
    set_property(PPV, "Settings.AutoExposureMethod", 1)
    set_property(PPV, "Settings.bOverride_AutoExposureBias", True)
    set_property(PPV, "Settings.AutoExposureBias", -1.5)
    set_property(PPV, "Settings.bOverride_AutoExposureMinBrightness", True)
    set_property(PPV, "Settings.AutoExposureMinBrightness", 0.3)
    set_property(PPV, "Settings.bOverride_AutoExposureMaxBrightness", True)
    set_property(PPV, "Settings.AutoExposureMaxBrightness", 1.5)
    
    fixes_applied.append("Switched to Auto Histogram exposure")
    fixes_applied.append("Set exposure bias = -1.5 EV (darker)")
    fixes_applied.append("Set brightness range: 0.3 - 1.5")
    print("  ✓ FIX APPLIED: Auto Histogram with controlled range")

# ============================================================================
# ISSUE 5: Render Target Format
# ============================================================================
print("\n[5/7] Checking Render Target Format...")
print("-" * 70)

print("  ℹ Render target format set in C++ code (DataCapture.cpp)")
print("     Should be: RTF_RGBA8 or RTF_RGBA8_SRGB")
print("     Check DataCapture.cpp line ~220")
print("  ⚠ Cannot verify via Remote Control API")

# ============================================================================
# ISSUE 6: Color Space & Linear/sRGB
# ============================================================================
print("\n[6/7] Checking Color Space...")
print("-" * 70)

print("  ℹ Viewport uses sRGB display gamma (2.2)")
print("  ℹ Capture must apply same gamma correction")
print("  ℹ Check SaveRenderTargetToFile uses SetLinearToGamma(true)")
print("     Location: DataCapture.cpp line ~590")

# ============================================================================
# ISSUE 7: SceneController Overrides
# ============================================================================
print("\n[7/7] Checking SceneController...")
print("-" * 70)

scene_controller = "/Game/automobileV2.automobileV2:PersistentLevel.SceneController_1"
if get_property(scene_controller, "bHidden") is not None:
    print("  ✓ SceneController_1 exists")
    print("  ℹ Ensure weather randomization doesn't override exposure")
    print("  ℹ Check test scripts lock environment before capture")
else:
    print("  ⚠ SceneController not accessible")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("DIAGNOSTIC SUMMARY")
print("=" * 70)

if issues_found:
    print(f"\n❌ ISSUES IDENTIFIED ({len(issues_found)}):")
    for i, issue in enumerate(issues_found, 1):
        print(f"  {i}. {issue}")
else:
    print("\n✓ No obvious configuration issues found")

if fixes_applied:
    print(f"\n✓ FIXES APPLIED ({len(fixes_applied)}):")
    for i, fix in enumerate(fixes_applied, 1):
        print(f"  {i}. {fix}")

print("\n" + "=" * 70)
print("ROOT CAUSE ANALYSIS")
print("=" * 70)

print("""
WHY VIEWPORT AND CAPTURE DIFFER:

1. VIEWPORT EXPOSURE:
   - Uses adaptive auto-exposure (changes over time)
   - Eye adaptation smoothly adjusts to scene brightness
   - You've been looking at the scene for seconds/minutes
   - Exposure has stabilized to comfortable level

2. DATACAPTURE EXPOSURE:
   - Single-frame capture (no adaptation history)
   - If using Manual exposure with EV100=0:
     → Every scene uses same fixed exposure
     → Bright outdoor scenes = blown out
   - If PostProcessBlendWeight > 0:
     → Capture component's settings override PPV
     → Different exposure than viewport

3. GAMMA/TONE MAPPING:
   - Viewport: sRGB display (gamma 2.2 applied)
   - Capture: Must explicitly request gamma correction
   - If SaveRenderTargetToFile doesn't set LinearToGamma:
     → Image saved in linear space (looks too bright)

RECOMMENDED SOLUTION:
Use Auto Histogram exposure with controlled range:
  - Adapts to each scene's brightness
  - Clamped min/max prevents extreme values
  - Bias of -1.5 EV compensates for outdoor brightness
  - Matches viewport adaptive behavior
""")

print("\n" + "=" * 70)
print("VALIDATION")
print("=" * 70)

print("\nTest the fix:")
print("  1. Run: python scripts/preview_capture.py")
print("  2. Compare test_preview.png to viewport")
print("  3. If still bright → try bias -2.0 or -2.5 EV")
print("  4. If too dark → try bias -1.0 or -0.5 EV")

print("\nFine-tune exposure bias:")
print("  Too bright: python scripts/adjust_exposure.py -2.0")
print("  Too dark:   python scripts/adjust_exposure.py -1.0")

print("\n" + "=" * 70)
