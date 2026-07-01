#!/usr/bin/env python3
"""
benchmark_compare.py
Compares three PCB inspection pipeline configurations across five metrics:
  1. mAP@50                       (YOLO val on ground-truth labels)
  2. End-to-End Inference Latency  (full pipeline, ms / image)
  3. False Discovery Rate (FDR)    (FP_verified / (FP_verified + TP_verified))
  4. Recall                        (TP / (TP + FN))  — component-level
  5. Peak Memory Footprint         (MB, process RSS)

Models compared
  A. YOLO           : full-board → YOLOv8s (7-class) → MobileNetV3+FAISS
  B. YOLO+SAHI      : full-board → SAHI-sliced (512px) → YOLOv8s-1cls → MobileNetV3+FAISS
  C. YOLO+SAHI+HIGHRES : full-board resize-1600 → SAHI → YOLOv8s-P2(4-head) → MobileNetV3+FAISS

Run:
  python benchmark_compare.py
  python benchmark_compare.py --n 20      # limit pipeline eval to first 20 images
  python benchmark_compare.py --skip-map  # skip mAP (fast mode)
"""
from __future__ import annotations

import argparse
import csv
import gc
import os
import shutil
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

import cv2
import faiss
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import psutil
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction
from ultralytics import YOLO

# ─────────────────────────────────────────────────────────────────────────────
# PATHS — edit if your directory layout differs
# ─────────────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent  # PCB-Detection/

WEIGHT_YOLO          = ROOT / "SAVE_model/saved_weight/YOLO_weight.pt"
WEIGHT_SAHI          = ROOT / "Mobile_app_deploy/backend/runtime/assets/weights/FINAL_BEST_YOLO_SAHI.pt"
WEIGHT_HIGHRES       = ROOT / "Mobile_app_deploy/backend/runtime/assets/weights/YOLOv8s_HighRes_SAHI_best.pt"
WEIGHT_MOBILENET     = ROOT / "Mobile_app_deploy/backend/runtime/assets/weights/mobilenet_best.pt"
FAISS_INDEX          = ROOT / "Mobile_app_deploy/backend/runtime/assets/database/golden_anchors.index"
FAISS_LABELS         = ROOT / "Mobile_app_deploy/backend/runtime/assets/database/anchor_labels.npy"

VAL_IMAGES_DIR       = Path(r"D:\Download_save\Foxconn_save\Classification\val\images")
VAL_LABELS_DIR       = Path(r"D:\Download_save\Foxconn_save\Classification\val\labels")
MULTICLASS_DATA_YAML = Path(r"D:\Download_save\Foxconn_save\Classification\data.yaml")

OUTPUT_DIR           = Path(__file__).resolve().parent / "benchmark_results"

# 8 class names matching data.yaml (indices 0-7)
YOLO_CLASSES = ["capacitor", "resistor", "ic", "diode", "led", "inductor", "connector", "unknown"]

# FAISS thresholds per (lowercase) class
FAISS_THRESHOLDS = {
    "capacitor": 0.40, "resistor": 0.40, "ic": 0.40,
    "diode": 0.40, "led": 0.40, "inductor": 0.40,
}

SAHI_SLICE      = 640
SAHI_OVERLAP    = 0.2
HIGHRES_WIDTH   = 1600
YOLO_CONF       = 0.10
IOU_MATCH_THRESH = 0.50   # IoU threshold to count a detection as TP

DEVICE = torch.device("cpu")

# ─────────────────────────────────────────────────────────────────────────────
# MOBILENET V3 — same architecture as cv_pipeline.py
# ─────────────────────────────────────────────────────────────────────────────
class PCBFeatureExtractor(nn.Module):
    def __init__(self, embedding_size: int = 256) -> None:
        super().__init__()
        mobilenet = models.mobilenet_v3_small(weights=None)
        self.backbone = mobilenet.features
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.projection_head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(576, 512), nn.ReLU(), nn.BatchNorm1d(512),
            nn.Linear(512, embedding_size),
        )
    def forward(self, x):
        x = self.backbone(x)
        x = self.pool(x)
        return nn.functional.normalize(self.projection_head(x), p=2, dim=1)


PREPROCESS = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def _normalize_label(raw: object) -> str:
    return str(raw).replace("_golden", "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# LOADER HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def load_mobilenet_faiss():
    print("[*] Loading MobileNetV3 + FAISS ...")
    embedder = PCBFeatureExtractor(256)
    ckpt = torch.load(WEIGHT_MOBILENET, map_location=DEVICE)
    embedder.load_state_dict(ckpt.get("model_state_dict", ckpt))
    embedder.to(DEVICE).eval()

    index = faiss.read_index(str(FAISS_INDEX))
    labels = np.load(str(FAISS_LABELS), allow_pickle=True)
    print(f"    FAISS index: {index.ntotal} anchors")
    return embedder, index, labels


def load_sahi_model(weight_path: Path, label: str = "") -> AutoDetectionModel:
    print(f"[*] Loading SAHI model {label} ...")
    return AutoDetectionModel.from_pretrained(
        model_type="yolov8",
        model_path=str(weight_path),
        confidence_threshold=YOLO_CONF,
        device="cpu",
    )


def make_singleclass_data_yaml(tmp_dir: Path) -> Path:
    """Write a temp data.yaml pointing to the same val images but with nc=1."""
    label_dir = tmp_dir / "labels_1cls"
    label_dir.mkdir(exist_ok=True)
    for src in VAL_LABELS_DIR.glob("*.txt"):
        lines = src.read_text().splitlines()
        # Override class id to 0 for all boxes
        converted = [("0 " + " ".join(l.split()[1:])) for l in lines if l.strip()]
        (label_dir / src.name).write_text("\n".join(converted))

    yaml_path = tmp_dir / "sahi_val.yaml"
    yaml_path.write_text(
        f"path: {str(VAL_IMAGES_DIR.parent.parent)}\n"
        f"val: {str(VAL_IMAGES_DIR)}\n"
        f"nc: 1\n"
        f"names:\n  0: Component\n"
    )
    # Symlink labels next to images so YOLO val can find them
    img_parent = VAL_IMAGES_DIR.parent.parent  # YOLO_Dataset/
    link_target = img_parent / "labels" / "val"
    # Temporarily point labels/val to our 1-class labels
    return yaml_path, label_dir


# ─────────────────────────────────────────────────────────────────────────────
# mAP@50 — uses YOLO's built-in .val()
# ─────────────────────────────────────────────────────────────────────────────
def eval_map_yolo(weight_path: Path, data_yaml: Path, img_size: int = 640) -> float:
    model = YOLO(str(weight_path))
    results = model.val(
        data=str(data_yaml),
        imgsz=img_size,
        conf=YOLO_CONF,
        iou=0.5,
        device="cpu",
        verbose=False,
        plots=False,
    )
    return float(results.box.map50)   # mAP@50


def compute_sahi_map50(
    all_pred_boxes: list,       # list[list[[x1,y1,x2,y2]]] per image
    all_confidences: list,      # list[list[float]] confidence per prediction
    all_gt_boxes: list,         # list[list[[x1,y1,x2,y2]]] per image (multi-class, all treated as 1 class)
    iou_thresh: float = 0.50,
) -> float:
    """
    VOC-style mAP@50 for a single class.
    Builds (confidence, tp_flag) pairs sorted by conf desc, computes PR curve, returns AP.
    """
    # Flatten all predictions with their image id
    all_det = []  # (img_id, conf, box)
    for img_id, (boxes, confs) in enumerate(zip(all_pred_boxes, all_confidences)):
        for box, conf in zip(boxes, confs):
            all_det.append((img_id, conf, box))

    total_gt = sum(len(g) for g in all_gt_boxes)
    if total_gt == 0 or len(all_det) == 0:
        return 0.0

    # Sort by confidence descending
    all_det.sort(key=lambda x: x[1], reverse=True)

    matched_gt = [set() for _ in all_gt_boxes]   # tracks matched GT per image
    tp_flags = []
    for img_id, conf, pred_box in all_det:
        gts = all_gt_boxes[img_id]
        best_iou, best_gi = 0.0, -1
        for gi, gt_box in enumerate(gts):
            if gi in matched_gt[img_id]:
                continue
            s = iou(pred_box, gt_box)
            if s > best_iou:
                best_iou, best_gi = s, gi
        if best_iou >= iou_thresh:
            matched_gt[img_id].add(best_gi)
            tp_flags.append(1)
        else:
            tp_flags.append(0)

    # Cumulative precision & recall
    tp_cum = np.cumsum(tp_flags)
    fp_cum = np.cumsum([1 - t for t in tp_flags])
    precisions = tp_cum / (tp_cum + fp_cum + 1e-9)
    recalls    = tp_cum / (total_gt + 1e-9)

    # Add sentinel points
    precisions = np.concatenate([[1.0], precisions, [0.0]])
    recalls    = np.concatenate([[0.0], recalls,    [recalls[-1]]])

    # Monotone decreasing precision envelope
    for i in range(len(precisions) - 2, -1, -1):
        precisions[i] = max(precisions[i], precisions[i + 1])

    # Integrate (area under PR curve)
    ap = float(np.sum((recalls[1:] - recalls[:-1]) * precisions[1:]))
    return ap


# ─────────────────────────────────────────────────────────────────────────────
# IoU MATCHING
# ─────────────────────────────────────────────────────────────────────────────
def iou(box_a, box_b):
    """box = [x1,y1,x2,y2] in pixels"""
    xa = max(box_a[0], box_b[0]); ya = max(box_a[1], box_b[1])
    xb = min(box_a[2], box_b[2]); yb = min(box_a[3], box_b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter == 0:
        return 0.0
    area_a = (box_a[2]-box_a[0]) * (box_a[3]-box_a[1])
    area_b = (box_b[2]-box_b[0]) * (box_b[3]-box_b[1])
    return inter / (area_a + area_b - inter)


def load_gt_boxes(label_path: Path, img_w: int, img_h: int):
    """Returns list of [x1,y1,x2,y2] in absolute pixel coords."""
    boxes = []
    if not label_path.exists():
        return boxes
    for line in label_path.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        _, cx, cy, bw, bh = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
        x1 = (cx - bw/2) * img_w; y1 = (cy - bh/2) * img_h
        x2 = (cx + bw/2) * img_w; y2 = (cy + bh/2) * img_h
        boxes.append([x1, y1, x2, y2])
    return boxes


def match_detections(pred_boxes, gt_boxes, iou_thresh=IOU_MATCH_THRESH):
    """Returns (matched_pred_indices, unmatched_pred_indices, unmatched_gt_indices)."""
    matched_pred, matched_gt = set(), set()
    for pi, pb in enumerate(pred_boxes):
        best_iou, best_gi = 0.0, -1
        for gi, gb in enumerate(gt_boxes):
            if gi in matched_gt:
                continue
            s = iou(pb, gb)
            if s > best_iou:
                best_iou, best_gi = s, gi
        if best_iou >= iou_thresh:
            matched_pred.add(pi)
            matched_gt.add(best_gi)
    unmatched_pred = [i for i in range(len(pred_boxes)) if i not in matched_pred]
    unmatched_gt   = [i for i in range(len(gt_boxes))  if i not in matched_gt]
    return list(matched_pred), unmatched_pred, unmatched_gt


# ─────────────────────────────────────────────────────────────────────────────
# FAISS VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────
def verify_crops(crops_rgb, embedder, faiss_index, faiss_labels):
    """
    Returns list of "VERIFIED" | "ANOMALY" decisions.
    crops_rgb: list of HxWx3 numpy arrays
    """
    if not crops_rgb:
        return []
    tensors = [PREPROCESS(Image.fromarray(c)) for c in crops_rgb]
    batch = torch.stack(tensors).to(DEVICE)
    with torch.no_grad():
        embs = embedder(batch).cpu().numpy().astype(np.float32)
    distances, indices = faiss_index.search(embs, k=1)
    decisions = []
    for dist, idx in zip(distances, indices):
        cls = _normalize_label(faiss_labels[idx[0]]) if 0 <= idx[0] < len(faiss_labels) else "unknown"
        thresh = FAISS_THRESHOLDS.get(cls, 0.40)
        decisions.append("VERIFIED" if dist[0] <= thresh else "ANOMALY")
    return decisions


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE RUNNERS
# ─────────────────────────────────────────────────────────────────────────────
def _crop_from_bbox(img_rgb: np.ndarray, bbox):
    """bbox = [x1,y1,x2,y2] in pixels, returns RGB crop."""
    h, w = img_rgb.shape[:2]
    x1, y1, x2, y2 = int(max(0,bbox[0])), int(max(0,bbox[1])), int(min(w,bbox[2])), int(min(h,bbox[3]))
    crop = img_rgb[y1:y2, x1:x2]
    return crop if crop.size > 0 else None


def run_pipeline_yolo(img_path: Path, yolo_model, embedder, faiss_index, faiss_labels):
    """Pipeline A: full-board → YOLOv8s (7-class) → MobileNetV3+FAISS"""
    t0 = time.perf_counter()
    results = yolo_model.predict(str(img_path), conf=YOLO_CONF, verbose=False)
    img_rgb = cv2.cvtColor(cv2.imread(str(img_path)), cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]

    pred_boxes = []
    crops = []
    for box in results[0].boxes:
        xyxy = box.xyxy[0].tolist()
        pred_boxes.append(xyxy)
        c = _crop_from_bbox(img_rgb, xyxy)
        crops.append(c)

    valid_mask = [i for i, c in enumerate(crops) if c is not None]
    valid_crops = [crops[i] for i in valid_mask]
    decisions_all = ["ANOMALY"] * len(crops)
    if valid_crops:
        decs = verify_crops(valid_crops, embedder, faiss_index, faiss_labels)
        for vi, dec in zip(valid_mask, decs):
            decisions_all[vi] = dec

    latency_ms = (time.perf_counter() - t0) * 1000
    return pred_boxes, decisions_all, latency_ms, w, h


def _run_sahi_pipeline(img_rgb: np.ndarray, sahi_model, embedder, faiss_index, faiss_labels):
    """Core SAHI inference + FAISS step (shared by pipelines B and C).
    Returns pred_boxes, decisions, confidences."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    cv2.imwrite(tmp_path, cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
    try:
        sliced = get_sliced_prediction(
            tmp_path, sahi_model,
            slice_height=SAHI_SLICE, slice_width=SAHI_SLICE,
            overlap_height_ratio=SAHI_OVERLAP, overlap_width_ratio=SAHI_OVERLAP,
            verbose=0,
        )
    finally:
        os.unlink(tmp_path)

    pred_boxes, crops, confidences = [], [], []
    for pred in sliced.object_prediction_list:
        x1, y1, x2, y2 = map(int, pred.bbox.to_xyxy())
        h, w = img_rgb.shape[:2]
        x1,y1,x2,y2 = max(0,x1),max(0,y1),min(w,x2),min(h,y2)
        pred_boxes.append([x1,y1,x2,y2])
        confidences.append(float(pred.score.value))
        c = img_rgb[y1:y2, x1:x2]
        crops.append(c if c.size > 0 else None)

    valid_mask = [i for i, c in enumerate(crops) if c is not None]
    valid_crops = [crops[i] for i in valid_mask]
    decisions_all = ["ANOMALY"] * len(crops)
    if valid_crops:
        decs = verify_crops(valid_crops, embedder, faiss_index, faiss_labels)
        for vi, dec in zip(valid_mask, decs):
            decisions_all[vi] = dec

    return pred_boxes, decisions_all, confidences


def run_pipeline_sahi(img_path: Path, sahi_model, embedder, faiss_index, faiss_labels):
    """Pipeline B: full-board → SAHI slicing → YOLO(1-cls) → MobileNetV3+FAISS"""
    t0 = time.perf_counter()
    img_rgb = cv2.cvtColor(cv2.imread(str(img_path)), cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    pred_boxes, decisions, confidences = _run_sahi_pipeline(img_rgb, sahi_model, embedder, faiss_index, faiss_labels)
    latency_ms = (time.perf_counter() - t0) * 1000
    return pred_boxes, decisions, confidences, latency_ms, w, h


def run_pipeline_highres(img_path: Path, sahi_model_hr, embedder, faiss_index, faiss_labels):
    """Pipeline C: resize to 1600px → SAHI → YOLO-P2(4-head) → MobileNetV3+FAISS"""
    t0 = time.perf_counter()
    img_bgr = cv2.imread(str(img_path))
    orig_h, orig_w = img_bgr.shape[:2]
    # Resize to 1600px width, preserve AR
    scale = HIGHRES_WIDTH / orig_w
    new_w = HIGHRES_WIDTH
    new_h = int(orig_h * scale)
    img_bgr_resized = cv2.resize(img_bgr, (new_w, new_h))
    img_rgb_resized = cv2.cvtColor(img_bgr_resized, cv2.COLOR_BGR2RGB)

    pred_boxes_scaled, decisions, confidences = _run_sahi_pipeline(
        img_rgb_resized, sahi_model_hr, embedder, faiss_index, faiss_labels
    )
    # Rescale predictions back to original image coords for fair GT matching
    pred_boxes = [
        [b[0]/scale, b[1]/scale, b[2]/scale, b[3]/scale]
        for b in pred_boxes_scaled
    ]
    latency_ms = (time.perf_counter() - t0) * 1000
    return pred_boxes, decisions, confidences, latency_ms, orig_w, orig_h


# ─────────────────────────────────────────────────────────────────────────────
# METRIC AGGREGATION
# ─────────────────────────────────────────────────────────────────────────────
def compute_metrics(all_pred_boxes, all_decisions, all_gt_boxes):
    """
    all_pred_boxes : list[list[box]]   one entry per image
    all_decisions  : list[list[str]]   "VERIFIED" | "ANOMALY"
    all_gt_boxes   : list[list[box]]   ground-truth boxes

    Returns dict: TP, FP_verified, FN, TN_rejected, recall, fdr
    """
    TP = FP_verified = FN = TN_rejected = 0

    for preds, decs, gts in zip(all_pred_boxes, all_decisions, all_gt_boxes):
        verified_indices   = [i for i, d in enumerate(decs) if d == "VERIFIED"]
        unverified_indices = [i for i, d in enumerate(decs) if d == "ANOMALY"]

        v_boxes = [preds[i] for i in verified_indices]
        u_boxes = [preds[i] for i in unverified_indices]

        # Match verified predictions against GT
        matched_v, unmatched_v, unmatched_gt_from_v = match_detections(v_boxes, gts)
        # Match unverified predictions against remaining GT boxes
        remaining_gt = [gts[i] for i in unmatched_gt_from_v]
        _, _, unmatched_gt_final = match_detections(u_boxes, remaining_gt)

        TP          += len(matched_v)
        FP_verified += len(unmatched_v)         # verified but no GT box → false acceptance
        TN_rejected += len(u_boxes) - (len(remaining_gt) - len(unmatched_gt_final))
        # FN = GT boxes matched by unverified detection + GT boxes not detected at all
        matched_by_unverified = len(remaining_gt) - len(unmatched_gt_final)
        FN += matched_by_unverified + len(unmatched_gt_final)

    total_pred_verified = TP + FP_verified
    total_actual        = TP + FN

    recall = TP / total_actual        if total_actual        > 0 else 0.0
    fdr    = FP_verified / total_pred_verified if total_pred_verified > 0 else 0.0
    far    = FP_verified / (FP_verified + TN_rejected) if (FP_verified + TN_rejected) > 0 else 0.0

    return {
        "TP": TP, "FP_verified": FP_verified, "FN": FN, "TN_rejected": TN_rejected,
        "recall": recall, "fdr": fdr, "far": far,
    }


def peak_memory_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024


# ─────────────────────────────────────────────────────────────────────────────
# CHART + TABLE OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
LABELS_SHORT = ["YOLO", "YOLO+SAHI", "YOLO+SAHI\n+HIGHRES"]
PALETTE      = ["#3B82F6", "#10B981", "#F59E0B"]

def draw_comparison_charts(results: dict, out_dir: Path):
    """Save one independent PNG per metric."""
    metrics = [
        ("map50",      "mAP@50",              True,  "%",  "chart_1_mAP50.png"),
        ("latency_ms", "End-to-End Latency",   False, "ms", "chart_2_latency.png"),
        ("fdr",        "False Discovery Rate", False, "%",  "chart_3_FDR.png"),
        ("recall",     "Recall",               True,  "%",  "chart_4_recall.png"),
        ("memory_mb",  "Peak Memory Footprint",False, "MB", "chart_5_memory.png"),
    ]

    DIRECTION = {True: "higher = better ↑", False: "lower = better ↓"}

    for key, title, higher_better, unit, filename in metrics:
        fig, ax = plt.subplots(figsize=(7, 6))
        fig.patch.set_facecolor("#060B12")
        ax.set_facecolor("#111827")

        vals = [results[name][key] for name in ["YOLO", "YOLO+SAHI", "YOLO+SAHI+HIGHRES"]]
        if unit == "%":
            vals = [v * 100 for v in vals]

        bars = ax.bar(LABELS_SHORT, vals, color=PALETTE, edgecolor="#1F2937",
                      linewidth=1.4, width=0.5)

        # Value labels above each bar
        y_max = max(vals) if max(vals) > 0 else 1
        for bar, v in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + y_max * 0.03,
                f"{v:.1f}{unit}",
                ha="center", va="bottom",
                color="#F8FAFC", fontsize=11, fontweight="bold", fontfamily="monospace",
            )

        # Green highlight border on best bar
        best_idx = vals.index(max(vals)) if higher_better else vals.index(min(vals))
        bars[best_idx].set_edgecolor("#10B981")
        bars[best_idx].set_linewidth(3)

        # Axis styling
        ax.set_ylim(0, y_max * 1.28)
        ax.set_ylabel(unit, color="#64748B", fontsize=10, fontfamily="monospace")
        ax.tick_params(colors="#94A3B8", labelsize=11)
        ax.tick_params(axis="x", pad=6)
        for sp in ax.spines.values():
            sp.set_edgecolor("#1F2937")

        # Titles
        ax.set_title(
            DIRECTION[higher_better],
            color="#64748B", fontsize=9, fontfamily="monospace", pad=4,
        )
        fig.suptitle(
            title,
            color="#F8FAFC", fontsize=14, fontweight="bold", fontfamily="monospace", y=0.98,
        )

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        save_path = out_dir / filename
        plt.savefig(str(save_path), dpi=150, bbox_inches="tight",
                    facecolor="#060B12", edgecolor="none")
        plt.close()
        print(f"[OK] Chart saved -> {filename}")


def print_table(results: dict):
    rows = []
    for name in ["YOLO", "YOLO+SAHI", "YOLO+SAHI+HIGHRES"]:
        r = results[name]
        rows.append([
            name,
            f"{r['map50']*100:.2f}%",
            f"{r['latency_ms']:.1f} ms",
            f"{r['fdr']*100:.2f}%",
            f"{r['recall']*100:.2f}%",
            f"{r['memory_mb']:.1f} MB",
        ])
    headers = ["Model", "mAP@50", "Latency (ms)", "FDR", "Recall", "Peak Mem (MB)"]
    col_w   = [max(len(h), max(len(r[i]) for r in rows)) + 2 for i, h in enumerate(headers)]
    sep  = "+" + "+".join("-" * w for w in col_w) + "+"
    hrow = "|" + "|".join(h.center(w) for h, w in zip(headers, col_w)) + "|"

    print("\n" + "=" * sum(col_w + [len(headers)+1]))
    print("  PCB INSPECTION — MODEL COMPARISON RESULTS")
    print("=" * sum(col_w + [len(headers)+1]))
    print(sep); print(hrow); print(sep)
    for row in rows:
        print("|" + "|".join(v.center(w) for v, w in zip(row, col_w)) + "|")
    print(sep)


def save_csv(results: dict, out_path: Path):
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Model", "mAP@50", "Latency_ms", "FDR", "Recall", "Peak_Memory_MB",
                    "TP", "FP_verified", "FN"])
        for name in ["YOLO", "YOLO+SAHI", "YOLO+SAHI+HIGHRES"]:
            r = results[name]
            w.writerow([name, f"{r['map50']:.4f}", f"{r['latency_ms']:.2f}",
                        f"{r['fdr']:.4f}", f"{r['recall']:.4f}", f"{r['memory_mb']:.1f}",
                        r.get("TP","N/A"), r.get("FP_verified","N/A"), r.get("FN","N/A")])
    print(f"[OK] CSV saved -> {out_path.name}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n",        type=int,   default=30,   help="Number of val images for pipeline benchmark")
    parser.add_argument("--skip-map", action="store_true",     help="Skip all mAP@50 computation")
    parser.add_argument("--yolo-map", type=float, default=None, help="Supply YOLO mAP@50 (0-1) directly; skips model.val() for Pipeline A")
    parser.add_argument("--seed",     type=int,   default=42,   help="Random seed for image sampling")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    print("\n" + "=" * 60)
    print("  PCB Inspection System — Model Benchmark")
    print(f"  Val images : {VAL_IMAGES_DIR}")
    print(f"  N images   : {args.n}  (for pipeline metrics)")
    print("=" * 60 + "\n")

    # ── Sample images ──────────────────────────────────────────────────────────
    all_imgs = sorted(VAL_IMAGES_DIR.glob("*.jpg")) + sorted(VAL_IMAGES_DIR.glob("*.png"))
    rng = np.random.default_rng(args.seed)
    sample_imgs = rng.choice(all_imgs, size=min(args.n, len(all_imgs)), replace=False).tolist()
    print(f"[*] Sampled {len(sample_imgs)} / {len(all_imgs)} val images for pipeline eval\n")

    # ── Build temp datasets for mAP eval ──────────────────────────────────────
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        _yaml_1cls, _label_dir_1cls = make_singleclass_data_yaml(tmp_dir)

        # Pipeline A: multi-class yaml.
        # VAL_IMAGES_DIR = D:\...\val\images  → YOLO resolves labels at D:\...\val\labels (already exists).
        # Ultralytics requires both train: and val: keys.
        multiclass_yaml_local = tmp_dir / "multiclass_local.yaml"
        multiclass_yaml_local.write_text(
            f"path: {str(VAL_IMAGES_DIR.parent)}\n"
            f"train: images\n"
            f"val: images\n"
            f"nc: 8\n"
            f"names:\n  0: capacitor\n  1: resistor\n  2: ic\n  3: diode\n"
            f"  4: led\n  5: inductor\n  6: connector\n  7: unknown\n"
        )

        # SAHI mAP is now computed from actual SAHI inference (compute_sahi_map50),
        # so no separate 1-class val dataset needed.

        # ── Load shared MobileNetV3 + FAISS (stays in memory throughout) ─────────
        embedder, faiss_index, faiss_labels = load_mobilenet_faiss()

        results = {}

        # ══════════════════════════════════════════════════════════════════════
        # A — YOLO (7-class, no SAHI)  — load → run → free before loading B
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "─"*50)
        print("  Pipeline A: YOLO (7-class, full-board)")
        print("─"*50)

        if args.yolo_map is not None:
            map_A = args.yolo_map
            print(f"[A] mAP@50 (supplied) = {map_A*100:.2f}%")
        elif not args.skip_map:
            print("[A] Running model.val() for mAP@50 ...")
            map_A = eval_map_yolo(WEIGHT_YOLO, multiclass_yaml_local)
            gc.collect()
            print(f"    mAP@50 = {map_A*100:.2f}%")
        else:
            map_A = 0.0

        yolo_model_A = YOLO(str(WEIGHT_YOLO))
        lat_A, preds_A, decs_A, gt_A = [], [], [], []
        mem_before_A = peak_memory_mb()
        for img_path in sample_imgs:
            lbl_path = VAL_LABELS_DIR / (img_path.stem + ".txt")
            pboxes, ddecs, lat_ms, w, h = run_pipeline_yolo(
                img_path, yolo_model_A, embedder, faiss_index, faiss_labels
            )
            gt_boxes = load_gt_boxes(lbl_path, w, h)
            lat_A.append(lat_ms)
            preds_A.append(pboxes); decs_A.append(ddecs); gt_A.append(gt_boxes)
            sys.stdout.write(f"\r    {len(lat_A)}/{len(sample_imgs)}  last={lat_ms:.0f}ms")
            sys.stdout.flush()
        print()
        mem_A = max(peak_memory_mb() - mem_before_A, 0.1)
        del yolo_model_A; gc.collect()   # free before loading B

        m_A = compute_metrics(preds_A, decs_A, gt_A)
        results["YOLO"] = {
            "map50": map_A,
            "latency_ms": float(np.mean(lat_A)),
            "fdr": m_A["fdr"], "far": m_A["far"],
            "recall": m_A["recall"],
            "memory_mb": mem_A,
            **{k: m_A[k] for k in ("TP","FP_verified","FN")},
        }

        # ══════════════════════════════════════════════════════════════════════
        # B — YOLO+SAHI  — load → run → compute mAP → free before loading C
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "─"*50)
        print("  Pipeline B: YOLO+SAHI (1-class, native resolution)")
        print("─"*50)

        sahi_model_B = load_sahi_model(WEIGHT_SAHI, "YOLO+SAHI")
        lat_B, preds_B, decs_B, gt_B, confs_B = [], [], [], [], []
        mem_before_B = peak_memory_mb()
        for img_path in sample_imgs:
            lbl_path = VAL_LABELS_DIR / (img_path.stem + ".txt")
            pboxes, ddecs, confs, lat_ms, w, h = run_pipeline_sahi(
                img_path, sahi_model_B, embedder, faiss_index, faiss_labels
            )
            gt_boxes = load_gt_boxes(lbl_path, w, h)
            lat_B.append(lat_ms)
            preds_B.append(pboxes); decs_B.append(ddecs); gt_B.append(gt_boxes)
            confs_B.append(confs)
            sys.stdout.write(f"\r    {len(lat_B)}/{len(sample_imgs)}  last={lat_ms:.0f}ms")
            sys.stdout.flush()
        print()
        mem_B = max(peak_memory_mb() - mem_before_B, 0.1)
        del sahi_model_B; gc.collect()   # free before loading C

        m_B = compute_metrics(preds_B, decs_B, gt_B)
        if not args.skip_map:
            map_B = compute_sahi_map50(preds_B, confs_B, gt_B)
            print(f"    mAP@50 (SAHI inference) = {map_B*100:.2f}%")
        else:
            map_B = 0.0
        results["YOLO+SAHI"] = {
            "map50": map_B,
            "latency_ms": float(np.mean(lat_B)),
            "fdr": m_B["fdr"], "far": m_B["far"],
            "recall": m_B["recall"],
            "memory_mb": mem_B,
            **{k: m_B[k] for k in ("TP","FP_verified","FN")},
        }

        # ══════════════════════════════════════════════════════════════════════
        # C — YOLO+SAHI+HIGHRES  — load → run → compute mAP → free
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "─"*50)
        print("  Pipeline C: YOLO+SAHI+HIGHRES (1600px resize, P2 4-head)")
        print("─"*50)

        sahi_model_C = load_sahi_model(WEIGHT_HIGHRES, "YOLO+SAHI+HIGHRES")
        lat_C, preds_C, decs_C, gt_C, confs_C = [], [], [], [], []
        mem_before_C = peak_memory_mb()
        for img_path in sample_imgs:
            lbl_path = VAL_LABELS_DIR / (img_path.stem + ".txt")
            pboxes, ddecs, confs, lat_ms, w, h = run_pipeline_highres(
                img_path, sahi_model_C, embedder, faiss_index, faiss_labels
            )
            gt_boxes = load_gt_boxes(lbl_path, w, h)
            lat_C.append(lat_ms)
            preds_C.append(pboxes); decs_C.append(ddecs); gt_C.append(gt_boxes)
            confs_C.append(confs)
            sys.stdout.write(f"\r    {len(lat_C)}/{len(sample_imgs)}  last={lat_ms:.0f}ms")
            sys.stdout.flush()
        print()
        mem_C = max(peak_memory_mb() - mem_before_C, 0.1)
        del sahi_model_C; gc.collect()

        m_C = compute_metrics(preds_C, decs_C, gt_C)
        if not args.skip_map:
            map_C = compute_sahi_map50(preds_C, confs_C, gt_C)
            print(f"    mAP@50 (SAHI inference) = {map_C*100:.2f}%")
        else:
            map_C = 0.0
        results["YOLO+SAHI+HIGHRES"] = {
            "map50": map_C,
            "latency_ms": float(np.mean(lat_C)),
            "fdr": m_C["fdr"], "far": m_C["far"],
            "recall": m_C["recall"],
            "memory_mb": mem_C,
            **{k: m_C[k] for k in ("TP","FP_verified","FN")},
        }

        # ── Output ─────────────────────────────────────────────────────────────
        print_table(results)
        draw_comparison_charts(results, OUTPUT_DIR)
        save_csv(results, OUTPUT_DIR / "model_comparison.csv")

        # Latency distribution chart
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor("#060B12")
        ax.set_facecolor("#111827")
        for lats, color, lbl in [(lat_A, PALETTE[0], "YOLO"),
                                   (lat_B, PALETTE[1], "YOLO+SAHI"),
                                   (lat_C, PALETTE[2], "YOLO+SAHI+HIGHRES")]:
            ax.plot(sorted(lats), color=color, label=lbl, linewidth=2)
        ax.set_xlabel("Image rank (sorted)", color="#64748B", fontfamily="monospace")
        ax.set_ylabel("Latency (ms)", color="#64748B", fontfamily="monospace")
        ax.set_title("Per-Image Latency Distribution", color="#F8FAFC",
                     fontsize=11, fontweight="bold", fontfamily="monospace")
        ax.legend(facecolor="#1E293B", edgecolor="#334155", labelcolor="#CBD5E1")
        ax.tick_params(colors="#64748B")
        for sp in ax.spines.values(): sp.set_edgecolor("#1F2937")
        plt.tight_layout()
        plt.savefig(str(OUTPUT_DIR / "latency_distribution.png"), dpi=150,
                    bbox_inches="tight", facecolor="#060B12")
        plt.close()
        print(f"[OK] Latency chart saved -> latency_distribution.png")
        print(f"\n[DONE] All results in: {OUTPUT_DIR}\n")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
