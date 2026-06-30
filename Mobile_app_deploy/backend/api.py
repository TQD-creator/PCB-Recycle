from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from celery_app import celery_app
from config import UPLOADS_DIR
from database import (
    get_all_corrections,
    get_session,
    login_user,
    logout_user,
    review_correction,
    submit_correction,
)
from models import (
    AuthResponse,
    InventoryReport,
    LoginRequest,
    ResolveAnchorRequest,
    ResolveAnchorResponse,
    ReviewCorrectionRequest,
    ScanState,
    SubmitCorrectionRequest,
    TaskAcceptedResponse,
    TaskStatusResponse,
)

router = APIRouter()


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _get_session(authorization: str | None) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return get_session(authorization[7:])


def _require_auth(authorization: str | None) -> dict:
    session = _get_session(authorization)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return session


def _require_admin(authorization: str | None) -> dict:
    session = _require_auth(authorization)
    if session["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return session


# ── Auth endpoints ────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=AuthResponse)
async def auth_login(request: LoginRequest):
    result = login_user(request.username, request.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return result


@router.post("/auth/logout")
async def auth_logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        logout_user(authorization[7:])
    return {"message": "Logged out."}


@router.get("/auth/me")
async def auth_me(authorization: str | None = Header(default=None)):
    session = _require_auth(authorization)
    return {
        "username":   session["username"],
        "role":       session["role"],
        "user_id":    session["user_id"],
        "expires_at": session.get("expires_at"),
    }


# ── Scan endpoints ────────────────────────────────────────────────────────────

def _persist_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "scan.jpg").suffix or ".jpg"
    image_name = f"scan_{uuid4().hex}{suffix}"
    target = UPLOADS_DIR / image_name
    with target.open("wb") as handle:
        handle.write(file.file.read())
    return target


@router.post("/scan/upload", response_model=TaskAcceptedResponse, status_code=202)
async def upload_scan(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    session = _require_auth(authorization)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image uploads are supported.")
    saved_path = _persist_upload(file)
    task = celery_app.send_task(
        "pcb.scan.execute",
        kwargs={"image_path": str(saved_path), "user_id": session["user_id"]},
    )
    return TaskAcceptedResponse(
        task_id=task.id,
        state=ScanState.queued,
        message="Scan accepted and queued for asynchronous processing.",
    )


@router.get("/scan/status/{task_id}", response_model=TaskStatusResponse)
async def get_scan_status(
    task_id: str,
    authorization: str | None = Header(default=None),
):
    _require_auth(authorization)
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
            task_id=task_id, state=ScanState.processing,
            stage=str(meta.get("stage", "Processing")), progress=int(meta.get("progress", 10)),
        )

    if task.state == "SUCCESS":
        payload = task.result or {}
        report_data = payload.get("report")
        report = InventoryReport.model_validate(report_data) if report_data else None
        return TaskStatusResponse(
            task_id=task_id, state=ScanState.completed,
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
        task_id=task_id, state=ScanState.failed, stage="Failed", progress=100, error=error_message
    )


@router.post("/anchors/resolve", response_model=ResolveAnchorResponse)
async def resolve_anchor(
    request: ResolveAnchorRequest,
    authorization: str | None = Header(default=None),
):
    _require_auth(authorization)
    try:
        task = celery_app.send_task(
            "pcb.anchors.resolve",
            kwargs={
                "task_id": request.task_id,
                "anomaly_index": request.anomaly_index,
                "decision": request.decision.value,
                "approved_class": request.approved_class,
            },
        )
        message = task.get(timeout=10)
        return ResolveAnchorResponse(
            task_id=request.task_id,
            anomaly_index=request.anomaly_index,
            decision=request.decision,
            message=message,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to resolve anomaly: {exc}")


# ── Corrections ───────────────────────────────────────────────────────────────

@router.post("/corrections/submit", status_code=201)
async def submit_corrections(
    request: SubmitCorrectionRequest,
    authorization: str | None = Header(default=None),
):
    session = _require_auth(authorization)
    if not request.corrections:
        raise HTTPException(status_code=400, detail="No corrections provided.")
    data = [c.model_dump() for c in request.corrections]
    correction_id = submit_correction(
        request.task_id, request.image_url or "", data,
        submitted_by=session["user_id"],
    )
    return {"correction_id": correction_id, "status": "PENDING", "count": len(data)}


@router.get("/corrections")
async def list_corrections(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return get_all_corrections()


@router.post("/corrections/{correction_id}/review")
async def review_correction_endpoint(
    correction_id: int,
    request: ReviewCorrectionRequest,
    authorization: str | None = Header(default=None),
):
    _require_admin(authorization)
    if request.action not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="action must be APPROVE or REJECT")
    found = review_correction(correction_id, request.action, request.reviewer_note)
    if not found:
        raise HTTPException(status_code=404, detail="Correction not found.")
    return {"correction_id": correction_id, "status": request.action}
