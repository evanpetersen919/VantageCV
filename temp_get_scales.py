#!/usr/bin/env python3
"""Query UE5 for current scales of all vehicles in the pool"""
import requests
import yaml

# Load current vehicle config
with open("configs/levels/automobileV2_vehicles.yaml", "r") as f:
    config = yaml.safe_load(f)

vehicles = config["vehicles"]
level_path = config["level"]["path"]

print("Fetching current scales from UE5...\n")

updated_vehicles = {}

for category, vehicle_list in vehicles.items():
    updated_vehicles[category] = []
    
    for vehicle in vehicle_list:
        name = vehicle["name"]
        path = f"{level_path}:PersistentLevel.{name}"
        
        # Use the same method as vehicle_spawn_controller
        response = requests.put(
            "http://127.0.0.1:30010/remote/object/call",
            json={
                "objectPath": path,
                "functionName": "GetActorScale3D"
            },
            timeout=5.0
        )
        
        if response.status_code == 200:
            result = response.json()
            if "ReturnValue" in result:
                scale = result["ReturnValue"]
                vehicle["default_transform"]["scale"] = {
                    "X": round(scale["X"], 2),
                    "Y": round(scale["Y"], 2),
                    "Z": round(scale["Z"], 2)
                }
                print(f"✓ {name}: Scale=({scale['X']:.2f}, {scale['Y']:.2f}, {scale['Z']:.2f})")
            else:
                print(f"✗ {name}: No ReturnValue - {result}")
        else:
            print(f"✗ {name}: HTTP {response.status_code}")
        
        updated_vehicles[category].append(vehicle)

# Update config
config["vehicles"] = updated_vehicles

# Write updated config
with open("configs/levels/automobileV2_vehicles.yaml", "w") as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

print(f"\n✅ Updated automobileV2_vehicles.yaml with current scales")
