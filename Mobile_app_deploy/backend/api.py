"""
To expose the local FastAPI server externally for mobile testing:
- ngrok: `ngrok http 8000` (use the HTTPS forwarding URL in the mobile app)
- playit.gg: `playit` then create an HTTP tunnel to localhost:8000
Update API_BASE_URL in the mobile client to the tunnel URL (e.g. https://random-id.ngrok-free.app).
"""

import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal, List
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import get_db_connection
from ml_pipeline import (
    ensure_image_readable,
    run_sahi_yolo,
    normalize_ai_output
)
from services import cleanup_failed_scan, generate_excel, save_uploaded_file

router = APIRouter()

API_LOGGER = logging.getLogger("API")

# --- FLYWHEEL CONFIGURATION ---
STAGING_DIR = Path(__file__).resolve().parent / "dataset_staging"
IMAGES_DIR = STAGING_DIR / "images"
LABELS_DIR = STAGING_DIR / "labels"

# Ensure staging directories exist when the server starts
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
LABELS_DIR.mkdir(parents=True, exist_ok=True)

# Exact mapping based on your custom YOLO training classes
YOLO_CLASS_MAP = {
    "capacitor": 0,
    "resistor": 1,
    "ic": 2,
    "diode": 3,
    "led": 4,
    "inductor": 5,
    "connector": 6,
    "unknown": 7
}

# --- TYPE DEFINITIONS ---
ScanMode = Literal["YOLO", "MOBILENET", "UNIFIED"]

class AnalyzeResponse(BaseModel):
    status: str
    scan_id: str
    download_url: str
    message: str

class ScanSummary(BaseModel):
    scan_id: str
    timestamp: str
    scan_mode: str

class ScanListResponse(BaseModel):
    status: str
    scans: List[ScanSummary]


# --- ROUTES ---

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_board(
    file: UploadFile = File(...),
    mode: ScanMode = Form(...),
    corners: str = Form(None),
) -> AnalyzeResponse:
    scan_id = str(uuid4())
    image_path = save_uploaded_file(file)
    
    scan_mode = "EUCLIDEAN_TOPOLOGY" 

    try:
        try:
            await run_in_threadpool(ensure_image_readable, image_path)
        except ValueError:
            cleanup_failed_scan(image_path)
            raise HTTPException(status_code=400, detail="Image Unreadable")

        yolo_results = await run_in_threadpool(run_sahi_yolo, image_path, corners)
        mobilenet_results = None
        normalized_rows = normalize_ai_output(scan_id, yolo_results, mobilenet_results)
        
        timestamp = datetime.utcnow().isoformat()

        with get_db_connection() as connection:
            connection.execute(
                "INSERT INTO scans (scan_id, timestamp, image_path, scan_mode) VALUES (?, ?, ?, ?)",
                (scan_id, timestamp, image_path, scan_mode),
            )

            for row in normalized_rows:
                connection.execute(
                    """
                    INSERT INTO normalized_results (
                        result_id, scan_id, source_model, class_label,
                        bounding_box_x, bounding_box_y, box_width, box_height,
                        confidence_score, defect_status, defect_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["result_id"], row["scan_id"], row["source_model"],
                        row["class_label"], row["bounding_box_x"], row["bounding_box_y"],
                        row["box_width"], row["box_height"], row["confidence_score"],
                        row["defect_status"], row["defect_type"],
                    ),
                )

        excel_path = generate_excel(scan_id)
        download_url = f"/api/v2/download/{scan_id}"

        return AnalyzeResponse(
            status="success",
            scan_id=scan_id,
            download_url=download_url,
            message="Analysis complete. Download report is ready.",
        )
    except HTTPException:
        cleanup_failed_scan(image_path)
        raise
    except Exception as exc:
        API_LOGGER.exception("Analysis failed for scan %s", scan_id)
        cleanup_failed_scan(image_path)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


@router.post("/flywheel/ingest")
async def ingest_flywheel_correction(
    file: UploadFile = File(...),
    boxes: str = Form(...),            
    screen_width: float = Form(...),   
    screen_height: float = Form(...)   
):
    """
    Phase 2 Ingestion Route: Catches mobile screen corrections and translates them 
    into normalized YOLO .txt format for the staging dataset.
    """
    try:
        parsed_boxes = json.loads(boxes)
        asset_id = f"flywheel_{uuid4().hex[:8]}"
        
        # Save Raw Image
        image_ext = Path(file.filename).suffix or ".jpg"
        image_filename = f"{asset_id}{image_ext}"
        image_path = IMAGES_DIR / image_filename
        
        image_bytes = await file.read()
        with open(image_path, "wb") as f:
            f.write(image_bytes)
            
        # Mathematical Translation (Mobile Pixels -> YOLO Coordinates)
        label_filename = f"{asset_id}.txt"
        label_path = LABELS_DIR / label_filename
        
        yolo_lines = []
        for box in parsed_boxes:
            # We map it to lowercase just in case the mobile app sends "Capacitor" instead of "capacitor"
            label_str = str(box.get("label")).strip().lower() if box.get("label") else "unknown"
            
            if label_str not in YOLO_CLASS_MAP:
                API_LOGGER.warning(f"Unknown label '{label_str}' mapping to 'unknown' (7).")
                class_id = YOLO_CLASS_MAP["unknown"]
            else:
                class_id = YOLO_CLASS_MAP[label_str]
            
            # Translate Top-Left coordinates to YOLO Center-Normalized coordinates
            center_x = (box["x"] + (box["width"] / 2.0)) / screen_width
            center_y = (box["y"] + (box["height"] / 2.0)) / screen_height
            norm_width = box["width"] / screen_width
            norm_height = box["height"] / screen_height
            
            # Clamp values to strictly 0.0 - 1.0 to prevent training crashes
            center_x = max(0.0, min(1.0, center_x))
            center_y = max(0.0, min(1.0, center_y))
            norm_width = max(0.0, min(1.0, norm_width))
            norm_height = max(0.0, min(1.0, norm_height))
            
            yolo_line = f"{class_id} {center_x:.6f} {center_y:.6f} {norm_width:.6f} {norm_height:.6f}"
            yolo_lines.append(yolo_line)
            
        # Save Label File
        with open(label_path, "w") as f:
            f.write("\n".join(yolo_lines))
            
        API_LOGGER.info(f"[+] Flywheel Ingestion Success: Saved {len(yolo_lines)} bounding boxes for {asset_id}.")
        
        return {
            "status": "success",
            "message": "Asset successfully translated and added to staging dataset.",
            "asset_id": asset_id
        }

    except Exception as exc:
        API_LOGGER.exception("Flywheel ingestion failed.")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(exc)}")


@router.get("/scans", response_model=ScanListResponse)
async def list_scans() -> ScanListResponse:
    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT scan_id, timestamp, scan_mode FROM scans ORDER BY timestamp DESC"
        ).fetchall()

    scans = [
        ScanSummary(
            scan_id=row["scan_id"],
            timestamp=row["timestamp"],
            scan_mode=row["scan_mode"],
        )
        for row in rows
    ]
    return ScanListResponse(status="success", scans=scans)


@router.post("/upgrade/{scan_id}", response_model=AnalyzeResponse)
async def upgrade_scan(scan_id: str) -> AnalyzeResponse:
    with get_db_connection() as connection:
        scan_row = connection.execute(
            "SELECT scan_id FROM scans WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()

        if not scan_row:
            raise HTTPException(status_code=404, detail="Scan ID not found")

    return AnalyzeResponse(
        status="success",
        scan_id=scan_id,
        download_url=f"/api/v2/download/{scan_id}",
        message="Scan is already running full Euclidean Topology. Report ready.",
    )


@router.get("/download/{scan_id}")
async def download_report(scan_id: str) -> FileResponse:
    export_path = Path(__file__).resolve().parent / "exports" / f"inventory_{scan_id}.xlsx"
    if not export_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path=str(export_path), filename=export_path.name)