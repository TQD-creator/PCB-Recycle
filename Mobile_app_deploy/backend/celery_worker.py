from __future__ import annotations
import asyncio
import json
from celery import states
from redis.asyncio import Redis

from config import REDIS_URL
from celery_app import celery_app
from cv_pipeline import run_scan_pipeline, PipelineRegistry
from database import init_db, save_scan_to_db

# ==========================================
# CRITICAL FIX: THE PRE-WARMER
# ==========================================
# Initialize DB and load the 30MB of AI models into the 16GB RAM immediately on boot.
# This ensures the first HTTP request is instantaneous.
init_db()
PipelineRegistry.get() 
# ==========================================

def _publish_sync(task_id: str, payload: dict) -> None:
    """Pushes JSON telemetry to the Redis WebSocket pipeline."""
    async def _publish() -> None:
        redis = Redis.from_url(REDIS_URL, decode_responses=True)
        try:
            await redis.publish(f"scan_status:{task_id}", json.dumps(payload))
        finally:
            await redis.aclose()
    asyncio.run(_publish())


@celery_app.task(bind=True, name="pcb.scan.execute", acks_late=True)
def execute_scan_task(self, image_path: str) -> dict:
    def progress(stage: str, pct: int) -> None:
        _publish_sync(self.request.id, {"state": "PROCESSING", "stage": stage, "progress": pct})
        self.update_state(state="PROGRESS", meta={"stage": stage, "progress": pct})

    try:
        _publish_sync(self.request.id, {"state": "PROCESSING", "stage": "Initializing Pipeline...", "progress": 5})
        
        # Execute Stages 1 -> 4
        report, triage_queue, image_url = run_scan_pipeline(
            task_id=self.request.id, 
            image_path=image_path, 
            progress_cb=progress
        )
        
        # Execute Stage 5: Save to SQLite
        progress("Writing to Database...", 95)
        report_dict = report.model_dump()
        save_scan_to_db(self.request.id, image_url, report_dict)
        
        # Broadcast Final Payload to WebSocket
        final_payload = {
            "state": "COMPLETED",
            "stage": "Completed",
            "progress": 100,
            "image_url": image_url,
            "report": report_dict,
            "triage_queue": [item.model_dump() for item in triage_queue],
        }
        _publish_sync(self.request.id, final_payload)
        return final_payload
        
    except Exception as exc:
        failure_payload = {"state": "FAILED", "stage": "Failed", "progress": 100, "error": str(exc)}
        _publish_sync(self.request.id, failure_payload)
        self.update_state(state=states.FAILURE, meta={"stage": "Failed", "progress": 100, "error": str(exc)})
        raise
    
@celery_app.task(bind=True, name="pcb.anchors.resolve")
def execute_resolve_anchor_task(self, task_id: str, anomaly_index: int, decision: str, approved_class: str | None) -> str:
    """Handles the Human-in-the-loop update from the API."""
    from cv_pipeline import resolve_anomaly
    from database import update_anomaly_status

    # 1. Update the AI Brain (FAISS RAM + Disk)
    message = resolve_anomaly(task_id, anomaly_index, decision, approved_class)

    # 2. Update the SQLite Database so the mobile app UI updates correctly
    if decision == "ACCEPT":
        update_anomaly_status(task_id, anomaly_index, "VERIFIED", approved_class)
    else:
        update_anomaly_status(task_id, anomaly_index, "REJECTED", None)

    return message