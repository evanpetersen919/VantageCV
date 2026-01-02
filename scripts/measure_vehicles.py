#!/usr/bin/env python3
"""
Discover actual vehicle sizes and calculate normalization scales.

This script queries UE5 for the actual bounding box of each vehicle actor,
then calculates a normalization scale to bring them to realistic sizes.
"""

from vantagecv.ue5_bridge import UE5Bridge
from vantagecv.research_v2.config import ResearchConfig

# Target sizes in centimeters (realistic vehicle dimensions)
TARGET_SIZES = {
    "car": {"length": 450, "width": 180, "height": 150},       # 4.5m x 1.8m x 1.5m
    "truck": {"length": 700, "width": 250, "height": 300},     # 7m x 2.5m x 3m
    "bus": {"length": 1200, "width": 250, "height": 350},      # 12m x 2.5m x 3.5m
    "motorcycle": {"length": 220, "width": 80, "height": 120}, # 2.2m x 0.8m x 1.2m
    "bicycle": {"length": 180, "width": 60, "height": 110},    # 1.8m x 0.6m x 1.1m
}

def main():
    b = UE5Bridge()
    config = ResearchConfig()
    
    print("Querying actual vehicle bounds from UE5...")
    print("=" * 90)
    
    normalization_scales = {}
    
    for class_name, actors in config.vehicles.vehicle_actors.items():
        target = TARGET_SIZES.get(class_name, TARGET_SIZES["car"])
        target_length = target["length"]
        
        print(f"\n{class_name.upper()} (target length: {target_length} cm)")
        print("-" * 90)
        
        for actor_name in actors:
            path = f'/Game/automobile.automobile:PersistentLevel.{actor_name}'
            try:
                # Get actor bounds - returns Origin and BoxExtent (half-extents)
                result = b.call_function(path, 'GetActorBounds', {'bOnlyCollidingComponents': False})
                
                extent = result.get('BoxExtent', {})
                origin = result.get('Origin', {})
                
                # BoxExtent is half the size, so multiply by 2
                length = extent.get('X', 0) * 2  # X is typically forward/length
                width = extent.get('Y', 0) * 2   # Y is typically lateral/width
                height = extent.get('Z', 0) * 2  # Z is up/height
                
                # Calculate scale needed to normalize to target size
                # Use length as the primary dimension for normalization
                if length > 0:
                    norm_scale = target_length / length
                else:
                    norm_scale = 1.0
                
                # Store the normalization scale
                normalization_scales[actor_name] = {
                    "class": class_name,
                    "actual_size": {"length": length, "width": width, "height": height},
                    "target_length": target_length,
                    "norm_scale": round(norm_scale, 4),
                }
                
                status = "OK" if 0.5 <= norm_scale <= 2.0 else "NEEDS SCALING"
                print(f"  {actor_name:25s} Actual: {length:7.0f} x {width:6.0f} x {height:6.0f} cm  "
                      f"Scale: {norm_scale:.3f}  [{status}]")
                
            except Exception as e:
                print(f"  {actor_name:25s} ERROR: {e}")
                normalization_scales[actor_name] = {"class": class_name, "norm_scale": 1.0, "error": str(e)}
    
    print("\n" + "=" * 90)
    print("\nNORMALIZATION SCALES (copy to config):")
    print("-" * 90)
    
    # Output in Python dict format for config
    print("vehicle_normalization_scales = {")
    for actor_name, data in normalization_scales.items():
        scale = data.get('norm_scale', 1.0)
        print(f'    "{actor_name}": {scale},  # {data.get("class", "?")}')
    print("}")
    
    print("\n" + "=" * 90)
    print("\nTo apply these scales, run: python scripts/apply_vehicle_scales.py")

if __name__ == "__main__":
    main()
