"""Analysis endpoints: status, results, regions, media and metadata."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ValidationError

from ..analytics.metrics import build_analysis, deserialise_analysis
from ..analytics.timeline import build_timeline
from ..config import settings
from ..models.schemas import (
    Analysis,
    AnalysisListItem,
    DeleteResult,
    Health,
    JobStatus,
    Regions,
    VideoInfo,
)
from ..storage import read_result
from .exports import (
    ExportBundle,
    build_events_csv,
    build_queue_csv,
    build_summary_json,
    build_trajectories_csv,
    measurements_payload,
)
from .jobs import STAGE_DEFINITIONS
from .state import (
    DEMO_ID,
    annotated_file,
    database,
    delete_analysis as delete_files,
    demo_analysis,
    is_processing,
    jobs,
    register_demo,
    save_analysis,
    source_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analysis"])


class RegionUpdate(BaseModel):
    regions: Regions


class MetaResponse(BaseModel):
    """Configuration the UI needs to draw sensible controls."""

    model_name: str
    device: str
    vehicle_classes: list[str]
    sample_fps: float
    speed_threshold: float
    min_stop_seconds: float
    allowed_extensions: list[str]
    max_upload_mb: int
    max_duration_seconds: float
    stages: list[dict[str, str]]


def _require_analysis(analysis_id: str) -> tuple[Analysis, list]:
    """Load the stored analysis together with the tracks used to measure it."""
    payload = read_result(settings, analysis_id)
    if payload:
        try:
            return deserialise_analysis(payload)
        except ValueError as exc:
            logger.warning("Stored analysis %s is invalid: %s", analysis_id, exc)
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "The stored result for this analysis could not be read.",
            ) from exc
    if analysis_id == DEMO_ID:
        demo = demo_analysis()
        if demo is not None:
            return demo, demo.trajectories
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"No analysis with id '{analysis_id}'.")


@router.get("/health", response_model=Health)
async def health() -> Health:
    """Liveness plus a check that the detection model can be loaded."""
    from ..vision.detector import detector

    message: str | None = None
    status_value = "ok"
    try:
        detector.load()
    except Exception as exc:  # the API stays up so the UI can explain the problem
        status_value = "degraded"
        message = str(exc)
    return Health(
        status=status_value,
        model_loaded=detector.is_loaded,
        device=detector.device,
        model_name=settings.model_name,
        message=message,
    )


@router.get("/meta", response_model=MetaResponse)
async def meta() -> MetaResponse:
    return MetaResponse(
        model_name=settings.model_name,
        device=settings.device,
        vehicle_classes=list(settings.classes),
        sample_fps=settings.sample_fps,
        speed_threshold=settings.speed_threshold,
        min_stop_seconds=settings.min_stop_seconds,
        allowed_extensions=list(settings.allowed_extensions),
        max_upload_mb=settings.max_upload_bytes // (1024 * 1024),
        max_duration_seconds=settings.max_duration_seconds,
        stages=[{"key": key, "label": label} for key, label, _, _ in STAGE_DEFINITIONS],
    )


@router.get("/analyses", response_model=list[AnalysisListItem])
async def list_analyses(limit: int = Query(default=25, ge=1, le=100)) -> list[AnalysisListItem]:
    register_demo()
    items: list[AnalysisListItem] = []
    for record in database.list_recent(limit=limit):
        summary = record.get("summary") or {}
        video = record.get("video") or {}
        items.append(
            AnalysisListItem(
                analysis_id=record["analysis_id"],
                filename=record["filename"],
                source=record["source"],
                status=record["status"],
                created_at=record["created_at"],
                duration=float(video.get("duration") or 0.0),
                vehicles_tracked=int(summary.get("vehicles_tracked") or 0),
                peak_queue=summary.get("peak_queue"),
                throughput_per_minute=summary.get("throughput_per_minute"),
            )
        )
    return items


@router.get("/demo", response_model=Analysis)
async def demo() -> Analysis:
    """The bundled demo dataset.  Always served with ``source='demo'``."""
    analysis = register_demo()
    if analysis is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The demo dataset is not bundled with this build.",
        )
    return analysis


@router.get("/analyses/{analysis_id}/status", response_model=JobStatus)
async def analysis_status(analysis_id: str) -> JobStatus:
    job = jobs.get(analysis_id)
    if job is not None:
        return job
    record = database.get(analysis_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No analysis with id '{analysis_id}'.")
    video = VideoInfo.model_validate(record["video"]) if record.get("video") else None
    return JobStatus(
        analysis_id=analysis_id,
        status="complete" if record["status"] == "complete" else record["status"],  # type: ignore[arg-type]
        stage=record["stage"],
        progress=record["progress"],
        stages=[],
        error=record.get("error"),
        hint=record.get("hint"),
        video=video,
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


@router.get("/analyses/{analysis_id}/result", response_model=Analysis)
async def analysis_result(
    analysis_id: str,
    trajectory_points: int = Query(
        default=60, ge=4, le=600, description="Maximum trajectory samples returned per vehicle."
    ),
) -> Analysis:
    """Full result.  Trajectories are down-sampled for the client by default."""
    analysis, _ = _require_analysis(analysis_id)
    return _downsample(analysis, trajectory_points)


def _downsample(analysis: Analysis, limit: int) -> Analysis:
    """Uniformly thin trajectory points without touching the measurements."""
    thinned = []
    for track in analysis.trajectories:
        points = track.points
        if len(points) <= limit:
            thinned.append(track)
            continue
        stride = len(points) / limit
        picked = [points[int(index * stride)] for index in range(limit)]
        if picked[-1] is not points[-1]:
            picked[-1] = points[-1]
        thinned.append(track.model_copy(update={"points": picked}))
    return analysis.model_copy(update={"trajectories": thinned})


@router.put("/analyses/{analysis_id}/regions", response_model=Analysis)
async def update_regions(analysis_id: str, payload: RegionUpdate) -> Analysis:
    """Re-measure with new regions.  No detection is repeated - this is fast."""
    analysis, tracks = _require_analysis(analysis_id)
    if analysis.source == "demo":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The demo dataset is read-only: upload a video to draw your own regions.",
        )
    try:
        updated = await asyncio.to_thread(
            build_analysis,
            analysis_id=analysis.analysis_id,
            video=analysis.video,
            tracks=tracks,
            regions=payload.regions.model_copy(update={"auto_detected": False}),
            source=analysis.source,
            created_at=analysis.created_at,
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    save_analysis(updated, raw_tracks=tracks)
    database.update(
        analysis_id,
        summary=updated.summary.model_dump(mode="json"),
    )
    return _downsample(updated, 60)


@router.get("/analyses/{analysis_id}/video/annotated", response_class=FileResponse)
async def annotated_video(analysis_id: str) -> FileResponse:
    path = annotated_file(analysis_id)
    if path is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No annotated video is available for this analysis.",
        )
    return FileResponse(path, media_type="video/mp4", filename=f"{analysis_id}-annotated.mp4")


@router.get("/analyses/{analysis_id}/video/source", response_class=FileResponse)
async def original_video(analysis_id: str) -> FileResponse:
    path = source_file(analysis_id)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The source video is no longer on disk.")
    return FileResponse(path, media_type="video/mp4", filename=Path(path).name)


@router.get("/analyses/{analysis_id}/timeline")
async def analysis_timeline(
    analysis_id: str,
    hz: float = Query(
        default=4.0,
        ge=1.0,
        le=15.0,
        description="Replay resolution in samples per second.",
    ),
) -> dict:
    """Replay data: positions over time, split into segments at tracking gaps.

    This is deliberately *not* the thinned trajectory list used for the map.
    Here the resolution is uniform in time and a track that was lost comes back
    as several segments, so the player can show "position unknown" instead of
    inventing motion across the gap.
    """
    analysis, tracks = _require_analysis(analysis_id)
    return build_timeline(tracks, analysis.regions, analysis.video.duration, hz=hz)


@router.delete("/analyses/{analysis_id}", response_model=DeleteResult)
async def delete_analysis(analysis_id: str) -> DeleteResult:
    """Delete the record **and its files**: upload, annotated video, results.

    A delete that left the uploaded footage on disk would be a false promise,
    so the response reports exactly how many files were removed and how much
    space was freed.  A running job is refused: it would recreate the files.
    """
    if analysis_id == DEMO_ID:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The demo dataset cannot be deleted.")
    if database.get(analysis_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No analysis with id '{analysis_id}'.")
    if is_processing(analysis_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This analysis is still being processed. Wait for it to finish before deleting it.",
        )
    files, freed = delete_files(analysis_id)
    return DeleteResult(
        analysis_id=analysis_id,
        deleted_files=files,
        bytes_freed=freed,
        message=(
            f"Deleted {files} file(s) and freed {freed / 1_000_000:.1f} MB of local storage."
            if files
            else "The analysis record was removed; no local files were left behind."
        ),
    )


# ------------------------------------------------------------------- export


def _download(bundle: ExportBundle) -> Response:
    return Response(
        content=bundle.content,
        media_type=bundle.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{bundle.filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/analyses/{analysis_id}/export/summary.json")
async def export_summary(
    analysis_id: str,
    include_points: bool = Query(
        default=False, description="Include raw trajectory samples (larger file)."
    ),
) -> Response:
    """Full result as JSON.  Contains no video, ever."""
    analysis, _ = _require_analysis(analysis_id)
    return _download(build_summary_json(analysis, include_points=include_points))


@router.get("/analyses/{analysis_id}/export/vehicles.csv")
async def export_vehicles(analysis_id: str) -> Response:
    """Per-vehicle durations and queue times."""
    analysis, _ = _require_analysis(analysis_id)
    return _download(build_trajectories_csv(analysis))


@router.get("/analyses/{analysis_id}/export/queue.csv")
async def export_queue(analysis_id: str) -> Response:
    """The queue length series."""
    analysis, _ = _require_analysis(analysis_id)
    return _download(build_queue_csv(analysis))


@router.get("/analyses/{analysis_id}/export/events.csv")
async def export_events(analysis_id: str) -> Response:
    """Events, bottleneck evidence and stopped intervals."""
    analysis, _ = _require_analysis(analysis_id)
    return _download(build_events_csv(analysis))


@router.get("/analyses/{analysis_id}/export/measurements")
async def export_measurements(analysis_id: str) -> dict:
    """The headline numbers with units and definitions, as JSON."""
    analysis, _ = _require_analysis(analysis_id)
    return measurements_payload(analysis)

