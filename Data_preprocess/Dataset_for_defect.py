import os
import cv2
import numpy as np
import random
import shutil

print("\n[!] ================= THE PHYSICAL FORGERY ENGINE ================= [!]")

def apply_defect(img, defect_type):
    """
    Applies mathematically modeled physical defects to a pristine component crop.
    """
    fake = img.copy()
    h, w = fake.shape[:2]
    
    try:
        # ---------------------------------------------------------
        # CATEGORY 1: THE VIABLE SYNTHETICS
        # ---------------------------------------------------------
        if defect_type == 'shifted':
            # Combines Shift (Translation) and Misalignment (Rotation)
            center = (w // 2, h // 2)
            angle = random.choice([random.randint(10, 35), random.randint(-35, -10)])
            shift_x = random.randint(-w//5, w//5)
            shift_y = random.randint(-h//5, h//5)
            
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            cos, sin = np.abs(M[0, 0]), np.abs(M[0, 1])
            new_w, new_h = int((h * sin) + (w * cos)), int((h * cos) + (w * sin))
            
            M[0, 2] += (new_w / 2) - center[0] + shift_x
            M[1, 2] += (new_h / 2) - center[1] + shift_y
            
            fake = cv2.warpAffine(fake, M, (new_w, new_h), borderMode=cv2.BORDER_REPLICATE)
            fake = cv2.resize(fake, (w, h), interpolation=cv2.INTER_CUBIC)

        elif defect_type == 'bridge':
            # Simulates a metallic solder short between pins
            if random.choice([True, False]): # Vertical
                x = random.randint(int(w*0.1), int(w*0.9))
                y1, y2 = random.randint(0, h//3), random.randint((2*h)//3, h)
                pt1, pt2 = (x, y1), (x + random.randint(-5, 5), y2)
            else: # Horizontal
                y = random.randint(int(h*0.1), int(h*0.9))
                x1, x2 = random.randint(0, w//3), random.randint((2*w)//3, w)
                pt1, pt2 = (x1, y), (x2, y + random.randint(-5, 5))

            bridge_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.line(bridge_mask, pt1, pt2, 255, thickness=random.randint(3, 7))
            bridge_mask = cv2.GaussianBlur(bridge_mask, (5, 5), 0)

            # Specular metal reflection logic
            bridge_area = fake[bridge_mask > 50].astype(np.float32)
            bridge_area = np.clip(bridge_area * 1.8, 0, 255).astype(np.uint8)
            fake[bridge_mask > 50] = bridge_area

        elif defect_type == 'dirty':
            # Simulates baked flux residue or factory dust
            stain_color = np.array([30, 80, 120]) # BGR yellowish-brown
            noise = np.random.randint(0, 255, (h, w), dtype=np.uint8)
            cloud_mask = cv2.GaussianBlur(noise, (31, 31), 0)
            
            _, cloud_mask = cv2.threshold(cloud_mask, 140, 255, cv2.THRESH_BINARY)
            cloud_mask = cv2.GaussianBlur(cloud_mask, (15, 15), 0) 
            
            alpha = (cloud_mask / 255.0) * 0.4 # 40% Opacity
            alpha = np.stack([alpha]*3, axis=-1)
            fake = (fake * (1 - alpha) + stain_color * alpha).astype(np.uint8)
            
        elif defect_type == 'bad_solder':
            # Simulates dull, crystallized cold joints
            target_w = int(w * 0.25)
            is_left = random.choice([True, False])
            x_start = 0 if is_left else w - target_w
            x_end = target_w if is_left else w
            
            solder_roi = fake[0:h, x_start:x_end].astype(np.float32)
            # Darken to kill reflection
            solder_roi = solder_roi * random.uniform(0.4, 0.6)
            # Add salt/pepper crystallization
            grain = np.random.normal(0, 25, solder_roi.shape).astype(np.float32)
            solder_roi = np.clip(solder_roi + grain, 0, 255).astype(np.uint8)
            fake[0:h, x_start:x_end] = solder_roi

        # ---------------------------------------------------------
        # CATEGORY 2: THE QUARANTINED SYNTHETICS (USE WITH EXTREME CAUTION)
        # ---------------------------------------------------------
        elif defect_type == 'crack':
            pts = [(random.randint(0, int(w*0.8)), random.randint(0, int(h*0.5)))]
            for _ in range(random.randint(4, 9)):
                pts.append((np.clip(pts[-1][0] + random.randint(-15, 15), 0, w), np.clip(pts[-1][1] + random.randint(5, 20), 0, h)))
            cv2.polylines(fake, [np.array(pts, np.int32)], False, (10, 10, 15), random.randint(1, 2))
            
        elif defect_type == 'burn':
            cx, cy = random.randint(w//4, int(w*0.75)), random.randint(h//4, int(h*0.75))
            base_radius = random.randint(min(w,h)//6, min(w,h)//3)
            mask = np.zeros((h, w), dtype=np.uint8)
            
            for _ in range(random.randint(4, 7)):
                offset_x = random.randint(-base_radius//2, base_radius//2)
                offset_y = random.randint(-base_radius//2, base_radius//2)
                cv2.circle(mask, (cx + offset_x, cy + offset_y), random.randint(base_radius//2, base_radius), 255, -1)
            
            mask = cv2.GaussianBlur(mask, (5, 5), 0)
            noise = np.random.randint(0, 40, (h, w, 3), dtype=np.uint8)
            mask_bool = mask > 100
            fake[mask_bool] = noise[mask_bool]
            
    except Exception as e:
        # If OpenCV math fails on a weirdly shaped crop, return original to prevent crashes
        pass 
        
    return fake


def generate_dataset(input_dir, output_dir, num_fakes=5, train_ratio=0.8, active_defects=None):
    """
    Crawls the input directory, splits data to prevent leaks, applies defects, and saves to output.
    """
    if active_defects is None:
        active_defects = ['shifted', 'bridge', 'dirty', 'bad_solder']
        
    if 'burn' in active_defects or 'crack' in active_defects:
        print("[-] WARNING: You are activating 'burn' or 'crack'. These are highly prone to the Clever Hans effect.")
        print("[-] Proceeding at your own QA risk.\n")

    if os.path.exists(output_dir):
        print(f"[*] Purging existing output directory: {output_dir}")
        shutil.rmtree(output_dir)

    total_generated = 0
    
    for root, _, files in os.walk(input_dir):
        class_name = os.path.basename(root)
        if not class_name or class_name == os.path.basename(input_dir): 
            continue
            
        print(f"[*] Processing Class: {class_name}...")
        
        # Create Train/Val PyTorch structure
        for split in ['train', 'val']:
            os.makedirs(os.path.join(output_dir, split, f"good_{class_name}"), exist_ok=True)
            os.makedirs(os.path.join(output_dir, split, f"bad_{class_name}"), exist_ok=True)

        for file in files:
            if not file.lower().endswith(('.png', '.jpg', '.jpeg')): 
                continue
                
            img_path = os.path.join(root, file)
            img = cv2.imread(img_path)
            if img is None: 
                continue
            
            # SPLIT FIRST: Prevents background data leaks
            split = 'train' if random.random() < train_ratio else 'val'
            
            # Save the pristine good image
            pure_path = os.path.join(output_dir, split, f"good_{class_name}", f"{file}_pure.jpg")
            cv2.imwrite(pure_path, img)
            
            # Forge the defects
            for i in range(num_fakes):
                defect = random.choice(active_defects)
                fake_img = apply_defect(img, defect)
                
                fake_path = os.path.join(output_dir, split, f"bad_{class_name}", f"{file}_fake_{defect}_{i}.jpg")
                cv2.imwrite(fake_path, fake_img)
                total_generated += 1

    print(f"\n[+] MISSION ACCOMPLISHED. {total_generated} synthetic defects generated safely.")


if __name__ == "__main__":
    # --- CONFIGURATION ZONE ---
    # Update these paths to match your local or cloud environment
    INPUT_DATA_PATH = r"C:\\Users\\Lenovo\\Documents\\Foxconn\\PCB-Detection\\Dataset_Filtered_Sharp"
    OUTPUT_DATA_PATH = r"C:\\Users\\Lenovo\\Documents\\Foxconn\\PCB-Detection\\Defect_Dataset_Final"
    
    # The multiplier. 1 good image = 5 fake defects.
    MULTIPLIER = 5 
    
    # 80% Training, 20% Validation
    TRAIN_VAL_SPLIT = 0.8 
    
    # The Safe List. 
    # Do NOT add 'burn' or 'crack' unless you accept the QA risk.
    # Do NOT add 'missing', 'stack', or 'pin' (Gather physical data for those).
    VIABLE_DEFECTS = ['shifted', 'bridge', 'dirty', 'bad_solder']
    
    if not os.path.exists(INPUT_DATA_PATH):
        print(f"[-] FATAL ERROR: Input directory '{INPUT_DATA_PATH}' does not exist.")
    else:
        generate_dataset(
            input_dir=INPUT_DATA_PATH, 
            output_dir=OUTPUT_DATA_PATH, 
            num_fakes=MULTIPLIER, 
            train_ratio=TRAIN_VAL_SPLIT,
            active_defects=VIABLE_DEFECTS
        )