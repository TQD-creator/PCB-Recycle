import os
import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import HTTPException, UploadFile
from openpyxl.utils import get_column_letter

from database import get_db_connection

BASE_DIR = Path(__file__).resolve().parent
CAPTURED_DIR = BASE_DIR / "captured_boards"
EXPORTS_DIR = BASE_DIR / "exports"


def save_uploaded_file(upload_file: UploadFile) -> str:
    CAPTURED_DIR.mkdir(parents=True, exist_ok=True)

    suffix = Path(upload_file.filename or "board.jpg").suffix or ".jpg"
    file_name = f"board_{uuid4().hex}{suffix}"
    destination = CAPTURED_DIR / file_name

    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {exc}") from exc

    return str(destination.resolve())


def generate_excel(task_id: str) -> str:
    """Export scan results into a formatted Excel file."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT task_id, status, predicted_class, faiss_distance, bbox FROM components WHERE task_id = ?",
            (task_id,),
        ).fetchall()

    data = [dict(row) for row in rows]
    dataframe = pd.DataFrame(data) if data else pd.DataFrame(
        columns=["task_id", "status", "predicted_class", "faiss_distance", "bbox"]
    )
    dataframe.rename(
        columns={
            "task_id": "Task_ID",
            "status": "Status",
            "predicted_class": "Component_Class",
            "faiss_distance": "FAISS_Distance",
            "bbox": "Bounding_Box",
        },
        inplace=True,
    )

    column_order = ["Task_ID", "Status", "Component_Class", "FAISS_Distance", "Bounding_Box"]
    dataframe = dataframe[column_order].fillna("N/A")

    export_path = EXPORTS_DIR / f"inventory_{task_id}.xlsx"
    with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Results")
        worksheet = writer.sheets["Results"]
        for idx, column in enumerate(dataframe.columns, start=1):
            max_length = max(len(str(value)) for value in [column] + dataframe[column].tolist())
            worksheet.column_dimensions[get_column_letter(idx)].width = max(12, min(max_length + 2, 40))

    return str(export_path.resolve())


def cleanup_failed_scan(image_path: str) -> None:
    if not image_path:
        return

    try:
        if os.path.exists(image_path):
            os.remove(image_path)
    except OSError:
        pass
