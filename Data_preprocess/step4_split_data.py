import os
import shutil
import random

def fix_folders_and_split():
    print("[*] Initiating File System Architecture Protocol...")
    
    base_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection"
    train_base = os.path.join(base_dir, "train")
    
    # 1. Create the strict YOLOv8 folders
    train_img_dir = os.path.join(train_base, "images")
    train_lbl_dir = os.path.join(train_base, "labels")
    
    val_img_dir = os.path.join(base_dir, "val", "images")
    val_lbl_dir = os.path.join(base_dir, "val", "labels")
    
    for folder in [train_img_dir, val_img_dir, val_lbl_dir]:
        os.makedirs(folder, exist_ok=True)
        
    print("[+] YOLOv8 strict folder structure verified.")

    # 2. Move loose images into the 'train/images' folder
    print("[*] Scanning for loose images in the main train folder...")
    loose_images = [f for f in os.listdir(train_base) if f.endswith(('.jpg', '.png'))]
    
    if loose_images:
        print(f"[*] Moving {len(loose_images)} loose images into train/images/ ...")
        for img in loose_images:
            shutil.move(os.path.join(train_base, img), os.path.join(train_img_dir, img))
    else:
        print("[-] No loose images found. They are already in the images folder.")

    # 3. Clean up Orphans (The Step 3 Fix)
    print("\n[*] Sweeping for Orphaned Images (Images with no labels)...")
    all_images = os.listdir(train_img_dir)
    all_labels = set(os.listdir(train_lbl_dir))
    
    orphans_deleted = 0
    valid_images = []
    
    for img in all_images:
        base_name = os.path.splitext(img)[0]
        expected_lbl = f"{base_name}.txt"
        
        if expected_lbl not in all_labels:
            # Delete the orphaned image
            os.remove(os.path.join(train_img_dir, img))
            orphans_deleted += 1
        else:
            valid_images.append(img)
            
    print(f"[!] Erased {orphans_deleted} orphaned images left behind by Step 3.")
    
    # 4. The 80/20 Validation Split
    print("\n[*] Executing the 80/20 Validation Split...")
    random.shuffle(valid_images)
    
    val_count = int(len(valid_images) * 0.20)
    val_images = valid_images[:val_count]
    
    print(f"[*] Moving {val_count} files to the validation exam folder...")
    
    for img in val_images:
        # Move image to val/images
        shutil.move(os.path.join(train_img_dir, img), os.path.join(val_img_dir, img))
        
        # Move matching label to val/labels
        base_name = os.path.splitext(img)[0]
        lbl_name = f"{base_name}.txt"
        shutil.move(os.path.join(train_lbl_dir, lbl_name), os.path.join(val_lbl_dir, lbl_name))
            
    print("\n[+] ARCHITECTURE COMPLETE! You are cleared to run train_master.py")

if __name__ == "__main__":
    fix_folders_and_split()