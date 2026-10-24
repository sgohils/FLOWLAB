"""PostgreSQL repository and immutable Blob references for hosted instances.

Construction is offline: Vercel imports modules while building. Run the schema
migration explicitly before serving traffic, never as an import side effect.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .database import _SCHEMA, Database

SCHEMA = _SCHEMA.replace("REAL", "DOUBLE PRECISION") + """
CREATE TABLE IF NOT EXISTS objects (
    object_key TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    size_bytes BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS object_versions (
    object_key TEXT NOT NULL,
    url TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    PRIMARY KEY (object_key, url)
);
CREATE TABLE IF NOT EXISTS upload_intents (
    analysis_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL,
    filename TEXT NOT NULL,
    object_key TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL
);
"""


class HostedStorageError(Exception):
    """An actionable storage failure safe to return without connection secrets."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.hint = hint


class _Connection:
    """Translate this repository's positional parameters to psycopg syntax."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def execute(self, sql: str, params: tuple = ()) -> Any:
        return self.connection.execute(sql.replace("?", "%s"), params)


class PostgresDatabase(Database):
    def __init__(self, url: str) -> None:
        self.url = url
        self._lock = threading.Lock()

    def connect(self, *, autocommit: bool = False) -> Any:
        import psycopg
        from psycopg.rows import dict_row

        if not self.url:
            raise HostedStorageError(
                "Saved analyses are unavailable because PostgreSQL is not configured.",
                "Set DATABASE_URL in the Vercel project, run the database migration, "
                "and redeploy. The bundled demo still works.",
            )
        try:
            return psycopg.connect(
                self.url, row_factory=dict_row, autocommit=autocommit,
                connect_timeout=10, prepare_threshold=None,
            )
        except (psycopg.OperationalError, psycopg.ProgrammingError) as exc:
            raise HostedStorageError(
                "The analysis database is unavailable.",
                "Check the PostgreSQL connection and DATABASE_URL in Vercel. "
                "The bundled demo still works.",
            ) from exc

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        import psycopg

        try:
            with self.connect() as connection:
                yield _Connection(connection)
        except psycopg.errors.UndefinedTable as exc:
            raise HostedStorageError(
                "The analysis database has not been initialized.",
                "Run python -m backend.scripts.migrate_hosted with DATABASE_URL set, "
                "then retry. The bundled demo still works.",
            ) from exc
        except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
            raise HostedStorageError(
                "The analysis database connection was interrupted.",
                "Retry shortly, or check the PostgreSQL connection in Vercel.",
            ) from exc

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.execute(SCHEMA)

    @contextmanager
    def job_lock(self, analysis_id: str) -> Iterator[bool]:
        # A transaction-scoped advisory lock works with pooled PostgreSQL URLs.
        # It is released on disconnect, including a killed worker. Progress is
        # written on separate short-lived connections and remains visible.
        key = int.from_bytes(hashlib.sha256(analysis_id.encode()).digest()[:8], "big", signed=True)
        with self.connect() as connection:
            locked = connection.execute(
                "SELECT pg_try_advisory_xact_lock(%s) AS locked", (key,)
            ).fetchone()["locked"]
            yield bool(locked)

    def put_object(self, key: str, url: str, size: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO object_versions VALUES (?,?,?) ON CONFLICT DO NOTHING",
                (key, url, size),
            )
            connection.execute(
                "INSERT INTO objects VALUES (?,?,?) ON CONFLICT (object_key) DO UPDATE"
                " SET url=EXCLUDED.url, size_bytes=EXCLUDED.size_bytes", (key, url, size),
            )

    def get_object(self, key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return connection.execute("SELECT * FROM objects WHERE object_key=?", (key,)).fetchone()

    def delete_object(self, key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM objects WHERE object_key=?", (key,))

    def object_versions(self, key: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM object_versions WHERE object_key=?", (key,)
            ).fetchall()

    def delete_version(self, key: str, url: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM object_versions WHERE object_key=? AND url=?", (key, url),
            )

    def create_intent(self, values: tuple) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO upload_intents VALUES (?,?,?,?,?,?)", values)

    def get_intent(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM upload_intents WHERE analysis_id=?", (analysis_id,)
            ).fetchone()

    def delete_intent(self, analysis_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM upload_intents WHERE analysis_id=?", (analysis_id,))

    def pending_count(self) -> int:
        with self._connect() as connection:
            return connection.execute(
                "SELECT count(*) AS n FROM analyses WHERE status IN ('queued','processing')"
            ).fetchone()["n"]
