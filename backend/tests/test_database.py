"""Connection ownership in the storage layer.

``Database._connect()`` used to return a bare ``sqlite3.Connection`` that every
caller consumed as ``with self._connect() as connection:``.  That is SQLite's
*transaction* context manager: it commits or rolls back, and it never closes the
handle.  Every database access therefore leaked a connection, and the file
descriptor was only reclaimed when the cyclic collector ran - which is why the
suite could not run with ``filterwarnings = ["error"]`` for so long.

These tests pin the lifetime.  Every one of them fails against the old
implementation, and the ``ResourceWarning`` test is the one the rest of the
suite's warnings-as-errors gate depends on.
"""

from __future__ import annotations

import contextlib
import gc
import sqlite3
import threading
import warnings

import pytest

from backend.storage.database import Database


class _TrackedConnection(sqlite3.Connection):
    """A connection that counts its own ``close()`` calls."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        super().close()


@pytest.fixture()
def tracked(monkeypatch) -> list[_TrackedConnection]:
    """Every connection the storage layer opens, with ``close()`` counted."""
    opened: list[_TrackedConnection] = []
    real_connect = sqlite3.connect

    def recording_connect(*args, **kwargs) -> _TrackedConnection:
        connection = real_connect(*args, **kwargs, factory=_TrackedConnection)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", recording_connect)
    return opened


def _exercise(database: Database) -> None:
    """One call of every public operation, so every branch opens a connection."""
    database.create("case", source="video", filename="clip.mp4", upload_path=None)
    database.update("case", status="complete", progress=1.0)
    assert database.get("case") is not None
    assert database.list_recent(limit=5)
    database.delete("case")


def _unclosed(opened: list[_TrackedConnection]) -> list[_TrackedConnection]:
    return [connection for connection in opened if connection.close_calls == 0]


# ------------------------------------------------------------------- lifetime


def test_every_operation_closes_its_connection(tmp_path, tracked):
    """The whole public surface, including the schema script in ``__init__``."""
    database = Database(tmp_path / "flowlab.db")

    _exercise(database)

    assert len(tracked) >= 6, "the fixture did not see the connections it should"
    assert _unclosed(tracked) == [], f"{len(_unclosed(tracked))} connection(s) never closed"


def test_a_connection_is_unusable_once_its_block_exits(tmp_path, tracked):
    """``close()`` must actually run, not merely be called."""
    database = Database(tmp_path / "flowlab.db")
    database.create("case", source="video", filename="clip.mp4", upload_path=None)

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        tracked[-1].execute("SELECT 1")


def test_a_failing_statement_still_closes_the_connection(tmp_path, tracked):
    """The ``finally`` has to cover the error path, or a bad write leaks too."""
    database = Database(tmp_path / "flowlab.db")

    with pytest.raises(sqlite3.OperationalError):
        database.update("case", not_a_real_column=1)

    assert tracked[-1].close_calls == 1


def test_the_garbage_collector_is_not_needed_to_release_a_connection(tmp_path):
    """The leak this file exists for: ``ResourceWarning: unclosed database``."""
    database = Database(tmp_path / "flowlab.db")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _exercise(database)
        gc.collect()

    leaked = [
        str(warning.message)
        for warning in caught
        if issubclass(warning.category, ResourceWarning)
    ]
    assert leaked == [], f"unclosed resources: {leaked}"


# ------------------------------------------------------- behaviour we kept


def test_the_database_is_still_in_wal_mode(tmp_path):
    """The PRAGMA moved inside the try block; the journal mode must not change."""
    path = tmp_path / "flowlab.db"
    Database(path)

    with contextlib.closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_concurrent_writers_are_serialised_by_the_lock(tmp_path):
    """One connection per call is only safe because the lock still spans it."""
    database = Database(tmp_path / "flowlab.db")
    errors: list[BaseException] = []

    def write(index: int) -> None:
        try:
            for step in range(5):
                name = f"a{index}-{step}"
                database.create(name, source="video", filename="clip.mp4", upload_path=None)
                database.update(name, progress=float(step))
        except BaseException as exc:  # re-raised in the main thread
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30.0)
        assert not thread.is_alive(), "a writer thread deadlocked on the database lock"

    assert errors == []
    assert len(database.list_recent(limit=100)) == 20
