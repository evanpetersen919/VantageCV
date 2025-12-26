"""
Verify that generated images have different lighting
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def main():
    output_dir = Path(__file__).parent.parent.parent / "output" / "test_randomized_batch" / "images"
    
    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}")
        return
    
    images = sorted(output_dir.glob("image_*.png"))
    
    if len(images) < 2:
        print(f"Need at least 2 images, found {len(images)}")
        return
    
    print(f"Analyzing {len(images)} images for lighting variation...\n")
    
    # Load images and compute average brightness
    brightness_values = []
    
    for img_path in images:
        img = Image.open(img_path).convert('RGB')
        img_array = np.array(img)
        avg_brightness = img_array.mean()
        brightness_values.append(avg_brightness)
        print(f"{img_path.name}: Avg brightness = {avg_brightness:.2f}")
    
    # Check variation
    brightness_std = np.std(brightness_values)
    brightness_range = max(brightness_values) - min(brightness_values)
    
    print(f"\n{'='*60}")
    print(f"Lighting Variation Analysis")
    print(f"{'='*60}")
    print(f"Brightness range: {brightness_range:.2f} (min={min(brightness_values):.2f}, max={max(brightness_values):.2f})")
    print(f"Standard deviation: {brightness_std:.2f}")
    
    if brightness_range > 5.0:
        print(f"\n✓ PASS: Images show lighting variation!")
        print(f"  The {brightness_range:.1f} brightness difference indicates randomization is working.")
    else:
        print(f"\n✗ WARNING: Low brightness variation ({brightness_range:.2f})")
        print(f"  Images may look very similar. Check viewport is in Lit mode.")
    
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
