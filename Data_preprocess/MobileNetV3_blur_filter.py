import cv2
import os
import shutil

def variance_of_laplacian(image):
    # Computes the mathematical sharpness of the image matrix
    return cv2.Laplacian(image, cv2.CV_64F).var()

def execute_laplacian_purge():
    print("\n[!] ================= THE LAPLACIAN PURGE ENGINE (WINDOWS) ================= [!]")
    
    # --- CONFIGURATION ZONE ---
    # Using 'r' before the string prevents Windows backslash errors.
    # Replace 'Lenovo' with your actual Windows username if it is different.
    INPUT_DIR = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\MobileNet_Pure_Dataset"
    
    # These folders will be automatically created right next to your input folder
    SHARP_DIR = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Dataset_Filtered_Sharp"
    BLURRY_DIR = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Dataset_Rejected_Blurry"
    
    # THE KILL SWITCH THRESHOLD
    SHARPNESS_THRESHOLD = 78.0 

    # Safety check to ensure the input directory actually exists before running
    if not os.path.exists(INPUT_DIR):
        print(f"[-] FATAL ERROR: Cannot find the folder at {INPUT_DIR}")
        print("[-] Please check your Windows username and path.")
        return

    os.makedirs(SHARP_DIR, exist_ok=True)
    os.makedirs(BLURRY_DIR, exist_ok=True)

    total_scanned = 0
    total_saved = 0
    total_rejected = 0

    print(f"[*] Scanning {INPUT_DIR} for mathematical pixel degradation...")

    # Walk through every class folder (capacitor, resistor, etc.)
    for root, dirs, files in os.walk(INPUT_DIR):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                total_scanned += 1
                file_path = os.path.join(root, file)
                
                # Read in grayscale (color data is irrelevant to mathematical sharpness)
                image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
                
                if image is None:
                    continue
                
                # Calculate the exact sharpness score
                fm = variance_of_laplacian(image)
                
                # Reconstruct the class subfolder architecture
                class_name = os.path.basename(root)
                sharp_class_dir = os.path.join(SHARP_DIR, class_name)
                blurry_class_dir = os.path.join(BLURRY_DIR, class_name)
                os.makedirs(sharp_class_dir, exist_ok=True)
                os.makedirs(blurry_class_dir, exist_ok=True)
                
                if fm > SHARPNESS_THRESHOLD:
                    # Move to the Sharp folder
                    dest_path = os.path.join(sharp_class_dir, f"{fm:.1f}_{file}")
                    shutil.copy(file_path, dest_path)
                    total_saved += 1
                else:
                    # Quarantine in the Blurry folder
                    dest_path = os.path.join(blurry_class_dir, f"{fm:.1f}_{file}")
                    shutil.copy(file_path, dest_path)
                    total_rejected += 1

    print("\n[+] PURGE COMPLETE.")
    print(f"[*] Total Components Scanned: {total_scanned}")
    print(f"[+] Sharp Data Retained: {total_saved} (Safe for Forgery)")
    print(f"[-] Blurry Data Rejected: {total_rejected} (Quarantined)")
    
if __name__ == "__main__":
    execute_laplacian_purge()