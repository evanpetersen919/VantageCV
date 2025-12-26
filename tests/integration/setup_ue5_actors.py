"""
Setup UE5 actors with proper tags via Remote Control API
Research-level approach: Programmatic actor configuration
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vantagecv.ue5_bridge import UE5Bridge
import requests

def setup_pcb_actor(bridge: UE5Bridge):
    """
    Configure PCB actor with proper tags via Remote Control API
    """
    print("Configuring PCB actor for material randomization...")
    
    # Method 1: Try to add tag via property setting
    pcb_path = "/Game/main.main:PersistentLevel.PCB"
    
    try:
        # Get current tags
        response = requests.put(
            f"http://{bridge.host}:{bridge.port}/remote/object/property",
            json={
                "objectPath": pcb_path,
                "propertyName": "Tags",
                "access": "READ_ACCESS"
            },
            timeout=5
        )
        
        print(f"Current tags response: {response.status_code}")
        if response.status_code == 200:
            print(f"Tags: {response.json()}")
        
        # Set tags array
        response = requests.put(
            f"http://{bridge.host}:{bridge.port}/remote/object/property",
            json={
                "objectPath": pcb_path,
                "propertyName": "Tags",
                "propertyValue": ["PCB"],
                "generateTransaction": True
            },
            timeout=5
        )
        
        print(f"Set tags response: {response.status_code}")
        if response.status_code == 200:
            print("✓ Successfully tagged PCB actor")
            return True
        else:
            print(f"Failed to set tags: {response.text}")
            
    except Exception as e:
        print(f"Error configuring PCB actor: {e}")
    
    return False

def list_all_actors(bridge: UE5Bridge):
    """
    Use Remote Control to list actors (if preset exists)
    """
    print("\nAttempting to list actors in level...")
    
    # This requires a Remote Control Preset to be set up
    # For now, we'll use a different approach
    
    print("Note: Direct actor listing requires Remote Control Preset setup")
    print("Please manually verify PCB actor name in Outliner")

def main():
    print("="*60)
    print("UE5 Actor Configuration for Material Randomization")
    print("Research-Level Setup")
    print("="*60)
    
    bridge = UE5Bridge(host="localhost", port=30010)
    
    print("\nStep 1: Verify PCB actor exists")
    pcb_name = input("Enter exact PCB actor name from Outliner (default: PCB): ").strip() or "PCB"
    
    print(f"\nStep 2: Attempting to configure actor: {pcb_name}")
    
    # Try to add tags programmatically
    if not setup_pcb_actor(bridge):
        print("\n" + "="*60)
        print("Automatic tagging failed. Manual setup required:")
        print("="*60)
        print(f"1. In UE5 Outliner, select actor: {pcb_name}")
        print("2. Details panel → Actor section")
        print("3. Find 'Tags' property (expand if needed)")
        print("4. Click '+' to add element")
        print("5. Type: PCB")
        print("6. Click outside to confirm")
        print("="*60)
        
        input("\nPress Enter after manually adding tag...")
    
    print("\nStep 3: Testing material randomization...")
    try:
        bridge.randomize_materials(object_types=["PCB"])
        print("✓ Material randomization call succeeded")
        print("\nCheck UE5 Output Log for:")
        print("  - 'RandomizeMaterials called with 1 tags'")
        print("  - 'Searching for tag/name: PCB'")
        print("  - 'Found X actors' or 'Matched actor by name'")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
