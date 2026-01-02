#!/usr/bin/env python3
"""Check and reset vehicle visibility and scale in UE5."""

from vantagecv.ue5_bridge import UE5Bridge
from vantagecv.research_v2.config import ResearchConfig

def main():
    b = UE5Bridge()
    config = ResearchConfig()
    
    all_actors = []
    for class_name, actors in config.vehicles.vehicle_actors.items():
        all_actors.extend([(a, class_name) for a in actors])
    
    print("Resetting all vehicles to hidden and scale 1.0...")
    print("-" * 70)
    
    reset_count = 0
    for actor_name, class_name in all_actors:
        path = f'/Game/automobile.automobile:PersistentLevel.{actor_name}'
        try:
            # Hide the actor
            b.call_function(path, 'SetActorHiddenInGame', {'bNewHidden': True})
            
            # Reset scale to 1.0
            b.call_function(path, 'SetActorScale3D', {'NewScale3D': {'X': 1.0, 'Y': 1.0, 'Z': 1.0}})
            
            # Verify scale
            scale = b.call_function(path, 'GetActorScale3D', {}).get('ReturnValue', {})
            sx, sy, sz = scale.get('X', 1), scale.get('Y', 1), scale.get('Z', 1)
            
            print(f"  {actor_name:25s} [{class_name:10s}] HIDDEN, Scale=({sx:.2f}, {sy:.2f}, {sz:.2f})")
            reset_count += 1
        except Exception as e:
            print(f"  {actor_name:25s} FAILED: {e}")
    
    print("-" * 70)
    print(f"Reset {reset_count}/{len(all_actors)} vehicles")

if __name__ == "__main__":
    main()
