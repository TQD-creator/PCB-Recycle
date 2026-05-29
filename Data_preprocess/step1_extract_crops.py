import os
import cv2
import numpy as np

def extract_crops_loudly():
    print("[*] Initiating Diagnostic Extraction Pipeline...")
    
    images_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train"
    labels_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\NLP_Cleaned_Labels"
    triage_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\Visual_Triage"
    
    os.makedirs(triage_dir, exist_ok=True)
    
    # --- DIAGNOSTIC TRACKERS ---
    diag_no_match = 0
    diag_cv2_fail = 0
    diag_wrong_class = 0
    diag_tiny_box = 0
    count = 0
    
    if not os.path.exists(images_dir) or not os.path.exists(labels_dir):
        print("[!] FATAL: One of your directories does not physically exist.")
        return

    # Map all images
    image_map = {}
    for img_name in os.listdir(images_dir):
        base_name = os.path.splitext(img_name)[0]
        image_map[base_name] = img_name

    txt_files = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
    print(f"[*] Found {len(txt_files)} text files in the labels folder.")
    
    if len(txt_files) == 0:
        print("[!] BOTTLENECK DETECTED: Your labels folder is completely empty.")
        print("[!] Did you accidentally delete your labels in the previous step and forget to regenerate them?")
        return

    for filename in txt_files:
        base_name = filename.replace(".txt", "")
        
        # BOTTLENECK 1: Name Mismatch
        if base_name not in image_map:
            diag_no_match += 1
            continue
            
        img_path = os.path.join(images_dir, image_map[base_name])
        img = cv2.imread(img_path)
        
        # BOTTLENECK 2: Corrupted or unreadable image
        if img is None:
            diag_cv2_fail += 1
            continue
            
        h, w, _ = img.shape
        
        with open(os.path.join(labels_dir, filename), 'r') as f:
            lines = f.readlines()
            
        for line_idx, line in enumerate(lines):
            parts = line.strip().split()
            if len(parts) < 5: continue
            
            cls_id = int(parts[0])
            
            # BOTTLENECK 3: Wrong Component
            if cls_id not in [2, 3, 99]: 
                diag_wrong_class += 1
                continue 
                
            cx, cy, bw, bh = map(float, parts[1:5])
            x1 = max(0, int((cx - bw / 2) * w))
            y1 = max(0, int((cy - bh / 2) * h))
            x2 = min(w, int((cx + bw / 2) * w))
            y2 = min(h, int((cy + bh / 2) * h))
            
            crop = img[y1:y2, x1:x2]
            
            # BOTTLENECK 4: Box is impossibly small (bad YOLO math)
            if crop.shape[0] < 5 or crop.shape[1] < 5: 
                diag_tiny_box += 1
                continue
                
            brightness = int(np.mean(crop))
            crop_name = f"{brightness:03d}_{base_name}_LINE_{line_idx}.jpg"
            cv2.imwrite(os.path.join(triage_dir, crop_name), crop)
            count += 1
            
    print("\n" + "="*50)
    print("[!] DIAGNOSTIC CASUALTY REPORT")
    print("="*50)
    print(f"[*] Successful Extractions: {count}")
    print(f"[!] Skipped (No matching image file found): {diag_no_match}")
    print(f"[!] Skipped (OpenCV could not read the image): {diag_cv2_fail}")
    print(f"[!] Skipped (Component was a Resistor/Capacitor, not an IC): {diag_wrong_class}")
    print(f"[!] Skipped (Bounding box was mathematically < 5 pixels): {diag_tiny_box}")

if __name__ == "__main__":
    extract_crops_loudly()