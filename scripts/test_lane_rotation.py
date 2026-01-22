"""
Test script to specifically test lane rotation validation.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.research_v2.vehicle_spawn_controller import VehicleSpawnController
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Initialize controller
spawner = VehicleSpawnController(
    host="127.0.0.1",
    port=30010,
    level_path="/Game/VantageCV/AutomobileV2",
    anchor_config_path="configs/levels/automobileV2_anchors.yaml"
)

print("\n" + "=" * 60)
print("LANE ROTATION VALIDATION TEST")
print("=" * 60)

# Detect vehicles
print("\nDetecting vehicle pool...")
spawner.detect_vehicle_pool()

# Access lanes from loaded config
all_lanes = spawner.anchor_config.get("lanes", {}).get("definitions", [])
print(f"\nTotal lanes loaded: {len(all_lanes)}")

# Filter for Location 2 lanes
location_2_lanes = [lane for lane in all_lanes if 20000.0 <= lane['StartY'] <= 39600.0]

print(f"Location 2 lanes: {len(location_2_lanes)}")
for lane in location_2_lanes:
    print(f"  Lane {lane['id']}: {lane['Start']} → {lane['End']}")

# Spawn buses on lanes in Location 2
print("\nSpawning buses on Location 2 lanes...")
spawner.location_filter = {
    "min_y": 20000.0,
    "max_y": 39600.0
}

result = spawner.spawn_lane(
    seed=1234,
    count=3,
    vehicle_types=["bus"]
)

print(f"\n{result['spawned']}/{result['requested']} buses spawned")
print(f"Skipped: {result['skipped']}")

# Check for rotation errors
if result['spawned'] < result['requested']:
    print(f"\n⚠️ Some spawns were skipped - check logs above for rotation errors")
else:
    print(f"\n✓ All spawns successful")

print("\n" + "=" * 60)
