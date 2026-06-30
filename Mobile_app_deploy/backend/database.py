import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH  = BASE_DIR / "pcb_scans.db"

SESSION_TTL_HOURS = 24  # sessions expire after 24 hours


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password: str, hashed: str) -> bool:
    return _hash_password(password) == hashed


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()


# ── Schema migration (safe for existing databases) ────────────────────────────

def _migrate_db(conn: sqlite3.Connection) -> None:
    """
    Adds new columns to existing databases without destroying data.
    SQLite supports ALTER TABLE ... ADD COLUMN but NOT dropping/renaming columns,
    so we check PRAGMA table_info and skip columns that already exist.
    """
    def _has_column(table: str, column: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(row["name"] == column for row in rows)

    migrations = [
        # (table, column, alter_sql)
        ("scans",           "user_id",      "ALTER TABLE scans ADD COLUMN user_id INTEGER REFERENCES users(id)"),
        ("modify_approved", "submitted_by", "ALTER TABLE modify_approved ADD COLUMN submitted_by INTEGER REFERENCES users(id)"),
        ("sessions",        "expires_at",   "ALTER TABLE sessions ADD COLUMN expires_at DATETIME"),
    ]

    for table, column, sql in migrations:
        if not _has_column(table, column):
            conn.execute(sql)

    # Existing sessions have no expires_at — give them a 1-hour grace window then force re-login
    conn.execute(
        "UPDATE sessions SET expires_at = datetime('now', '+1 hour') WHERE expires_at IS NULL"
    )
    conn.commit()


# ── Database initialisation ───────────────────────────────────────────────────

def init_db() -> None:
    with sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                task_id          TEXT PRIMARY KEY,
                timestamp        DATETIME,
                image_url        TEXT,
                total_verified   INTEGER,
                total_anomalies  INTEGER,
                user_id          INTEGER REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS components (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id          TEXT,
                status           TEXT,
                predicted_class  TEXT,
                faiss_distance   REAL,
                bbox             TEXT,
                FOREIGN KEY (task_id) REFERENCES scans (task_id)
            );
            CREATE TABLE IF NOT EXISTS modify_approved (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id          TEXT NOT NULL,
                image_url        TEXT,
                corrections      TEXT NOT NULL,
                submitted_at     DATETIME NOT NULL,
                status           TEXT DEFAULT 'PENDING',
                reviewed_at      DATETIME,
                reviewer_note    TEXT,
                submitted_by     INTEGER REFERENCES users(id),
                FOREIGN KEY (task_id) REFERENCES scans (task_id)
            );
            CREATE TABLE IF NOT EXISTS users (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                username         TEXT UNIQUE NOT NULL,
                password_hash    TEXT NOT NULL,
                role             TEXT NOT NULL DEFAULT 'user',
                created_at       DATETIME NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token            TEXT PRIMARY KEY,
                user_id          INTEGER NOT NULL,
                role             TEXT NOT NULL,
                username         TEXT NOT NULL,
                created_at       DATETIME NOT NULL,
                expires_at       DATETIME NOT NULL
            );
        """)

        # Seed default accounts once
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing == 0:
            now = _now_utc()
            conn.executemany(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                [
                    ("admin", _hash_password("admin123"), "admin", now),
                    ("user",  _hash_password("user123"),  "user",  now),
                ],
            )
            conn.commit()

        # Safe migration for existing databases (adds new columns if absent)
        _migrate_db(conn)


# ── Scan helpers ──────────────────────────────────────────────────────────────

def save_scan_to_db(task_id: str, image_url: str, report: dict, user_id: int | None = None) -> None:
    with get_db_connection() as conn:
        verified_count = len(report.get("verified_components", []))
        anomaly_count  = len(report.get("anomaly_queue", []))
        conn.execute(
            "INSERT INTO scans (task_id, timestamp, image_url, total_verified, total_anomalies, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, _now_utc(), image_url, verified_count, anomaly_count, user_id),
        )
        for comp in report.get("verified_components", []) + report.get("anomaly_queue", []):
            conn.execute(
                "INSERT INTO components (task_id, status, predicted_class, faiss_distance, bbox) "
                "VALUES (?, ?, ?, ?, ?)",
                (task_id, comp["status"], comp["matched_anchor_class"], comp["faiss_distance"], json.dumps(comp["bbox"])),
            )
        conn.commit()


def update_anomaly_status(task_id: str, anomaly_index: int, new_status: str, approved_class: str | None) -> None:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id FROM components WHERE task_id = ? AND status = 'ANOMALY' ORDER BY id ASC LIMIT 1 OFFSET ?",
            (task_id, anomaly_index),
        )
        row = cursor.fetchone()
        if row:
            comp_id = row["id"]
            if approved_class:
                conn.execute(
                    "UPDATE components SET status = ?, predicted_class = ? WHERE id = ?",
                    (new_status, approved_class, comp_id),
                )
            else:
                conn.execute("UPDATE components SET status = ? WHERE id = ?", (new_status, comp_id))
            if new_status == "VERIFIED":
                conn.execute(
                    "UPDATE scans SET total_verified = total_verified + 1, total_anomalies = total_anomalies - 1 "
                    "WHERE task_id = ?",
                    (task_id,),
                )
            conn.commit()


# ── Corrections ───────────────────────────────────────────────────────────────

def submit_correction(task_id: str, image_url: str, corrections: list, submitted_by: int | None = None) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO modify_approved (task_id, image_url, corrections, submitted_at, status, submitted_by) "
            "VALUES (?, ?, ?, ?, 'PENDING', ?)",
            (task_id, image_url, json.dumps(corrections), _now_utc(), submitted_by),
        )
        conn.commit()
        return cursor.lastrowid


def get_all_corrections() -> list:
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT
                m.id, m.task_id, m.image_url, m.corrections,
                m.submitted_at, m.status, m.reviewed_at, m.reviewer_note,
                m.submitted_by,
                u.username AS submitted_by_username
            FROM modify_approved m
            LEFT JOIN users u ON m.submitted_by = u.id
            ORDER BY m.submitted_at DESC
        """).fetchall()
        result = []
        for row in rows:
            r = dict(row)
            r["corrections"] = json.loads(r["corrections"])
            result.append(r)
        return result


def review_correction(correction_id: int, action: str, reviewer_note: str | None) -> bool:
    with get_db_connection() as conn:
        result = conn.execute(
            "UPDATE modify_approved SET status = ?, reviewed_at = ?, reviewer_note = ? WHERE id = ?",
            (action, _now_utc(), reviewer_note, correction_id),
        )
        conn.commit()
        return result.rowcount > 0


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_user(username: str, password: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not row or not _verify_password(password, row["password_hash"]):
            return None
        token = secrets.token_hex(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id, role, username, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (token, row["id"], row["role"], row["username"], _now_utc(), _expires_at()),
        )
        conn.commit()
        return {"token": token, "role": row["role"], "username": row["username"]}


def logout_user(token: str) -> bool:
    with get_db_connection() as conn:
        result = conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return result.rowcount > 0


def get_session(token: str) -> dict | None:
    """Returns session dict if token is valid and not expired; None otherwise."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT token, user_id, role, username, expires_at "
            "FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            return None
        # Enforce expiry (expires_at is an ISO-8601 string)
        expires_at = row["expires_at"]
        if expires_at:
            try:
                # Strip timezone info for comparison if present
                exp_str = expires_at.replace("Z", "+00:00")
                exp_dt = datetime.fromisoformat(exp_str)
                # Make both offset-aware for comparison
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > exp_dt:
                    # Expired — clean it up
                    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                    conn.commit()
                    return None
            except ValueError:
                # Unparseable date — treat as expired
                return None
        return dict(row)
