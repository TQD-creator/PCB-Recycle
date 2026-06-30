from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ScanState(str, Enum):
    queued = "QUEUED"
    processing = "PROCESSING"
    completed = "COMPLETED"
    failed = "FAILED"


class ComponentRecord(BaseModel):
    bbox: List[int] = Field(..., min_length=4, max_length=4)
    yolo_prelim_guess: str
    matched_anchor_class: str
    faiss_distance: float
    status: str
    reason: Optional[str] = None


class InventoryReport(BaseModel):
    verified_counts: Dict[str, int]
    verified_components: List[ComponentRecord]
    anomaly_queue: List[ComponentRecord]


class TaskAcceptedResponse(BaseModel):
    task_id: str
    state: ScanState
    message: str


class TriageItem(BaseModel):
    anomaly_index: int
    crop_url: str
    record: ComponentRecord


class TaskStatusResponse(BaseModel):
    task_id: str
    state: ScanState
    stage: str
    progress: int = Field(0, ge=0, le=100)
    error: Optional[str] = None
    image_url: Optional[str] = None
    report: Optional[InventoryReport] = None
    triage_queue: List[TriageItem] = Field(default_factory=list)


class ResolveDecision(str, Enum):
    approve = "APPROVE"
    reject = "REJECT"


class ResolveAnchorRequest(BaseModel):
    task_id: str
    anomaly_index: int = Field(..., ge=0)
    decision: ResolveDecision
    approved_class: Optional[str] = None


class ResolveAnchorResponse(BaseModel):
    task_id: str
    anomaly_index: int
    decision: ResolveDecision
    message: str


class CorrectionBox(BaseModel):
    bbox: List[int] = Field(..., min_length=4, max_length=4)
    label: Optional[str] = ""
    action: str  # "ADD" | "RELABEL" | "RELABEL_VERIFIED" | "DELETE_VERIFIED"
    anomaly_index: Optional[int] = None
    component_index: Optional[int] = None


class SubmitCorrectionRequest(BaseModel):
    task_id: str
    image_url: Optional[str] = None
    corrections: List[CorrectionBox]


class ReviewCorrectionRequest(BaseModel):
    action: str  # "APPROVE" or "REJECT"
    reviewer_note: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    role: str
    username: str
