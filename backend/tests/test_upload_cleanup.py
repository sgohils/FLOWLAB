"""An upload that does not finish must leave nothing on disk.

The write is streamed, so any exit that is not a completed upload can leave a
half-written file in ``data/uploads`` with no database row behind it.  Such a
file is invisible to the UI and unreachable by ``delete_analysis``, which walks
the database - nothing ever reclaims it.  The size cap and the probe failure
each cleaned up after themselves; an ``OSError`` from a full disk, a
``ClientDisconnect`` mid-read and a cancelled request did not.
"""

from __future__ import annotations

import asyncio
import pathlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app

#: Two chunks plus a bit, so the second ``handle.write`` is reached and fails.
BIG = b"\0" * (1024 * 1024 + 4096)


def _uploads() -> list[str]:
    return sorted(path.name for path in settings.upload_dir.iterdir())


class _FailsOnWrite:
    """A file handle that accepts a write and then fails like a full volume."""

    def __init__(self, handle, allowed: int) -> None:
        self._handle = handle
        self._allowed = allowed
        self.writes = 0

    def write(self, data):
        if self.writes >= self._allowed:
            raise OSError(28, "No space left on device")
        self.writes += 1
        return self._handle.write(data)

    def close(self) -> None:
        self._handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
        return False


def test_a_full_disk_mid_write_leaves_no_upload_behind(tmp_path, monkeypatch):
    """An OSError out of ``handle.write`` used to leave a partial file forever."""
    real_open = pathlib.Path.open

    def only_uploads_fail(self, mode="r", *args, **kwargs):
        handle = real_open(self, mode, *args, **kwargs)
        return _FailsOnWrite(handle, 1) if "w" in mode else handle

    monkeypatch.setattr(pathlib.Path, "open", only_uploads_fail)
    source = tmp_path / "clip.mp4"
    source.write_bytes(BIG)

    before = _uploads()
    with TestClient(app, raise_server_exceptions=False) as client, source.open("rb") as handle:
        response = client.post("/api/uploads", files={"file": ("clip.mp4", handle, "video/mp4")})
    assert response.status_code == 500
    assert _uploads() == before, "a partial upload was left in data/uploads"


def test_a_client_that_disappears_mid_upload_leaves_no_upload_behind(monkeypatch):
    """``ClientDisconnect`` is an ordinary exception; the leak was not about its type."""
    from backend.api.routes_upload import upload_video

    class Disconnecting:
        """One chunk, then the browser goes away mid-stream."""

        filename = "clip.mp4"

        def __init__(self) -> None:
            self.reads = 0
            self.closed = False

        async def read(self, _size):
            self.reads += 1
            if self.reads == 1:
                return b"\0" * 1024
            raise ConnectionResetError("client disconnected")

        async def close(self) -> None:
            self.closed = True

    upload = Disconnecting()
    before = _uploads()
    with pytest.raises(ConnectionResetError):
        asyncio.run(upload_video(file=upload))
    assert upload.closed, "the request body must be closed either way"
    assert _uploads() == before


def test_a_cancelled_upload_leaves_no_upload_behind(monkeypatch):
    """Cancellation is a ``BaseException``: an ``except Exception`` would leak here."""
    from backend.api.routes_upload import upload_video

    class Cancelling:
        filename = "clip.mp4"

        def __init__(self) -> None:
            self.reads = 0

        async def read(self, _size):
            self.reads += 1
            if self.reads == 1:
                return b"\0" * 1024
            raise asyncio.CancelledError

        async def close(self) -> None:
            return None

    before = _uploads()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(upload_video(file=Cancelling()))
    assert _uploads() == before, "a cancelled upload was left in data/uploads"


def test_the_size_cap_still_refuses_and_still_cleans_up(tmp_path, monkeypatch):
    """Behaviour preserved by the refactor: 413, the same message, no file left."""
    monkeypatch.setattr(settings, "max_upload_bytes", 4096)
    source = tmp_path / "big.mp4"
    source.write_bytes(b"\0" * 8192)
    before = _uploads()
    with TestClient(app) as client, source.open("rb") as handle:
        response = client.post("/api/uploads", files={"file": ("big.mp4", handle, "video/mp4")})
    assert response.status_code == 413
    assert "larger than" in response.json()["message"]
    assert _uploads() == before


def test_a_successful_upload_still_lands_on_disk(tmp_video, monkeypatch):
    """The other direction: the cleanup must not delete a completed upload."""
    from backend.api import state

    monkeypatch.setattr(state.jobs, "submit", lambda *args, **kwargs: None)
    path = tmp_video("clip.mp4", seconds=3.0)
    with TestClient(app) as client, open(path, "rb") as handle:
        response = client.post("/api/uploads", files={"file": ("clip.mp4", handle, "video/mp4")})
    assert response.status_code == 202
    analysis_id = response.json()["analysis_id"]
    stored = Path(state.database.get(analysis_id)["upload_path"])
    try:
        assert stored.is_file()
        assert stored.stat().st_size > 0
    finally:
        state.database.delete(analysis_id)
        stored.unlink(missing_ok=True)
