import os
import json
from collections import Counter
from sentence_transformers import SentenceTransformer, util
import torch

# ==========================================
# 1. CONFIGURATION
# ==========================================
JSON_FILE_PATH = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\_annotations.coco.json"
OUTPUT_LABELS_DIR = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\train\NLP_Cleaned_Labels"

os.makedirs(OUTPUT_LABELS_DIR, exist_ok=True)

MASTER_CLASSES = {
    "0": "capacitor",
    "1": "resistor",
    "2": "ic", 
    "3": "diode",
    "4": "led",
    "5": "inductor",
    "6": "connector",
    "99": "unknown"
}

# ==========================================
# 2. THE AUDIT SCRIPT
# ==========================================
def run_strict_nlp_pipeline():
    print("[*] Loading NLP Engine ('all-MiniLM-L6-v2')...")
    nlp_model = SentenceTransformer('all-MiniLM-L6-v2')
    master_embeddings = nlp_model.encode(list(MASTER_CLASSES.values()), convert_to_tensor=True)

    print("[*] Loading COCO JSON Data...")
    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Count raw instances before any mapping
    raw_category_names = {cat['id']: cat['name'] for cat in data['categories']}
    raw_instance_counts = Counter(ann['category_id'] for ann in data['annotations'])

    print("\n" + "="*50)
    print("[!] BEFORE NLP: RAW DATASET CASUALTY REPORT")
    print("="*50)
    for cat_id, count in raw_instance_counts.items():
        print(f"RAW: '{raw_category_names[cat_id]}' -> {count} instances")

    # Build the mapping and track translations
    nlp_map = {}
    print("\n" + "="*50)
    print("[!] NLP TRANSLATION LOG (Threshold: 45%)")
    print("="*50)
    
    for category in data['categories']:
        class_id = category['id']
        raw_name = category['name'].lower()
        
        query_embedding = nlp_model.encode(raw_name, convert_to_tensor=True)
        cosine_scores = util.cos_sim(query_embedding, master_embeddings)[0]
        
        best_match_index = torch.argmax(cosine_scores).item()
        best_match_score = cosine_scores[best_match_index].item()
        master_id = list(MASTER_CLASSES.keys())[best_match_index]
        master_name = MASTER_CLASSES[master_id]
        
        # Stricter threshold. 40% is too low for industrial components.
        if best_match_score > 0.45 and master_id != 99:
            nlp_map[class_id] = master_id
            print(f"[OK] Mapped: '{raw_name}' --> '{master_name}' (Confidence: {best_match_score*100:.1f}%)")
        else:
            print(f"[REJECTED] Trashed: '{raw_name}' --> Guessed '{master_name}' but score was only {best_match_score*100:.1f}%")

    # Apply mapping and track the AFTER state
    final_instance_counts = Counter()
    annotations_by_image = {}
    trashed_annotations = 0

    for ann in data['annotations']:
        raw_cat_id = ann['category_id']
        img_id = ann['image_id']
        
        if raw_cat_id in nlp_map:
            master_id = nlp_map[raw_cat_id]
            final_instance_counts[master_id] += 1
            
            if img_id not in annotations_by_image:
                annotations_by_image[img_id] = []
            
            # Inject the new ID into the annotation for the next step
            ann['new_master_id'] = master_id
            annotations_by_image[img_id].append(ann)
        else:
            trashed_annotations += 1

    print("\n" + "="*50)
    print("[!] AFTER NLP: THE FINAL DATA BALANCE")
    print("="*50)
    for m_id, count in sorted(final_instance_counts.items()):
        print(f"MASTER CLASS [{m_id}] {MASTER_CLASSES[m_id].upper()}: {count} total instances")
    
    print(f"\n[!] TOTAL LABELS TRASHED BY NLP: {trashed_annotations}")
    
    if final_instance_counts.get(2, 0) < 200:
        print("\n[!] CRITICAL WARNING: You have severe minority class starvation for ICs.")
        print("[!] Proceeding to train on this dataset will result in model failure for IC detection.")

    # Convert to YOLO (Only saving what survived)
    print("\n[*] Exporting Surviving Data to YOLO Format...")
    images_dict = {img['id']: img for img in data['images']}
    success_count = 0
    
    for img_id, annotations in annotations_by_image.items():
        img_info = images_dict[img_id]
        img_width = img_info['width']
        img_height = img_info['height']
        label_filename = os.path.splitext(img_info['file_name'])[0] + '.txt'
        label_path = os.path.join(OUTPUT_LABELS_DIR, label_filename)
        
        valid_yolo_lines = []
        for ann in annotations:
            new_class_id = ann['new_master_id']
            x, y, w, h = [float(v) for v in ann['bbox']]
            
            # YOLO Math
            center_x = max(0, min(1, (x + w / 2) / img_width))
            center_y = max(0, min(1, (y + h / 2) / img_height))
            norm_w = max(0, min(1, w / img_width))
            norm_h = max(0, min(1, h / img_height))
            
            valid_yolo_lines.append(f"{new_class_id} {center_x} {center_y} {norm_w} {norm_h}\n")
            
        with open(label_path, 'w') as label_file:
            label_file.writelines(valid_yolo_lines)
        success_count += 1
        
    print(f"[*] Process Complete. Wrote {success_count} valid .txt files.")

if __name__ == "__main__":
    run_strict_nlp_pipeline()