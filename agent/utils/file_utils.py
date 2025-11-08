"""
File system utility functions for dataset handling and cleanup.
"""
import os
import shutil
import zipfile
import random
from pathlib import Path
from typing import List


def unzip_dataset(zip_path: str, extract_dir: str) -> None:
    """
    Extract a zip archive to the specified directory.
    
    Args:
        zip_path: Path to the zip file to extract
        extract_dir: Directory where files should be extracted
        
    Raises:
        FileNotFoundError: If zip file doesn't exist
        zipfile.BadZipFile: If file is not a valid zip archive
    """
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Zip file not found: {zip_path}")
    
    # Create extract directory if it doesn't exist
    os.makedirs(extract_dir, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)


def validate_dataset_structure(data_dir: str) -> bool:
    """
    Verify that the dataset contains the required train, val, and test folders.
    
    Args:
        data_dir: Root directory of the extracted dataset
        
    Returns:
        True if all required folders exist, False otherwise
    """
    # Check for lowercase versions
    required_folders = ['train', 'val', 'test']
    
    for folder in required_folders:
        folder_path = os.path.join(data_dir, folder)
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return False
    
    return True


def normalize_folder_names(data_dir: str) -> None:
    """
    Normalize folder names to lowercase (Train -> train, Test -> test, etc.).
    
    Args:
        data_dir: Root directory to normalize
    """
    for item in os.listdir(data_dir):
        item_path = os.path.join(data_dir, item)
        if os.path.isdir(item_path):
            lower_name = item.lower()
            if item != lower_name:
                new_path = os.path.join(data_dir, lower_name)
                # Avoid conflicts if both exist
                if not os.path.exists(new_path):
                    os.rename(item_path, new_path)
                    print(f"📝 Renamed '{item}' -> '{lower_name}'")


def create_val_from_train(data_dir: str, val_ratio: float = 0.2) -> None:
    """
    Create validation set by splitting from training set.
    
    Used when dataset has train/test but no val folder.
    
    Args:
        data_dir: Root directory containing train folder
        val_ratio: Proportion of training data to use for validation
    """
    train_dir = os.path.join(data_dir, 'train')
    val_dir = os.path.join(data_dir, 'val')
    
    if not os.path.exists(train_dir):
        raise ValueError("Train directory not found")
    
    os.makedirs(val_dir, exist_ok=True)
    print(f"📊 Creating validation set from training data ({val_ratio:.0%})...")
    
    # Get all class folders in train
    class_folders = [
        d for d in os.listdir(train_dir)
        if os.path.isdir(os.path.join(train_dir, d))
    ]
    
    total_moved = 0
    for cls in class_folders:
        train_cls_dir = os.path.join(train_dir, cls)
        val_cls_dir = os.path.join(val_dir, cls)
        os.makedirs(val_cls_dir, exist_ok=True)
        
        # Get all images in this class
        images = [
            f for f in os.listdir(train_cls_dir)
            if os.path.isfile(os.path.join(train_cls_dir, f))
            and f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'))
        ]
        
        # Shuffle and split
        random.seed(42)
        random.shuffle(images)
        
        val_count = int(len(images) * val_ratio)
        val_images = images[:val_count]
        
        # Move validation images
        for img in val_images:
            src = os.path.join(train_cls_dir, img)
            dst = os.path.join(val_cls_dir, img)
            shutil.move(src, dst)
            total_moved += 1
        
        print(f"  ✓ {cls}: moved {len(val_images)} images to validation")
    
    print(f"✅ Validation set created: {total_moved} images")


def auto_flatten_dataset(base_dir: str) -> None:
    """
    Flatten nested dataset structure if there's only one subdirectory.
    
    Many Kaggle datasets are structured as:
    dataset.zip/
      dataset-name/
        class1/
        class2/
    
    This function moves everything up one level if only one subdirectory exists.
    
    Args:
        base_dir: Root directory to check and flatten
    """
    subdirs = [
        d for d in os.listdir(base_dir)
        if os.path.isdir(os.path.join(base_dir, d))
    ]
    
    # If there's exactly one subdirectory, flatten it
    if len(subdirs) == 1:
        inner_path = os.path.join(base_dir, subdirs[0])
        print(f"📦 Found nested folder: '{subdirs[0]}' — flattening structure...")
        
        # Move all contents from inner folder to base
        for item in os.listdir(inner_path):
            src = os.path.join(inner_path, item)
            dst = os.path.join(base_dir, item)
            shutil.move(src, dst)
        
        # Remove the now-empty inner folder
        shutil.rmtree(inner_path)
        print(f"✓ Flattened dataset structure")


def auto_split_dataset(data_dir: str, train_ratio: float = 0.7, val_ratio: float = 0.2) -> None:
    """
    Automatically split a flat dataset structure into train/val/test folders.
    
    This function handles datasets that have class folders directly in the root
    (e.g., data_dir/class1/, data_dir/class2/) and splits them into:
    - data_dir/train/class1/, data_dir/train/class2/
    - data_dir/val/class1/, data_dir/val/class2/
    - data_dir/test/class1/, data_dir/test/class2/
    
    Args:
        data_dir: Root directory containing class folders
        train_ratio: Proportion of data for training (default: 0.7)
        val_ratio: Proportion of data for validation (default: 0.2)
        Test ratio is automatically calculated as 1 - train_ratio - val_ratio
        
    Raises:
        ValueError: If ratios are invalid or no class folders found
    """
    # Validate ratios
    test_ratio = 1.0 - train_ratio - val_ratio
    if test_ratio < 0 or train_ratio <= 0 or val_ratio <= 0:
        raise ValueError("Invalid split ratios: train + val must be < 1.0")
    
    print(f"⚙️  Auto-splitting dataset: {train_ratio:.0%} train, {val_ratio:.0%} val, {test_ratio:.0%} test")
    
    # Find all class directories (ignore train/val/test and common non-class folders)
    subdirs = [
        d for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d))
        and d.lower() not in ['train', 'val', 'test', 'validation', '__pycache__', '.git']
    ]
    
    if not subdirs:
        raise ValueError(f"No class folders found in {data_dir}")
    
    print(f"📁 Found {len(subdirs)} class folders: {', '.join(subdirs)}")
    
    # Create train/val/test directories
    train_dir = os.path.join(data_dir, 'train')
    val_dir = os.path.join(data_dir, 'val')
    test_dir = os.path.join(data_dir, 'test')
    
    os.makedirs(train_dir, exist_ok=True)
    os.makedirs(val_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)
    
    # Process each class folder
    total_moved = 0
    for cls in subdirs:
        cls_path = os.path.join(data_dir, cls)
        
        # Get all image files in this class
        all_files = [
            f for f in os.listdir(cls_path)
            if os.path.isfile(os.path.join(cls_path, f))
            and f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'))
        ]
        
        if not all_files:
            print(f"⚠️  Warning: No images found in {cls}, skipping")
            continue
        
        # Shuffle for random split
        random.seed(42)  # For reproducibility
        random.shuffle(all_files)
        
        # Calculate split indices
        n = len(all_files)
        train_cut = int(train_ratio * n)
        val_cut = int((train_ratio + val_ratio) * n)
        
        # Create class subdirectories in train/val/test
        train_cls_dir = os.path.join(train_dir, cls)
        val_cls_dir = os.path.join(val_dir, cls)
        test_cls_dir = os.path.join(test_dir, cls)
        
        os.makedirs(train_cls_dir, exist_ok=True)
        os.makedirs(val_cls_dir, exist_ok=True)
        os.makedirs(test_cls_dir, exist_ok=True)
        
        # Move files to appropriate splits
        for i, filename in enumerate(all_files):
            src = os.path.join(cls_path, filename)
            
            if i < train_cut:
                dst = os.path.join(train_cls_dir, filename)
            elif i < val_cut:
                dst = os.path.join(val_cls_dir, filename)
            else:
                dst = os.path.join(test_cls_dir, filename)
            
            shutil.move(src, dst)
            total_moved += 1
        
        # Remove empty original class folder
        try:
            os.rmdir(cls_path)
        except OSError:
            # Folder not empty, leave it
            pass
        
        print(f"✓ Split {cls}: {train_cut} train, {val_cut - train_cut} val, {n - val_cut} test")
    
    print(f"✅ Auto-split complete: {total_moved} files organized into train/val/test")


def count_classes(train_dir: str) -> int:
    """
    Count the number of classes by counting subdirectories in the train folder.
    
    Args:
        train_dir: Path to the train directory containing class subdirectories
        
    Returns:
        Number of class subdirectories found
        
    Raises:
        FileNotFoundError: If train directory doesn't exist
    """
    if not os.path.exists(train_dir):
        raise FileNotFoundError(f"Train directory not found: {train_dir}")
    
    if not os.path.isdir(train_dir):
        raise NotADirectoryError(f"Path is not a directory: {train_dir}")
    
    # Count only directories (not files)
    subdirs = [
        item for item in os.listdir(train_dir)
        if os.path.isdir(os.path.join(train_dir, item))
    ]
    
    return len(subdirs)


def cleanup_temp_files(paths: List[str]) -> None:
    """
    Remove temporary files and directories.
    
    Args:
        paths: List of file or directory paths to remove
    """
    for path in paths:
        if not path or not os.path.exists(path):
            continue
        
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            # Log but don't raise - cleanup is best effort
            print(f"Warning: Failed to cleanup {path}: {e}")
