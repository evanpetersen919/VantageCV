"""
Test lighting randomization via SceneController
"""

import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vantagecv.ue5_bridge import UE5Bridge

def main():
    print("="*60)
    print("Testing SceneController Lighting Randomization")
    print("="*60)
    
    # Connect to UE5
    print("\n1. Connecting to UE5...")
    try:
        bridge = UE5Bridge(host="localhost", port=30010)
        print("   ✓ Connected!")
    except Exception as e:
        print(f"   ✗ Failed to connect: {e}")
        return
    
    # Test lighting randomization
    print("\n2. Testing lighting randomization (3 iterations)...")
    print("   Watch the UE5 viewport - lights should change!\n")
    
    for i in range(3):
        print(f"   Iteration {i+1}/3:")
        print(f"     - Intensity: 300-800 cd")
        print(f"     - Color temp: 4000-6500K")
        
        try:
            bridge.randomize_lighting(
                intensity_range=(300, 800),
                color_temp_range=(4000, 6500)
            )
            print(f"     ✓ Randomization applied!")
            time.sleep(2)  # Pause so you can see the change
        except Exception as e:
            print(f"     ✗ Failed: {e}")
            break
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)
    print("\nIf you saw the lights changing in UE5, it works!")

if __name__ == "__main__":
    main()
