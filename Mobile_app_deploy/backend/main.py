from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import router as api_router
from database import init_db
from ml_pipeline import load_models

BASE_DIR = Path(__file__).resolve().parent
CAPTURED_DIR = BASE_DIR / "captured_boards"
EXPORTS_DIR = BASE_DIR / "exports"


def create_app() -> FastAPI:
    app = FastAPI(title="PCB Mobile Inspection API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    CAPTURED_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")
    app.include_router(api_router, prefix="/api/v2")

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        load_models()

    return app


app = create_app()
