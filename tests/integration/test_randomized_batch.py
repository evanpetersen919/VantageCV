"""
Test batch generation with lighting randomization integrated
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vantagecv.config import Config
from vantagecv.annotator import AnnotationExporter
from vantagecv.generator import SyntheticDataGenerator
from domains.industrial import IndustrialDomain

def main():
    print("Testing batch generation with lighting randomization\n")
    
    # Load config
    config_path = Path(__file__).parent.parent.parent / "configs" / "industrial.yaml"
    config = Config(str(config_path))
    
    # Create domain
    domain = IndustrialDomain(config.data)
    
    # Create annotator with class names from config
    class_names = config.get('objects.classes', ['object'])
    annotator = AnnotationExporter(class_names=class_names)
    
    # Create generator with UE5
    generator = SyntheticDataGenerator(
        domain=domain,
        config=config,
        annotator=annotator,
        use_ue5=True,
        ue5_host="localhost",
        ue5_port=30010,
        ue5_screenshot_path=Path("F:/Unreal Editor/VantageCV_Project/Saved/Screenshots/test_capture.png")
    )
    
    # Generate 5 images with randomized lighting
    output_dir = Path(__file__).parent.parent.parent / "output" / "test_randomized_batch"
    print(f"Generating 5 images to {output_dir}")
    print("Watch the UE5 viewport - lighting should change before each capture!\n")
    
    stats = generator.generate_dataset(num_images=5, output_dir=str(output_dir))
    
    print(f"\n{'='*60}")
    print(f"Test complete!")
    print(f"Generated: {stats['generated']} images")
    print(f"Check UE5 Output Log for 'Randomized 4 lights' messages")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
