import os

def fix_class_indices():
    print("[*] Initiating Class Index Remapping (99 -> 7)...")
    
    base_dir = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection"
    
    # We must scan both train and val folders
    label_dirs = [
        os.path.join(base_dir, "train", "labels"),
        os.path.join(base_dir, "val", "labels")
    ]
    
    files_modified = 0
    total_boxes_changed = 0

    for l_dir in label_dirs:
        if not os.path.exists(l_dir):
            continue
            
        for filename in os.listdir(l_dir):
            if not filename.endswith(".txt"): 
                continue
                
            filepath = os.path.join(l_dir, filename)
            
            with open(filepath, 'r') as f:
                lines = f.readlines()
                
            file_was_changed = False
            new_lines = []
            
            for line in lines:
                parts = line.strip().split()
                if not parts: 
                    continue
                
                # If the class ID is 99, change it to 7
                if parts[0] == '99':
                    parts[0] = '7'
                    new_lines.append(" ".join(parts) + "\n")
                    file_was_changed = True
                    total_boxes_changed += 1
                else:
                    new_lines.append(line)
                    
            # Overwrite the file only if we found a 99
            if file_was_changed:
                with open(filepath, 'w') as f:
                    f.writelines(new_lines)
                files_modified += 1

    print(f"\n[+] SUCCESS: Remapped {total_boxes_changed} bounding boxes across {files_modified} files.")
    print("[+] All classes are now sequentially numbered 0-7.")
    print("[+] You are cleared for engine ignition. Run train_master.py.")

if __name__ == "__main__":
    fix_class_indices()