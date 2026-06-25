from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
UPLOADS_DIR = RUNTIME_DIR / "uploads"
ARTIFACTS_DIR = RUNTIME_DIR / "artifacts"
TRIAGE_CROPS_DIR = RUNTIME_DIR / "triage_crops"
ASSETS_DIR = RUNTIME_DIR / "assets"

WEIGHTS_YOLO_PATH = Path(os.getenv("WEIGHTS_YOLO_PATH", str(ASSETS_DIR / "weights" / "yolov8_factory_best.pt")))
WEIGHTS_MOBILENET_PATH = Path(
    os.getenv("WEIGHTS_MOBILENET_PATH", str(ASSETS_DIR / "weights" / "mobilenet_best.pt"))
)
FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", str(ASSETS_DIR / "database" / "golden_anchors.index")))
FAISS_LABELS_PATH = Path(os.getenv("FAISS_LABELS_PATH", str(ASSETS_DIR / "database" / "anchor_labels.npy")))

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
RESULT_BACKEND_URL = os.getenv("RESULT_BACKEND_URL", "redis://127.0.0.1:6379/1")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def ensure_runtime_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    TRIAGE_CROPS_DIR.mkdir(parents=True, exist_ok=True)
