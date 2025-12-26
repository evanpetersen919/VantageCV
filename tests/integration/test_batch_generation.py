"""
Test batch generation with UE5 integration
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vantagecv.config import Config
from vantagecv.generator import SyntheticDataGenerator
from vantagecv.annotator import AnnotationExporter
from domains.industrial import IndustrialDomain

def main():
    # Load config
    config = Config("configs/industrial.yaml")
    
    # Initialize components
    annotator = AnnotationExporter(class_names=['resistor', 'capacitor', 'ic'])
    domain = IndustrialDomain(config)
    
    # Create generator with UE5 connection
    generator = SyntheticDataGenerator(
        domain=domain,
        config=config,
        annotator=annotator,
        use_ue5=True,
        ue5_host="localhost",
        ue5_port=30010,
        ue5_screenshot_path="F:/Unreal Editor/VantageCV_Project/Saved/Screenshots/test_capture.png"
    )
    
    # Generate small test batch
    print("Generating 5-image test batch...")
    stats = generator.generate_dataset(
        num_images=5,
        output_dir="data/synthetic/industrial_test"
    )
    
    print(f"\nTest complete!")
    print(f"Generated: {stats['generated']}")
    print(f"Rejected: {stats['rejected']}")
    print(f"Mode: {stats['mode']}")

if __name__ == "__main__":
    main()
