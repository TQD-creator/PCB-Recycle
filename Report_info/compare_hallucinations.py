import os
import glob
from ultralytics import YOLO

def execute_visual_hallucination_test():
    print("\n[!] ================= VISUAL HALLUCINATION STRESS TEST ================= [!]")
    
    # --- CONFIGURATION ZONE (WINDOWS PATHS) ---
    MODELS = {
        # CHANGE THESE TO YOUR LOCAL WINDOWS PATHS
        "Old_Model (Phase 1 Winner)": r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\SAVE_model\YOLOv8s_Balanced_Run\weights\old_cpu_best.pt", 
        "New_Model (Background Mined)": r"C:\Users\Lenovo\Documents\Foxconn\Colab_save\GPU2\best.pt" 
    }
    
    BARE_BOARD_IMAGE = r"C:\Users\Lenovo\Documents\Foxconn\Test_Board\6a840d7aae562f0876471.jpg" 
    TRAP_CROPS_FOLDER = r"C:\Users\Lenovo\Documents\Foxconn\Missing_components" 
    
    CONFIDENCE_THRESHOLD = 0.25 
    
    results_scorecard = {}

    for model_name, weights_path in MODELS.items():
        print(f"\n[*] ================= INTERROGATING: {model_name} ================= [*]")
        if not os.path.exists(weights_path):
            print(f"[-] ERROR: Model {weights_path} not found. Check your path!")
            continue
            
        try:
            model = YOLO(weights_path)
            model_score = {"bare_board_ghosts": 0, "trap_crop_fails": 0}
            
            # Create a dedicated Autopsy folder in your current directory
            AUTOPSY_DIR = os.path.join(os.getcwd(), "Hallucination_Autopsy", model_name.replace(' ', '_'))
            os.makedirs(AUTOPSY_DIR, exist_ok=True)
            
            # --- TEST 1: THE GHOST TOWN (BARE BOARD) ---
            if os.path.exists(BARE_BOARD_IMAGE):
                print(f"[*] Executing Bare Board Stress Test...")
                results = model.predict(source=BARE_BOARD_IMAGE, conf=CONFIDENCE_THRESHOLD, verbose=False)
                
                ghost_count = len(results[0].boxes)
                model_score["bare_board_ghosts"] = ghost_count
                print(f"    -> Hallucinated Components: {ghost_count} (Target is 0)")
                
                # Save the visual proof of the bare board
                results[0].save(filename=os.path.join(AUTOPSY_DIR, "Bare_Board_Fails.jpg"))
            else:
                print("[-] WARNING: Bare board image not found.")

            # --- TEST 2: THE TRAP CROPS (VISUAL EXTRACTION) ---
            trap_images = glob.glob(os.path.join(TRAP_CROPS_FOLDER, "*.*"))
            if trap_images:
                print(f"[*] Executing Targeted Trap Crop Test on {len(trap_images)} images...")
                failed_crops = 0
                
                for img_path in trap_images:
                    res = model.predict(source=img_path, conf=CONFIDENCE_THRESHOLD, verbose=False)
                    
                    # If it hallucinated a box...
                    if len(res[0].boxes) > 0:
                        failed_crops += 1
                        filename = os.path.basename(img_path)
                        save_path = os.path.join(AUTOPSY_DIR, f"FAIL_{filename}")
                        
                        # Physically draw the boxes/confidence and save it to the Autopsy folder
                        res[0].save(filename=save_path)
                        print(f"      [!] TRAP TRIGGERED on {filename} -> Saved to Autopsy folder.")
                        
                model_score["trap_crop_fails"] = failed_crops
                print(f"    -> Tricked by Trap Crops: {failed_crops}/{len(trap_images)} (Target is 0)")
            else:
                print("[-] WARNING: No trap crops found in folder.")
                
            results_scorecard[model_name] = model_score
            
        except Exception as e:
            print(f"[-] FATAL ERROR evaluating {model_name}: {e}")

    # --- THE HARSH TRUTH SCORECARD ---
    print("\n[!] ================= FINAL HALLUCINATION SCORECARD ================= [!]")
    print(f"(Tested at Confidence Floor: {CONFIDENCE_THRESHOLD})")
    print("-" * 65)
    print(f"{'MODEL NAME':<30} | {'BARE BOARD GHOSTS':<20} | {'TRAP FAILS'}")
    print("-" * 65)
    
    for name, scores in results_scorecard.items():
        ghosts = scores['bare_board_ghosts']
        traps = scores['trap_crop_fails']
        print(f"{name:<30} | {ghosts:<20} | {traps}")
    print("-" * 65)
    print(f"\n[+] VISUALS EXPORTED to {os.path.join(os.getcwd(), 'Hallucination_Autopsy')}")

if __name__ == "__main__":
    execute_visual_hallucination_test()