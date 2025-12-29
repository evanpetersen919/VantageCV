"""
Test hybrid Python/C++ randomization via SceneController.
Tests lighting and material randomization through C++ plugin.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vantagecv.ue5_bridge import UE5Bridge
from vantagecv.config import Config
import time

def main():
    print("=" * 70)
    print("Testing Hybrid Python/C++ Randomization")
    print("=" * 70)
    
    # Load configuration
    config = Config("configs/industrial.yaml")
    ue5_config = config.get("industrial.ue5", {})
    
    # Connect to UE5
    print("\n1. Connecting to UE5 Remote Control API...")
    try:
        bridge = UE5Bridge(
            host="localhost",
            port=ue5_config.get("remote_control_port", 30010),
            scene_controller_path=ue5_config.get("scene_controller_path"),
            data_capture_path=ue5_config.get("data_capture_path")
        )
        print("✓ Connected to UE5")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nMake sure:")
        print("  - UE5 is running with VantageCV_Project")
        print("  - Remote Control Web Interface plugin is enabled")
        print("  - main.umap is loaded")
        return
    
    # Test configurations
    test_configs = [
        {"name": "Dim Warm Lighting", "intensity": (200, 400), "temp": (3500, 4500)},
        {"name": "Bright Neutral Lighting", "intensity": (600, 900), "temp": (5000, 6000)},
        {"name": "Very Bright Cool Lighting", "intensity": (900, 1200), "temp": (6000, 7000)}
    ]
    
    output_dir = ue5_config.get("output_directory", "F:/Unreal Editor/VantageCV_Project/Saved/Screenshots/VantageCV")
    resolution = ue5_config.get("default_resolution", [1920, 1080])
    actor_pattern = ue5_config.get("target_actor_pattern", "StaticMeshActor")
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n{'='*70}")
        print(f"Iteration {i}/3: {config['name']}")
        print(f"{'='*70}")
        
        # Randomize lighting
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
        
        # Randomize materials
        print(f"\n3. Randomizing materials (C++)...")
        try:
            bridge.randomize_materials(object_types=[actor_pattern])
            print("✓ Materials randomized via SceneController")
        except Exception as e:
            print(f"✗ Materials failed: {e}")
        
        # Randomize camera (optional - varies viewpoint slightly)
        print(f"\n4. Randomizing camera position (C++)...")
        try:
            # Overhead inspection camera with slight variation
            bridge.randomize_camera(distance_range=(50, 70), fov_range=(65, 75))
            print("✓ Camera randomized via SceneController")
        except Exception as e:
            print(f"✗ Camera failed: {e}")
        
        # Capture frame
        print(f"\n5. Capturing frame (C++)...")
        try:
            output_path = f"{output_dir}/frame_{i:04d}.png"
            success = bridge.capture_frame(output_path, resolution[0], resolution[1])
            if success:
                print(f"✓ Frame captured: {output_path}")
            else:
                print(f"✗ Frame capture returned false")
        except Exception as e:
            print(f"✗ Capture failed: {e}")
        
        if i < len(test_configs):
            print(f"\n⏳ Waiting 3 seconds before next iteration...")
            time.sleep(3)
    
    print("\n" + "=" * 70)
    print("✓ Test complete - check captured images and UE5 viewport")
    print("=" * 70)

if __name__ == "__main__":
    main()
