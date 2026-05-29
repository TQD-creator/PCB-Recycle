import os
import cv2
import json
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction

def execute_dynamic_sahi_diagnostic():
    print("\n[!] ================= DYNAMIC SAHI INFERENCE ENGINE ================= [!]")
    
    # --- CONFIGURATION ZONE ---
    MODELS_TO_TEST = {
        "BEST_WEIGHTS": r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\runs\detect\Foxconn_PCB\YOLOv8s_Final_Production_Run-4\weights\best.pt",
        "LAST_WEIGHTS": r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\runs\detect\Foxconn_PCB\YOLOv8s_Final_Production_Run-4\weights\last.pt"
    }
    
    TEST_IMAGE_PATH = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\Test_Eva\691063159_4359215137668395_228965728409097010_n.jpg"
    OUTPUT_FOLDER = "Foxconn_SAHI_Comparison"
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # --- 1. DYNAMIC DIMENSION RADAR ---
    print(f"[*] Scanning physical dimensions of '{TEST_IMAGE_PATH}'...")
    image = cv2.imread(TEST_IMAGE_PATH)
    
    if image is None:
        print(f"[-] FATAL ERROR: Cannot read image at '{TEST_IMAGE_PATH}'. Check the path.")
        return
        
    img_h, img_w = image.shape[:2]
    print(f"[*] Raw Image Dimensions: {img_w}W x {img_h}H")

    # The Math: Clamp slice dimensions to a maximum of 640. 
    optimal_slice_h = min(img_h, 640)
    optimal_slice_w = min(img_w, 640)

    # The Math: Overlap is physically impossible if the slice size equals the image size.
    optimal_overlap_h = 0.25 if img_h > 640 else 0.0
    optimal_overlap_w = 0.25 if img_w > 640 else 0.0

    print(f"[*] Dynamic Slicer configured to: {optimal_slice_w}x{optimal_slice_h} with Overlap: {optimal_overlap_w}x{optimal_overlap_h}")

    base_name = os.path.splitext(os.path.basename(TEST_IMAGE_PATH))[0]

    # --- 2. EXECUTION LOOP ---
    for model_name, weights_path in MODELS_TO_TEST.items():
        print(f"\n[*] --- INITIATING RUN: {model_name} ---")
        
        try:
            detection_model = AutoDetectionModel.from_pretrained(
                model_type='yolov8',
                model_path=weights_path,
                confidence_threshold=0.25, 
                device="cpu" 
            )
        except Exception as e:
            print(f"[-] FATAL ERROR loading {model_name}: {e}")
            continue

        print("[*] Executing dynamic slicing and prediction...")
        
        try:
            result = get_sliced_prediction(
                TEST_IMAGE_PATH,
                detection_model,
                slice_height=optimal_slice_h,
                slice_width=optimal_slice_w,
                overlap_height_ratio=optimal_overlap_h,
                overlap_width_ratio=optimal_overlap_w,
                postprocess_match_metric="IOS",
                postprocess_match_threshold=0.5
            )
        except Exception as e:
            print(f"[-] FATAL ERROR during SAHI Inference: {e}")
            continue

        output_filename = f"{base_name}_SAHI_{model_name}"
        
        # --- JSON EXPORT (Fixed for Python standard library) ---
        json_path = os.path.join(OUTPUT_FOLDER, f"{output_filename}.json")
        coco_predictions = result.to_coco_predictions(image_id=1)
        with open(json_path, "w") as f:
            json.dump(coco_predictions, f, indent=4)
        print(f"[+] Exported Raw Data: {json_path}")
        
        # --- VISUAL EXPORT (Clean Box Implementation) ---
        result.export_visuals(
            export_dir=OUTPUT_FOLDER, 
            file_name=output_filename,
            rect_th=1,          # Forces the bounding box to be 1 pixel thin
            hide_labels=True,   # Kills the text labels
            hide_conf=True      # Kills the percentage text
        )
        print(f"[+] Exported Clean Image: {OUTPUT_FOLDER}/{output_filename}.png")

    print(f"\n[+] MISSION ACCOMPLISHED. The pipeline survived the dynamic size check.")

if __name__ == "__main__":
    execute_dynamic_sahi_diagnostic()