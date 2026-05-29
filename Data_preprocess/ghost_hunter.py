import os
import cv2
import numpy as np

def run_safe_ghost_hunter():
    print("[*] Initiating Non-Destructive Ghost Hunter Algorithm...")
    
    # 1. The Untouchable Vault (Input)
    images_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train"
    vault_labels_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\NLP_Cleaned_Labels"
    
    # 2. The Sandbox (Output)
    # The script will output the cleaned labels here. It will never touch the Vault.
    safe_output_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\Ghost_Free_Labels"
    suspect_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Ghost_Review"
    
    os.makedirs(safe_output_dir, exist_ok=True)
    os.makedirs(suspect_dir, exist_ok=True)
    
    # --- YOUR EXPERIMENT VARIABLE ---
    # Change this number, run the script, and check the Ghost_Review folder.
    # Keep lowering it until you stop seeing real components in the review folder.
    TEXTURE_THRESHOLD = 20.0 
    # --------------------------------
    
    total_boxes = 0
    ghosts_destroyed = 0
    
    for filename in os.listdir(vault_labels_dir):
        if not filename.endswith(".txt"): continue
            
        vault_path = os.path.join(vault_labels_dir, filename)
        output_path = os.path.join(safe_output_dir, filename)
        img_path = os.path.join(images_dir, filename.replace(".txt", ".jpg"))
        
        if not os.path.exists(img_path): continue
            
        img = cv2.imread(img_path)
        if img is None: continue
        h, w, _ = img.shape
        
        valid_lines = []
        
        with open(vault_path, 'r') as file:
            lines = file.readlines()
            
            for line in lines:
                parts = line.strip().split()
                if len(parts) < 5: continue
                
                total_boxes += 1
                cls_id = int(parts[0])
                cx, cy, bw, bh = map(float, parts[1:5])
                
                x1 = max(0, int((cx - bw / 2) * w))
                y1 = max(0, int((cy - bh / 2) * h))
                x2 = min(w, int((cx + bw / 2) * w))
                y2 = min(h, int((cy + bh / 2) * h))
                
                crop = img[y1:y2, x1:x2]
                
                if crop.shape[0] < 2 or crop.shape[1] < 2:
                    ghosts_destroyed += 1
                    continue
                    
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                texture_score = cv2.Laplacian(gray, cv2.CV_64F).var()
                
                if texture_score >= TEXTURE_THRESHOLD:
                    valid_lines.append(line) # It's a real component, save it!
                else:
                    # It's a ghost. Save the picture for review, but DO NOT add it to valid_lines
                    ghosts_destroyed += 1
                    suspect_filename = f"ghost_{ghosts_destroyed}_class{cls_id}_score{int(texture_score)}.jpg"
                    cv2.imwrite(os.path.join(suspect_dir, suspect_filename), crop)

        # Write the survivors to the brand NEW folder.
        with open(output_path, 'w') as file:
            file.writelines(valid_lines)
            
    print("\n" + "="*50)
    print(f"[!] GHOST HUNTER COMPLETE (Threshold: {TEXTURE_THRESHOLD})")
    print("="*50)
    print(f"[*] Total Boxes Audited: {total_boxes}")
    print(f"[*] Ghosts Removed: {ghosts_destroyed}")
    print(f"[*] Your master NLP labels were untouched.")
    print(f"[*] The new, cleaned labels are safely stored in: {safe_output_dir}")

if __name__ == "__main__":
    run_safe_ghost_hunter()