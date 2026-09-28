"""Video upload endpoint.

The file is streamed to disk (never buffered in memory), validated, probed with
OpenCV and only then handed to the processing queue.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from ..config import settings
from ..models.schemas import VideoInfo
from ..storage import StorageError, extension_allowed, new_id, probe_video, safe_filename
from .errors import api_error
from .state import database, jobs, resolve_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["upload"])

#: 1 MiB chunks: large enough to be fast, small enough to bound memory.
CHUNK = 1024 * 1024

QUEUE_FULL_HINT = (
    "Wait for the current analysis to finish, or restart the backend to clear the queue."
)


class UploadResponse(BaseModel):
    analysis_id: str
    video: VideoInfo
    status_url: str
    result_url: str
    message: str


@router.post("", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_video(file: UploadFile = File(...)) -> UploadResponse:
    filename = safe_filename(file.filename or "video.mp4")
    if not extension_allowed(filename, settings):
        allowed = ", ".join(settings.allowed_extensions)
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"'{Path(filename).suffix or filename}' is not a supported video format. Use: {allowed}.",
        )

    analysis_id = new_id()
    destination = resolve_upload(analysis_id, filename)
    # Bounded work: a queued job is refused rather than silently piling up.
    if jobs.pending_count() >= settings.max_queued_jobs:
        destination.unlink(missing_ok=True)
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"{settings.max_queued_jobs} analyses are already queued on this machine.",
            hint=QUEUE_FULL_HINT,
        )
    written = 0
    try:
        with destination.open("wb") as handle:
            while chunk := await file.read(CHUNK):
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    handle.close()
                    destination.unlink(missing_ok=True)
                    limit_mb = settings.max_upload_bytes // (1024 * 1024)
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"File is larger than the {limit_mb} MB limit.",
                    )
                handle.write(chunk)
    finally:
        await file.close()

    try:
        probe = probe_video(destination, settings)
    except StorageError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    video = VideoInfo(
        filename=filename,
        duration=round(probe.duration, 3),
        fps=round(probe.fps, 3),
        width=probe.width,
        height=probe.height,
        size_bytes=written,
        processed_fps=0.0,
        frame_count=probe.frame_count,
    )
    database.create(analysis_id, source="video", filename=filename, upload_path=str(destination))
    jobs.register(analysis_id, video)
    jobs.submit(analysis_id, destination)
    logger.info("Accepted %s (%.1f MB) as %s", filename, written / 1e6, analysis_id)
    return UploadResponse(
        analysis_id=analysis_id,
        video=video,
        status_url=f"/api/analyses/{analysis_id}/status",
        result_url=f"/api/analyses/{analysis_id}/result",
        message="Upload accepted. Processing has started.",
    )

