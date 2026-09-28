"""Central configuration for FLOWLAB.

Every tunable lives here so the vision, analytics and simulation layers stay
free of scattered magic numbers.  Values can be overridden with environment
variables, which keeps the Docker image and local development in sync.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_roi(name: str = "FLOWLAB_ROI") -> tuple[float, float, float, float] | None:
    """Parse ``"x0,y0,x1,y1"`` in normalised coordinates, e.g. ``0.45,0,0.65,1``."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        x0, y0, x1, y1 = (float(part) for part in raw.split(","))
    except ValueError:
        return None
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        return None
    return (x0, y0, x1, y1)


# COCO class ids used by the pretrained Ultralytics checkpoint.  ``person`` is
# deliberately absent: FLOWLAB never stores or analyses people, which is the
# strongest privacy stance we can take without adding value to a traffic twin.
COCO_CLASS_IDS: dict[str, int] = {
    "bicycle": 1,
    "car": 2,
    "motorcycle": 3,
    "bus": 5,
    "truck": 7,
}

#: Vehicles we are interested in, ordered by typical size in the scene.
VEHICLE_CLASSES: tuple[str, ...] = ("car", "bus", "truck", "motorcycle", "bicycle")


@dataclass(slots=True)
class Settings:
    """Runtime settings resolved from the environment.

    Deliberately not frozen: the test suite redirects the data directory to a
    temporary folder, and a single-writer process has no reason to guard
    against mutation at runtime.
    """

    # --- vision -----------------------------------------------------------
    model_name: str
    confidence: float
    iou: float
    imgsz: int
    device: str
    tracker_config: str
    classes: tuple[str, ...]
    #: Optional region of interest ``(x0, y0, x1, y1)`` in normalised frame
    #: coordinates.  Frames are cropped to it before inference, which is a big
    #: win for elevated cameras where vehicles are only a few pixels wide.
    #: Detection coordinates are mapped back to the full frame afterwards.
    roi: tuple[float, float, float, float] | None
    #: Processed frames per second of source video (5-15 is plenty).
    sample_fps: float
    #: Tracks shorter than this are discarded as detector noise.
    min_track_points: int
    #: Exponential smoothing factor for the contact point (0 = no smoothing).
    smoothing_alpha: float
    #: A jump larger than this (normalised units) is treated as real movement
    #: and is never smoothed away.
    smoothing_jump: float

    # --- analytics --------------------------------------------------------
    #: Motion below this (normalised units per second) counts as "stopped".
    speed_threshold: float
    min_stop_seconds: float
    bottleneck_cols: int
    bottleneck_rows: int
    bottleneck_min_passes: int
    bottleneck_max_cells: int
    #: Trail length drawn on the annotated video, in samples.
    trail_length: int
    #: Number of simulated vehicles kept for the corridor visualisation.
    sim_profiles: int

    # --- storage / limits -------------------------------------------------
    data_dir: Path
    upload_dir: Path
    processed_dir: Path
    database_path: Path
    max_upload_bytes: int
    max_duration_seconds: float
    min_duration_seconds: float
    max_frame_dimension: int
    allowed_extensions: tuple[str, ...]
    max_concurrent_jobs: int
    #: Uploads waiting for a worker before the API starts refusing them.
    max_queued_jobs: int
    keep_raw_tracks: bool

    @property
    def class_ids(self) -> list[int]:
        """COCO ids matching :attr:`classes`, passed straight to Ultralytics."""
        return [COCO_CLASS_IDS[name] for name in self.classes if name in COCO_CLASS_IDS]


def build_settings() -> Settings:
    data_dir = Path(_env_str("FLOWLAB_DATA_DIR", str(PROJECT_DIR / "data"))).resolve()
    return Settings(
        model_name=_env_str("FLOWLAB_MODEL", "yolo11n.pt"),
        confidence=_env_float("FLOWLAB_CONFIDENCE", 0.25),
        iou=_env_float("FLOWLAB_IOU", 0.50),
        imgsz=_env_int("FLOWLAB_IMGSZ", 640),
        device=_env_str("FLOWLAB_DEVICE", "auto"),
        tracker_config=_env_str("FLOWLAB_TRACKER", "bytetrack.yaml"),
        classes=tuple(
            name.strip()
            for name in _env_str("FLOWLAB_CLASSES", ",".join(VEHICLE_CLASSES)).split(",")
            if name.strip() in COCO_CLASS_IDS
        )
        or VEHICLE_CLASSES,
        roi=_env_roi(),
        sample_fps=min(15.0, max(5.0, _env_float("FLOWLAB_SAMPLE_FPS", 10.0))),
        min_track_points=_env_int("FLOWLAB_MIN_TRACK_POINTS", 4),
        smoothing_alpha=min(1.0, max(0.0, _env_float("FLOWLAB_SMOOTHING_ALPHA", 0.55))),
        smoothing_jump=_env_float("FLOWLAB_SMOOTHING_JUMP", 0.02),
        speed_threshold=_env_float("FLOWLAB_SPEED_THRESHOLD", 0.012),
        min_stop_seconds=_env_float("FLOWLAB_MIN_STOP_SECONDS", 1.5),
        bottleneck_cols=_env_int("FLOWLAB_BOTTLENECK_COLS", 8),
        bottleneck_rows=_env_int("FLOWLAB_BOTTLENECK_ROWS", 6),
        bottleneck_min_passes=_env_int("FLOWLAB_BOTTLENECK_MIN_PASSES", 2),
        bottleneck_max_cells=_env_int("FLOWLAB_BOTTLENECK_MAX", 6),
        trail_length=_env_int("FLOWLAB_TRAIL_LENGTH", 20),
        sim_profiles=_env_int("FLOWLAB_SIM_PROFILES", 10),
        data_dir=data_dir,
        upload_dir=data_dir / "uploads",
        processed_dir=data_dir / "processed",
        database_path=data_dir / "flowlab.db",
        max_upload_bytes=_env_int("FLOWLAB_MAX_UPLOAD_MB", 250) * 1024 * 1024,
        max_duration_seconds=_env_float("FLOWLAB_MAX_DURATION", 900.0),
        min_duration_seconds=_env_float("FLOWLAB_MIN_DURATION", 2.0),
        max_frame_dimension=_env_int("FLOWLAB_MAX_FRAME_DIM", 4096),
        allowed_extensions=(".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"),
        max_concurrent_jobs=_env_int("FLOWLAB_MAX_JOBS", 1),
        max_queued_jobs=_env_int("FLOWLAB_MAX_QUEUED", 3),
        keep_raw_tracks=_env_bool("FLOWLAB_KEEP_RAW_TRACKS", True),
    )


def ensure_directories(settings: Settings) -> None:
    """Create the storage layout.  Safe to call repeatedly."""
    for directory in (settings.data_dir, settings.upload_dir, settings.processed_dir):
        directory.mkdir(parents=True, exist_ok=True)


settings = build_settings()
ensure_directories(settings)
