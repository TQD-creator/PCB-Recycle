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


def generate_excel(scan_id: str) -> str:
    """Export normalized results for a scan into a formatted Excel file."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as connection:
        scan_row = connection.execute(
            "SELECT scan_id, scan_mode FROM scans WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()
        rows = connection.execute(
            """
            SELECT
                scan_id,
                source_model,
                class_label,
                defect_status,
                defect_type,
                confidence_score,
                bounding_box_x,
                bounding_box_y,
                box_width,
                box_height
            FROM normalized_results
            WHERE scan_id = ?
            """,
            (scan_id,),
        ).fetchall()

    data = [dict(row) for row in rows]
    dataframe = pd.DataFrame(data)
    dataframe.rename(
        columns={
            "scan_id": "Scan_ID",
            "source_model": "Source_Model",
            "class_label": "Component_Class",
            "defect_status": "Defect_Status",
            "defect_type": "Defect_Type",
            "confidence_score": "Confidence",
            "bounding_box_x": "X_Center",
            "bounding_box_y": "Y_Center",
            "box_width": "Width",
            "box_height": "Height",
        },
        inplace=True,
    )

    column_order = [
        "Scan_ID",
        "Source_Model",
        "Component_Class",
        "Defect_Status",
        "Defect_Type",
        "Confidence",
        "X_Center",
        "Y_Center",
        "Width",
        "Height",
    ]

    for column in column_order:
        if column not in dataframe.columns:
            dataframe[column] = None

    if scan_row and scan_row["scan_mode"] == "YOLO_ONLY":
        dataframe["Defect_Status"] = "Not Inspected"

    dataframe = dataframe[column_order].fillna("N/A")

    export_path = EXPORTS_DIR / f"inventory_{scan_id}.xlsx"
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
