#!/usr/bin/env python3
"""Apply normalization scales to all vehicle actors in UE5."""

from vantagecv.ue5_bridge import UE5Bridge
from vantagecv.research_v2.config import ResearchConfig

def main():
    b = UE5Bridge()
    config = ResearchConfig()
    
    print("Applying normalization scales to vehicles...")
    print("=" * 70)
    
    scales = config.vehicles.vehicle_normalization_scales
    
    success_count = 0
    for class_name, actors in config.vehicles.vehicle_actors.items():
        for actor_name in actors:
            scale = scales.get(actor_name, 1.0)
            path = f'/Game/automobile.automobile:PersistentLevel.{actor_name}'
            
            try:
                # Apply normalization scale
                b.call_function(path, 'SetActorScale3D', {
                    'NewScale3D': {'X': scale, 'Y': scale, 'Z': scale}
                })
                
                # Hide the actor
                b.call_function(path, 'SetActorHiddenInGame', {'bNewHidden': True})
                
                print(f"  {actor_name:25s} [{class_name:10s}] Scale={scale:.3f} - APPLIED")
                success_count += 1
                
            except Exception as e:
                print(f"  {actor_name:25s} FAILED: {e}")
    
    print("=" * 70)
    print(f"Applied scales to {success_count} vehicles (all hidden)")
    print("\nVehicles now have consistent, realistic sizes!")

if __name__ == "__main__":
    main()
