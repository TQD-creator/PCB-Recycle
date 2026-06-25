from __future__ import annotations

import asyncio
import json

from celery import states
from redis.asyncio import Redis

from config import REDIS_URL
from celery_app import celery_app
from cv_pipeline import run_scan_pipeline


def _publish_sync(task_id: str, payload: dict) -> None:
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
        _publish_sync(self.request.id, {"state": "PROCESSING", "stage": "Queued", "progress": 1})
        report, triage_queue, image_url = run_scan_pipeline(task_id=self.request.id, image_path=image_path, progress_cb=progress)
        final_payload = {
            "state": "COMPLETED",
            "stage": "Completed",
            "progress": 100,
            "image_url": image_url,
            "report": report.model_dump(),
            "triage_queue": [item.model_dump() for item in triage_queue],
        }
        _publish_sync(self.request.id, final_payload)
        return final_payload
    except Exception as exc:
        failure_payload = {"state": "FAILED", "stage": "Failed", "progress": 100, "error": str(exc)}
        _publish_sync(self.request.id, failure_payload)
        self.update_state(state=states.FAILURE, meta={"stage": "Failed", "progress": 100, "error": str(exc)})
        raise
