from __future__ import annotations

import gc
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Sequence
from uuid import uuid4

import cv2
import numpy as np
import torch
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction

# --- Paths and Setup ---
MODEL_DIR = Path(r"C:\Users\Lenovo\Documents\Foxconn\PCB-Detection\SAVE_model")
YOLO_WEIGHTS = MODEL_DIR / "best_NoConnector_20260526_2158.pt"
TEMPLATES_PATH = MODEL_DIR.parent / "golden_templates.json"

_MODEL_LOCK = Lock()
_MODEL_SAHI: AutoDetectionModel | None = None

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

SAHI_LOGGER = logging.getLogger("SAHI_ENGINE")
WARP_LOGGER = logging.getLogger("WARP_ENGINE")
NORMALIZER_LOGGER = logging.getLogger("NORMALIZER")


def load_models() -> None:
    """Load SAHI YOLO model into memory once per server lifecycle."""
    global _MODEL_SAHI

    if _MODEL_SAHI is not None:
        return

    with _MODEL_LOCK:
        if _MODEL_SAHI is not None:
            return

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        device_name = "cuda:0" if device.type == "cuda" else "cpu"

        SAHI_LOGGER.info("Loading YOLOv8 Model via SAHI wrapper on %s...", device_name)
        sahi_model = AutoDetectionModel.from_pretrained(
            model_type="yolov8",
            model_path=str(YOLO_WEIGHTS),
            confidence_threshold=0.15,
            device=device_name,
        )

        _MODEL_SAHI = sahi_model


def ensure_image_readable(image_path: str) -> None:
    """Validate that OpenCV can decode the uploaded image bytes."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Image unreadable")
    del image


def flatten_pcb_image(image_path: str, relative_corners: List[Dict[str, float]], target_size: int = 1000) -> None:
    """
    Transforms a skewed smartphone photo into a normalized 1000x1000 square image
    using relative touch coordinates submitted from the React Native screen interface.
    """
    WARP_LOGGER.info("Executing 4-point perspective alignment for: %s", image_path)
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Cannot read image for perspective warp transformation.")
        
    img_h, img_w = img.shape[:2]

    # Convert normalized screen ratios (0.0 to 1.0) into exact canvas coordinates
    src_pts = []
    for corner in relative_corners:
        abs_x = int(corner['x'] * img_w)
        abs_y = int(corner['y'] * img_h)
        src_pts.append([abs_x, abs_y])
        
    source_corners = np.float32(src_pts)

    # Establish target projection layout (1000x1000 canvas boundary limits)
    dest_corners = np.float32([
        [0, 0], 
        [target_size - 1, 0], 
        [target_size - 1, target_size - 1], 
        [0, target_size - 1]
    ])

    # Execute geometric mapping operations
    matrix = cv2.getPerspectiveTransform(source_corners, dest_corners)
    flattened_img = cv2.warpPerspective(img, matrix, (target_size, target_size))

    # Overwrite source disk file layout with perfectly flat image copy
    cv2.imwrite(image_path, flattened_img)
    WARP_LOGGER.info("Image mapping completed. Normalized workspace updated.")


def ensure_golden_templates_exist() -> None:
    """Creates a baseline mock golden template dictionary fallback if the file is missing."""
    if not TEMPLATES_PATH.exists():
        fallback_data = {
            "Foxconn_Demo_Board": {
                "Anchor_Component": {
                    "class_label": "IC",
                    "absolute_x": 500.0,
                    "absolute_y": 500.0
                },
                "Expected_Components": {
                    "IC_Phase_1": {"class_label": "IC", "vector_x": 120.0, "vector_y": -80.0, "w": 85.0, "h": 85.0},
                    "Capacitor_Filter_1": {"class_label": "Capacitor", "vector_x": -210.0, "vector_y": 140.0, "w": 40.0, "h": 40.0},
                    "Resistor_Line_1": {"class_label": "Resistor", "vector_x": 50.0, "vector_y": 300.0, "w": 25.0, "h": 60.0}
                }
            }
        }
        with open(TEMPLATES_PATH, "w") as f:
            json.dump(fallback_data, f, indent=2)
        NORMALIZER_LOGGER.info("Generated default reference architecture file layout at %s", TEMPLATES_PATH)


def run_sahi_yolo(image_path: str, corners_json: str | None = None) -> List[Dict[str, Any]]:
    """Applies perspective warping if coordinates exist, then generates window-sliced inferences."""
    load_models()

    if _MODEL_SAHI is None:
        raise RuntimeError("SAHI wrapper instance validation failure.")

    # Execute dynamic perspective normalization if corners coordinates exist
    if corners_json:
        try:
            parsed_corners = json.loads(corners_json)
            if len(parsed_corners) == 4:
                flatten_pcb_image(image_path, parsed_corners)
            else:
                WARP_LOGGER.warning("Invalid corner coordinates array length payload. Skipping alignment phase.")
        except Exception as e:
            WARP_LOGGER.error("Failed to parse corner layout schema matrix: %s", str(e))

    SAHI_LOGGER.info("Starting SAHI canvas segmentation sweeps for %s", image_path)
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
        SAHI_LOGGER.info("Inference sweeps completed. Generated %d records.", len(detections))
        del sahi_result
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return detections


def normalize_ai_output(
    scan_id: str,
    yolo_results: Sequence[Dict[str, Any]] | None,
    mobilenet_results: Sequence[Dict[str, Any]] | None = None, # Left intact for signature safety
) -> List[Dict[str, Any]]:
    """
    Core Logic Engine. Compares YOLO live detections against the Anchor-Based
    Golden Template file framework via strict Euclidean vector math.
    """
    normalized: List[Dict[str, Any]] = []
    ensure_golden_templates_exist()

    try:
        with open(TEMPLATES_PATH, "r") as f:
            templates = json.load(f)
        template_profile = templates["Foxconn_Demo_Board"]
    except Exception as e:
        NORMALIZER_LOGGER.error("Failed reading JSON profile data templates: %s. Using naive schema pass.", str(e))
        template_profile = None

    # Fallback to direct mapping if no golden metadata profiles exist on the host system
    if not template_profile or not yolo_results:
        for detection in yolo_results or []:
            normalized.append({
                "result_id": str(uuid4()),
                "scan_id": scan_id,
                "source_model": "YOLO (No Template Match)",
                "class_label": detection["label"],
                "bounding_box_x": float(detection["x_center"]),
                "bounding_box_y": float(detection["y_center"]),
                "box_width": float(detection["width"]),
                "box_height": float(detection["height"]),
                "confidence_score": float(detection["confidence"]),
                "defect_status": "Intact",
                "defect_type": None,
            })
        return normalized

    # --- TOPOLOGY ENGINE ALGORITHMIC EVALUATION ---
    anchor_cfg = template_profile["Anchor_Component"]
    expected_components = template_profile["Expected_Components"]

    # Step 1: Find the target reference layout Anchor point from the live detections pool
    live_anchor_x, live_anchor_y = None, None
    best_anchor_dist = float('inf')

    for item in yolo_results:
        if item["label"] == anchor_cfg["class_label"]:
            # Match item closest to expected absolute layout blueprint center metrics
            dist = math.sqrt((item["x_center"] - anchor_cfg["absolute_x"])**2 + (item["y_center"] - anchor_cfg["absolute_y"])**2)
            if dist < best_anchor_dist:
                best_anchor_dist = dist
                live_anchor_x = item["x_center"]
                live_anchor_y = item["y_center"]

    # Fallback to the hardcoded coordinate configuration map if layout anchor point cannot be isolated
    if live_anchor_x is None or live_anchor_y is None:
        NORMALIZER_LOGGER.warning("Primary reference blueprint layout Anchor component not matched. Using absolute scaling matrix.")
        live_anchor_x = anchor_cfg["absolute_x"]
        live_anchor_y = anchor_cfg["absolute_y"]

    # Step 2: Cross-reference expected layout objects against live component tracking arrays
    DISTANCE_TOLERANCE = 35.0  # Maximum pixel shift threshold allocation distance limit
    AREA_TOLERANCE = 0.25      # Maximum bounding box layout volume expansion margin allowance limit

    for component_id, expected in expected_components.items():
        # Extrapolate ideal absolute canvas pixel positions using anchor vector math metrics
        target_absolute_x = live_anchor_x + expected["vector_x"]
        target_absolute_y = live_anchor_y + expected["vector_y"]

        matched_candidate = None
        closest_distance = float('inf')

        for live_item in yolo_results:
            if live_item["label"] == expected["class_label"]:
                dist = math.sqrt((live_item["x_center"] - target_absolute_x)**2 + (live_item["y_center"] - target_absolute_y)**2)
                if dist < closest_distance:
                    closest_distance = dist
                    matched_candidate = live_item

        # Step 3: Run programmatic logic gating layers to identify layout variances
        defect_status = "Intact"
        defect_type = None

        if matched_candidate is None or closest_distance > DISTANCE_TOLERANCE:
            defect_status = "Defective"
            defect_type = "Missing Component"
            final_x, final_y = target_absolute_x, target_absolute_y
            final_w, final_h = expected["w"], expected["h"]
            confidence = 0.0
        else:
            final_x, final_y = matched_candidate["x_center"], matched_candidate["y_center"]
            final_w, final_h = matched_candidate["width"], matched_candidate["height"]
            confidence = matched_candidate["confidence"]

            # Calculate area variance metrics to detect rotational skew problems
            expected_area = expected["w"] * expected["h"]
            detected_area = final_w * final_h
            area_drift = abs(detected_area - expected_area) / expected_area

            if closest_distance > 12.0:
                defect_status = "Defective"
                defect_type = f"Misaligned Component (Shifted {closest_distance:.1f}px)"
            elif area_drift > AREA_TOLERANCE:
                defect_status = "Defective"
                defect_type = f"Rotational Skew Error (Area Variance: {area_drift*100:.1f}%)"

        normalized.append({
            "result_id": str(uuid4()),
            "scan_id": scan_id,
            "source_model": "YOLO + Euclidean Logic",
            "class_label": f"{expected['class_label']} ({component_id})",
            "bounding_box_x": float(final_x),
            "bounding_box_y": float(final_y),
            "box_width": float(final_w),
            "box_height": float(final_h),
            "confidence_score": float(confidence),
            "defect_status": defect_status,
            "defect_type": defect_type,
        })

    NORMALIZER_LOGGER.info("Calculated %d topological evaluations for run profile execution reference ID %s", len(normalized), scan_id)
    return normalized