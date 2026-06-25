import os
import shutil
import torch
import numpy as np
from pathlib import Path
from torchvision import models, transforms
from torch.utils.data import Dataset, DataLoader
from sklearn.cluster import KMeans
from PIL import Image
from tqdm import tqdm

print("\n[*] IGNITING DEEP FEATURE CLUSTERING ENGINE...")

# --- CONFIGURATION ---
INPUT_DIR = Path(r"C:\Users\Lenovo\Documents\Foxconn\content\MobileNet_Pure_Dataset\capacitor")
OUTPUT_DIR = Path(r"C:\Users\Lenovo\Documents\Foxconn\content\Clustered_Capacitors")
NUM_CLUSTERS = 20  # The AI will organize 14k images into 20 folders
BATCH_SIZE = 128

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[*] Hardware selected: {device}")

# 1. Load Pre-trained ResNet18 (Feature Extractor)
# We remove the final classification layer to just get the raw mathematical features
model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
model = torch.nn.Sequential(*(list(model.children())[:-1]))
model = model.to(device)
model.eval()

# Standard ImageNet Transforms
transform = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

class UnsortedDataset(Dataset):
    def __init__(self, image_paths):
        self.image_paths = image_paths
    def __len__(self):
        return len(self.image_paths)
    def __getitem__(self, idx):
        path = self.image_paths[idx]
        try:
            img = Image.open(path).convert('RGB')
            return transform(img), str(path)
        except:
            # Handle corrupted YOLO crops
            return torch.zeros((3, 128, 128)), str(path)

# Gather files
all_files = [f for f in INPUT_DIR.rglob('*') if f.suffix.lower() in ['.png', '.jpg', '.jpeg']]
print(f"[*] Found {len(all_files)} total images to sort.")

dataloader = DataLoader(UnsortedDataset(all_files), batch_size=BATCH_SIZE, num_workers=4)

features_list = []
paths_list = []

# 2. Extract Mathematical Barcodes (Embeddings)
print("\n[*] Extracting Deep Features (This will take a few minutes)...")
with torch.no_grad():
    for imgs, paths in tqdm(dataloader):
        imgs = imgs.to(device)
        features = model(imgs)
        features = features.view(features.size(0), -1).cpu().numpy()
        
        features_list.append(features)
        paths_list.extend(paths)

features_matrix = np.vstack(features_list)

# 3. K-Means Clustering
print(f"\n[*] Running K-Means to find {NUM_CLUSTERS} visual patterns...")
kmeans = KMeans(n_clusters=NUM_CLUSTERS, random_state=42, n_init=10)
labels = kmeans.fit_predict(features_matrix)

# 4. Route files to their new Cluster Folders
print("\n[*] Moving files to cluster folders...")
for i in range(NUM_CLUSTERS):
    (OUTPUT_DIR / f"Cluster_{i:02d}").mkdir(parents=True, exist_ok=True)

for path_str, label in tqdm(zip(paths_list, labels), total=len(paths_list)):
    src_path = Path(path_str)
    dest_path = OUTPUT_DIR / f"Cluster_{label:02d}" / src_path.name
    try:
        shutil.copy(src_path, dest_path)
    except:
        pass

print("\n[+] CLUSTERING COMPLETE.")
print(f"[*] Your 14,000 images are now organized into {NUM_CLUSTERS} folders at: {OUTPUT_DIR}")