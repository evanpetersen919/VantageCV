#!/usr/bin/env python3
"""
Interactive Spawn Test Script - Manual Validation Tool

PURPOSE:
Debug and validate vehicle spawning one case at a time without modifying main test script.

CRITICAL RULES:
- NO spawn logic changes
- Reuses EXACT same functions from VehicleSpawnController
- Spawns ONE vehicle per test
- Full cleanup after each test
- Deterministic with seed control

WORKFLOW:
1. Select location (1-7)
2. Select zone type (Lane/Parking/Sidewalk)
3. Spawn ONE vehicle
4. Inspect results
5. Cleanup
6. Repeat or exit
"""
import sys
import time
import random
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.research_v2.vehicle_spawn_controller import VehicleSpawnController

# =============================================================================
# LOCATION BOUNDARIES (must match main test script exactly)
# =============================================================================

LOCATION_BOUNDARIES = {
    1: (400, 19600),
    2: (19600, 39600),
    3: (39600, 59600),
    4: (59600, 79600),
    5: (79600, 97600),
    6: (97600, 117600),
    7: (117600, 137600),
}

# =============================================================================
# VEHICLE ZONE CONSTRAINTS (must match main test script exactly)
# =============================================================================

VEHICLE_ZONE_CONSTRAINTS = {
    "bicycle": ["parking", "sidewalk"],
    "motorcycle": ["parking"],
    "bus": ["lane"],
    "car": ["parking", "lane"],
    "truck": ["parking", "lane"],
}

# Zone type to allowed vehicle types
ZONE_TYPE_VEHICLES = {
    "lane": ["car", "truck", "bus"],
    "parking": ["car", "truck", "motorcycle"],
    "sidewalk": ["bicycle"],
}

# =============================================================================
# ANCHOR CONFIG FILTERING (reused from main test script)
# =============================================================================

def filter_anchor_config_by_location(spawner, location: int) -> Dict:
    """Filter anchor config to only zones within a specific location's Y boundaries.
    
    This fetches actor positions from UE5 since the YAML only stores actor names.
    MUST match main test script exactly.
    """
    if not spawner.anchor_config or location not in LOCATION_BOUNDARIES:
        return spawner.anchor_config
    
    y_min, y_max = LOCATION_BOUNDARIES[location]
    filtered_config = {}
    
    # Filter parking anchors (list of dicts with name/position/yaw or old format strings)
    if 'parking' in spawner.anchor_config:
        parking_section = spawner.anchor_config['parking'].copy()
        anchors = parking_section.get('anchors', [])
        
        filtered_parking = []
        for anchor in anchors:
            # Handle both new format (dict) and old format (string)
            if isinstance(anchor, dict):
                anchor_name = anchor.get('name')
                # Use position from YAML if available
                if 'position' in anchor:
                    y_pos = anchor['position'][1]  # Y is second element
                    if y_min <= y_pos < y_max:
                        filtered_parking.append(anchor)
                else:
                    # Fallback to fetching from UE5
                    transform = spawner._get_anchor_transform(anchor_name)
                    if transform:
                        y_pos = transform['location'].get('Y', 0)
                        if y_min <= y_pos < y_max:
                            filtered_parking.append(anchor)
            else:
                # Old format: anchor is just a string name
                transform = spawner._get_anchor_transform(anchor)
                if transform:
                    y_pos = transform['location'].get('Y', 0)
                    if y_min <= y_pos < y_max:
                        filtered_parking.append(anchor)
        
        parking_section['anchors'] = filtered_parking
        filtered_config['parking'] = parking_section
    
    # Filter lanes (list of dicts with start/end anchor names)
    if 'lanes' in spawner.anchor_config:
        lanes_section = spawner.anchor_config['lanes'].copy()
        lane_defs = lanes_section.get('definitions', [])
        
        filtered_lanes = []
        for lane in lane_defs:
            # Handle both old format (start/end) and new format (start_anchor/end_anchor)
            start_name = lane.get('start_anchor') or lane.get('start')
            if start_name:
                transform = spawner._get_anchor_transform(start_name)
                if transform:
                    y_pos = transform['location'].get('Y', 0)
                    if y_min <= y_pos < y_max:
                        filtered_lanes.append(lane)
        
        lanes_section['definitions'] = filtered_lanes
        filtered_config['lanes'] = lanes_section
    
    # Filter sidewalks (both singular 'sidewalk' and plural 'sidewalks')
    # Handle new format (sidewalks with definitions list)
    if 'sidewalks' in spawner.anchor_config:
        sidewalks_section = spawner.anchor_config['sidewalks'].copy()
        sidewalk_defs = sidewalks_section.get('definitions', [])
        
        filtered_sidewalks = []
        for sidewalk in sidewalk_defs:
            anchor_1_name = sidewalk.get('anchor_1')
            if anchor_1_name:
                transform = spawner._get_anchor_transform(anchor_1_name)
                if transform:
                    y_pos = transform['location'].get('Y', 0)
                    if y_min <= y_pos < y_max:
                        filtered_sidewalks.append(sidewalk)
        
        sidewalks_section['definitions'] = filtered_sidewalks
        filtered_config['sidewalks'] = sidewalks_section
    
    # Handle old format (singular sidewalk with anchor_1/anchor_2)
    elif 'sidewalk' in spawner.anchor_config:
        sidewalk_section = spawner.anchor_config['sidewalk']
        anchor_1_name = sidewalk_section.get('anchor_1')
        
        if anchor_1_name:
            transform = spawner._get_anchor_transform(anchor_1_name)
            if transform:
                y_pos = transform['location'].get('Y', 0)
                if y_min <= y_pos < y_max:
                    filtered_config['sidewalk'] = sidewalk_section
    
    return filtered_config


# =============================================================================
# INTERACTIVE SPAWN TEST
# =============================================================================

class InteractiveSpawnTest:
    def __init__(self):
        self.spawner = VehicleSpawnController(
            host="127.0.0.1",
            port=30010,
            level_path="/Game/automobileV2.automobileV2"
        )
        
        # Store original config for reset
        self.original_anchor_config = None
        if self.spawner.anchor_config:
            import copy
            self.original_anchor_config = copy.deepcopy(self.spawner.anchor_config)
        
        # Track spawned vehicles for cleanup
        self.spawned_vehicles = []
        
        # Test counter
        self.test_count = 0
    
    def initialize(self):
        """Initialize vehicle pool"""
        print("\n" + "=" * 70)
        print("INTERACTIVE SPAWN TEST - DEBUG TOOL")
        print("=" * 70)
        print("\nDetecting vehicle pool...")
        self.spawner.detect_vehicle_pool()
        print("\n[OK] Initialization complete")
    
    def select_location(self) -> Optional[int]:
        """Prompt user to select location 1-7"""
        print("\n" + "=" * 70)
        print("STEP 1: SELECT LOCATION")
        print("=" * 70)
        print("\nAvailable locations:")
        for loc_num in sorted(LOCATION_BOUNDARIES.keys()):
            y_min, y_max = LOCATION_BOUNDARIES[loc_num]
            print(f"  {loc_num}: Y ∈ [{y_min}, {y_max})")
        
        while True:
            try:
                user_input = input("\nEnter location (1-7) or 0 to exit: ").strip()
                location = int(user_input)
                if location == 0:
                    return None
                elif location in LOCATION_BOUNDARIES:
                    return location
                else:
                    print(f"[ERROR] Invalid location. Enter 1-7 or 0 to exit.")
            except ValueError:
                print(f"[ERROR] Invalid input. Enter a number 1-7 or 0 to exit.")
            except KeyboardInterrupt:
                print("\n\n[EXIT] Test cancelled.")
                return None
    
    def select_zone_type(self) -> Optional[str]:
        """Prompt user to select zone type"""
        print("\n" + "=" * 70)
        print("STEP 2: SELECT ZONE TYPE")
        print("=" * 70)
        print("\nAvailable zone types:")
        print("  1 = Lane    (cars, trucks, buses)")
        print("  2 = Parking (cars, trucks, motorcycles)")
        print("  3 = Sidewalk (bicycles)")
        
        while True:
            try:
                user_input = input("\nEnter zone type (1-3) or 0 to exit: ").strip()
                choice = int(user_input)
                if choice == 0:
                    return None
                elif choice == 1:
                    return "lane"
                elif choice == 2:
                    return "parking"
                elif choice == 3:
                    return "sidewalk"
                else:
                    print(f"[ERROR] Invalid choice. Enter 1-3 or 0 to exit.")
            except ValueError:
                print(f"[ERROR] Invalid input. Enter a number 1-3 or 0 to exit.")
            except KeyboardInterrupt:
                print("\n\n[EXIT] Test cancelled.")
                return None
    
    def confirm_spawn(self) -> bool:
        """Prompt user to spawn or exit"""
        print("\n" + "=" * 70)
        print("STEP 3: EXECUTE SPAWN")
        print("=" * 70)
        print("\nOptions:")
        print("  1 = Spawn vehicle (will stay visible)")
        print("  0 = Cancel and return to location selection")
        
        while True:
            try:
                user_input = input("\nEnter choice: ").strip()
                choice = int(user_input)
                if choice == 1:
                    return True
                else:
                    return False
            except ValueError:
                print(f"[ERROR] Invalid input. Enter 1 or 0.")
            except KeyboardInterrupt:
                print("\n\n[EXIT] Test cancelled.")
                return False
    
    def prompt_next_action(self) -> str:
        """Prompt user for next action after spawn"""
        print("\n" + "=" * 70)
        print("NEXT ACTION")
        print("=" * 70)
        print("\nOptions:")
        print("  1 = Cleanup and repeat same test (same location + zone)")
        print("  2 = Cleanup and start new test (choose location + zone)")
        print("  0 = Exit (cleanup all vehicles)")
        
        while True:
            try:
                user_input = input("\nEnter choice: ").strip()
                if user_input == "":
                    # Press Enter to repeat
                    return "repeat"
                choice = int(user_input)
                if choice == 1:
                    return "repeat"
                elif choice == 2:
                    return "new"
                else:
                    return "exit"
            except ValueError:
                print(f"[ERROR] Invalid input. Enter 1, 2, or 0.")
            except KeyboardInterrupt:
                print("\n\n[EXIT] Test cancelled.")
                return "exit"
    
    def apply_location_filter(self, location: int):
        """Apply location filter to spawner's anchor config"""
        print(f"\n[FILTER] Applying location {location} filter...")
        
        # Count original
        original_parking = len(self.spawner.anchor_config.get('parking', {}).get('anchors', [])) if self.spawner.anchor_config else 0
        original_lanes = len(self.spawner.anchor_config.get('lanes', {}).get('definitions', [])) if self.spawner.anchor_config else 0
        original_sidewalk = 1 if self.spawner.anchor_config and 'sidewalk' in self.spawner.anchor_config else 0
        
        # Filter
        if self.spawner.anchor_config:
            self.spawner.anchor_config = filter_anchor_config_by_location(self.spawner, location)
        
        # Count filtered
        filtered_parking = len(self.spawner.anchor_config.get('parking', {}).get('anchors', [])) if self.spawner.anchor_config else 0
        filtered_lanes = len(self.spawner.anchor_config.get('lanes', {}).get('definitions', [])) if self.spawner.anchor_config else 0
        filtered_sidewalk = 1 if self.spawner.anchor_config and 'sidewalk' in self.spawner.anchor_config else 0
        
        print(f"  Parking: {original_parking} → {filtered_parking}")
        print(f"  Lanes:   {original_lanes} → {filtered_lanes}")
        print(f"  Sidewalk: {original_sidewalk} → {filtered_sidewalk}")
    
    def reset_location_filter(self):
        """Reset spawner config to original (all locations)"""
        if self.original_anchor_config:
            import copy
            self.spawner.anchor_config = copy.deepcopy(self.original_anchor_config)
    
    def spawn_test_case(self, location: int, zone_type: str):
        """Spawn ONE vehicle in specified location and zone type.
        
        Uses EXACT same spawn functions as main test script.
        """
        self.test_count += 1
        seed = int(time.time() * 1000) % 1000000  # Deterministic but unique per test
        
        print("\n" + "=" * 70)
        print(f"TEST {self.test_count}: SPAWN EXECUTION")
        print("=" * 70)
        print(f"\n[CONFIG]")
        print(f"  Location:  {location}")
        print(f"  Zone Type: {zone_type}")
        print(f"  Seed:      {seed}")
        
        # Get allowed vehicle types for this zone
        vehicle_types = ZONE_TYPE_VEHICLES.get(zone_type, [])
        print(f"  Allowed vehicles: {', '.join(vehicle_types)}")
        
        # Spawn using EXACT same functions as main script
        try:
            if zone_type == "lane":
                print(f"\n[SPAWN] Calling spawn_lane(seed={seed}, count=1, vehicle_types={vehicle_types})")
                result = self.spawner.spawn_lane(
                    seed=seed,
                    count=1,
                    vehicle_types=vehicle_types
                )
            
            elif zone_type == "parking":
                print(f"\n[SPAWN] Calling spawn_parking(seed={seed}, count=1, vehicle_types={vehicle_types})")
                result = self.spawner.spawn_parking(
                    seed=seed,
                    count=1,
                    vehicle_types=vehicle_types
                )
            
            elif zone_type == "sidewalk":
                print(f"\n[SPAWN] Calling spawn_sidewalk(seed={seed}, count=1, vehicle_types={vehicle_types})")
                result = self.spawner.spawn_sidewalk(
                    seed=seed,
                    count=1,
                    vehicle_types=vehicle_types
                )
            
            else:
                print(f"\n[ERROR] Unknown zone type: {zone_type}")
                return
            
            # Log results
            if result.success and result.spawned_vehicles:
                vehicle = result.spawned_vehicles[0]
                self.spawned_vehicles.append(vehicle)
                
                print(f"\n[SUCCESS] Vehicle spawned:")
                print(f"  Vehicle:     {vehicle.name}")
                print(f"  Category:    {vehicle.category}")
                print(f"  Anchor:      {vehicle.anchor_name}")
                print(f"  Position:    X={vehicle.spawn_location['X']:.1f}, Y={vehicle.spawn_location['Y']:.1f}, Z={vehicle.spawn_location['Z']:.1f}")
                print(f"  Rotation:    Yaw={vehicle.spawn_rotation['Yaw']:.1f}°")
                
                # Check if in correct location bounds
                y_min, y_max = LOCATION_BOUNDARIES[location]
                y_pos = vehicle.spawn_location['Y']
                in_bounds = y_min <= y_pos < y_max
                print(f"  In location bounds: {in_bounds} (Y={y_pos:.1f}, expected [{y_min}, {y_max}))")
                
            else:
                print(f"\n[FAILURE] Spawn failed")
                print(f"  Reason: {result.failure_reason or 'Unknown'}")
        
        except Exception as e:
            print(f"\n[ERROR] Exception during spawn: {e}")
            import traceback
            traceback.print_exc()
    
    def cleanup(self):
        """Cleanup spawned vehicles and reset scene"""
        if not self.spawned_vehicles:
            print("\n[CLEANUP] No vehicles to clean up")
            return
        
        print(f"\n[CLEANUP] Cleaning up {len(self.spawned_vehicles)} spawned vehicle(s)...")
        
        # Get vehicle pool for default transforms
        vehicle_pool = {}
        if self.spawner.vehicle_config and 'vehicles' in self.spawner.vehicle_config:
            for category, vehicles in self.spawner.vehicle_config['vehicles'].items():
                for v in vehicles:
                    vehicle_pool[v['name']] = v.get('default_transform', {})
        
        # Reset each vehicle to its original pool position
        success_count = 0
        for vehicle in self.spawned_vehicles:
            try:
                # Get default transform from vehicle pool
                default_transform = vehicle_pool.get(vehicle.name)
                
                if default_transform:
                    result = self.spawner._teleport_actor(
                        vehicle.name,
                        default_transform['location'],
                        default_transform['rotation']
                    )
                    if result:
                        success_count += 1
                        print(f"  ✓ Reset {vehicle.name} to pool position")
                    else:
                        print(f"  ✗ Failed to reset {vehicle.name} (teleport returned False)")
                else:
                    print(f"  ✗ No default transform for {vehicle.name}")
            except Exception as e:
                print(f"  ✗ Exception resetting {vehicle.name}: {e}")
        
        print(f"[CLEANUP] Reset {success_count}/{len(self.spawned_vehicles)} vehicles to pool positions")
        self.spawned_vehicles = []
    
    def reset_all_vehicles_to_pool(self):
        """Reset ALL vehicles in the pool to their original positions (final cleanup)"""
        print("\n" + "=" * 70)
        print("FINAL CLEANUP: RESETTING ALL VEHICLES TO POOL")
        print("=" * 70)
        
        if not self.spawner.vehicle_config or 'vehicles' not in self.spawner.vehicle_config:
            print("[WARNING] No vehicle pool found, skipping reset")
            return
        
        total_reset = 0
        for category, vehicles in self.spawner.vehicle_config['vehicles'].items():
            for vehicle in vehicles:
                try:
                    if 'default_transform' in vehicle:
                        result = self.spawner._teleport_actor(
                            vehicle['name'],
                            vehicle['default_transform']['location'],
                            vehicle['default_transform']['rotation']
                        )
                        if result:
                            total_reset += 1
                except Exception as e:
                    print(f"  [WARNING] Failed to reset {vehicle.get('name', 'unknown')}: {e}")
        
        print(f"[OK] Reset {total_reset} vehicles to pool positions")
        print("=" * 70)
    
    def run(self):
        """Main interactive loop"""
        self.initialize()
        
        while True:
            # Reset filter before each test
            self.reset_location_filter()
            
            # Step 1: Select location
            location = self.select_location()
            if location is None:
                print("\n[EXIT] Exiting test script.")
                break
            
            # Apply location filter
            self.apply_location_filter(location)
            
            # Step 2: Select zone type
            zone_type = self.select_zone_type()
            if zone_type is None:
                print("\n[EXIT] Exiting test script.")
                break
            
            # Inner loop for quick repeat
            while True:
                # Step 3: Confirm spawn
                if not self.confirm_spawn():
                    print("\n[SKIP] Spawn cancelled. Starting over...")
                    break
                
                # Execute spawn
                self.spawn_test_case(location, zone_type)
                
                # Prompt for next action
                action = self.prompt_next_action()
                
                if action == "repeat":
                    # Cleanup current vehicle and repeat same test
                    self.cleanup()
                    print("\n[REPEAT] Testing same location + zone again...\n")
                    continue
                elif action == "new":
                    # Cleanup and start new test
                    self.cleanup()
                    print("\n[NEW TEST] Starting over...\n")
                    break
                else:
                    # Exit
                    self.cleanup()
                    print("\n[EXIT] Exiting test script.")
                    # Final cleanup and exit
                    print("\n")
                    self.reset_all_vehicles_to_pool()
                    print("\n[OK] Interactive test script finished.")
                    return
        
        # Final cleanup - reset ALL vehicles to pool
        print("\n")
        self.reset_all_vehicles_to_pool()
        print("\n[OK] Interactive test script finished.")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    test = None
    try:
        test = InteractiveSpawnTest()
        test.run()
    except KeyboardInterrupt:
        print("\n\n[EXIT] Test interrupted by user.")
        # Ensure cleanup on interrupt
        if test:
            test.cleanup()
            test.reset_all_vehicles_to_pool()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        # Ensure cleanup on error
        if test:
            test.cleanup()
            test.reset_all_vehicles_to_pool()


if __name__ == "__main__":
    main()
