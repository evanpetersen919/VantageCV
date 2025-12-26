"""
Test hybrid Python/C++ randomization via SceneController.
Tests lighting and material randomization through C++ plugin.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vantagecv.ue5_bridge import UE5Bridge
import time

def main():
    print("=" * 70)
    print("Testing Hybrid Python/C++ Randomization")
    print("=" * 70)
    
    # Connect to UE5
    print("\n1. Connecting to UE5 Remote Control API...")
    try:
        bridge = UE5Bridge(
            host="localhost",
            port=30010,
            scene_controller_path="/Game/main.main:PersistentLevel.BP_SceneController_C_UAID_B48C9D9F0BCA05AF02_1237591175"
        )
        print("✓ Connected to UE5")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nMake sure:")
        print("  - UE5 is running with VantageCV_Project")
        print("  - Remote Control Web Interface plugin is enabled")
        print("  - main.umap is loaded")
        return
    
    # Test 3 iterations with different settings
    test_configs = [
        {
            "name": "Dim Warm Lighting",
            "intensity": (200, 400),
            "temp": (3500, 4500)
        },
        {
            "name": "Bright Neutral Lighting", 
            "intensity": (600, 900),
            "temp": (5000, 6000)
        },
        {
            "name": "Very Bright Cool Lighting",
            "intensity": (900, 1200),
            "temp": (6000, 7000)
        }
    ]
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n{'='*70}")
        print(f"Iteration {i}/3: {config['name']}")
        print(f"{'='*70}")
        
        # Randomize lighting via C++ SceneController
        print(f"\n2. Randomizing lighting (C++)...")
        print(f"   Intensity: {config['intensity']} cd")
        print(f"   Temperature: {config['temp']} K")
        try:
            bridge.randomize_lighting(
                intensity_range=config['intensity'],
                color_temp_range=config['temp']
            )
            print("✓ Lighting randomized via SceneController")
        except Exception as e:
            print(f"✗ Lighting failed: {e}")
            print("\nMake sure BP_SceneController exists in level")
        
        # Randomize materials via C++ SceneController
        print(f"\n3. Randomizing materials (C++)...")
        try:
            bridge.randomize_materials(object_types=["StaticMeshActor"])
            print("✓ Materials randomized via SceneController")
        except Exception as e:
            print(f"✗ Materials failed: {e}")
        
        # Capture frame
        print(f"\n4. Capturing frame (C++)...")
        try:
            success = bridge.capture_frame()
            if success:
                print("✓ Frame captured via VantageCVSubsystem")
            else:
                print("✗ Frame capture returned false")
        except Exception as e:
            print(f"✗ Capture failed: {e}")
            print("\nMake sure DataCapture actor exists in level")
        
        if i < len(test_configs):
            print(f"\n⏳ Waiting 3 seconds before next iteration...")
            time.sleep(3)
    
    print("\n" + "=" * 70)
    print("✓ Test complete - check UE5 viewport for visual changes")
    print("=" * 70)
    print("\nExpected results:")
    print("  - Lighting should change dramatically each iteration")
    print("  - Materials should have different metallic/roughness")
    print("  - Screenshots saved to: Saved/Screenshots/WindowsEditor/")

if __name__ == "__main__":
    main()
