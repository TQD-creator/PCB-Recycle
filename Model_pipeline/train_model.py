import traceback
from ultralytics import YOLO
import torch

def train_bulletproof_model():
    try:
        print("[*] Acquiring Official Pre-Trained YOLOv8s Base Model...")
        model = YOLO("yolov8s.pt")
        
        device = "0" if torch.cuda.is_available() else "cpu"
        print(f"[*] Hardware engine selected: {device.upper()}")
        
        print("[*] Initiating Bulletproof Fine-Tuning Pipeline...")
        
        results = model.train(
            # 1. Core Data
            data=r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\YOLO_Dataset\data.yaml",
            epochs=300,
            patience=25,
            
            # 2. LAPTOP SURVIVAL SETTINGS (Prevents Crashing)
            imgsz=640,
            batch=8,
            device=device,
            cache=False,# CRITICAL: Stops your RAM from overflowing
            workers=2,# REDUCED: Limits background threads
            
            # 3. Transfer Learning Math
            freeze=10,
            optimizer="AdamW",
            lr0=0.001,
            lrf=0.01,
            cos_lr=True,
            
            # 4. Output Location
            project="Foxconn_PCB",
            name="YOLOv8s_Balanced_Run"
        )
        
        print("\n[*] TRAINING SUCCESSFULLY COMPLETED!")
        print("[*] Your champion weights are saved in: Foxconn_PCB/YOLOv8s_Balanced_Run/weights/best.pt")

    except Exception as e:
        # 5. THE CRASH CATCHER
        print("\n[!] ================= CRITICAL CRASH DETECTED ================= [!]")
        print(f"[*] The AI engine encountered a fatal error: {str(e)}")
        print("[*] Writing detailed traceback report to 'crash_log.txt'...")
        with open("crash_log.txt", "w") as f:
            traceback.print_exc(file=f)
        print("[!] Please open crash_log.txt to see exactly what killed the process.")

if __name__ == "__main__":
    train_bulletproof_model()