"""Central configuration for FLOWLAB.

Every tunable lives here so the vision, analytics and simulation layers stay
free of scattered magic numbers.  Values can be overridden with environment
variables, which keeps the Docker image and local development in sync.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from urllib.parse import urlsplit

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

logger = logging.getLogger(__name__)


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


def _env_list(name: str, default: str) -> tuple[str, ...]:
    """Split a comma-separated environment variable, dropping empty entries."""
    return tuple(
        part.strip() for part in _env_str(name, default).split(",") if part.strip()
    )


#: Host names that name this machine and nothing else.  Membership is tested as
#: whole strings, never as substrings: ``localhost.evil.com`` is a routable host
#: that merely begins with an allowed name, and an ``"localhost" in origin`` test
#: would wave it through.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

#: The shape of an accepted entry, quoted verbatim in the error message so
#: the operator does not have to guess what "loopback origin" excludes.
CORS_ORIGIN_FORMAT = "http(s)://<localhost|127.0.0.1|[::1]>[:port]"

#: Escape hatch for the one case where a wider list is legitimate: an
#: authenticating proxy in front of the API, as the DEFAULT_CORS_ORIGINS
#: note below anticipates.  Off unless an operator sets it to "1", it is
#: validated by nothing, and it logs every origin it allowed.
UNSAFE_CORS_FLAG = "FLOWLAB_ALLOW_UNSAFE_CORS"


def is_loopback_origin(origin: str) -> bool:
    """True for an http(s) origin whose host is this machine.

    A CORS origin is a scheme, a host and an optional port; a path is
    meaningless and credentials are never legitimate.  ``urlsplit`` does the
    parsing: ``hostname`` lowercases the host and strips the brackets from
    ``[::1]``, and a value with no scheme at all (``localhost:5173``) has no
    host, so it is refused rather than guessed at.
    """
    try:
        parts = urlsplit(origin)
        host = parts.hostname
    except ValueError:  # a port that is not a number, e.g. "localhost:99999"
        return False
    return (
        parts.scheme in {"http", "https"}
        and not parts.username
        and not parts.password
        and host is not None
        and host.lower() in LOOPBACK_HOSTS
    )


def _cors_rejection(name: str, origin: str) -> ValueError:
    """The error for one refused entry: what it was, why, and what is accepted."""
    if origin == "*":
        reason = (
            "A wildcard is the one value that must never be accepted here: it "
            "lets every site the user visits read every stored analysis, and "
            "this API has no authentication of any kind."
        )
    else:
        reason = (
            "This API has no authentication, so its browser origin list is the "
            "only access boundary there is and it stays on this machine."
        )
    return ValueError(
        f"{name} contains {origin!r}, which is not an accepted origin. {reason} "
        f"Accepted entries are {CORS_ORIGIN_FORMAT} - for example "
        f"'http://localhost:5173'. Put authentication in front of the API before "
        f"widening it, or set {UNSAFE_CORS_FLAG}=1 to accept this list deliberately."
    )


def _env_origins(name: str = "FLOWLAB_CORS_ORIGINS") -> tuple[str, ...]:
    """Resolve *and validate* the browser origin allow-list.

    A refused entry raises rather than warns.  Dropping it silently is how a
    CORS mistake becomes invisible: an operator who widens the list would see
    the API start and believe their host is allowed, when in fact nothing
    changed, and a wildcard that survived into ``allow_origins=["*"]`` would
    hand every page the user visits the stored trajectories.  Failing at
    settings construction stops the process with a message that names the
    value and the accepted form, which is the only outcome an operator can
    act on.  The one escape is :data:`UNSAFE_CORS_FLAG`: never the default, and
    loud when used.
    """
    origins = _env_list(name, ",".join(DEFAULT_CORS_ORIGINS))
    if not origins:
        # Empty means "unset": never "allow nothing" and never "allow all".
        return DEFAULT_CORS_ORIGINS
    if _env_bool(UNSAFE_CORS_FLAG, False):
        logger.warning(
            "%s is set, so %s is accepted without validation: %s. Every one of "
            "those origins can read every stored analysis, because the API has "
            "no authentication.",
            UNSAFE_CORS_FLAG,
            name,
            ", ".join(origins),
        )
        return origins
    for origin in origins:
        if not is_loopback_origin(origin):
            raise _cors_rejection(name, origin)
    return origins


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

#: Browser origins allowed to call the API: the Vite dev server and the preview
#: server, on loopback only.
#:
#: **The API has no authentication.**  There is no token, no session and no
#: per-user identity, so this list is the only thing standing between a
#: browser on the machine and every uploaded vehicle on it.  The API is bound
#: to 127.0.0.1 for the same reason.  Widening ``FLOWLAB_CORS_ORIGINS`` to a
#: routable host means any page that origin loads can read the raw tracks and
#: the uploaded file paths, so keep it on loopback unless you have put
#: authentication in front of the API.
DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)
#:
#: This is not documentation the reader is trusted to follow: :func:`_env_origins`
#: refuses every entry that is not an http(s) loopback origin, ``*`` included, and
#: ``build_settings`` raises on a refused one so the process will not start.  The
#: escape hatch is ``FLOWLAB_ALLOW_UNSAFE_CORS=1``, for a deployment that really
#: does have authentication in front of the API.


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
    #: Browser origins allowed to call the API.  Loopback only: the API is
    #: unauthenticated, so this list is its only access boundary.  Validated at
    #: construction - see :func:`_env_origins`.
    cors_origins: tuple[str, ...]
    #: Hosted persistence is selected explicitly or by the Vercel runtime.
    hosted: bool = False
    database_url: str = ""

    @property
    def class_ids(self) -> list[int]:
        """COCO ids matching :attr:`classes`, passed straight to Ultralytics."""
        return [COCO_CLASS_IDS[name] for name in self.classes if name in COCO_CLASS_IDS]


def build_settings() -> Settings:
    # A deployed Vercel function can write only to temporary storage. This is
    # instance-local scratch space, not persistent or shared application state.
    on_vercel = os.getenv("VERCEL") == "1"
    hosted = _env_bool("FLOWLAB_HOSTED", on_vercel)
    default_data_dir = Path(gettempdir()) / "flowlab" if hosted else PROJECT_DIR / "data"
    data_dir = Path(_env_str("FLOWLAB_DATA_DIR", str(default_data_dir))).resolve()
    default_model = str(data_dir / "yolo11n.pt") if hosted else "yolo11n.pt"
    return Settings(
        hosted=hosted,
        database_url=_env_str("DATABASE_URL", ""),
        model_name=_env_str("FLOWLAB_MODEL", default_model),
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
        cors_origins=_env_origins(),
    )


def ensure_directories(settings: Settings) -> None:
    """Create the storage layout.  Safe to call repeatedly."""
    for directory in (settings.data_dir, settings.upload_dir, settings.processed_dir):
        directory.mkdir(parents=True, exist_ok=True)


settings = build_settings()
ensure_directories(settings)
