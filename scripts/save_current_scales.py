#!/usr/bin/env python3
"""Read current vehicle scales from UE5 and save to config."""

import requests
import sys
sys.path.insert(0, "f:/vscode/VantageCV")

from vantagecv.research_v2.config import ResearchConfig

UE5_URL = "http://localhost:30010/remote/object/call"

def get_actor_scale(actor_name: str) -> float:
    """Get current uniform scale of an actor."""
    actor_path = f"/Game/automobile.automobile:PersistentLevel.{actor_name}"
    
    payload = {
        "objectPath": actor_path,
        "functionName": "GetActorScale3D",
        "parameters": {},
        "generateTransaction": False
    }
    
    resp = requests.put(UE5_URL, json=payload, timeout=5)
    if resp.ok:
        result = resp.json()
        scale = result.get("ReturnValue", {})
        # Return X component (should be uniform)
        return scale.get("X", 1.0)
    return 1.0

def main():
    config = ResearchConfig()
    
    print("Reading current scales from UE5...")
    print("=" * 70)
    
    current_scales = {}
    
    for class_name, actors in config.vehicles.vehicle_actors.items():
        print(f"\n{class_name.upper()}:")
        for actor_name in actors:
            scale = get_actor_scale(actor_name)
            current_scales[actor_name] = round(scale, 3)
            print(f"  {actor_name}: {scale:.3f}")
    
    print("\n" + "=" * 70)
    print("\nGenerate config update? This will print Python code to update config.py")
    response = input("Continue? (y/n): ")
    
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    print("\n" + "=" * 70)
    print("COPY THIS TO config.py:")
    print("=" * 70)
    print("\nvehicle_normalization_scales: dict[str, float] = {")
    
    for actor_name, scale in sorted(current_scales.items()):
        print(f'    "{actor_name}": {scale},')
    
    print("}")
    print("\n" + "=" * 70)
    print("\nInstructions:")
    print("1. Copy the dict above")
    print("2. Open vantagecv/research_v2/config.py")
    print("3. Find the vehicle_normalization_scales dict")
    print("4. Replace it with the new dict")
    print("=" * 70)

if __name__ == "__main__":
    main()
