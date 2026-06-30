from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import redis.asyncio as aioredis

from api import router
from config import REDIS_URL, TRIAGE_CROPS_DIR, UPLOADS_DIR, ensure_runtime_dirs
from database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_dirs()
    init_db()
    yield


app = FastAPI(title="PCB Master AI Gateway", lifespan=lifespan)

app.include_router(router, prefix="/api/v2")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/triage-crops", StaticFiles(directory=str(TRIAGE_CROPS_DIR)), name="triage-crops")


@app.websocket("/api/v2/scan/ws/status/{task_id}")
async def scan_status_ws(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    redis = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"scan_status:{task_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            payload = json.loads(message["data"])
            await websocket.send_json(payload)
            if payload.get("state") in ("COMPLETED", "FAILED"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"scan_status:{task_id}")
        await pubsub.aclose()
        await redis.aclose()
