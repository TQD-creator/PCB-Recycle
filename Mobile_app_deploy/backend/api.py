"""
To expose the local FastAPI server externally for mobile testing:
- ngrok: `ngrok http 8000` (use the HTTPS forwarding URL in the mobile app)
- playit.gg: `playit` then create an HTTP tunnel to localhost:8000
Update API_BASE_URL in the mobile client to the tunnel URL (e.g. https://random-id.ngrok-free.app).
"""

import asyncio
import json
import logging
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
    normalize_ai_output,
    run_grid_mobilenet,
    run_sahi_yolo,
)
from services import cleanup_failed_scan, generate_excel, save_uploaded_file
from warp_engine import flatten_dynamic

router = APIRouter()

API_LOGGER = logging.getLogger("API")

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


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_board(
    file: UploadFile = File(...),
    mode: ScanMode = Form(...),
    corners: str = Form(None),
) -> AnalyzeResponse:
    scan_id = str(uuid4())
    image_path = save_uploaded_file(file)
    scan_mode = {
        "YOLO": "YOLO_ONLY",
        "MOBILENET": "MOBILENET_ONLY",
        "UNIFIED": "UNIFIED",
    }[mode]

    try:
        if corners:
            try:
                parsed_corners = json.loads(corners)
                if len(parsed_corners) == 4:
                    await run_in_threadpool(flatten_dynamic, image_path, parsed_corners)
            except Exception as exc:
                API_LOGGER.warning("Failed to parse or apply corners: %s", exc)

        try:
            await run_in_threadpool(ensure_image_readable, image_path)
        except ValueError:
            cleanup_failed_scan(image_path)
            raise HTTPException(status_code=400, detail="Image Unreadable")

        yolo_results = []
        mobilenet_results = []

        if mode == "YOLO":
            yolo_results = await run_in_threadpool(run_sahi_yolo, image_path)
        elif mode == "MOBILENET":
            mobilenet_results = await run_in_threadpool(run_grid_mobilenet, image_path)
        else:
            yolo_results, mobilenet_results = await asyncio.gather(
                run_in_threadpool(run_sahi_yolo, image_path),
                run_in_threadpool(run_grid_mobilenet, image_path),
            )

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
                        result_id,
                        scan_id,
                        source_model,
                        class_label,
                        bounding_box_x,
                        bounding_box_y,
                        box_width,
                        box_height,
                        confidence_score,
                        defect_status,
                        defect_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["result_id"],
                        row["scan_id"],
                        row["source_model"],
                        row["class_label"],
                        row["bounding_box_x"],
                        row["bounding_box_y"],
                        row["box_width"],
                        row["box_height"],
                        row["confidence_score"],
                        row["defect_status"],
                        row["defect_type"],
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
            "SELECT scan_id, image_path, scan_mode FROM scans WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()

        if not scan_row:
            raise HTTPException(status_code=404, detail="Scan ID not found")

        source_rows = connection.execute(
            "SELECT DISTINCT source_model FROM normalized_results WHERE scan_id = ?",
            (scan_id,),
        ).fetchall()

    existing_sources = {row["source_model"] for row in source_rows}
    scan_mode = scan_row["scan_mode"]
    image_path = scan_row["image_path"]

    if scan_mode == "UNIFIED" or existing_sources == {"YOLO", "MOBILENET"}:
        with get_db_connection() as connection:
            connection.execute(
                "UPDATE scans SET scan_mode = 'UNIFIED' WHERE scan_id = ?",
                (scan_id,),
            )

        generate_excel(scan_id)
        return AnalyzeResponse(
            status="success",
            scan_id=scan_id,
            download_url=f"/api/v2/download/{scan_id}",
            message="Scan already unified. Report ready.",
        )

    try:
        try:
            await run_in_threadpool(ensure_image_readable, image_path)
        except ValueError:
            raise HTTPException(status_code=400, detail="Image Unreadable")

        need_yolo = scan_mode == "MOBILENET_ONLY" or "YOLO" not in existing_sources
        need_mobilenet = scan_mode == "YOLO_ONLY" or "MOBILENET" not in existing_sources

        yolo_results = []
        mobilenet_results = []

        if need_yolo:
            yolo_results = await run_in_threadpool(run_sahi_yolo, image_path)
        if need_mobilenet:
            mobilenet_results = await run_in_threadpool(run_grid_mobilenet, image_path)

        normalized_rows = normalize_ai_output(scan_id, yolo_results, mobilenet_results)

        with get_db_connection() as connection:
            for row in normalized_rows:
                connection.execute(
                    """
                    INSERT INTO normalized_results (
                        result_id,
                        scan_id,
                        source_model,
                        class_label,
                        bounding_box_x,
                        bounding_box_y,
                        box_width,
                        box_height,
                        confidence_score,
                        defect_status,
                        defect_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["result_id"],
                        row["scan_id"],
                        row["source_model"],
                        row["class_label"],
                        row["bounding_box_x"],
                        row["bounding_box_y"],
                        row["box_width"],
                        row["box_height"],
                        row["confidence_score"],
                        row["defect_status"],
                        row["defect_type"],
                    ),
                )

            connection.execute(
                "UPDATE scans SET scan_mode = 'UNIFIED' WHERE scan_id = ?",
                (scan_id,),
            )

        generate_excel(scan_id)
        return AnalyzeResponse(
            status="success",
            scan_id=scan_id,
            download_url=f"/api/v2/download/{scan_id}",
            message="Scan upgraded to unified. Report ready.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        API_LOGGER.exception("Upgrade failed for scan %s", scan_id)
        raise HTTPException(status_code=500, detail=f"Upgrade failed: {exc}") from exc


@router.get("/download/{scan_id}")
async def download_report(scan_id: str) -> FileResponse:
    export_path = Path(__file__).resolve().parent / "exports" / f"inventory_{scan_id}.xlsx"
    if not export_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path=str(export_path), filename=export_path.name)
