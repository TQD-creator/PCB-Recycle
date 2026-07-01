from __future__ import annotations
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import faiss
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction

from config import (
    API_BASE_URL, ARTIFACTS_DIR, FAISS_INDEX_PATH, FAISS_LABELS_PATH,
    TRIAGE_CROPS_DIR, WEIGHTS_MOBILENET_PATH, WEIGHTS_YOLO_PATH,
)
from models import ComponentRecord, InventoryReport, TriageItem

_MODEL_LOCK = threading.Lock()
_FAISS_LOCK = threading.Lock()

class PCBFeatureExtractor(nn.Module):
    def __init__(self, embedding_size: int = 256) -> None:
        super().__init__()
        mobilenet = models.mobilenet_v3_small(weights=None)
        self.backbone = mobilenet.features
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.projection_head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(576, 512),
            nn.ReLU(),
            nn.BatchNorm1d(512),
            nn.Linear(512, embedding_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.backbone(x)
        x = self.pool(x)
        return nn.functional.normalize(self.projection_head(x), p=2, dim=1)

@dataclass
class RuntimeModels:
    device: torch.device
    detector: AutoDetectionModel
    embedder: PCBFeatureExtractor
    faiss_index: faiss.Index
    anchor_labels: np.ndarray
    preprocess: transforms.Compose

class PipelineRegistry:
    _instance: RuntimeModels | None = None

    @classmethod
    def get(cls) -> RuntimeModels:
        if cls._instance is not None:
            return cls._instance

        with _MODEL_LOCK:
            if cls._instance is not None:
                return cls._instance

            print("[*] Loading AI Models into 16GB System RAM (CPU Mode)...")

            # CRITICAL RULE: FORCE CPU. DO NOT USE CUDA ON 700MB VRAM.
            device = torch.device("cpu")
            device_name = "cpu"

            detector = AutoDetectionModel.from_pretrained(
                model_type="yolov8",
                model_path=str(WEIGHTS_YOLO_PATH),
                confidence_threshold=0.10,
                device=device_name,
            )

            embedder = PCBFeatureExtractor(embedding_size=256)
            checkpoint = torch.load(WEIGHTS_MOBILENET_PATH, map_location=device)
            state_dict = checkpoint.get("model_state_dict", checkpoint)
            embedder.load_state_dict(state_dict)
            embedder.to(device)
            embedder.eval()

            faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))
            anchor_labels = np.load(str(FAISS_LABELS_PATH), allow_pickle=True)

            preprocess = transforms.Compose([
                transforms.Resize((128, 128)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])

            cls._instance = RuntimeModels(
                device=device,
                detector=detector,
                embedder=embedder,
                faiss_index=faiss_index,
                anchor_labels=anchor_labels,
                preprocess=preprocess,
            )
            print("[+] AI Engine Armed & Ready.")
        return cls._instance

def _normalize_label(raw_label: object) -> str:
    return str(raw_label).replace("_golden", "")

def run_scan_pipeline(task_id: str, image_path: str, progress_cb) -> Tuple[InventoryReport, List[TriageItem], str]:
    runtime = PipelineRegistry.get()
    thresholds: Dict[str, float] = {
        "capacitor": 0.40, "resistor": 0.40, "ic": 0.40,
        "diode": 0.40, "led": 0.40, "inductor": 0.40, "connector": 0.40,
    }

    progress_cb("Stage 1: SAHI Slicing...", 15)
    slicing = get_sliced_prediction(
        image_path,
        detection_model=runtime.detector,
        slice_height=640,
        slice_width=640,
        overlap_height_ratio=0.2,
        overlap_width_ratio=0.2,
    )

    image = cv2.imread(image_path)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    report = InventoryReport(
        verified_counts={"capacitor": 0, "resistor": 0, "ic": 0, "diode": 0, "led": 0, "inductor": 0, "connector": 0},
        verified_components=[],
        anomaly_queue=[],
    )

    tensor_batch: List[torch.Tensor] = []
    metadata: List[Dict[str, object]] = []

    progress_cb("Stage 2: Tensor Extraction...", 35)
    for prediction in slicing.object_prediction_list:
        x1, y1, x2, y2 = map(int, prediction.bbox.to_xyxy())
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(rgb.shape[1], x2), min(rgb.shape[0], y2)
        crop = rgb[y1:y2, x1:x2]
        if crop.size == 0: continue

        tensor_batch.append(runtime.preprocess(Image.fromarray(crop)))
        metadata.append({"bbox": [x1, y1, x2, y2], "yolo_guess": prediction.category.name or "unknown", "crop": crop})

    if not tensor_batch:
        return report, [], f"{API_BASE_URL}/uploads/{Path(image_path).name}"

    progress_cb("Stage 3: MobileNet Fingerprinting...", 55)
    with torch.no_grad():
        batch_tensor = torch.stack(tensor_batch).to(runtime.device)
        embeddings = runtime.embedder(batch_tensor).cpu().numpy().astype(np.float32)

    progress_cb("Stage 4: FAISS Verification...", 70)
    distances, indices = runtime.faiss_index.search(embeddings, k=1)

    triage_items: List[TriageItem] = []
    
    progress_cb("Stage 5: Routing Data...", 85)
    for i, item in enumerate(metadata):
        distance = float(distances[i][0])
        nearest_idx = int(indices[i][0])
        matched_class = _normalize_label(runtime.anchor_labels[nearest_idx]) if 0 <= nearest_idx < len(runtime.anchor_labels) else "unknown"
        threshold = thresholds.get(matched_class, 0.40)
        bbox = item["bbox"]

        if distance <= threshold:
            record = ComponentRecord(bbox=bbox, yolo_prelim_guess=str(item["yolo_guess"]), matched_anchor_class=matched_class, faiss_distance=distance, status="VERIFIED")
            report.verified_components.append(record)
            report.verified_counts[matched_class] = report.verified_counts.get(matched_class, 0) + 1
        else:
            record = ComponentRecord(bbox=bbox, yolo_prelim_guess=str(item["yolo_guess"]), matched_anchor_class=matched_class, faiss_distance=distance, status="ANOMALY", reason=f"L2 {distance:.4f} > {threshold:.4f}")
            report.anomaly_queue.append(record)
            
            crop_file = TRIAGE_CROPS_DIR / f"{task_id}_{len(report.anomaly_queue) - 1}.jpg"
            cv2.imwrite(str(crop_file), cv2.cvtColor(item["crop"], cv2.COLOR_RGB2BGR))
            triage_items.append(TriageItem(anomaly_index=len(report.anomaly_queue)-1, crop_url=f"{API_BASE_URL}/triage-crops/{crop_file.name}", record=record))

    return report, triage_items, f"{API_BASE_URL}/uploads/{Path(image_path).name}"

def resolve_anomaly(task_id: str, anomaly_index: int, decision: str, approved_class: str | None) -> str:
    """Secured function to update the FAISS index in RAM and on Disk."""
    if decision == "REJECT":
        return "Anomaly marked as damaged and excluded from golden anchors."

    artifact_path = ARTIFACTS_DIR / f"{task_id}.json"
    if not artifact_path.exists():
        raise FileNotFoundError("Task artifact not found. Unable to resolve anomaly.")

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    embeddings = payload.get("anomaly_embeddings", [])
    labels = payload.get("anomaly_labels", [])

    if anomaly_index >= len(embeddings):
        raise IndexError("Anomaly index out of range for this task.")

    runtime = PipelineRegistry.get()
    selected_embedding = np.asarray([embeddings[anomaly_index]], dtype=np.float32)
    label = approved_class or labels[anomaly_index] or "unknown"

    # Lock the thread to prevent corruption during concurrent uploads
    with _FAISS_LOCK:
        # 1. Update the Active RAM
        runtime.faiss_index.add(selected_embedding)
        runtime.anchor_labels = np.concatenate([runtime.anchor_labels, np.asarray([f"{label}_golden"], dtype=object)])

        # 2. Persist to Disk for the next container reboot
        faiss.write_index(runtime.faiss_index, str(FAISS_INDEX_PATH))
        np.save(str(FAISS_LABELS_PATH), runtime.anchor_labels)

    return f"Anomaly {anomaly_index} approved and embedded into golden anchors as '{label}'."