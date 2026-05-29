import os
import random

def intelligent_undersample():
    print("[*] Initiating Surgical Undersampling...")
    
    images_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\images"
    labels_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\labels" # Updated path!
    
    # Target retention percentage for "Boring" files (keeping 25%, killing 75%)
    KEEP_RATIO = 0.25 
    
    # Classes we CANNOT afford to lose (ICs, Diodes, LEDs, Inductors, Connectors, Unknowns)
    PROTECTED_CLASSES = {2, 3, 4, 5, 6, 99}
    
    expendable_files = []
    protected_files_count = 0
    
    # 1. Analyze the dataset
    for filename in os.listdir(labels_dir):
        if not filename.endswith(".txt"): continue
            
        txt_path = os.path.join(labels_dir, filename)
        is_protected = False
        
        with open(txt_path, 'r') as f:
            lines = f.readlines()
            
        for line in lines:
            parts = line.strip().split()
            if len(parts) > 0 and int(parts[0]) in PROTECTED_CLASSES:
                is_protected = True
                break # Found a rare component, protect this file instantly!
                
        if is_protected:
            protected_files_count += 1
        else:
            expendable_files.append(filename)
            
    print(f"[*] Found {protected_files_count} 'High-Value' images containing rare components.")
    print(f"[*] Found {len(expendable_files)} 'Boring' images (Only Resistors/Capacitors).")
    
    # 2. Calculate the purge
    files_to_delete_count = int(len(expendable_files) * (1.0 - KEEP_RATIO))
    files_to_delete = random.sample(expendable_files, files_to_delete_count)
    
    print(f"[!] Executing purge on {files_to_delete_count} boring files to balance dataset...")
    
    # 3. Destroy the files (Labels AND Images)
    for filename in files_to_delete:
        base_name = filename.replace(".txt", "")
        
        # Delete Text File
        os.remove(os.path.join(labels_dir, filename))
        
        # Try to delete matching Image (Check both jpg and png)
        jpg_path = os.path.join(images_dir, f"{base_name}.jpg")
        png_path = os.path.join(images_dir, f"{base_name}.png")
        
        if os.path.exists(jpg_path): os.remove(jpg_path)
        if os.path.exists(png_path): os.remove(png_path)
            
    print("\n[+] Undersampling Complete. Run your analyzer script again to see the new distribution.")

if __name__ == "__main__":
    intelligent_undersample()