import os
import random
import shutil
from pathlib import Path

def separate_leftout_images(source_folder_path):
    """
    Randomly keeps exactly 34 images in the source folder and moves 
    the rest to a new 'leftout_[folder_name]' directory.
    """
    source_path = Path(source_folder_path)
    
    # Check if the provided folder exists
    if not source_path.exists() or not source_path.is_dir():
        print(f"❌ Error: The directory '{source_folder_path}' does not exist.")
        return

    # Define standard image file extensions
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'}
    
    # Gather all images from the folder
    all_images = [
        file for file in source_path.iterdir() 
        if file.is_file() and file.suffix.lower() in image_extensions
    ]
    
    total_images = len(all_images)
    
    # Check if there are enough images to process
    if total_images <= 34:
        print(f"⚠️ Notice: The folder only has {total_images} images. Nothing to move.")
        return
        
    print(f"Found {total_images} images. Preparing to move {total_images - 34} leftout images...")

    # Randomly pick exactly 34 images to KEEP
    images_to_keep = set(random.sample(all_images, 34))
    
    # Identify the leftout images that need to be moved
    images_to_move = [img for img in all_images if img not in images_to_keep]
    
    # Create the new folder name and path
    new_folder_name = f"leftout_{source_path.name}"
    new_folder_path = source_path.parent / new_folder_name
    
    # Create the new directory (doesn't throw an error if it already exists)
    new_folder_path.mkdir(parents=True, exist_ok=True)
    
    # Move the leftout files
    moved_count = 0
    for img in images_to_move:
        destination = new_folder_path / img.name
        shutil.move(str(img), str(destination))
        moved_count += 1

    print("✅ Process Complete!")
    print(f" - Kept exactly 34 images in: '{source_path.name}'")
    print(f" - Moved {moved_count} images to: '{new_folder_path}'")


# --- How to use the script ---
# Replace the path below with the actual path to your folder.
# Example for Windows: r"C:\Users\Name\Pictures\MyPhotos"
# Example for Mac/Linux: "/Users/Name/Pictures/MyPhotos"

folder_to_process = r"C:\Users\Lenovo\Documents\Foxconn\content\MobileNet_Pure_Dataset\Golden\capacitor_golden" 
separate_leftout_images(folder_to_process)