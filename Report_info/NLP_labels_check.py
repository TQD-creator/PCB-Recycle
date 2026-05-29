import os
import random
import cv2
from pathlib import Path

def run_visual_audit():
    print("[*] Initiating Statistical Visual Audit...")
    
    # Update these paths
    images_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train"
    labels_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\NLP_Cleaned_Labels"
    audit_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Visual_Audit_Output"
    
    os.makedirs(audit_dir, exist_ok=True)
    
    # Master dictionary
    classes = {0: "Capacitor", 1: "Resistor", 2: "IC", 3: "Diode", 
               4: "LED", 5: "Inductor", 6: "Connector", 99: "Unknown"}
               
    # Get all valid label files
    all_labels = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
    
    # Randomly sample 50 images
    sample_size = min(50, len(all_labels))
    sampled_files = random.sample(all_labels, sample_size)
    
    print(f"[*] Randomly selected {sample_size} images for visual inspection.")
    
    for label_file in sampled_files:
        img_name = label_file.replace('.txt', '.jpg')
        img_path = os.path.join(images_dir, img_name)
        txt_path = os.path.join(labels_dir, label_file)
        
        if not os.path.exists(img_path):
            continue
            
        # Read image
        img = cv2.imread(img_path)
        if img is None: continue
        h, w, _ = img.shape
        
        # Read and draw labels
        with open(txt_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5: continue
                
                cls_id = int(parts[0])
                cx, cy, bw, bh = map(float, parts[1:5])
                
                # YOLO to Pixel Math
                x1 = int((cx - bw / 2) * w)
                y1 = int((cy - bh / 2) * h)
                x2 = int((cx + bw / 2) * w)
                y2 = int((cy + bh / 2) * h)
                
                name = classes.get(cls_id, "Unknown")
                color = (0, 255, 0) if cls_id == 2 else (0, 165, 255) # ICs are Green, others Orange
                
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                cv2.putText(img, name, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
        # Save to audit folder
        cv2.imwrite(os.path.join(audit_dir, img_name), img)
        
    print(f"[*] Audit complete. Please open: {audit_dir}")
    print("[*] Spend 5 minutes scrolling through these images to verify the NLP logic.")

if __name__ == "__main__":
    run_visual_audit()