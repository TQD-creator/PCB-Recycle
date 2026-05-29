from ultralytics import YOLO
import os

def run_modern_evaluation():
    print("[*] Locating Champion Weights (best.pt)...")
    
    # Check the exact name of the folder your training script generated
    # It will likely be YOLOv8s_Run1 or YOLOv8s_Balanced_Run
    weights_path = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\runs\detect\Foxconn_PCB\YOLOv8s_Balanced_Run\weights\best.pt" 
    
    if not os.path.exists(weights_path):
        print(f"[!] CRITICAL ERROR: Could not find weights at {weights_path}")
        print("[!] Please update the folder name in the script to match your training output.")
        return

    # Load the highly-trained Foxconn model
    model = YOLO(weights_path)

    print("\n[*] ===========================================")
    print("[*] PHASE 1: QUANTITATIVE VALIDATION (METRICS)")
    print("[*] ===========================================")
    # The model automatically remembers the data.yaml location from its training
    metrics = model.val(
        split='val',       # Audit against the 20% validation split
        conf=0.25,         # Baseline confidence threshold for metrics
        iou=0.6,           # Modern NMS (Non-Maximum Suppression) threshold to prevent overlapping boxes
        plots=True         # Forces the engine to generate diagnostic charts
    )
    
    # Directly print the metrics for the minority classes
    print(f"[*] Overall mAP50-95: {metrics.box.map:.4f}")
    
    print("\n[*] ===========================================")
    print("[*] PHASE 2: QUALITATIVE INFERENCE (VISUALS)")
    print("[*] ===========================================")
    
    # Target the validation folder to see how it performs on images it was not trained on
    test_source = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\YOLO_Dataset\images\val"
    
    print(f"[*] Running industrial inference engine on: {test_source}")
    predictions = model.predict(
        source=test_source,
        conf=0.5,          # Stricter 50% confidence requirement for "production" output
        iou=0.45,          # Stricter overlap removal for cleaner visual results
        save=True,         # Physically draw the bounding boxes on the images
        save_txt=True,     # Save the raw coordinate math (crucial for robotic assembly integration)
        save_conf=True,    # Append the confidence percentage to the text files
        project="Foxconn_PCB",
        name="Inference_Results"
    )

    print("\n[*] EVALUATION PIPELINE COMPLETE!")
    print("[*] -> Visual Box Results: Check 'Foxconn_PCB/Inference_Results'")
    print("[*] -> Statistical Charts: Check 'Foxconn_PCB/YOLOv8s_Run1'")

if __name__ == "__main__":
    run_modern_evaluation()