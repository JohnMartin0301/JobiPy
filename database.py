"""
database.py — SQLite persistence layer.

Handles:
  • Schema creation
  • Duplicate detection via hash_id
  • Inserting new job records
"""

import sqlite3
import logging
from pathlib import Path
from config import DB_PATH

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hash_id     TEXT    UNIQUE NOT NULL,
    job_title   TEXT    NOT NULL,
    company     TEXT,
    location    TEXT,
    skills      TEXT,
    source      TEXT,
    job_url     TEXT,
    posted_date TEXT,
    posted_days INTEGER,
    score       INTEGER DEFAULT 0,
    notified_at TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_hash ON jobs(hash_id);
CREATE INDEX IF NOT EXISTS idx_created ON jobs(created_at);
"""


def get_connection() -> sqlite3.Connection:
    """Return a connection with row_factory set for dict-like access."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    with get_connection() as conn:
        conn.executescript(_DDL)
    logger.info("Database initialised at %s", DB_PATH)


def is_duplicate(hash_id: str) -> bool:
    """Return True if this hash_id already exists in the DB."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE hash_id = ?", (hash_id,)
        ).fetchone()
    return row is not None


def insert_job(job: dict) -> None:
    """
    Insert a new job record.
    Silently ignores duplicates (UNIQUE constraint on hash_id).
    """
    sql = """
        INSERT OR IGNORE INTO jobs
            (hash_id, job_title, company, location, skills,
             source, job_url, posted_date, posted_days, score)
        VALUES
            (:hash_id, :job_title, :company, :location, :skills,
             :source, :job_url, :posted_date, :posted_days, :score)
    """
    with get_connection() as conn:
        conn.execute(sql, job)
    logger.debug("Inserted job: %s @ %s", job.get("job_title"), job.get("company"))


def mark_notified(hash_id: str) -> None:
    """Stamp the notification timestamp on a job row."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET notified_at = datetime('now') WHERE hash_id = ?",
            (hash_id,),
        )


def recent_jobs(days: int = 30) -> list[dict]:
    """Fetch jobs inserted within the last N days (for reporting)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM jobs
            WHERE created_at >= datetime('now', ? || ' days')
            ORDER BY score DESC, created_at DESC
            """,
            (f"-{days}",),
        ).fetchall()
    return [dict(r) for r in rows]