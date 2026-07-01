from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
UPLOADS_DIR = RUNTIME_DIR / "uploads"
ARTIFACTS_DIR = RUNTIME_DIR / "artifacts"
TRIAGE_CROPS_DIR = RUNTIME_DIR / "triage_crops"
ASSETS_DIR = RUNTIME_DIR / "assets"

# ── YOLO detector weight ──────────────────────────────────────────────────────
# Exactly ONE line below should be active at a time.
#
# Option A — FP32 PyTorch (default, always works)
#   model_type="yolov8"  |  model_path = file path (.pt)
#   No image-size constraint.
WEIGHTS_YOLO_PATH = Path(os.getenv("WEIGHTS_YOLO_PATH", str(ASSETS_DIR / "weights" / "YOLOv8s_HighRes_SAHI_best.pt")))

# Option B — INT8 ONNX (7.5× smaller, but requires onnxruntime; see requirements.txt)
#   model_type="yolov8"  |  model_path = file path (.onnx)
#   NOTE: confidence scores may collapse after aggressive quantization — verify dets > 0
#         before deploying (run debug_onnx_conf.py to check).
# WEIGHTS_YOLO_PATH = Path(os.getenv("WEIGHTS_YOLO_PATH", str(ASSETS_DIR / "weights" / "high_res_p2_int8.onnx")))

# Option C — OpenVINO FP16 (load from DIRECTORY, not a file; requires openvino>=2024.0.0)
#   model_type="yolov8"  |  model_path = directory path
#   IMPORTANT: inference call MUST set imgsz=640 (static graph — any other size raises an error).
#   In cv_pipeline.py, change AutoDetectionModel.from_pretrained(...) to pass:
#     model_path=str(WEIGHTS_YOLO_PATH),   ← points to the folder, Ultralytics resolves .xml inside
#   And in get_sliced_prediction(...) set perform_standard_pred=False and
#   call model.predict(..., imgsz=640) if running outside SAHI.
# WEIGHTS_YOLO_PATH = Path(os.getenv("WEIGHTS_YOLO_PATH", str(ASSETS_DIR / "weights" / "high_res_openvino_fp16")))

# Option D — OpenVINO INT8 (load from DIRECTORY; same constraints as Option C)
#   model_type="yolov8"  |  model_path = directory path
# WEIGHTS_YOLO_PATH = Path(os.getenv("WEIGHTS_YOLO_PATH", str(ASSETS_DIR / "weights" / "high_res_openvino_int8")))
# ─────────────────────────────────────────────────────────────────────────────
WEIGHTS_MOBILENET_PATH = Path(
    os.getenv("WEIGHTS_MOBILENET_PATH", str(ASSETS_DIR / "weights" / "mobilenet_best.pt"))
)
FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", str(ASSETS_DIR / "database" / "golden_anchors.index")))
FAISS_LABELS_PATH = Path(os.getenv("FAISS_LABELS_PATH", str(ASSETS_DIR / "database" / "anchor_labels.npy")))

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
RESULT_BACKEND_URL = os.getenv("RESULT_BACKEND_URL", "redis://127.0.0.1:6379/1")
API_BASE_URL = os.getenv("API_BASE_URL", "http://192.168.0.101:8000")


def ensure_runtime_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    TRIAGE_CROPS_DIR.mkdir(parents=True, exist_ok=True)
