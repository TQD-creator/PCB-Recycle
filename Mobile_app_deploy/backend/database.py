import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pcb_scans.db"


def get_db_connection() -> sqlite3.Connection:
    """Create a SQLite connection with safe defaults for concurrent API usage."""
    connection = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Initialize the normalized schema used by parallel AI pipelines."""
    with sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS scans (
                scan_id TEXT PRIMARY KEY,
                timestamp DATETIME,
                image_path TEXT,
                scan_mode TEXT
            );

            CREATE TABLE IF NOT EXISTS normalized_results (
                result_id TEXT PRIMARY KEY,
                scan_id TEXT,
                source_model TEXT,
                class_label TEXT,
                bounding_box_x REAL,
                bounding_box_y REAL,
                box_width REAL,
                box_height REAL,
                confidence_score REAL,
                defect_status TEXT,
                defect_type TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans (scan_id)
            );
            """
        )
