"""Background job orchestration for the processing pipeline.

The pipeline runs in a worker thread so the HTTP API stays responsive and the
UI can poll progress.  Progress is reported in the nine stages the product
specifies, and every stage maps onto a slice of the overall 0-1 progress bar.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..analytics.metrics import build_analysis, serialise_analysis
from ..analytics.suggestions import suggest_regions
from ..config import Settings
from ..config import settings as default_settings
from ..models.schemas import (
    JobStatus,
    Regions,
    StageStatus,
    VideoInfo,
)
from ..storage import Database, annotated_path, write_result
from ..vision.detector import DetectorError, detector
from ..vision.video_processor import VideoProcessingError, process_video

logger = logging.getLogger(__name__)

#: The four states a processing stage can be in (mirrors ``StageStatus.status``).
StageStatusValue = Literal["pending", "active", "done", "error"]

#: (key, label, start, end) - the slice of the progress bar owned by a stage.
STAGE_DEFINITIONS: tuple[tuple[str, str, float, float], ...] = (
    ("queued", "Queued", 0.0, 0.0),
    ("reading_video", "Reading video", 0.0, 0.08),
    ("detecting", "Detecting vehicles", 0.08, 0.85),
    ("tracking", "Tracking vehicles", 0.85, 0.90),
    ("trajectories", "Calculating trajectories", 0.90, 0.92),
    ("queues", "Analyzing queues", 0.92, 0.95),
    ("bottlenecks", "Finding bottlenecks", 0.95, 0.97),
    ("results", "Generating results", 0.97, 1.0),
)

STAGE_LABELS = {key: label for key, label, _, _ in STAGE_DEFINITIONS}
STAGE_RANGES = {key: (start, end) for key, _, start, end in STAGE_DEFINITIONS}

#: Friendly guidance attached to each failure mode.
ERROR_HINTS: dict[str, str] = {
    "detector": (
        "The detection model could not be loaded. Check your internet connection the "
        "first time it runs, or set FLOWLAB_MODEL to a local yolo*.pt file."
    ),
    "video": (
        "The video file may be damaged or use an unsupported codec. "
        "Try re-exporting it as H.264 MP4."
    ),
    "empty": (
        "No vehicles were detected. Try footage with a fixed camera, better lighting, "
        "a visible roadway, and vehicles occupying a larger part of the frame."
    ),
    "generic": "Processing failed unexpectedly. Check the backend log for details.",
}


@dataclass(slots=True)
class _Job:
    status: JobStatus
    lock: threading.Lock = field(default_factory=threading.Lock)


class JobManager:
    """Owns the in-memory job table and the single processing worker."""

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        self._db = database
        self._settings = settings or default_settings
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()
        self._last_written = 0.0
        self._deadline: float | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=self._settings.max_concurrent_jobs, thread_name_prefix="flowlab"
        )

    # -- public API --------------------------------------------------------

    def register(self, analysis_id: str, video: VideoInfo) -> JobStatus:
        job = _Job(status=_initial_status(analysis_id, video))
        with self._lock:
            self._jobs[analysis_id] = job
        self._db.update(analysis_id, status="processing", stage="reading_video", progress=0.0)
        return job.status

    def submit(
        self,
        analysis_id: str,
        source_path: Path,
        regions: Regions | None = None,
    ) -> None:
        self._executor.submit(self._run, analysis_id, source_path, regions or Regions())

    def get(self, analysis_id: str) -> JobStatus | None:
        with self._lock:
            job = self._jobs.get(analysis_id)
        if job is None:
            return None
        with job.lock:
            return job.status.model_copy(deep=True)

    def pending_count(self) -> int:
        """How many analyses are running or waiting for the worker."""
        with self._lock:
            jobs = list(self._jobs.values())
        count = 0
        for job in jobs:
            with job.lock:
                if job.status.status in {"queued", "processing"}:
                    count += 1
        return count

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # -- worker ------------------------------------------------------------

    def _run(
        self, analysis_id: str, source_path: Path, regions: Regions, *, retry_errors: bool = False
    ) -> None:
        started = time.time()
        self._deadline = time.monotonic() + 240 if self._settings.hosted else None
        try:
            self._advance(analysis_id, "reading_video", 0.0, "Opening the video")
            result = process_video(
                source_path,
                output_path=annotated_path(self._settings, analysis_id),
                progress=lambda key, fraction, message: self._advance(
                    analysis_id, key, fraction, message
                ),
                detector=detector,
                settings=self._settings,
                sample_fps=regions.sample_fps,
            )
            self._advance(analysis_id, "tracking", 0.9, f"{len(result.tracks)} trajectories built")

            effective_regions = regions
            if not regions.has_queue or not regions.exit:
                suggested = suggest_regions(result.tracks, result.video, self._settings)
                effective_regions = _merge_regions(regions, suggested)

            self._advance(analysis_id, "trajectories", 0.0, "Measuring vehicle movement")
            analysis = build_analysis(
                analysis_id=analysis_id,
                video=result.video,
                tracks=result.tracks,
                regions=effective_regions,
                source="video",
            )
            self._advance(analysis_id, "queues", 0.0, "Queue and wait time statistics")
            self._advance(analysis_id, "bottlenecks", 0.0, "Bottleneck grid")
            self._advance(analysis_id, "results", 0.5, "Serialising results")

            write_result(
                self._settings,
                analysis_id,
                serialise_analysis(analysis, raw_tracks=result.tracks),
            )
            if self._settings.hosted and result.annotated_path:
                from ..storage.cloud import publish

                publish(self._settings, result.annotated_path)
            self._db.update(
                analysis_id,
                status="complete",
                stage="results",
                progress=1.0,
                video=result.video.model_dump(mode="json"),
                summary=analysis.summary.model_dump(mode="json"),
                error=None,
                hint=None,
            )
            self._finish(analysis_id, 1.0, "Complete")
            logger.info("Analysis %s finished in %.1fs", analysis_id, time.time() - started)
        except DetectorError as exc:
            self._fail(analysis_id, str(exc), ERROR_HINTS["detector"])
        except VideoProcessingError as exc:
            self._fail(analysis_id, str(exc), ERROR_HINTS["video"])
        except Exception as exc:  # pragma: no cover - defensive
            if retry_errors:
                raise
            logger.exception("Analysis %s failed", analysis_id)
            self._fail(
                analysis_id,
                "Processing failed unexpectedly.",
                f"{ERROR_HINTS['generic']} ({type(exc).__name__})",
            )

    # -- state helpers -----------------------------------------------------

    def _advance(self, analysis_id: str, stage: str, fraction: float, message: str) -> None:
        if self._deadline is not None and time.monotonic() > self._deadline:
            raise TimeoutError("Video processing exceeded its worker time budget.")
        job = self._jobs.get(analysis_id)
        if job is None:
            return
        start, end = STAGE_RANGES.get(stage, (0.0, 1.0))
        overall = start + (end - start) * max(0.0, min(1.0, fraction))
        with job.lock:
            status = job.status
            previous_stage = status.stage
            status.stage = stage
            status.status = "processing"
            status.progress = max(status.progress, overall)
            status.updated_at = time.time()
            _activate_stage(status, stage, overall, message)
        # Persisting every frame would hammer SQLite; only the stage change and
        # large jumps are worth a write.
        if previous_stage != stage or fraction >= 1.0 or overall - self._last_written > 0.02:
            self._last_written = overall
            self._db.update(analysis_id, status="processing", stage=stage, progress=overall)

    def _finish(self, analysis_id: str, progress: float, message: str) -> None:
        job = self._jobs.get(analysis_id)
        if job is None:
            return
        with job.lock:
            job.status.status = "complete"
            job.status.stage = "results"
            job.status.progress = progress
            job.status.updated_at = time.time()
            for item in job.status.stages:
                item.status = "done"
                item.progress = 1.0
            job.status.stages[-1].detail = message

    def _fail(self, analysis_id: str, message: str, hint: str | None) -> None:
        job = self._jobs.get(analysis_id)
        if job is not None:
            with job.lock:
                job.status.status = "error"
                job.status.stage = "results"
                job.status.error = message
                job.status.hint = hint
                job.status.updated_at = time.time()
                _activate_stage(job.status, "results", 1.0, message, status_value="error")
        self._db.update(analysis_id, status="error", error=message, hint=hint)


def _initial_status(analysis_id: str, video: VideoInfo) -> JobStatus:
    now = time.time()
    stages = [
        StageStatus(key=key, label=label, status="pending")
        for key, label, _, _ in STAGE_DEFINITIONS
    ]
    stages[0].status = "active"
    return JobStatus(
        analysis_id=analysis_id,
        status="queued",
        stage="queued",
        progress=0.0,
        stages=stages,
        video=video,
        created_at=now,
        updated_at=now,
    )


def _activate_stage(
    status: JobStatus,
    stage: str,
    progress: float,
    detail: str | None,
    status_value: StageStatusValue = "active",
) -> None:
    """Move the highlight to ``stage`` and close every earlier stage."""
    found = False
    for item in status.stages:
        if item.key == stage:
            item.status = status_value
            item.progress = max(item.progress, progress)
            item.detail = detail
            found = True
        elif not found and item.status in {"active", "pending"}:
            item.status = "done" if status_value != "error" else "pending"
    if not found:
        status.stages.append(
            StageStatus(
                key=stage,
                label=STAGE_LABELS.get(stage, stage),
                status=status_value,
                progress=progress,
                detail=detail,
            )
        )


def _merge_regions(user: Regions, suggested: Regions) -> Regions:
    """Keep whatever the user drew, fill in the rest from the suggestion."""
    queue = user.queue or suggested.queue
    entry = user.entry or suggested.entry
    exit_line = user.exit or suggested.exit
    return user.model_copy(
        update={
            "queue": queue,
            "entry": entry,
            "exit": exit_line,
            "auto_detected": not (user.queue and user.exit),
        }
    )
