import sqlite3
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pcb_scans.db"

def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection

def init_db() -> None:
    with sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                task_id TEXT PRIMARY KEY,
                timestamp DATETIME,
                image_url TEXT,
                total_verified INTEGER,
                total_anomalies INTEGER
            );
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                status TEXT,
                predicted_class TEXT,
                faiss_distance REAL,
                bbox TEXT,
                FOREIGN KEY (task_id) REFERENCES scans (task_id)
            );
        """)

def save_scan_to_db(task_id: str, image_url: str, report: dict) -> None:
    """Invoked by the Celery Worker at the end of Stage 5."""
    with get_db_connection() as conn:
        verified_count = len(report.get("verified_components", []))
        anomaly_count = len(report.get("anomaly_queue", []))
        
        conn.execute(
            "INSERT INTO scans (task_id, timestamp, image_url, total_verified, total_anomalies) VALUES (?, ?, ?, ?, ?)",
            (task_id, datetime.now().isoformat(), image_url, verified_count, anomaly_count)
        )
        
        for comp in report.get("verified_components", []) + report.get("anomaly_queue", []):
            conn.execute(
                "INSERT INTO components (task_id, status, predicted_class, faiss_distance, bbox) VALUES (?, ?, ?, ?, ?)",
                (task_id, comp["status"], comp["matched_anchor_class"], comp["faiss_distance"], json.dumps(comp["bbox"]))
            )
        conn.commit()
        
def update_anomaly_status(task_id: str, anomaly_index: int, new_status: str, approved_class: str | None) -> None:
    """Updates the specific anomaly's status in the database after Human Review."""
    with get_db_connection() as conn:
        # Find the exact component ID by offsetting the anomalies
        cursor = conn.execute(
            "SELECT id FROM components WHERE task_id = ? AND status = 'ANOMALY' ORDER BY id ASC LIMIT 1 OFFSET ?",
            (task_id, anomaly_index)
        )
        row = cursor.fetchone()
        
        if row:
            comp_id = row["id"]
            # Update the component row
            if approved_class:
                conn.execute("UPDATE components SET status = ?, predicted_class = ? WHERE id = ?", (new_status, approved_class, comp_id))
            else:
                conn.execute("UPDATE components SET status = ? WHERE id = ?", (new_status, comp_id))
            
            # Update the aggregate counts in the master scans table
            if new_status == "VERIFIED":
                conn.execute(
                    "UPDATE scans SET total_verified = total_verified + 1, total_anomalies = total_anomalies - 1 WHERE task_id = ?", 
                    (task_id,)
                )
            
            conn.commit()