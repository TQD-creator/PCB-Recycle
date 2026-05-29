# ==========================================
# CELL 1: GLOBAL SETUP & DATASET EXTRACTION
# ==========================================
import os
import glob
import shutil
import torch
import gc
from datetime import datetime
import pandas as pd
from google.colab import drive
from ultralytics import YOLO
import ultralytics

print("[*] Mounting Google Drive...")
drive.mount('/content/drive')

print("[*] Verifying Ultralytics Neural Engine...")
ultralytics.checks()

# BYPASS DRIVE BOTTLENECK: Copy zip to local NVMe and extract
print("\n[*] Deploying Dataset to local SSD...")
!cp "/content/drive/MyDrive/Grad_project/Foxconn_Cloud_Run/Foxconn_Dataset.zip" /content/
!unzip -q /content/Foxconn_Dataset.zip -d /content/datasets/
print("[+] Dataset successfully deployed.")

def fix_yaml_paths():
    """Helper function to hunt down and correct data.yaml absolute paths."""
    print("\n[*] Initiating Deep Path Radar...")
    yaml_search = glob.glob('/content/datasets/**/data.yaml', recursive=True)

    if not yaml_search:
        print("[-] FATAL ERROR: data.yaml is missing. Re-zip and re-upload.")
        return None

    actual_yaml_path = yaml_search[0]
    actual_root_dir = os.path.dirname(actual_yaml_path)

    print("[*] Performing surgical correction on data.yaml...")
    with open(actual_yaml_path, 'r') as file:
        lines = file.readlines()
        
    with open(actual_yaml_path, 'w') as file:
        for line in lines:
            if line.strip().startswith('path:'):
                file.write(f"path: {actual_root_dir}\n")
            else:
                file.write(line)
                
    print(f"[+] CORRECTED: YOLO is locked onto {actual_root_dir}")
    return actual_yaml_path
# ==========================================
# CELL 2: PHASE 1 TRAINING (NO CONNECTOR)
# ==========================================
def ignite_training_pipeline():
    actual_yaml_path = fix_yaml_paths()
    if not actual_yaml_path: return

    # --- DIRECTORIES ---
    PROJECT_DIR = "/content/drive/MyDrive/Foxconn_Cloud_Run/Models"
    RUN_NAME = "YOLOv8s_No_Connector"
    GOLDEN_VAULT = "/content/drive/MyDrive/Foxconn_Cloud_Run/Golden_Weights"
    os.makedirs(GOLDEN_VAULT, exist_ok=True)

    print("\n[*] Igniting Cloud GPU Training Engine...")
    model = YOLO("yolov8s.pt")

    try:
        # --- THE MASTER TRAINING BLOCK ---
        model.train(
            data=actual_yaml_path,
            epochs=180,
            patience=50,
            classes=[0, 1, 2, 3, 4, 5, 7], # BYPASS CLASS 6 (CONNECTOR)
            
            imgsz=640,
            batch=32,
            device=0,
            workers=8,
            
            mosaic=0.5,
            mixup=0.0,
            copy_paste=0.0,
            degrees=5.0,
            cls=2.0,
            box=7.5,
            
            project=PROJECT_DIR,
            name=RUN_NAME
        )
        print("\n[+] TRAINING COMPLETE. Initiating extraction protocol...")

    except Exception as e:
        print(f"\n[-] TRAINING INTERRUPTED OR CRASHED: {e}")
        print("[!] Attempting to extract whatever weights survived...")

    finally:
        # --- THE AUTO-EXTRACTION PROTOCOL ---
        weights_dir = os.path.join(PROJECT_DIR, RUN_NAME, "weights")
        best_src = os.path.join(weights_dir, "best.pt")
        last_src = os.path.join(weights_dir, "last.pt")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")

        if os.path.exists(best_src):
            safe_best = os.path.join(GOLDEN_VAULT, f"best_NoConnector_{timestamp}.pt")
            shutil.copy(best_src, safe_best)
            print(f"[+] SECURED: best.pt safely copied to {safe_best}")

        if os.path.exists(last_src):
            safe_last = os.path.join(GOLDEN_VAULT, f"last_NoConnector_{timestamp}.pt")
            shutil.copy(last_src, safe_last)
            print(f"[+] SECURED: last.pt safely copied to {safe_last}")

if __name__ == "__main__":
    ignite_training_pipeline()
    
# ==========================================
# CELL 3: PHASE 2 TRAINING (MAX POWER)
# ==========================================
def ignite_phase_two():
    print("\n[!] PURGING VRAM CACHE...")
    torch.cuda.empty_cache()
    gc.collect()
    print("[+] GPU Memory Cleared. Maximum VRAM available.")

    actual_yaml_path = fix_yaml_paths()
    if not actual_yaml_path: return

    # --- THE COLD TRANSFER RESUME ---
    LAST_WEIGHTS_PATH = "/content/drive/MyDrive/Foxconn_Cloud_Run/Models/YOLOv8s_Phase2_MaxPower/weights/last.pt"

    if not os.path.exists(LAST_WEIGHTS_PATH):
        print(f"[-] CRITICAL ERROR: Cannot find the 154-epoch weights at {LAST_WEIGHTS_PATH}")
        return

    print(f"[*] Loading 154-epoch brain from: {LAST_WEIGHTS_PATH}")
    model = YOLO(LAST_WEIGHTS_PATH)

    print("[*] Igniting Phase 2 GPU Training (NO SACRIFICES)...")
    model.train(
        data=actual_yaml_path,
        epochs=150,
        patience=50,
        
        imgsz=640,
        batch=32,
        device=0,
        workers=4, # Dropped from 8 to 4 to prevent CPU RAM bottlenecking
        
        mosaic=0.5,
        mixup=0.0,
        copy_paste=0.0,
        degrees=5.0,
        
        cls=2.0,
        fl_gamma=1.5, # Focal Loss activated
        box=7.5,
        
        project="/content/drive/MyDrive/Foxconn_Cloud_Run/Models",
        name="YOLOv8s_Phase2_MaxPower"
    )

if __name__ == "__main__":
    # Uncomment to execute
    # ignite_phase_two()
    pass

# ==========================================
# CELL 4: THE 9-WAY MODEL SHOOTOUT
# ==========================================
def execute_shootout():
    print("\n[!] ================= MODEL SHOOTOUT ================= [!]")
    actual_yaml_path = fix_yaml_paths()
    if not actual_yaml_path: return

    # --- CONFIGURATION ZONE ---
    MODELS = {
        "1_CPU_old_Best": "/content/drive/MyDrive/Foxconn_Cloud_Run/Models/YOLOv8s_T4_Fixed_Augments-4/weights/old_cpu_best.pt",
        "2_CPU_old_Last": "/content/drive/MyDrive/Foxconn_Cloud_Run/Models/YOLOv8s_T4_Fixed_Augments-4/weights/old_cpu_last.pt",
        "3_CPU_Best": "/content/drive/MyDrive/Foxconn_Cloud_Run/Models/YOLOv8s_T4_Fixed_Augments-4/weights/cpu_best.pt",
        "4_CPU_Last": "/content/drive/MyDrive/Foxconn_Cloud_Run/Models/YOLOv8s_T4_Fixed_Augments-4/weights/cpu_last.pt",
        "5_GPU_2_Best": "/content/drive/MyDrive/Foxconn_Cloud_Run/Models/YOLOv8s_Phase2_MaxPower/weights/best.pt",
        "6_GPU_2_Last": "/content/drive/MyDrive/Foxconn_Cloud_Run/Models/YOLOv8s_Phase2_MaxPower/weights/last.pt",
        "7_GPU_1_Best": "/content/drive/MyDrive/Foxconn_Cloud_Run/Models/YOLOv8s_T4_Fixed_Augments-4/weights/last.pt",
        "8_GPU_1_Last": "/content/drive/MyDrive/Foxconn_Cloud_Run/Models/YOLOv8s_T4_Fixed_Augments-4/weights/best.pt", # Fixed syntax error here
        "9_GPU_3_Best": "/content/drive/MyDrive/Foxconn_Cloud_Run/Golden_Weights/best_NoConnector_20260526_2158.pt",
    }

    RAW_IMAGES_FOLDER = "/content/drive/MyDrive/Grad_project/Real_Factory_Test_Image"
    results_data = []

    # --- THE GAUNTLET ---
    for name, path in MODELS.items():
        print(f"\n[*] === INTERROGATING: {name} ===")
        if not os.path.exists(path):
            print(f"[-] ERROR: Could not find {path}. Skipping.")
            continue

        try:
            model = YOLO(path)

            # STAGE 1: MATH EXAM
            print(f"[*] Executing mathematical validation...")
            metrics = model.val(data=actual_yaml_path, split='val', verbose=False)
            
            results_data.append({
                "Model Name": name,
                "mAP@50": round(metrics.box.map50, 4),
                "Precision": round(metrics.box.mp, 4),
                "Recall": round(metrics.box.mr, 4)
            })
            print(f"[+] Math Scored -> Precision: {metrics.box.mp:.2f} | Recall: {metrics.box.mr:.2f}")

            # STAGE 2: VISUAL REALITY
            if os.path.exists(RAW_IMAGES_FOLDER) and len(os.listdir(RAW_IMAGES_FOLDER)) > 0:
                print(f"[*] Executing Visual Inference on raw images...")
                model.predict(
                    source=RAW_IMAGES_FOLDER,
                    conf=0.25,
                    save=True,
                    project="/content/drive/MyDrive/Foxconn_Cloud_Run/Shootout_Visuals",
                    name=name
                )
            else:
                print(f"[-] ERROR: Cannot find raw images at {RAW_IMAGES_FOLDER}.")

        except Exception as e:
            print(f"[-] FATAL ERROR evaluating {name}: {e}")

    # --- THE FINAL SCORECARD ---
    print("\n[!] ================= FINAL SCORECARD ================= [!]")
    if results_data:
        df = pd.DataFrame(results_data)
        print(df.to_string(index=False))
        
        csv_path = "/content/drive/MyDrive/Foxconn_Cloud_Run/Eight_Way_Shootout.csv"
        df.to_csv(csv_path, index=False)
        print(f"\n[+] Exported raw data to {csv_path}")
    else:
        print("[-] No models were successfully evaluated.")

if __name__ == "__main__":
    # Uncomment to execute
    # execute_shootout()
    pass

# # So sánh Model YOLO: Tác động của Dữ liệu Lỗi (Missing Defects)

# 1. **Mục đích:** Giảm lỗi nhận diện nhầm với background (False Positives).
# 2. **Phương pháp:** * So sánh 1 model được train với dataset có chứa lỗi "missing".
#    * So sánh với 2 model được train trên dataset đã loại bỏ hoàn toàn nhầm lẫn về "missing defect".
# 3. **Kế hoạch triển khai:**
#    * **Code:** [Thêm mã kiểm thử đặc tả tại đây]
#    * **Đánh giá Phương pháp:** Tại sao chọn phương pháp này? Liệu nó có triệt tiêu được nhiễu background và tối ưu hóa bounding box đúng như mục đích ban đầu không?

# # MobileNetV3
# [Khu vực dành cho thử nghiệm MobileNetV3/Classification Pipeline]