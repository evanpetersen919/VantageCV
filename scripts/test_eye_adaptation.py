"""
DIAGNOSTIC: Check if viewport is using Eye Adaptation (auto-exposure)
This would explain why viewport looks good but capture is white.
"""
import subprocess

print("\n=== INSTRUCTIONS ===\n")
print("In UE5 Editor:")
print("1. Click in the viewport")
print("2. Press the ~ key (tilde) to open console")
print("3. Type: show EyeAdaptation")
print("4. Press Enter")
print("\nDoes the viewport become WHITE/BRIGHT like the capture?")
print("  YES → Viewport is using Eye Adaptation (auto-exposure)")
print("        DataCapture can't use it because it's disabled in ShowFlags")
print("        SOLUTION: Enable Eye Adaptation in DataCapture")
print("\n  NO → Viewport stays the same")
print("       Problem is something else")
print("\nType 'show EyeAdaptation' again to toggle it back on.")
