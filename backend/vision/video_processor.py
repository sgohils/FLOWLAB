"""The video processing pipeline.

One pass over the clip does everything the vision layer needs:

    decode -> sample frames at ``sample_fps`` -> detect + track
           -> accumulate anonymous trajectories -> write the annotated video

Sampling is the main performance lever: a 60 fps clip is processed at 10 fps,
which is plenty for traffic analysis and cuts the inference cost six-fold.
The annotated video is written at the *source* frame rate, using the last known
overlays for frames that were not processed, so playback stays smooth.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2

from ..config import Settings, settings as default_settings
from ..models.schemas import Trajectory, TrajectoryPoint, VideoInfo
from .annotator import FrameAnnotation, build_annotation, draw_annotations
from .detector import RawDetection, VehicleDetector
from .trajectories import TrackAccumulator

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float, str], None]


class VideoProcessingError(RuntimeError):
    """Raised for problems that should be shown to the user as-is."""


@dataclass(slots=True)
class ProcessingResult:
    tracks: list[Trajectory]
    video: VideoInfo
    processed_frames: int
    total_frames: int
    annotated_path: Path | None
    annotated_ok: bool = True


def process_video(
    source: Path,
    *,
    output_path: Path | None,
    progress: ProgressCallback,
    detector: VehicleDetector,
    settings: Settings | None = None,
    sample_fps: float | None = None,
    write_video: bool = True,
) -> ProcessingResult:
    settings = settings or default_settings
    target_fps = min(15.0, max(1.0, sample_fps or settings.sample_fps))
    progress("reading_video", 0.0, "Opening the video file")

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        capture.release()
        raise VideoProcessingError("The video could not be opened for processing.")
    writer = None
    try:
        source_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        stride = max(1, int(round(source_fps / target_fps)))

        writer = _open_writer(output_path, source_fps, (width, height)) if write_video else None
        accumulator = TrackAccumulator(settings)
        recent: dict[int, deque[TrajectoryPoint]] = {}
        last_annotation = FrameAnnotation(boxes=[], trails=[])
        processed = 0
        frame_index = 0
        detection_count = 0

        progress("reading_video", 0.02, f"Video opened: {width}x{height} @ {source_fps:.1f} fps")

        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            is_sampled = frame_index % stride == 0
            if is_sampled:
                timestamp = frame_index / source_fps
                detections = detector.detect(frame)
                detection_count += len(detections)
                accumulator.update(frame_index, timestamp, detections)
                for detection in detections:
                    if detection.track_id is None:
                        continue
                    history = recent.setdefault(detection.track_id, deque(maxlen=settings.trail_length))
                    history.append(
                        TrajectoryPoint(
                            frame=frame_index,
                            time=round(timestamp, 3),
                            x=round(detection.contact[0], 5),
                            y=round(detection.contact[1], 5),
                            confidence=round(detection.confidence, 3),
                            bbox=[
                                round(detection.x1, 5),
                                round(detection.y1, 5),
                                round(detection.x2, 5),
                                round(detection.y2, 5),
                            ],
                        )
                    )
                last_annotation = build_annotation(
                    detections=_drawable(detections),
                    trails={key: list(value) for key, value in recent.items()},
                    width=width,
                    height=height,
                    trail_length=settings.trail_length,
                )
                processed += 1
                fraction = min(0.95, frame_index / max(total_frames, 1))
                progress(
                    "detecting",
                    fraction,
                    f"Frame {frame_index} - {accumulator.track_count} vehicles tracked",
                )

            if writer is not None:
                frame = draw_annotations(frame, last_annotation)
                writer.write(frame)
            frame_index += 1

        progress("tracking", 0.96, f"Finalising {accumulator.track_count} trajectories")
        tracks = accumulator.build()
        duration = frame_index / source_fps if source_fps > 0 else 0.0
        annotated_ok = True
        if writer is not None:
            writer.release()
            annotated_ok = _writer_usable(output_path)
            if not annotated_ok:
                logger.warning("Annotated video could not be written; results are unaffected.")
    finally:
        capture.release()
        if writer is not None and writer.isOpened():
            writer.release()

    video = VideoInfo(
        filename=source.name,
        duration=round(duration, 3),
        fps=round(source_fps, 3),
        width=width,
        height=height,
        size_bytes=source.stat().st_size if source.exists() else 0,
        processed_fps=round(processed / duration, 2) if duration > 0 else 0.0,
        frame_count=frame_index,
        annotated_path=str(output_path) if annotated_ok and output_path else None,
    )
    logger.info(
        "Processed %s: %d frames, %d detections, %d tracks",
        source.name,
        frame_index,
        detection_count,
        len(tracks),
    )
    return ProcessingResult(
        tracks=tracks,
        video=video,
        processed_frames=processed,
        total_frames=frame_index,
        annotated_path=output_path if annotated_ok else None,
        annotated_ok=annotated_ok,
    )


def _drawable(detections: list[RawDetection]) -> list[tuple[int, str, tuple[float, float, float, float]]]:
    return [
        (d.track_id or 0, d.class_name, (d.x1, d.y1, d.x2, d.y2))
        for d in detections
        if d.track_id is not None
    ]


def _open_writer(path: Path | None, fps: float, size: tuple[int, int]):
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, max(1.0, fps), size)
    if not writer.isOpened():
        writer.release()
        logger.warning("mp4v writer unavailable; the annotated video will be skipped")
        return None
    return writer


def _writer_usable(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    if path.stat().st_size < 1024:
        return False
    capture = cv2.VideoCapture(str(path))
    try:
        return bool(capture.isOpened())
    finally:
        capture.release()


__all__ = ["ProcessingResult", "VideoProcessingError", "process_video"]
