"""SQLite persistence for analysis records.

Only metadata and summaries live in the database; the full trajectory payload
is written next to the annotated video as gzipped JSON.  That keeps the
database small enough to open in any SQLite browser during a demo.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    analysis_id      TEXT PRIMARY KEY,
    source           TEXT NOT NULL,
    filename         TEXT NOT NULL,
    upload_path      TEXT,
    status           TEXT NOT NULL,
    stage            TEXT NOT NULL,
    progress         REAL NOT NULL DEFAULT 0,
    created_at       REAL NOT NULL,
    updated_at       REAL NOT NULL,
    video_json       TEXT,
    summary_json     TEXT,
    error            TEXT,
    hint             TEXT
);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses (created_at DESC);
"""


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a row, decoding the JSON columns back into Python objects."""
    data = dict(row)
    for key in ("video_json", "summary_json"):
        raw = data.pop(key, None)
        data[key.removesuffix("_json")] = json.loads(raw) if raw else None
    return data


class Database:
    """Tiny thread-safe repository around a single SQLite file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    @contextlib.contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open one connection, yield it, and always close it.

        ``sqlite3.Connection.__exit__`` ends the transaction; it does not close
        the connection.  Handing a bare connection to ``with self._connect() as
        connection:`` therefore committed the write and leaked the handle, and
        the descriptor was only reclaimed when the cyclic collector ran.  The
        ``with connection:`` below keeps the commit-on-success / rollback-on-
        error behaviour, and the ``finally`` owns the handle.
        """
        connection = sqlite3.connect(self._path, timeout=15.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            with connection:
                yield connection
        finally:
            connection.close()

    # -- writes ------------------------------------------------------------

    def create(
        self,
        analysis_id: str,
        source: str,
        filename: str,
        upload_path: str | None,
        stage: str = "queued",
    ) -> None:
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO analyses (analysis_id, source, filename, upload_path, status,"
                " stage, progress, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT (analysis_id) DO NOTHING",
                (analysis_id, source, filename, upload_path, "queued", stage, 0.0, now, now),
            )

    def update(self, analysis_id: str, **fields: Any) -> None:
        if not fields:
            return
        # ``video`` and ``summary`` are stored as JSON text columns.
        for field, column in (("video", "video_json"), ("summary", "summary_json")):
            if field in fields:
                value = fields.pop(field)
                fields[column] = json.dumps(value) if value is not None else None
        fields["updated_at"] = time.time()
        columns = ", ".join(f"{name} = ?" for name in fields)
        with self._lock, self._connect() as connection:
            connection.execute(
                f"UPDATE analyses SET {columns} WHERE analysis_id = ?",
                (*fields.values(), analysis_id),
            )

    def delete(self, analysis_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM analyses WHERE analysis_id = ?", (analysis_id,))

    # -- reads -------------------------------------------------------------

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def list_recent(self, limit: int = 25) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_dict(row) for row in rows]
