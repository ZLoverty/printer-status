"""Persistent printer state and utilization accounting."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


BUSY_STATES = {"RUNNING", "PAUSED", "BUSY"}
IDLE_STATES = {"IDLE", "FINISHED"}


class StateStore:
    def __init__(self, path: str, max_gap_seconds: float = 180):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_gap_seconds = max_gap_seconds
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS printer_state (
                printer_key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                is_busy INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                busy_seconds REAL NOT NULL DEFAULT 0,
                idle_seconds REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS state_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                printer_key TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                status TEXT NOT NULL,
                is_busy INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_state_samples_printer_time
                ON state_samples(printer_key, observed_at);
            """
        )
        self.db.commit()

    def record(self, printer_key: str, status: str) -> dict[str, float | str]:
        now = datetime.now(timezone.utc)
        is_busy = status in BUSY_STATES
        is_countable = is_busy or status in IDLE_STATES
        previous = self.db.execute(
            "SELECT * FROM printer_state WHERE printer_key = ?", (printer_key,)
        ).fetchone()
        busy_seconds = float(previous["busy_seconds"]) if previous else 0.0
        idle_seconds = float(previous["idle_seconds"]) if previous else 0.0
        if previous:
            previous_time = datetime.fromisoformat(previous["last_seen_at"])
            elapsed = (now - previous_time).total_seconds()
            if is_countable and 0 <= elapsed <= self.max_gap_seconds:
                if previous["status"] in BUSY_STATES:
                    busy_seconds += elapsed
                elif previous["status"] in IDLE_STATES:
                    idle_seconds += elapsed

        started_at = previous["started_at"] if previous else now.isoformat()
        self.db.execute(
            "INSERT INTO state_samples(printer_key, observed_at, status, is_busy) VALUES (?, ?, ?, ?)",
            (printer_key, now.isoformat(), status, int(is_busy) if is_countable else None),
        )
        self.db.execute(
            """INSERT INTO printer_state
               (printer_key, status, is_busy, started_at, last_seen_at, busy_seconds, idle_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(printer_key) DO UPDATE SET
                 status=excluded.status, is_busy=excluded.is_busy,
                 last_seen_at=excluded.last_seen_at,
                 busy_seconds=excluded.busy_seconds, idle_seconds=excluded.idle_seconds""",
            (printer_key, status, int(is_busy), started_at, now.isoformat(), busy_seconds, idle_seconds),
        )
        self.db.commit()
        observed = busy_seconds + idle_seconds
        return {
            "utilization": round(busy_seconds / observed * 100, 2) if observed else 0.0,
            "busy_seconds": round(busy_seconds, 1),
            "observed_seconds": round(observed, 1),
            "last_seen": now.isoformat(timespec="seconds"),
        }

    def close(self):
        self.db.close()
