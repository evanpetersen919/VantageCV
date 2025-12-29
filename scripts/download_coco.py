"""
VantageCV - COCO Dataset Downloader

File: download_coco.py
Description: Download COCO 2017 dataset with progress tracking
Author: Evan Petersen
Date: December 2025
"""

import os
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional


def download_with_progress(url: str, destination: Path) -> None:
    """
    Download file with progress bar.
    
    Args:
        url: URL to download from
        destination: Local file path to save to
    """
    def reporthook(count: int, block_size: int, total_size: int) -> None:
        percent = int(count * block_size * 100 / total_size)
        print(f"\rDownloading {destination.name}: {percent}% [{count * block_size / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB]", end="")
    
    urllib.request.urlretrieve(url, destination, reporthook)
    print()  # Newline after download completes


def extract_zip(zip_path: Path, extract_to: Path) -> None:
    """
    Extract ZIP file with progress.
    
    Args:
        zip_path: Path to ZIP file
        extract_to: Directory to extract to
    """
    print(f"Extracting {zip_path.name}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Extracted {zip_path.name}")


def download_coco(
    output_dir: Path,
    download_train: bool = True,
    download_val: bool = True,
    download_test: bool = False,
    cleanup_zips: bool = True
) -> None:
    """
    Download COCO 2017 dataset.
    
    Args:
        output_dir: Directory to save dataset
        download_train: Download training images (18GB)
        download_val: Download validation images (1GB)
        download_test: Download test images (6GB)
        cleanup_zips: Delete ZIP files after extraction
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    base_url = "http://images.cocodataset.org"
    
    downloads = []
    
    if download_train:
        downloads.append(("train2017.zip", f"{base_url}/zips/train2017.zip"))
    
    if download_val:
        downloads.append(("val2017.zip", f"{base_url}/zips/val2017.zip"))
    
    if download_test:
        downloads.append(("test2017.zip", f"{base_url}/zips/test2017.zip"))
    
    # Always download annotations
    downloads.append(("annotations_trainval2017.zip", f"{base_url}/annotations/annotations_trainval2017.zip"))
    
    # Download files
    for filename, url in downloads:
        filepath = output_dir / filename
        
        if filepath.exists():
            print(f"Skipping {filename} (already exists)")
            continue
        
        print(f"\nDownloading {filename}...")
        download_with_progress(url, filepath)
    
    # Extract files
    print("\n" + "="*60)
    print("Extracting archives...")
    print("="*60)
    
    for filename, _ in downloads:
        filepath = output_dir / filename
        
        if filepath.exists():
            extract_zip(filepath, output_dir)
            
            if cleanup_zips:
                print(f"Removing {filename}")
                filepath.unlink()
    
    print("\n" + "="*60)
    print("COCO dataset download complete!")
    print("="*60)
    print(f"Location: {output_dir.absolute()}")
    
    # Print directory structure
    print("\nDataset structure:")
    for item in sorted(output_dir.iterdir()):
        if item.is_dir():
            num_files = len(list(item.glob("*")))
            print(f"  {item.name}/  ({num_files} files)")
        else:
            size_mb = item.stat().st_size / 1024 / 1024
            print(f"  {item.name}  ({size_mb:.1f}MB)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download COCO 2017 dataset")
    parser.add_argument(
        "--output",
        type=str,
        default="data/coco",
        help="Output directory for COCO dataset"
    )
    parser.add_argument(
        "--no-train",
        action="store_true",
        help="Skip downloading training images (18GB)"
    )
    parser.add_argument(
        "--no-val",
        action="store_true",
        help="Skip downloading validation images (1GB)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Download test images (6GB)"
    )
    parser.add_argument(
        "--keep-zips",
        action="store_true",
        help="Keep ZIP files after extraction"
    )
    
    args = parser.parse_args()
    
    download_coco(
        output_dir=Path(args.output),
        download_train=not args.no_train,
        download_val=not args.no_val,
        download_test=args.test,
        cleanup_zips=not args.keep_zips
    )
