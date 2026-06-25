import os
import uuid
import asyncio
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
import redis.asyncio as redis

# We will build the actual Celery worker in Task 2, we import the task signature here
# from worker import process_pcb_scan 

app = FastAPI(title="PCB Master AI Gateway")

# Connection to the Redis Broker
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

# Shared Docker Volume path where the image gets dropped for the AI Worker
UPLOAD_DIR = "/shared_volume/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/scan")
async def create_scan_job(file: UploadFile = File(...)):
    """
    Step 1: The Heavy Lifting. 
    Receives the high-res image via HTTP, saves it, and queues the Celery job.
    """
    job_id = str(uuid.uuid4())
    file_location = f"{UPLOAD_DIR}/{job_id}.jpg"
    
    # Save the file to the shared volume
    with open(file_location, "wb+") as file_object:
        file_object.write(await file.read())
        
    # Send the job to the Celery AI Worker (We will build this in Task 2)
    # task = process_pcb_scan.apply_async(args=[job_id, file_location], task_id=job_id)
    
    # Return instantly to unblock the mobile UI
    return JSONResponse(status_code=202, content={
        "status": "ACCEPTED",
        "job_id": job_id,
        "message": "Image secured. Connect to WebSocket for real-time telemetry."
    })

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    Step 2: Real-Time Telemetry.
    Expo Go connects here to watch the AI worker in real-time.
    """
    await websocket.accept()
    
    try:
        # We poll Redis for updates from the Celery Worker
        while True:
            # In Task 2, Celery will update this Redis key with its current stage
            job_status = await redis_client.hgetall(f"job:{job_id}")
            
            if not job_status:
                await websocket.send_json({"status": "QUEUED", "message": "Waiting for AI Worker allocation..."})
            else:
                # Send the exact state of the pipeline to the phone
                await websocket.send_json(job_status)
                
                # If the AI worker finishes or crashes, close the socket gracefully
                if job_status.get("state") in ["COMPLETED", "FAILED"]:
                    await websocket.close()
                    break
            
            # Polling rate: 4 updates per second (perfect for smooth UI progress bars)
            await asyncio.sleep(0.25)
            
    except WebSocketDisconnect:
        print(f"[-] Client disconnected from job {job_id}")
    except Exception as e:
        print(f"[-] Socket Error: {e}")
        await websocket.close()