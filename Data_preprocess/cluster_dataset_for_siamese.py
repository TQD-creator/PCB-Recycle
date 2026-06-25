import os
import shutil
import numpy as np
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
from sklearn.cluster import KMeans
from tqdm import tqdm

# 1. Set up Device (Use GPU if available)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")
if device.type == 'cpu':
    print("WARNING: Running on CPU. If you have an NVIDIA GPU, make sure PyTorch CUDA is installed.")

# 2. Load Pre-trained ResNet50 in PyTorch
weights = models.ResNet50_Weights.DEFAULT
model = models.resnet50(weights=weights)
# Remove the final classification layer to get raw features
model = torch.nn.Sequential(*(list(model.children())[:-1]))
model = model.to(device)
model.eval()

# 3. Image Preprocessing Pipeline
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def extract_features_batch(img_paths, batch_size=64):
    """Extracts features for a batch of images quickly using GPU."""
    features_list = []
    valid_paths = []
    
    # Process in batches to maximize GPU efficiency
    for i in range(0, len(img_paths), batch_size):
        batch_paths = img_paths[i:i+batch_size]
        batch_tensors = []
        
        for p in batch_paths:
            try:
                img = Image.open(p).convert('RGB')
                batch_tensors.append(transform(img))
                valid_paths.append(p)
            except Exception as e:
                print(f"Skipping corrupt image {p}: {e}")
                
        if not batch_tensors:
            continue
            
        # Stack into a single batch tensor and move to GPU
        batch_tensor = torch.stack(batch_tensors).to(device)
        
        with torch.no_grad():
            # Shape: [batch_size, 2048, 1, 1] -> flatten to [batch_size, 2048]
            feats = model(batch_tensor).squeeze(-1).squeeze(-1)
            features_list.append(feats.cpu().numpy())
            
    if len(features_list) == 0:
        return np.array([]), []
        
    return np.vstack(features_list), valid_paths

def process_local_dataset(base_dir, class_folder, num_subgroups=3):
    target_dir = os.path.join(base_dir, class_folder)
    if not os.path.exists(target_dir):
        return

    valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tif')
    image_paths = [os.path.join(target_dir, f) for f in os.listdir(target_dir) 
                   if f.lower().endswith(valid_extensions)]

    if len(image_paths) < num_subgroups:
        print(f"Skipping {class_folder}: Not enough images.")
        return

    print(f"\n--- Processing Class: {class_folder} ---")
    
    # Extract features using PyTorch GPU batching
    features, valid_image_paths = extract_features_batch(image_paths, batch_size=64)
    
    if len(features) == 0:
        return

    print(f"Clustering {len(valid_image_paths)} images into {num_subgroups} groups...")
    kmeans = KMeans(n_clusters=num_subgroups, random_state=42, n_init=10)
    labels = kmeans.fit_predict(features)

    # Move files into subfolders
    for img_path, cluster_id in zip(valid_image_paths, labels):
        subgroup_dir = os.path.join(target_dir, f"group_{cluster_id}")
        os.makedirs(subgroup_dir, exist_ok=True)
        shutil.move(img_path, os.path.join(subgroup_dir, os.path.basename(img_path)))

    print(f"Done with class '{class_folder}'.")

if __name__ == "__main__":
    # Update to your local folder path
    LOCAL_DATASET_PATH = r"C:\Users\Lenovo\Documents\Foxconn\content\MobileNet_Pure_Dataset" 

    configs = {
        "0": 4,  # capacitor
        "1": 3,  # resistor
        "2": 4,  # ic
        "3": 2,  # diode
        "4": 3,  # led
        "5": 2,  # inductor
    }

    for class_folder, num_groups in configs.items():
        process_local_dataset(LOCAL_DATASET_PATH, class_folder, num_subgroups=num_groups)
        
    print("\nAll done! You can inspect your folders now.")