from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from celery_app import celery_app
from config import UPLOADS_DIR
from cv_pipeline import resolve_anomaly
from models import (
    InventoryReport,
    ResolveAnchorRequest,
    ResolveAnchorResponse,
    ScanState,
    TaskAcceptedResponse,
    TaskStatusResponse,
)

router = APIRouter()


def _persist_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "scan.jpg").suffix or ".jpg"
    image_name = f"scan_{uuid4().hex}{suffix}"
    target = UPLOADS_DIR / image_name

    with target.open("wb") as handle:
        handle.write(file.file.read())

    return target


@router.post("/scan/upload", response_model=TaskAcceptedResponse, status_code=202)
async def upload_scan(file: UploadFile = File(...)) -> TaskAcceptedResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image uploads are supported.")

    saved_path = _persist_upload(file)
    task = celery_app.send_task("pcb.scan.execute", kwargs={"image_path": str(saved_path)})

    return TaskAcceptedResponse(
        task_id=task.id,
        state=ScanState.queued,
        message="Scan accepted and queued for asynchronous processing.",
    )


@router.get("/scan/status/{task_id}", response_model=TaskStatusResponse)
async def get_scan_status(task_id: str) -> TaskStatusResponse:
    task = AsyncResult(task_id, app=celery_app)

    if task.state in {"PENDING", "RECEIVED", "STARTED"}:
        return TaskStatusResponse(
            task_id=task_id,
            state=ScanState.processing if task.state != "PENDING" else ScanState.queued,
            stage="Queued" if task.state == "PENDING" else "Worker Started",
            progress=5 if task.state == "PENDING" else 10,
        )

    if task.state == "PROGRESS":
        meta = task.info or {}
        return TaskStatusResponse(
            task_id=task_id,
            state=ScanState.processing,
            stage=str(meta.get("stage", "Processing")),
            progress=int(meta.get("progress", 10)),
        )

    if task.state == "SUCCESS":
        payload = task.result or {}
        report_data = payload.get("report")
        report = InventoryReport.model_validate(report_data) if report_data else None

        return TaskStatusResponse(
            task_id=task_id,
            state=ScanState.completed,
            stage=str(payload.get("stage", "Completed")),
            progress=int(payload.get("progress", 100)),
            image_url=payload.get("image_url"),
            report=report,
            triage_queue=payload.get("triage_queue", []),
        )

    error_message = "Unknown processing error"
    if isinstance(task.info, dict):
        error_message = str(task.info.get("error", error_message))
    elif task.info is not None:
        error_message = str(task.info)

    return TaskStatusResponse(
        task_id=task_id,
        state=ScanState.failed,
        stage="Failed",
        progress=100,
        error=error_message,
    )


@router.post("/anchors/resolve", response_model=ResolveAnchorResponse)
async def resolve_anchor(request: ResolveAnchorRequest) -> ResolveAnchorResponse:
    try:
        message = resolve_anomaly(
            task_id=request.task_id,
            anomaly_index=request.anomaly_index,
            decision=request.decision.value,
            approved_class=request.approved_class,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to resolve anomaly: {exc}") from exc

    return ResolveAnchorResponse(
        task_id=request.task_id,
        anomaly_index=request.anomaly_index,
        decision=request.decision,
        message=message,
    )
