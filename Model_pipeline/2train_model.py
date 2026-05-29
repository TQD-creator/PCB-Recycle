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
            # 1. CORE DATA
            data=r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Model_pipeline\data.yaml",
            epochs=300,
            patience=25,
            
            # 2. LAPTOP SURVIVAL SETTINGS
            imgsz=640,
            batch=16,            
            device=device,
            cache=False,        
            workers=2,          
            
            # 3. TRANSFER LEARNING MATH
            freeze=10,          
            optimizer="AdamW",
            lr0=0.001,
            lrf=0.01,
            cos_lr=True,
            
            # 4. ANTI-IMBALANCE & HYPER-AUGMENTATION
            copy_paste=0.3,     
            mosaic=1.0,         
            mixup=0.3,          
            degrees=15.0,       
            shear=2.0,          
            scale=0.5,          
            hsv_s=0.5,          
            hsv_v=0.5,          
            
            # 5. OUTPUT LOCATION
            project="Foxconn_PCB",
            name="YOLOv8s_Final_Production_Run"
        )
        
        print("\n[*] TRAINING SUCCESSFULLY COMPLETED!")
        print("[*] Your champion weights are saved in: Foxconn_PCB/YOLOv8s_Final_Production_Run/weights/best.pt")

    except Exception as e:
        print("\n[!] ================= CRITICAL CRASH DETECTED ================= [!]")
        print(f"[*] The AI engine encountered a fatal error: {str(e)}")
        print("[*] Writing detailed traceback report to 'crash_log.txt'...")
        
        # FIX APPLIED HERE: Added encoding="utf-8" so Windows can handle emojis
        with open("crash_log.txt", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
            
        print("[!] Please open crash_log.txt to see exactly what killed the process.")

if __name__ == "__main__":
    train_bulletproof_model()