import os
import json
from sentence_transformers import SentenceTransformer, util
import torch

# ==========================================
# 1. DIRECTORY CONFIGURATION
# ==========================================
JSON_FILE_PATH = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\PCB recognition for recycling.coco\train\_annotations.coco.json"
OUTPUT_LABELS_DIR = r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\PCB recognition for recycling.coco\train\NLP_Cleaned_Labels"

os.makedirs(OUTPUT_LABELS_DIR, exist_ok=True)

# ==========================================
# 2. NLP SETUP
# ==========================================
print("[*] Loading NLP Model...")
nlp_model = SentenceTransformer('all-MiniLM-L6-v2')

MASTER_CLASSES = {
    0: "capacitor",
    1: "resistor",
    2: "integrated circuit microchip",
    3: "diode",
    4: "led light",
    5: "inductor coil ferrite",
    6: "connector terminal",
    99: "random printed text letters numbers" # The trash bin
}

master_texts = list(MASTER_CLASSES.values())
master_embeddings = nlp_model.encode(master_texts, convert_to_tensor=True)

def build_nlp_mapping(data):
    mapping = {}
    print("[*] Running Semantic NLP on categories to build intelligence map...")
    
    for category in data['categories']:
        class_id = category['id']
        class_name = category['name'].lower()
        
        query_embedding = nlp_model.encode(class_name, convert_to_tensor=True)
        cosine_scores = util.cos_sim(query_embedding, master_embeddings)[0]
        
        best_match_index = torch.argmax(cosine_scores).item()
        best_match_score = cosine_scores[best_match_index].item()
        
        master_id = list(MASTER_CLASSES.keys())[best_match_index]
        
        # 40% confidence threshold. Otherwise, it's trash (99)
        if best_match_score > 0.40 and master_id != 99:
            mapping[class_id] = master_id
            
    return mapping

def extract_and_convert_directly_from_json():
    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 1. Build the NLP Map
    nlp_map = build_nlp_mapping(data)
    print(f"[*] NLP Engine identified {len(nlp_map)} valid component subclasses.")
    
    # 2. Create Image Dictionary for Width/Height reference
    images_dict = {img['id']: img for img in data['images']}
    
    # 3. Group Annotations by Image
    annotations_by_image = {}
    for ann in data['annotations']:
        img_id = ann['image_id']
        if img_id not in annotations_by_image:
            annotations_by_image[img_id] = []
        annotations_by_image[img_id].append(ann)
        
    print("[*] Generating perfect YOLO text files directly from COCO JSON...")
    
    success_count = 0
    
    # 4. Write the brand new text files
    for img_id, annotations in annotations_by_image.items():
        img_info = images_dict[img_id]
        img_width = img_info['width']
        img_height = img_info['height']
        
        img_filename = img_info['file_name']
        label_filename = os.path.splitext(img_filename)[0] + '.txt'
        label_path = os.path.join(OUTPUT_LABELS_DIR, label_filename)
        
        # Store valid boxes for this image
        valid_yolo_lines = []
        
        for ann in annotations:
            category_id = ann['category_id']
            
            # If the NLP model approved this category, do the math!
            if category_id in nlp_map:
                new_class_id = nlp_map[category_id]
                bbox = ann['bbox']  # [x_min, y_min, width, height]
                
                # Using YOUR math logic here:
                x, y, w, h = [float(v) for v in bbox]
                center_x = (x + w / 2) / img_width
                center_y = (y + h / 2) / img_height
                norm_w = w / img_width
                norm_h = h / img_height
                
                # Clamp to [0, 1] for safety
                center_x = max(0, min(1, center_x))
                center_y = max(0, min(1, center_y))
                norm_w = max(0, min(1, norm_w))
                norm_h = max(0, min(1, norm_h))
                
                valid_yolo_lines.append(f"{new_class_id} {center_x} {center_y} {norm_w} {norm_h}\n")
        
        # Only create a text file if there are actual valid components on the board
        if len(valid_yolo_lines) > 0:
            with open(label_path, 'w') as label_file:
                label_file.writelines(valid_yolo_lines)
            success_count += 1
            
    print("="*50)
    print(f"[*] CRITICAL SUCCESS: Generated {success_count} perfect YOLO label files.")
    print("="*50)

if __name__ == "__main__":
    extract_and_convert_directly_from_json()