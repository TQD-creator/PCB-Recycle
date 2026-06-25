import os
import time
import shutil
import yaml
import logging
from datetime import datetime
from pathlib import Path
from ultralytics import YOLO

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [FLYWHEEL BRAIN] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger("FLYWHEEL")

# --- PATH CONFIGURATION ---
BACKEND_DIR = Path(__file__).resolve().parent
STAGING_DIR = BACKEND_DIR / "dataset_staging"
IMAGES_DIR = STAGING_DIR / "images"
LABELS_DIR = STAGING_DIR / "labels"

ARCHIVE_DIR = BACKEND_DIR / "dataset_archive"
ARCHIVE_IMAGES = ARCHIVE_DIR / "images"
ARCHIVE_LABELS = ARCHIVE_DIR / "labels"

MODEL_DIR = Path(r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\SAVE_model")
CURRENT_WEIGHTS = MODEL_DIR / "production_master.pt"
BACKUP_WEIGHTS = MODEL_DIR / "production_backup.pt"

for folder in [ARCHIVE_IMAGES, ARCHIVE_LABELS, IMAGES_DIR, LABELS_DIR, MODEL_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# --- HYPERPARAMETERS ---
TRAIN_THRESHOLD = 1 #10  
POLL_INTERVAL_SECONDS = 30
MAP_DEPLOYMENT_THRESHOLD = 0.70  

YOLO_CLASSES = [
    'capacitor', 'resistor', 'ic', 'diode', 
    'led', 'inductor', 'connector', 'unknown'
]

def clear_yolo_cache():
    for cache_file in STAGING_DIR.rglob("*.cache"):
        try:
            cache_file.unlink()
            LOGGER.info(f"Cleared old YOLO cache: {cache_file.name}")
        except Exception:
            pass

def generate_yaml() -> Path:
    yaml_path = STAGING_DIR / "flywheel_data.yaml"
    
    # FIX: .as_posix() prevents Windows backslash escaping errors in YAML
    data = {
        "train": IMAGES_DIR.absolute().as_posix(),
        "val": IMAGES_DIR.absolute().as_posix(), 
        "nc": len(YOLO_CLASSES),
        "names": YOLO_CLASSES
    }
    
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
        
    return yaml_path

def archive_dataset(timestamp: str):
    LOGGER.info("Archiving staging dataset to cold storage...")
    for img_file in IMAGES_DIR.glob("*.*"):
        shutil.move(str(img_file), str(ARCHIVE_IMAGES / f"{timestamp}_{img_file.name}"))
    for lbl_file in LABELS_DIR.glob("*.txt"):
        shutil.move(str(lbl_file), str(ARCHIVE_LABELS / f"{timestamp}_{lbl_file.name}"))

def run_training_cycle(image_count: int):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dynamic_run_name = f"cycle_{timestamp}"
    
    LOGGER.info(f"Threshold reached ({image_count} images). Executing {dynamic_run_name}...")
    
    if not CURRENT_WEIGHTS.exists():
        LOGGER.warning(f"Production master missing at {CURRENT_WEIGHTS}. Sourcing default yolov8s.pt")
        base_model_source = "yolov8s.pt"
    else:
        base_model_source = str(CURRENT_WEIGHTS)

    clear_yolo_cache()
    yaml_path = generate_yaml()
    
    try:
        model = YOLO(base_model_source)
        LOGGER.info(f"Loaded base network source: {base_model_source}")
        
        runs_output_dir = BACKEND_DIR / "runs" / "flywheel"
        
        results = model.train(
            data=yaml_path.as_posix(),
            epochs=15,              
            imgsz=640,               # USER OVERRIDE: Locked to 640x640 
            batch=8,
            accumulate=4,
            lr0=0.0008,              
            project=runs_output_dir.as_posix(),
            name=dynamic_run_name,
            exist_ok=False,
            workers=0                # FIX: Must be 0 on Windows to prevent silent hanging
        )
        
        generated_best_weights = runs_output_dir / dynamic_run_name / "weights" / "best.pt"
        
        if generated_best_weights.exists():
            current_map = 0.0
            if hasattr(results, 'results_dict') and results.results_dict:
                current_map = results.results_dict.get('metrics/mAP50-95(B)', 0.0)
            
            LOGGER.info(f"Cycle performance validated. Evaluation mAP50-95: {current_map:.4f}")
            
            if current_map >= MAP_DEPLOYMENT_THRESHOLD or base_model_source == "yolov8s.pt":
                LOGGER.info("Performance passed quality gating constraints. Advancing master model...")
                
                if CURRENT_WEIGHTS.exists():
                    shutil.copy(str(CURRENT_WEIGHTS), str(BACKUP_WEIGHTS))
                
                temp_swap_path = MODEL_DIR / "production_master.tmp"
                shutil.copy(str(generated_best_weights), str(temp_swap_path))
                os.replace(str(temp_swap_path), str(CURRENT_WEIGHTS))
                
                LOGGER.info(f"[+] SUCCESS: Model weights advanced atomically to {CURRENT_WEIGHTS.name}")
            else:
                LOGGER.warning(f"[-] GATING REJECTED: Performance ({current_map:.4f}) below threshold. Weights preserved.")
        else:
            LOGGER.error("[-] CRITICAL: Training completed but no weights file was found.")
            
        archive_dataset(timestamp)
        
    except Exception as e:
        LOGGER.error(f"Execution crash detected. Isolating staging folder data. Error: {e}")
        archive_dataset(timestamp)

def start_watchdog():
    LOGGER.info(f"Flywheel Watchdog active. Monitoring directory path target: {IMAGES_DIR}")
    LOGGER.info(f"Trigger condition configuration: >= {TRAIN_THRESHOLD} images.")
    
    while True:
        try:
            if IMAGES_DIR.exists():
                image_count = len(list(IMAGES_DIR.glob("*.*")))
                if image_count >= TRAIN_THRESHOLD:
                    run_training_cycle(image_count)
        except Exception as e:
            LOGGER.error(f"Watchdog monitoring thread hit an exception: {e}")
            
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        start_watchdog()
    except KeyboardInterrupt:
        LOGGER.info("Shutdown sequence activated by user. Exiting operational loop clean.")