from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Sequence, Tuple
from uuid import uuid4

import cv2
import torch
import torch.nn.functional as F
from PIL import Image
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction
from torchvision import models, transforms

MODEL_DIR = Path(r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\SAVE_model")
YOLO_WEIGHTS = MODEL_DIR / "best.pt"
MOBILENET_WEIGHTS = MODEL_DIR / "last.pt"

_MODEL_LOCK = Lock()
_MODEL_SAHI: AutoDetectionModel | None = None
_MODEL_MOBILENET: torch.nn.Module | None = None
_MODEL_DEVICE: torch.device | None = None
_MOBILENET_TRANSFORM: transforms.Compose | None = None

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

SAHI_LOGGER = logging.getLogger("SAHI_ENGINE")
MOBILENET_LOGGER = logging.getLogger("MOBILENET")
NORMALIZER_LOGGER = logging.getLogger("NORMALIZER")


@dataclass
class GridCrop:
    """Represents a single grid crop and its center-based coordinates."""

    crop: Image.Image
    x_center: float
    y_center: float
    width: float
    height: float


def load_models() -> None:
    """Load SAHI YOLO and MobileNet models into memory once per server lifecycle."""
    global _MODEL_SAHI, _MODEL_MOBILENET, _MODEL_DEVICE, _MOBILENET_TRANSFORM

    if _MODEL_SAHI is not None and _MODEL_MOBILENET is not None:
        return

    with _MODEL_LOCK:
        if _MODEL_SAHI is not None and _MODEL_MOBILENET is not None:
            return

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        device_name = "cuda:0" if device.type == "cuda" else "cpu"

        sahi_model = AutoDetectionModel.from_pretrained(
            model_type="yolov8",
            model_path=str(YOLO_WEIGHTS),
            confidence_threshold=0.4,
            device=device_name,
        )

        mobilenet_model = models.mobilenet_v3_small(weights=None)
        mobilenet_model.classifier[3] = torch.nn.Linear(
            mobilenet_model.classifier[3].in_features,
            2,
        )
        #state_dict = torch.load(str(MOBILENET_WEIGHTS), map_location=device, weights_only=False)
        #mobilenet_model.load_state_dict(state_dict)
        mobilenet_model.to(device)
        mobilenet_model.eval()

        transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )

        _MODEL_DEVICE = device
        _MODEL_SAHI = sahi_model
        _MODEL_MOBILENET = mobilenet_model
        _MOBILENET_TRANSFORM = transform


def ensure_image_readable(image_path: str) -> None:
    """Validate that OpenCV can decode the uploaded image bytes."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Image unreadable")
    del image


def run_sahi_yolo(image_path: str) -> List[Dict[str, Any]]:
    """Run SAHI slicing + YOLO inference and return center-based detections."""
    load_models()

    if _MODEL_SAHI is None:
        raise RuntimeError("SAHI model not loaded")

    SAHI_LOGGER.info("Starting SAHI slicing for %s", image_path)
    sahi_result = get_sliced_prediction(
        image_path,
        detection_model=_MODEL_SAHI,
        slice_height=512,
        slice_width=512,
        overlap_height_ratio=0.2,
        overlap_width_ratio=0.2,
    )

    detections: List[Dict[str, Any]] = []
    try:
        for prediction in sahi_result.object_prediction_list:
            x_min, y_min, box_width, box_height = prediction.bbox.to_xywh()
            x_center = float(x_min + (box_width / 2))
            y_center = float(y_min + (box_height / 2))
            detections.append(
                {
                    "label": prediction.category.name,
                    "x_center": x_center,
                    "y_center": y_center,
                    "width": float(box_width),
                    "height": float(box_height),
                    "confidence": float(prediction.score.value),
                }
            )
    finally:
        SAHI_LOGGER.info(
            "Slicing complete. Generated %d merged detections.",
            len(detections),
        )
        del sahi_result
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return detections


def generate_image_grids(
    image_matrix: Any,
    grid_size: int = 224,
    stride: int = 112,
) -> Iterable[GridCrop]:
    """Yield grid crops across the image while preserving original coordinates."""
    height, width = image_matrix.shape[:2]

    for y in range(0, height, stride):
        for x in range(0, width, stride):
            x1 = max(x, 0)
            y1 = max(y, 0)
            x2 = min(x + grid_size, width)
            y2 = min(y + grid_size, height)

            if x2 <= x1 or y2 <= y1:
                continue

            crop = image_matrix[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb_crop, (grid_size, grid_size), interpolation=cv2.INTER_AREA)
            pil_crop = Image.fromarray(resized)

            width_px = float(x2 - x1)
            height_px = float(y2 - y1)
            x_center = float(x1 + width_px / 2)
            y_center = float(y1 + height_px / 2)

            yield GridCrop(
                crop=pil_crop,
                x_center=x_center,
                y_center=y_center,
                width=width_px,
                height=height_px,
            )


def run_grid_mobilenet(
    image_path: str,
    grid_size: int = 224,
    stride: int = 112,
) -> List[Dict[str, Any]]:
    """Run MobileNetV3 over sliding grid windows and return defect-only hits."""
    load_models()

    if _MODEL_MOBILENET is None or _MOBILENET_TRANSFORM is None or _MODEL_DEVICE is None:
        raise RuntimeError("MobileNet model not loaded")

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Image unreadable")

    crops: List[GridCrop] = list(generate_image_grids(image, grid_size=grid_size, stride=stride))
    MOBILENET_LOGGER.info("Generated %d grid crops.", len(crops))

    tensors: List[torch.Tensor] = []
    for crop in crops:
        tensors.append(_MOBILENET_TRANSFORM(crop.crop))

    if not tensors:
        return []

    batch = torch.stack(tensors).to(_MODEL_DEVICE)
    if batch.shape[0] >= 64:
        MOBILENET_LOGGER.warning("Batch tensor size is %s. Monitor VRAM usage.", list(batch.shape))

    defects: List[Dict[str, Any]] = []
    try:
        with torch.no_grad():
            logits = _MODEL_MOBILENET(batch)
            probabilities = F.softmax(logits, dim=1)
            defect_scores = probabilities[:, 1].detach().cpu().tolist()

        for crop, score in zip(crops, defect_scores):
            if score <= 0.65:
                continue
            defects.append(
                {
                    "label": "Grid Sector",
                    "x_center": crop.x_center,
                    "y_center": crop.y_center,
                    "width": crop.width,
                    "height": crop.height,
                    "confidence": float(score),
                    "defect_type": "Defective",
                }
            )
    finally:
        del batch
        del tensors
        del crops
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return defects


def normalize_ai_output(
    scan_id: str,
    yolo_results: Sequence[Dict[str, Any]] | None,
    mobilenet_results: Sequence[Dict[str, Any]] | None,
) -> List[Dict[str, Any]]:
    """Normalize YOLO and MobileNet outputs into the unified SQL schema."""
    normalized: List[Dict[str, Any]] = []

    for detection in yolo_results or []:
        normalized.append(
            {
                "result_id": str(uuid4()),
                "scan_id": scan_id,
                "source_model": "YOLO",
                "class_label": detection["label"],
                "bounding_box_x": float(detection["x_center"]),
                "bounding_box_y": float(detection["y_center"]),
                "box_width": float(detection["width"]),
                "box_height": float(detection["height"]),
                "confidence_score": float(detection["confidence"]),
                "defect_status": "Intact",
                "defect_type": None,
            }
        )

    for defect in mobilenet_results or []:
        normalized.append(
            {
                "result_id": str(uuid4()),
                "scan_id": scan_id,
                "source_model": "MOBILENET",
                "class_label": defect.get("label", "Grid Sector"),
                "bounding_box_x": float(defect["x_center"]),
                "bounding_box_y": float(defect["y_center"]),
                "box_width": float(defect["width"]),
                "box_height": float(defect["height"]),
                "confidence_score": float(defect["confidence"]),
                "defect_status": "Defective",
                "defect_type": defect.get("defect_type"),
            }
        )

    NORMALIZER_LOGGER.info("Normalized %d records for scan %s", len(normalized), scan_id)
    return normalized
