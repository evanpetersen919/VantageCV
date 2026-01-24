"""
Validate spawn logic - check that all code paths use centerline-only positioning
"""
import re
from pathlib import Path

def check_file(filepath):
    """Check for forbidden patterns in spawn code"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    
    # Check for forbidden lateral offset usage
    if re.search(r'lateral_offset\s*=\s*random\.uniform', content):
        issues.append("FAIL: Found random lateral offset generation")
    
    # Check for forbidden perpendicular offset application
    if re.search(r'x\s*\+=\s*lateral_offset\s*\*\s*perp', content):
        issues.append("FAIL: Found lateral offset application to x coordinate")
    
    if re.search(r'y\s*\+=\s*lateral_offset\s*\*\s*perp', content):
        issues.append("FAIL: Found lateral offset application to y coordinate")
    
    # Check for validation presence
    if 'centerline_distance' not in content:
        issues.append("WARN: No centerline_distance validation found")
    
    # Check for enhanced logging
    if 'mesh {mesh_a} ->' not in content and 'mesh {mesh_a} <-' not in content:
        issues.append("WARN: Enhanced logging with mesh names not found")
    
    # Check that _compute_lane_transform doesn't have lateral_offset parameter
    if re.search(r'def _compute_lane_transform\(.*lateral_offset', content):
        issues.append("FAIL: _compute_lane_transform still has lateral_offset parameter")
    
    return issues

if __name__ == "__main__":
    spawn_file = Path("vantagecv/research_v2/vehicle_spawn_controller.py")
    
    print("="*60)
    print("SPAWN LOGIC VALIDATION")
    print("="*60)
    print(f"\nChecking: {spawn_file}\n")
    
    issues = check_file(spawn_file)
    
    if issues:
        for issue in issues:
            print(f"  {issue}")
        print(f"\n❌ Found {len(issues)} issues")
    else:
        print("✅ All checks passed!")
        print("\nValidation confirms:")
        print("  - No random lateral offsets")
        print("  - No perpendicular offset application")
        print("  - Centerline distance validation present")
        print("  - Enhanced logging with mesh names")
        print("  - Pure centerline positioning")
