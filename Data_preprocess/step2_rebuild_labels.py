import os

def rebuild_and_analyze():
    print("[*] Initiating Master Label Synchronization and Dataset Analytics...")
    
    # Verify Paths (Ensure these are exactly correct)
    labels_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\NLP_Cleaned_Labels"
    triage_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\Visual_Triage"
    
    if not os.path.exists(labels_dir) or not os.path.exists(triage_dir):
        print("[!] FATAL: Directories not found. Check your paths.")
        return

    MASTER_CLASSES = {
        0: "capacitor",
        1: "resistor",
        2: "ic", 
        3: "diode",
        4: "led",
        5: "inductor",
        6: "connector",
        99: "unknown"
    }

    surviving_crops = set(os.listdir(triage_dir))
    
    # Analytics Trackers
    deleted_ghosts_count = 0
    files_modified = 0
    class_distribution = {k: 0 for k in MASTER_CLASSES.keys()}
    total_valid_boxes = 0

    txt_files = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
    
    for filename in txt_files:
        txt_path = os.path.join(labels_dir, filename)
        base_name = filename.replace(".txt", "")
        
        with open(txt_path, 'r') as f:
            lines = f.readlines()
            
        valid_lines = []
        file_was_changed = False
        
        for line_idx, line in enumerate(lines):
            parts = line.strip().split()
            if len(parts) < 5: continue
            
            cls_id = int(parts[0])
            
            # Logic for Minority Classes (Triaged)
            if cls_id in [0, 2, 3, 99]:
                search_suffix = f"_{base_name}_LINE_{line_idx}.jpg"
                survived = any(crop.endswith(search_suffix) for crop in surviving_crops)
                
                if survived:
                    valid_lines.append(line)
                    if cls_id in class_distribution:
                        class_distribution[cls_id] += 1
                    total_valid_boxes += 1
                else:
                    deleted_ghosts_count += 1
                    file_was_changed = True
            
            # Logic for Majority Classes (Not Triaged)
            else:
                valid_lines.append(line)
                if cls_id in class_distribution:
                    class_distribution[cls_id] += 1
                total_valid_boxes += 1
                
        # Overwrite file only if we deleted something
        if file_was_changed:
            with open(txt_path, 'w') as f:
                f.writelines(valid_lines)
            files_modified += 1

    # --- PRINTING THE ANALYTICS REPORT ---
    print("\n" + "="*60)
    print("   DATASET HEALTH & DISTRIBUTION REPORT (POST-CLEANUP)")
    print("="*60)
    print(f"[-] Total Ghost/Bad Labels Permanently Erased: {deleted_ghosts_count}")
    print(f"[-] Total Text Files Cleaned: {files_modified}")
    print(f"[-] Total Valid Bounding Boxes Remaining: {total_valid_boxes}")
    print("-" * 60)
    print(f"{'CLASS ID':<10} | {'CLASS NAME':<15} | {'COUNT':<10} | {'PERCENTAGE'}")
    print("-" * 60)
    
    for cls_id, name in MASTER_CLASSES.items():
        count = class_distribution[cls_id]
        if total_valid_boxes > 0:
            percentage = (count / total_valid_boxes) * 100
        else:
            percentage = 0.0
        print(f"{cls_id:<10} | {name:<15} | {count:<10} | {percentage:.2f}%")
    print("="*60)

if __name__ == "__main__":
    rebuild_and_analyze()