"""Durable dispatch; the API never starts a background processing thread."""

from __future__ import annotations

import time
from contextlib import suppress
from pathlib import Path

from ..config import Settings
from ..models.schemas import JobStatus, Regions, VideoInfo
from ..storage.postgres import PostgresDatabase
from .jobs import _activate_stage, _initial_status

TOPIC = "flowlab-video"


class HostedJobs:
    def __init__(self, database: PostgresDatabase, settings: Settings) -> None:
        self._db = database
        self._settings = settings

    def register(self, analysis_id: str, video: VideoInfo) -> JobStatus:
        self._db.update(
            analysis_id, status="queued", stage="queued", progress=0.0,
            video=video.model_dump(mode="json"),
        )
        return _initial_status(analysis_id, video)

    def submit(self, analysis_id: str, _source_path: Path, _regions: Regions | None = None) -> None:
        from vercel.queue import DuplicateIdempotencyKeyError
        from vercel.queue.sync import QueueClient

        with suppress(DuplicateIdempotencyKeyError):
            QueueClient(region="iad1").send(
                TOPIC, {"analysis_id": analysis_id}, idempotency_key=analysis_id,
            )

    def get(self, analysis_id: str) -> JobStatus | None:
        record = self._db.get(analysis_id)
        if record and record["status"] == "processing" and time.time() - record["updated_at"] > 600:
            # A hard function timeout cannot run finally/except. Polling repairs
            # the visible status after the worker and its retry window elapsed.
            self._db.update(
                analysis_id, status="error", error="Processing exceeded its runtime limit.",
                hint="Try a shorter clip or increase the worker's runtime limit.",
            )
            record = self._db.get(analysis_id)
        if not record or not record.get("video"):
            return None
        status = _initial_status(analysis_id, VideoInfo.model_validate(record["video"]))
        for name in ("status", "stage", "progress", "error", "hint", "created_at", "updated_at"):
            setattr(status, name, record.get(name))
        _activate_stage(status, status.stage, status.progress, status.error)
        if status.status == "complete":
            for stage in status.stages:
                stage.status = "done"
                stage.progress = 1.0
        return status

    def pending_count(self) -> int:
        return self._db.pending_count()

    def shutdown(self) -> None:
        pass
