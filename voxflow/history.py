"""SQLite-backed transcription history."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class History:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                language TEXT,
                raw_text TEXT,
                final_text TEXT,
                duration_s REAL
            )"""
        )
        self._conn.commit()

    def add(
        self,
        raw_text: str,
        final_text: str,
        language: Optional[str] = None,
        duration_s: float = 0.0,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO entries (created_at, language, raw_text, final_text, duration_s) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                language,
                raw_text,
                final_text,
                float(duration_s),
            ),
        )
        self._conn.commit()
        return cur.lastrowid or 0

    def list(self, limit: int = 200, search: Optional[str] = None) -> list[dict]:
        if search:
            q = f"%{search}%"
            cur = self._conn.execute(
                "SELECT id, created_at, language, raw_text, final_text, duration_s "
                "FROM entries WHERE final_text LIKE ? OR raw_text LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (q, q, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT id, created_at, language, raw_text, final_text, duration_s "
                "FROM entries ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        cols = ["id", "created_at", "language", "raw_text", "final_text", "duration_s"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def delete(self, entry_id: int) -> None:
        self._conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM entries")
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass
