"""Filesystem helpers: upload validation, ids, and result serialisation."""

from __future__ import annotations

import gzip
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from ..config import Settings

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class StorageError(Exception):
    """Raised when an upload cannot be accepted or read."""


def new_id() -> str:
    """Short, URL friendly identifier used for analyses."""
    return uuid.uuid4().hex[:12]


def safe_filename(name: str) -> str:
    """Strip any path components and unsafe characters from a client name."""
    base = Path(name.replace("\\", "/")).name
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "video"
    return cleaned[:120]


def analysis_dir(settings: Settings, analysis_id: str) -> Path:
    return settings.processed_dir / analysis_id


def result_path(settings: Settings, analysis_id: str) -> Path:
    return analysis_dir(settings, analysis_id) / "result.json.gz"


def annotated_path(settings: Settings, analysis_id: str) -> Path:
    return analysis_dir(settings, analysis_id) / "annotated.mp4"


def upload_path(settings: Settings, analysis_id: str, filename: str) -> Path:
    return settings.upload_dir / f"{analysis_id}_{safe_filename(filename)}"


def write_result(settings: Settings, analysis_id: str, payload: dict[str, Any]) -> Path:
    """Store an analysis as gzipped JSON (trajectory payloads get large)."""
    path = result_path(settings, analysis_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    return path


def read_result(settings: Settings, analysis_id: str) -> dict[str, Any] | None:
    path = result_path(settings, analysis_id)
    if not path.exists():
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


@dataclass(frozen=True, slots=True)
class VideoProbe:
    width: int
    height: int
    fps: float
    frame_count: int
    duration: float


def probe_video(path: Path, settings: Settings) -> VideoProbe:
    """Read container metadata and validate that frames can be decoded.

    Raises :class:`StorageError` with a user-facing message for anything the UI
    should explain (corrupt file, unreadable header, no video stream).
    """
    if not path.exists() or path.stat().st_size == 0:
        raise StorageError("The uploaded file is empty or missing.")
    if path.stat().st_size > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
        raise StorageError(f"File is larger than the {limit_mb} MB limit.")

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise StorageError(
            "This file could not be opened as a video. MP4 (H.264) and MOV are supported."
        )
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()

    if width <= 0 or height <= 0:
        raise StorageError("The video has no decodable picture stream.")
    if max(width, height) > settings.max_frame_dimension:
        raise StorageError(
            f"Resolution {width}x{height} is too large; the maximum supported size is "
            f"{settings.max_frame_dimension}px on the longest side."
        )
    # Some web containers report 0 or NaN fps; fall back to a sane default and
    # let the first decoded frame confirm the stream really works.
    if not (0 < fps < 500):
        fps = 25.0
    duration = frame_count / fps if frame_count > 0 else 0.0
    if duration < settings.min_duration_seconds:
        raise StorageError("The video is shorter than 2 seconds; there is nothing to measure.")
    if duration > settings.max_duration_seconds:
        raise StorageError(
            f"The clip is {duration / 60:.1f} minutes long; the limit is "
            f"{settings.max_duration_seconds / 60:.0f} minutes."
        )
    if not _first_frame_decodes(path):
        raise StorageError("The video header is readable but no frames could be decoded.")
    return VideoProbe(
        width=width, height=height, fps=fps, frame_count=frame_count, duration=duration
    )


def _first_frame_decodes(path: Path) -> bool:
    capture = cv2.VideoCapture(str(path))
    try:
        ok, frame = capture.read()
        return bool(ok) and frame is not None and frame.size > 0
    finally:
        capture.release()


def extension_allowed(filename: str, settings: Settings) -> bool:
    return Path(filename).suffix.lower() in settings.allowed_extensions
