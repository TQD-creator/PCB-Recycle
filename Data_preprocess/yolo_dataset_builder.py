import os
import random

# ==========================================
# 1. DIRECTORY CONFIGURATION
# ==========================================
SOURCE_IMAGES = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\PCB recognition for recycling.coco\train"
SOURCE_LABELS = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\PCB recognition for recycling.coco\train\NLP_Cleaned_Labels"

FINAL_DATASET_DIR = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\YOLO_Dataset"

DIRS_TO_MAKE = [
    os.path.join(FINAL_DATASET_DIR, "images", "train"),
    os.path.join(FINAL_DATASET_DIR, "images", "val"),
    os.path.join(FINAL_DATASET_DIR, "labels", "train"),
    os.path.join(FINAL_DATASET_DIR, "labels", "val")
]

for d in DIRS_TO_MAKE:
    os.makedirs(d, exist_ok=True)

# Extracts the unique 'rf.HASH' from the messy filenames
def extract_hash(filename):
    if ".rf." in filename:
        return filename.split(".rf.")[1].split(".")[0]
    return filename 

def build_smart_yolo_dataset():
    print("[*] Building Smart Index of Images and Labels...")
    
    valid_exts = ('.jpg', '.jpeg', '.png', '.bmp')
    image_files = [f for f in os.listdir(SOURCE_IMAGES) if f.lower().endswith(valid_exts)]
    label_files = [f for f in os.listdir(SOURCE_LABELS) if f.lower().endswith('.txt')]
    
    # Build a dictionary to map hashes to text files
    label_dict = {}
    for txt in label_files:
        exact_name = os.path.splitext(txt)[0]
        rf_hash = extract_hash(exact_name)
        label_dict[rf_hash] = txt
        label_dict[exact_name] = txt 

    valid_pairs = []
    
    for img_file in image_files:
        img_base = os.path.splitext(img_file)[0]
        img_hash = extract_hash(img_base)
        
        txt_file = None
        if img_base in label_dict:
            txt_file = label_dict[img_base]
        elif img_hash in label_dict: # Hash bypass for Chinese characters
            txt_file = label_dict[img_hash]
            
        if txt_file:
            img_path = os.path.join(SOURCE_IMAGES, img_file)
            txt_path = os.path.join(SOURCE_LABELS, txt_file)
            valid_pairs.append((img_path, txt_path, img_file, txt_file))
            
    print(f"[*] Found {len(valid_pairs)} perfectly matched boards using Hash Linking.")
    
    if len(valid_pairs) == 0:
        print("[!] CRITICAL ERROR: 0 matches. Something is structurally wrong with the folders.")
        return
        
    random.shuffle(valid_pairs)
    split_index = int(len(valid_pairs) * 0.8)
    train_pairs = valid_pairs[:split_index]
    val_pairs = valid_pairs[split_index:]
    
    print(f"[*] Splitting: {len(train_pairs)} Training | {len(val_pairs)} Validation.")
    print("[*] Copying and translating filenames to English... (Please wait)")
    
    # Binary copy to completely bypass Windows path crashes
    def safe_copy(src, dst):
        with open(src, 'rb') as fsrc:
            with open(dst, 'wb') as fdst:
                fdst.write(fsrc.read())

    def copy_data(pairs, subset_name):
        for img_path, txt_path, img_file, txt_file in pairs:
            # We rename the files to pure English (e.g., board_SwJkwMVPIaX.jpg)
            clean_hash = extract_hash(img_file)
            ext = os.path.splitext(img_file)[1]
            
            new_img_dst = os.path.join(FINAL_DATASET_DIR, "images", subset_name, f"board_{clean_hash}{ext}")
            new_txt_dst = os.path.join(FINAL_DATASET_DIR, "labels", subset_name, f"board_{clean_hash}.txt")
            
            safe_copy(img_path, new_img_dst)
            safe_copy(txt_path, new_txt_dst)

    copy_data(train_pairs, "train")
    copy_data(val_pairs, "val")
    
    print("="*50)
    print(f"[*] SUCCESS: YOLO Dataset successfully built at:\n    {FINAL_DATASET_DIR}")
    print("="*50)

if __name__ == "__main__":
    build_smart_yolo_dataset()