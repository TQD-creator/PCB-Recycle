from __future__ import annotations

from celery import Celery

from config import REDIS_URL, RESULT_BACKEND_URL


celery_app = Celery("pcb_scan_tasks", broker=REDIS_URL, backend=RESULT_BACKEND_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
