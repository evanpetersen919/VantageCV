"""
Test GetActorBounds via Remote Control API
"""

import requests
import yaml

# Load vehicle config
with open("configs/levels/automobileV2_vehicles.yaml", "r") as f:
    config = yaml.safe_load(f)

level_path = config["level"]["path"]
base_url = "http://127.0.0.1:30010/remote"
session = requests.Session()

# Get vehicle names
vehicles = []
for category, vehicle_list in config.get("vehicles", {}).items():
    for v in vehicle_list:
        vehicles.append((v["name"], category))

print("=" * 60)
print("TESTING GetActorBounds API")
print("=" * 60)

# Test on first 5 vehicles
for vehicle_name, category in vehicles[:5]:
    path = f"{level_path}:PersistentLevel.{vehicle_name}"
    print(f"\n{vehicle_name} ({category}):")
    
    try:
        response = session.put(
            f"{base_url}/object/call",
            json={
                "objectPath": path,
                "functionName": "GetActorBounds",
                "parameters": {
                    "bOnlyCollidingComponents": False
                }
            },
            timeout=2.0
        )
        
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"  Response: {result}")
            
            origin = result.get("Origin", {})
            extent = result.get("BoxExtent", {})
            
            if origin and extent:
                print(f"  Origin: ({origin.get('X', 0):.0f}, {origin.get('Y', 0):.0f}, {origin.get('Z', 0):.0f})")
                print(f"  Extent: ({extent.get('X', 0):.0f}, {extent.get('Y', 0):.0f}, {extent.get('Z', 0):.0f})")
                print(f"  Full Size: {extent.get('X', 0)*2:.0f} x {extent.get('Y', 0)*2:.0f} x {extent.get('Z', 0)*2:.0f} cm")
        else:
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"  Exception: {e}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
