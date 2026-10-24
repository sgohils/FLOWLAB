"""A failed analysis must end in ``error``, not sit at ``processing`` forever.

``JobManager._fail`` used to call ``_activate_stage(..., status="error")`` while
the helper's keyword is ``status_value`` - and ``status`` is already its first
positional parameter.  Python raised ``TypeError: got multiple values for
argument 'status'`` *inside* the failure path, before the ``database.update()``
on the next line.  The row therefore stayed ``processing`` in SQLite, the
``results`` stage kept whatever status the last advance gave it, and the user
saw a job that never finished.  Only the next restart repaired it, when
``reconcile_orphans()`` swept the orphan.

Every ``except`` branch in ``_run`` reaches ``_fail``, so each one is exercised
here against the real worker thread.  The wait is a poll with a deadline: an
unbounded sleep would turn a regression into a hung suite rather than a failure.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

from backend.api import jobs as jobs_module
from backend.api.jobs import ERROR_HINTS, JobManager
from backend.config import build_settings, ensure_directories
from backend.models.schemas import JobStatus, VideoInfo
from backend.storage import Database
from backend.vision.detector import DetectorError
from backend.vision.video_processor import VideoProcessingError

ANALYSIS_ID = "boom"

#: Long enough for a loaded CI runner, short enough that a regression fails the
#: suite instead of stalling it.
DEADLINE_S = 10.0


def _video() -> VideoInfo:
    return VideoInfo(
        filename="clip.mp4",
        duration=10.0,
        fps=10.0,
        width=640,
        height=360,
        size_bytes=4096,
        processed_fps=10.0,
        frame_count=100,
    )


def _wait_until(predicate: Callable[[], object], timeout: float = DEADLINE_S) -> object:
    """Poll ``predicate`` until it is truthy or ``timeout`` seconds have passed.

    Returns the last value seen, so a caller that asserts on it reports the real
    state of the job rather than just "timed out".
    """
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value or time.monotonic() >= deadline:
            return value
        time.sleep(0.01)


def _is_failed(status: JobStatus | None) -> bool:
    return status is not None and status.status == "error"


@pytest.fixture()
def job_manager(tmp_path, monkeypatch):
    """A JobManager with a real database, and an executor that is shut down."""
    settings = build_settings()
    settings.data_dir = tmp_path
    settings.upload_dir = tmp_path / "uploads"
    settings.processed_dir = tmp_path / "processed"
    settings.database_path = tmp_path / "flowlab.db"
    ensure_directories(settings)

    database = Database(settings.database_path)
    database.create(ANALYSIS_ID, source="video", filename="clip.mp4", upload_path=None)
    manager = JobManager(database, settings)
    try:
        yield manager, database, settings, monkeypatch
    finally:
        manager.shutdown()


def _run_and_fail(
    manager, database, monkeypatch, source, failure: BaseException
) -> JobStatus | None:
    """Submit a job whose pipeline raises ``failure``, and wait for the verdict."""

    def explode(*args, **kwargs):
        raise failure

    monkeypatch.setattr(jobs_module, "process_video", explode)
    manager.register(ANALYSIS_ID, _video())
    manager.submit(ANALYSIS_ID, source)
    _wait_until(lambda: _is_failed(manager.get(ANALYSIS_ID)))
    # The database write happens after the in-memory update, so give the worker
    # the moment it needs before reading the row back.
    _wait_until(lambda: database.get(ANALYSIS_ID)["status"] == "error")
    return manager.get(ANALYSIS_ID)


@pytest.mark.parametrize(
    ("failure", "hint_key"),
    [
        pytest.param(
            VideoProcessingError("unsupported codec in the container"), "video", id="video"
        ),
        pytest.param(DetectorError("yolo11n.pt could not be loaded"), "detector", id="detector"),
    ],
)
def test_a_failed_pipeline_is_persisted_as_an_error(job_manager, tmp_path, failure, hint_key):
    manager, database, _settings, monkeypatch = job_manager

    status = _run_and_fail(manager, database, monkeypatch, tmp_path / "clip.mp4", failure)

    assert status is not None
    assert status.status == "error", f"job stuck at {status.status}"
    assert status.stage == "results"
    assert status.error == str(failure)
    assert status.hint == ERROR_HINTS[hint_key]

    # The stage list is what the UI renders, and a stage left "active" next to
    # a failed job is the shape of the original bug.
    assert [stage.key for stage in status.stages if stage.status == "active"] == []
    results = next(stage for stage in status.stages if stage.key == "results")
    assert results.status == "error"
    assert results.detail == str(failure)

    record = database.get(ANALYSIS_ID)
    assert record["status"] == "error", "the row must be error, not processing"
    assert record["error"] == str(failure)
    assert record["hint"] == ERROR_HINTS[hint_key]
    assert manager.pending_count() == 0


def test_an_unexpected_exception_also_fails_the_job(job_manager, tmp_path):
    """The catch-all branch is where a typo like `status=` used to hide."""
    manager, database, _settings, monkeypatch = job_manager

    status = _run_and_fail(
        manager, database, monkeypatch, tmp_path / "clip.mp4", RuntimeError("boom")
    )

    assert status is not None
    assert status.status == "error"
    assert status.error == "Processing failed unexpectedly."
    assert "RuntimeError" in status.hint
    assert database.get(ANALYSIS_ID)["status"] == "error"


def test_a_failed_job_does_not_stop_the_next_one(job_manager, tmp_path):
    """The executor must still take work after a failure."""
    manager, database, _settings, monkeypatch = job_manager
    _run_and_fail(
        manager, database, monkeypatch, tmp_path / "clip.mp4", VideoProcessingError("bad clip")
    )

    database.create("second", source="video", filename="clip.mp4", upload_path=None)
    manager.register("second", _video())
    monkeypatch.setattr(jobs_module, "process_video", lambda *args, **kwargs: None)
    manager.submit("second", tmp_path / "clip.mp4")

    # The stub returns None, so the worker dies in the generic handler - which is
    # the point: it must fail that job and leave the manager usable.
    assert _wait_until(lambda: _is_failed(manager.get("second")))
    assert manager.get("second").status == "error"
