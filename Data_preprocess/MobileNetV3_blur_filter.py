import cv2
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

def variance_of_laplacian(image_path):
    """
    Safely reads the image and computes the mathematical sharpness.
    Returns the variance float, or -1.0 if the image is corrupted.
    """
    try:
        # cv2 doesn't natively love pathlib objects in older versions, so we convert to string
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None or image.size == 0:
            return -1.0
        return cv2.Laplacian(image, cv2.CV_64F).var()
    except Exception:
        return -1.0

def process_single_image(file_path, input_dir, sharp_dir, blurry_dir, threshold):
    """
    The worker function that analyzes a single image and routes it.
    Designed specifically to be run in a parallel thread.
    """
    # Calculate sharpness
    fm = variance_of_laplacian(file_path)
    
    # If corrupted, reject it automatically
    if fm == -1.0:
        return "corrupted"

    # Reconstruct the exact subfolder architecture (e.g., /IC_Square)
    relative_path = file_path.relative_to(input_dir)
    class_name = relative_path.parent
    
    if fm > threshold:
        # Route to Sharp Vault
        dest_dir = sharp_dir / class_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{fm:.1f}_{file_path.name}"
        shutil.copy(str(file_path), str(dest_path))
        return "sharp"
    else:
        # Route to Blurry Quarantine
        dest_dir = blurry_dir / class_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{fm:.1f}_{file_path.name}"
        shutil.copy(str(file_path), str(dest_path))
        return "blurry"

def execute_modern_laplacian_purge():
    print("\n[!] ================= MULTI-THREADED LAPLACIAN PURGE ================= [!]")
    
    # --- CONFIGURATION ZONE ---
    # Pathlib handles all the messy Windows slashes automatically.
    INPUT_DIR = Path(r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Siamese_Network_Dataset")
    SHARP_DIR = Path(r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Dataset_Filtered_Sharp")
    BLURRY_DIR = Path(r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Dataset_Rejected_Blurry")
    
    SHARPNESS_THRESHOLD = 78.0 
    MAX_THREADS = 8 # Adjust based on your CPU cores (8 to 16 is standard)

    if not INPUT_DIR.exists():
        print(f"[-] FATAL ERROR: Cannot find the folder at {INPUT_DIR}")
        return

    # Gather all images recursively
    print("[*] Indexing dataset files...")
    # Grabs jpg, jpeg, png in one clean generator
    all_files = [f for f in INPUT_DIR.rglob('*') if f.suffix.lower() in ['.png', '.jpg', '.jpeg']]
    
    if not all_files:
        print("[-] No images found in the input directory.")
        return

    print(f"[*] Found {len(all_files)} total images. Igniting {MAX_THREADS} parallel threads...\n")

    stats = {"sharp": 0, "blurry": 0, "corrupted": 0}

    # Execute the multithreaded pool with a visual progress bar
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Map the worker function to our files
        futures = {
            executor.submit(process_single_image, f, INPUT_DIR, SHARP_DIR, BLURRY_DIR, SHARPNESS_THRESHOLD): f 
            for f in all_files
        }
        
        # Wrap the futures in tqdm for the progress bar
        for future in tqdm(as_completed(futures), total=len(all_files), desc="Purging Dataset", unit="img"):
            result = future.result()
            stats[result] += 1

    print("\n[+] PURGE COMPLETE.")
    print(f"[*] Total Scanned:   {len(all_files)}")
    print(f"[+] Sharp Retained:  {stats['sharp']} (Ready for Siamese Forgery)")
    print(f"[-] Blurry Rejected: {stats['blurry']} (Quarantined)")
    if stats['corrupted'] > 0:
        print(f"[!] Corrupted Files: {stats['corrupted']} (Deleted or Unreadable)")

if __name__ == "__main__":
    execute_modern_laplacian_purge()