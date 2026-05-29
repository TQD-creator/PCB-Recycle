import cv2
import os
import numpy as np

# ==========================================
# 1. DIRECTORY CONFIGURATION
# ==========================================
# Pointing directly to your final YOLO dataset training folder
IMAGES_DIR = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\YOLO_Dataset\images\train"
LABELS_DIR = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\YOLO_Dataset\labels\train"

# Output folder for this final check
OUTPUT_DIR = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\QA_Review_Final"

# Your Master Classes
CLASS_NAMES = {
    0: "Capacitor", 1: "Resistor", 2: "IC", 
    3: "Diode", 4: "LED", 5: "Inductor", 6: "Connector"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

def draw_final_qa():
    print(f"[*] Scanning YOLO training dataset in: {IMAGES_DIR}")
    
    valid_exts = ('.jpg', '.jpeg', '.png', '.bmp')
    image_files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith(valid_exts)]
    
    if len(image_files) == 0:
        print("[!] ERROR: No images found. Check your IMAGES_DIR path!")
        return

    print(f"[*] Found {len(image_files)} training images. Generating QA boards...\n")
    
    success_count = 0

    for filename in image_files:
        img_path = os.path.join(IMAGES_DIR, filename)
        txt_filename = os.path.splitext(filename)[0] + ".txt"
        txt_path = os.path.join(LABELS_DIR, txt_filename)
        
        if not os.path.exists(txt_path):
            continue 
            
        # ==========================================
        # NUMPY MEMORY BYPASS FOR READING (Anti-Crash)
        # ==========================================
        img_array = np.fromfile(img_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if img is None: 
            print(f"[!] Warning: Data corruption in image {filename}")
            continue
            
        h, w, _ = img.shape
        
        with open(txt_path, "r") as f:
            lines = f.readlines()
            
        boxes_drawn = 0
        for line in lines:
            parts = line.strip().split()
            if len(parts) != 5: 
                continue
            
            class_id = int(parts[0])
            x_center, y_center, width, height = map(float, parts[1:])
            
            # Math to convert YOLO back to pixels for drawing
            x1 = int((x_center - width/2) * w)
            y1 = int((y_center - height/2) * h)
            x2 = int((x_center + width/2) * w)
            y2 = int((y_center + height/2) * h)
            
            # Draw Box (Green) and Text (Red)
            label = CLASS_NAMES.get(class_id, "Unknown")
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            boxes_drawn += 1
            
        # ==========================================
        # NUMPY MEMORY BYPASS FOR WRITING
        # ==========================================
        if boxes_drawn > 0:
            output_path = os.path.join(OUTPUT_DIR, filename)
            is_success, im_buf_arr = cv2.imencode('.jpg', img)
            if is_success:
                im_buf_arr.tofile(output_path)
                success_count += 1

    print("\n" + "="*50)
    print(f"FINAL QA REVIEW COMPLETE")
    print(f"Successfully generated QA images for: {success_count} boards")
    print(f"Open this folder and verify the boxes: {OUTPUT_DIR}")
    print("="*50)

if __name__ == "__main__":
    draw_final_qa()