"""Shared API state: database, job manager and analysis persistence helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from contextlib import suppress
from functools import lru_cache
from pathlib import Path

from ..analytics.metrics import deserialise_analysis, serialise_analysis
from ..config import BACKEND_DIR, settings
from ..models.schemas import Analysis, Trajectory
from ..storage import (
    Database,
    analysis_dir,
    annotated_path,
    read_result,
    result_path,
    upload_path,
    write_result,
)
from .jobs import JobManager

logger = logging.getLogger(__name__)

#: Fixed id of the bundled demo dataset.
DEMO_ID = "demo"
DEMO_FILE = BACKEND_DIR / "demo" / "sample_analysis.json"
REAL_DEMO_ID = "real-demo"
REAL_DEMO_FILE = BACKEND_DIR / "demo" / "real_analysis.json"
BUNDLED_IDS = frozenset((DEMO_ID, REAL_DEMO_ID))

if settings.hosted:
    from ..storage.postgres import PostgresDatabase
    from .hosted_jobs import HostedJobs

    hosted_database = PostgresDatabase(settings.database_url)
    database: Database = hosted_database
    jobs: HostedJobs | JobManager = HostedJobs(hosted_database, settings)
else:
    database = Database(settings.database_path)
    jobs = JobManager(database, settings)


@lru_cache(maxsize=1)
def demo_analysis() -> Analysis | None:
    """Load the bundled demo dataset (synthetic, always labelled as such)."""
    if not DEMO_FILE.exists():
        logger.warning("Demo dataset missing at %s", DEMO_FILE)
        return None
    try:
        return Analysis.model_validate(json.loads(DEMO_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Demo dataset could not be parsed: %s", exc)
        return None


@lru_cache(maxsize=1)
def real_demo_analysis() -> Analysis | None:
    """Read real detector output bundled with the licensed public-road footage."""
    if not REAL_DEMO_FILE.exists():
        return None
    try:
        return Analysis.model_validate_json(REAL_DEMO_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Real video example could not be loaded: %s", exc)
        return None


def bundled_analysis(analysis_id: str) -> Analysis | None:
    if analysis_id == DEMO_ID:
        return demo_analysis()
    if analysis_id == REAL_DEMO_ID:
        return real_demo_analysis()
    return None


def save_analysis(
    analysis: Analysis, raw_tracks: Sequence[Trajectory] | None = None
) -> None:
    """Persist an analysis, keeping the raw tracks for later re-measurement.

    ``raw_tracks`` are the **full-resolution, unfiltered** trajectories, stored
    under ``RAW_TRACKS_KEY``.  They are the input a later region change must
    see again, otherwise "vehicles detected" would silently change when only
    the regions were redrawn.
    """
    payload = serialise_analysis(analysis, raw_tracks=raw_tracks)
    write_result(settings, analysis.analysis_id, payload)


def load_analysis(analysis_id: str) -> Analysis | None:
    """Serve the bundled demo without requiring any external storage."""
    if analysis_id in BUNDLED_IDS:
        return bundled_analysis(analysis_id)
    payload = read_result(settings, analysis_id)
    if payload:
        try:
            analysis, _ = deserialise_analysis(payload)
            return analysis
        except ValueError as exc:
            logger.warning("Stored analysis %s is invalid: %s", analysis_id, exc)
            return None
    return None


def register_demo() -> Analysis | None:
    """Make the demo dataset appear in the analysis list.

    The bundled file is the source of truth: the stored summary and video
    metadata are refreshed on every start, so regenerating the demo dataset
    cannot leave the list showing numbers from an older build.
    """
    analysis = demo_analysis()
    if analysis is None or settings.hosted:
        # The demo belongs to this build, not a PostgreSQL/Blob record. In
        # particular, missing credentials must never prevent API startup.
        return analysis
    record = database.get(DEMO_ID)
    if record is None:
        database.create(
            DEMO_ID,
            source="demo",
            filename=analysis.video.filename,
            upload_path=None,
            stage="results",
        )
    database.update(
        DEMO_ID,
        status="complete",
        stage="results",
        progress=1.0,
        video=analysis.video.model_dump(mode="json"),
        summary=analysis.summary.model_dump(mode="json"),
    )
    return analysis


def annotated_file(analysis_id: str) -> Path | None:
    if analysis_id == DEMO_ID:
        return None
    if settings.hosted:
        return _cloud_media(f"processed/{analysis_id}/annotated.mp4")
    path = annotated_path(settings, analysis_id)
    return path if path.exists() and path.stat().st_size > 1024 else None


def source_file(analysis_id: str) -> Path | None:
    if analysis_id == DEMO_ID:
        return None
    record = database.get(analysis_id)
    if not record or not record.get("upload_path"):
        return None
    if settings.hosted:
        return _cloud_media(record["upload_path"])
    path = Path(record["upload_path"])
    return path if path.exists() else None


def _cloud_media(key: str) -> Path | None:
    from uuid import uuid4

    from ..storage.cloud import download

    path = settings.data_dir / "downloads" / f"{uuid4().hex}.mp4"
    return path if download(settings, key, path) else None


def is_processing(analysis_id: str) -> bool:
    """True while a job for this analysis is alive in this process."""
    job = jobs.get(analysis_id)
    if job is not None:
        return job.status in {"queued", "processing"}
    record = database.get(analysis_id)
    if not record:
        return False
    return record.get("status") in {"queued", "processing"}


def delete_analysis(analysis_id: str) -> tuple[int, int]:
    """Remove the database row **and every file** that belongs to the analysis.

    Returns ``(files_removed, bytes_freed)``.  A delete that leaves the uploaded
    footage on disk would be a false promise, so the upload, the annotated
    video, the result payload and the per-analysis directory all go.
    """
    record = database.get(analysis_id)
    if settings.hosted:
        from ..storage.cloud import cloud_database, remove

        keys = [f"processed/{analysis_id}/{name}" for name in ("annotated.mp4", "result.json.gz")]
        if record and record.get("upload_path"):
            keys.append(record["upload_path"])
        deleted = [remove(settings, key) for key in keys]
        cloud_database(settings).delete_intent(analysis_id)
        database.delete(analysis_id)
        return sum(item[0] for item in deleted), sum(item[1] for item in deleted)
    files = 0
    freed = 0

    if record and record.get("upload_path"):
        removed, size = _remove(Path(record["upload_path"]))
        files += removed
        freed += size
    for path in (annotated_path(settings, analysis_id), result_path(settings, analysis_id)):
        removed, size = _remove(path)
        files += removed
        freed += size

    directory = analysis_dir(settings, analysis_id)
    if directory.is_dir():
        for child in sorted(directory.rglob("*"), reverse=True):
            if child.is_file():
                removed, size = _remove(child)
                files += removed
                freed += size
        # A stray file we could not remove is still reported via `files`.
        with suppress(OSError):
            directory.rmdir()

    database.delete(analysis_id)
    return files, freed


def _remove(path: Path) -> tuple[int, int]:
    """Delete one file if it exists; return ``(files_removed, bytes_freed)``."""
    try:
        if path.is_file():
            size = path.stat().st_size
            path.unlink()
            return 1, max(0, size)
    except OSError as exc:  # locked file, permission problem
        logger.warning("Could not remove %s: %s", path, exc)
    return 0, 0


def reconcile_orphans() -> int:
    """Fail analyses that were interrupted by a restart.

    Jobs live in memory, so after a restart any row still marked
    ``processing`` describes work that is no longer running.  Marking them as
    an error is what stops the UI from polling a dead job forever.
    """
    if settings.hosted:
        # Other instances and queue retries own these jobs; a new API process
        # must never mark another worker's running analysis as interrupted.
        return 0
    repaired = 0
    for record in database.list_recent(limit=500):
        if record.get("status") not in {"queued", "processing"}:
            continue
        database.update(
            record["analysis_id"],
            status="error",
            error="Processing was interrupted (the backend was restarted).",
            hint="Upload the clip again to re-run the analysis.",
        )
        repaired += 1
    if repaired:
        logger.info("Marked %s interrupted analysis record(s) as failed", repaired)
    return repaired


def resolve_upload(analysis_id: str, filename: str) -> Path:
    return upload_path(settings, analysis_id, filename)
