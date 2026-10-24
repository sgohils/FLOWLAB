"""Private Vercel Queues subscriber, discovered without runtime DB access."""

from __future__ import annotations

import asyncio

from vercel.queue import Message, RetryAfter, subscribe


@subscribe(topic="flowlab-video", consumer_group="video-processing", max_concurrency=1,
           max_attempts=3, retry_after=60)
async def process(message: Message[dict[str, str]]) -> None:
    await asyncio.to_thread(
        _process, message.payload["analysis_id"], message.metadata.delivery_count,
    )


def _process(analysis_id: str, attempt: int) -> None:
    from .api.jobs import JobManager
    from .config import ensure_directories, settings
    from .models.schemas import Regions, VideoInfo
    from .storage import annotated_path, probe_video, upload_path
    from .storage.cloud import cloud_database, download

    ensure_directories(settings)
    database = cloud_database(settings)
    with database.job_lock(analysis_id) as acquired:
        if not acquired:
            raise RetryAfter(60)
        record = database.get(analysis_id)
        if not record or record["status"] == "complete":
            return
        if record["status"] == "error" and record.get("stage") != "dispatch_failed":
            return
        source = upload_path(settings, analysis_id, record["filename"])
        manager = JobManager(database, settings)
        try:
            if not download(settings, record["upload_path"], source):
                raise RuntimeError("The queued video is missing from Blob storage.")
            probe = probe_video(source, settings)
            video = VideoInfo(
                filename=record["filename"], duration=probe.duration, fps=probe.fps,
                width=probe.width, height=probe.height, size_bytes=source.stat().st_size,
                frame_count=probe.frame_count, processed_fps=0.0,
            )
            manager.register(analysis_id, video)
            manager._run(analysis_id, source, Regions(), retry_errors=True)
        except Exception:
            if attempt >= 3:
                database.update(
                    analysis_id, status="error", error="Processing failed after three attempts.",
                    hint="Upload the clip again or check the worker logs.",
                )
            else:
                raise
        finally:
            manager.shutdown()
            source.unlink(missing_ok=True)
            annotated_path(settings, analysis_id).unlink(missing_ok=True)
