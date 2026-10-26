"""Pydantic schemas shared by the API, the analytics layer and the demo loader.

Geometry is always stored in **normalised image coordinates**: ``x`` and ``y``
are fractions of the frame width and height in ``[0, 1]``.  The frontend and
the backend therefore never have to know the video resolution, and a user can
redraw regions on a resized player without breaking anything.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

#: Geometry primitives live in ``backend.geometry`` so this module can validate
#: a region without importing ``backend.analytics`` (which imports this module).
from ..geometry import polygon_area

Coordinate = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
Point = tuple[Coordinate, Coordinate]

Source = Literal["video", "demo"]
RegionKind = Literal["queue", "entry", "exit", "conflict"]
CrossingDirection = Literal["any", "forward"]
#: The four states a processing job can be in.  The database column is free-form
#: TEXT, so the API maps it onto this set explicitly instead of trusting it.
JobState = Literal["queued", "processing", "complete", "error"]

#: Smallest region FLOWLAB will accept, as a fraction of the frame area.
#: Below this, a handful of detector samples decide the whole metric.
MIN_POLYGON_AREA = 0.002


def _has_repeated_vertices(points: list[Point]) -> bool:
    """True when two consecutive (or first/last) points coincide."""
    ordered = list(points)
    if ordered[0] == ordered[-1]:
        # A repeated closing point is redundant rather than degenerate.
        ordered = ordered[:-1]
    return any(a == b for a, b in pairwise(ordered))


def _is_self_intersecting(points: list[Point]) -> bool:
    """True when any two non-adjacent edges of the polygon cross.

    A self-intersecting outline (a "bow tie") makes the inside/outside test
    ambiguous: ray casting can report a point as both inside and outside.
    A repeated closing vertex is stripped first, since it is a normal way to
    close a drawn polygon and only creates a degenerate edge.
    """
    if points and points[0] == points[-1]:
        points = points[:-1]
    count = len(points)
    if count < 4:
        return False

    def crosses(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
        def orient(a: Point, b: Point, c: Point) -> float:
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
        d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    for i in range(count):
        a1, a2 = points[i], points[(i + 1) % count]
        for j in range(i + 1, count):
            # Skip adjacent edges (they legitimately share a vertex) and the
            # wrap-around pair.
            if j == i or (i == 0 and j == count - 1) or j == i + 1:
                continue
            b1, b2 = points[j], points[(j + 1) % count]
            if crosses(a1, a2, b1, b2):
                return True
    return False


class Regions(BaseModel):
    """User defined measurement regions plus the stop-detection thresholds."""

    queue: list[Point] = Field(default_factory=list, max_length=40)
    entry: list[Point] = Field(default_factory=list, max_length=2)
    exit: list[Point] = Field(default_factory=list, max_length=2)
    conflict: list[Point] = Field(default_factory=list, max_length=40)
    #: Speed proxy threshold in normalised units per second (fraction of frame
    #: width travelled per second).  Below this a vehicle counts as slow.
    speed_threshold: float = Field(default=0.012, ge=0.0005, le=0.2)
    #: How long motion must stay below the threshold before it is a "stop".
    min_stop_seconds: float = Field(default=1.5, ge=0.2, le=60.0)
    #: How long a vehicle must stay inside the queue region *while slow* before
    #: it contributes to the queue length.  This is what keeps a single noisy
    #: sample from inflating the queue.
    min_queue_seconds: float = Field(default=0.5, ge=0.0, le=60.0)
    sample_fps: float = Field(default=10.0, ge=5.0, le=15.0)
    #: Counting policy for each measurement line.  ``forward`` only counts a
    #: crossing from the left side of the directed line (start -> end) to its
    #: right side, which is the normal direction of travel.
    entry_direction: CrossingDirection = "any"
    exit_direction: CrossingDirection = "any"
    #: True when part of the geometry was suggested by the heuristics in
    #: ``analytics.suggestions`` rather than drawn by the user.
    auto_detected: bool = False

    @model_validator(mode="after")
    def check_geometry(self) -> Regions:
        if self.queue and len(self.queue) < 3:
            raise ValueError("A queue region needs at least three points.")
        if self.conflict and len(self.conflict) < 3:
            raise ValueError("A conflict region needs at least three points.")
        for name in ("entry", "exit"):
            line = getattr(self, name)
            if line and (len(line) != 2 or line[0] == line[1]):
                raise ValueError(f"The {name} line needs two distinct points.")
        for name in ("queue", "conflict"):
            polygon = getattr(self, name)
            if not polygon:
                continue
            if _has_repeated_vertices(polygon):
                raise ValueError(
                    f"The {name} region has repeated points, which would create a "
                    "zero-length edge."
                )
            if _is_self_intersecting(polygon):
                raise ValueError(
                    f"The {name} region crosses over itself. Draw a simple "
                    "polygon: the inside/outside test is undefined otherwise."
                )
            if polygon_area(polygon) < MIN_POLYGON_AREA:
                raise ValueError(
                    f"The {name} region is too small to measure "
                    f"(needs at least {MIN_POLYGON_AREA * 100:.2f}% of the frame)."
                )
        return self

    @property
    def has_queue(self) -> bool:
        return len(self.queue) >= 3


class VideoInfo(BaseModel):
    filename: str
    duration: float
    fps: float
    width: int
    height: int
    size_bytes: int
    processed_fps: float
    frame_count: int
    annotated_path: str | None = None
    annotated_url: str | None = None


class TrajectoryPoint(BaseModel):
    frame: int
    time: float
    x: float
    y: float
    confidence: float
    bbox: list[float] = Field(default_factory=list)
    #: Instantaneous speed proxy in normalised units per second.
    speed: float = 0.0


class Trajectory(BaseModel):
    vehicle_id: int
    vehicle_class: str
    first_seen: float
    last_seen: float
    #: Traversal time: first to last tracked sample, gaps included.
    duration: float
    #: Path length in normalised units (sum of sample-to-sample distances).
    path_length: float
    #: Time spent below the speed threshold anywhere in the scene, in
    #: intervals of at least ``min_stop_seconds``.
    stopped_seconds: float = 0.0
    #: Time inside the queue region *and* below the speed threshold - this is
    #: what the wait statistics are built from.
    queue_seconds: float = 0.0
    #: Time inside the queue region regardless of speed.
    region_seconds: float = 0.0
    mean_speed: float = 0.0
    points: list[TrajectoryPoint]


class QueueSample(BaseModel):
    time: float
    queue: int


class StopInterval(BaseModel):
    vehicle_id: int
    start: float
    end: float
    duration: float
    x: float
    y: float
    region: Literal["queue", "scene"]


class QueueVisit(BaseModel):
    vehicle_id: int
    start: float
    end: float | None
    duration: float | None
    complete: bool


class Bottleneck(BaseModel):
    id: int
    x: float
    y: float
    width: float
    height: float
    vehicle_passes: int
    #: Which anonymous vehicles were measurably slowed in this cell, so the
    #: interface can highlight them and the number can be checked.
    vehicle_ids: list[int] = Field(default_factory=list, max_length=60)
    stopped_seconds: float
    mean_slowdown_seconds: float
    occupancy_seconds: float
    score: float


class TrafficEvent(BaseModel):
    time: float
    kind: str
    label: str
    value: float | None = None


class Summary(BaseModel):
    vehicles_detected: int
    vehicles_tracked: int
    vehicles_processed: int
    vehicles_incomplete: int
    peak_queue: int | None = None
    average_queue: float | None = None
    median_queue: float | None = None
    queue_duration_seconds: float | None = None
    average_wait_seconds: float | None = None
    median_wait_seconds: float | None = None
    max_wait_seconds: float | None = None
    #: Mean time vehicles spent inside the queue region, slow or not.
    average_region_seconds: float | None = None
    throughput_per_minute: float | None = None
    entry_per_minute: float | None = None
    mean_traversal_seconds: float | None = None
    mean_stopped_seconds: float | None = None
    bottleneck_count: int = 0
    completed_queue_visits: int = 0
    censored_queue_visits: int = 0


class Calibration(BaseModel):
    """Parameters handed to the digital twin, all derived from the footage."""

    arrival_rate_per_minute: float
    mean_arrival_headway_seconds: float
    service_time_seconds: float
    mean_traversal_seconds: float
    free_flow_seconds: float
    mean_queue_visit_seconds: float
    observation_seconds: float
    vehicles_used: int
    notes: list[str] = Field(default_factory=list)


class HeatCell(BaseModel):
    """One cell of the bottleneck grid, used for the heat map overlay."""

    x: float
    y: float
    width: float
    height: float
    value: float
    vehicle_passes: int


class Evidence(BaseModel):
    """The facts a reader needs before trusting the numbers.

    Everything here is a count or a derived share, never a score: there is no
    "confidence" figure, because none has been computed.  Every field has a
    default so a result stored by an older build still loads.
    """

    observation_seconds: float = 0.0
    sampling_fps: float = 0.0
    vehicles_detected: int = 0
    vehicles_tracked: int = 0
    vehicles_crossed_entry: int = 0
    vehicles_crossed_exit: int = 0
    completed_queue_visits: int = 0
    censored_queue_visits: int = 0
    censored_seconds: float = 0.0
    registered_stops: int = 0
    slow_seconds_total: float = 0.0
    tracks: int = 0
    short_fragments: int = 0
    #: Sample-to-sample breaks longer than 2.5 sampling intervals.
    gaps: int = 0
    missing_sample_share: float = 0.0

    @property
    def evidence_is_thin(self) -> bool:
        return self.vehicles_tracked < 5 or self.missing_sample_share > 0.15


class SampleProvenance(BaseModel):
    """Credits and processing context for a read-only, real-video example."""

    title: str
    description: str
    author: str
    source_url: str
    license: str
    license_url: str
    processing_notes: list[str]
    video_url: str
    annotated_video_url: str
    poster_url: str


class Analysis(BaseModel):
    analysis_id: str
    source: Source
    video: VideoInfo
    regions: Regions
    summary: Summary
    calibration: Calibration
    evidence: Evidence = Field(default_factory=Evidence)
    trajectories: list[Trajectory] = Field(default_factory=list)
    queue_timeseries: list[QueueSample] = Field(default_factory=list)
    #: Vehicles geometrically inside the queue region at each instant, ignoring
    #: speed.  This is the quantity a human annotator can reproduce by pausing
    #: the frame, and the validation script compares against it.
    #: Defaulted so results stored by earlier builds still load.
    region_occupancy_timeseries: list[QueueSample] = Field(default_factory=list)
    bottlenecks: list[Bottleneck] = Field(default_factory=list)
    heat_grid: list[HeatCell] = Field(default_factory=list)
    events: list[TrafficEvent] = Field(default_factory=list)
    stops: list[StopInterval] = Field(default_factory=list)
    queue_visits: list[QueueVisit] = Field(default_factory=list)
    arrivals: list[float] = Field(default_factory=list)
    departures: list[float] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: float
    sample: SampleProvenance | None = None


class StageStatus(BaseModel):
    key: str
    label: str
    status: Literal["pending", "active", "done", "error"] = "pending"
    progress: float = 0.0
    detail: str | None = None


class JobStatus(BaseModel):
    analysis_id: str
    status: JobState
    stage: str
    progress: float
    stages: list[StageStatus]
    error: str | None = None
    hint: str | None = None
    video: VideoInfo | None = None
    created_at: float
    updated_at: float


class AnalysisListItem(BaseModel):
    analysis_id: str
    filename: str
    source: Source
    status: str
    created_at: float
    duration: float
    vehicles_tracked: int
    peak_queue: int | None = None
    throughput_per_minute: float | None = None
    read_only: bool = False


class Scenario(BaseModel):
    """Adjustable simulation inputs (all relative to the observed baseline)."""

    #: 0.5 - 1.5, fraction of the observed vehicle count.
    volume: float = Field(default=1.0, ge=0.5, le=1.5)
    #: > 1 means faster exit processing (shorter service time).
    service_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)
    #: Extra seconds the arrival sequence is stretched over (0 = observed).
    spread_seconds: float = Field(default=0.0, ge=0.0, le=300.0)
    #: Number of parallel exit processing channels (1 = observed).
    channels: int = Field(default=1, ge=1, le=2)
    seed: int = Field(default=20240517, ge=0, le=2**31 - 1)


class SimulationMetrics(BaseModel):
    vehicles: int
    peak_queue: int
    average_queue: float
    average_wait_seconds: float
    max_wait_seconds: float
    throughput_per_minute: float
    total_delay_seconds: float
    observation_seconds: float
    #: Vehicles still inside the corridor when the window ends.  A non-zero
    #: value means the scenario has not finished discharging by the end of the
    #: observation window, which limits any comparison of throughput.
    vehicles_left_at_window_end: int = 0


class MetricDelta(BaseModel):
    metric: str
    label: str
    unit: str
    observed: float
    simulated: float
    absolute: float
    percent: float | None
    lower_is_better: bool = True


class SimulatedTrack(BaseModel):
    vehicle_id: int
    arrival: float
    departure: float | None
    wait: float | None
    points: list[list[float]] = Field(default_factory=list)


class ModelFidelity(BaseModel):
    """How well the *unmodified* model reproduces the observed clip.

    Reported next to every scenario so the numbers are read as "what this model
    says", not as a measurement of the real site.
    """

    peak_queue_observed: float
    peak_queue_model: float
    average_wait_observed: float
    average_wait_model: float
    ratio: float | None
    note: str


class SensitivityPoint(BaseModel):
    service_time_seconds: float
    peak_queue: int
    average_wait_seconds: float
    throughput_per_minute: float
    vehicles_left_at_window_end: int


class SensitivityRange(BaseModel):
    """Outcome of re-running the baseline under alternative service times."""

    parameter: str
    method: str
    baseline_value: float
    values: list[SensitivityPoint]
    peak_queue_range: tuple[int, int]
    average_wait_range: tuple[float, float]
    note: str


class SimulationResult(BaseModel):
    """Three-way comparison: A observed, B baseline model, C modified model.

    ``observed`` is what the camera measured, ``baseline`` is the unmodified
    model replaying the same arrivals, ``simulated`` is the model with the
    scenario applied.  ``deltas`` therefore measures the *scenario effect*
    (C vs B) and ``model_deltas`` the *model mismatch* (B vs A) - the two are
    never mixed together.
    """

    analysis_id: str
    scenario: Scenario
    calibration: Calibration
    observed: SimulationMetrics
    baseline: SimulationMetrics
    simulated: SimulationMetrics
    fidelity: ModelFidelity
    #: Sensitivity range for the one estimated parameter, exit service time.
    #: A range of model outcomes under stated alternative values, not a
    #: statistical confidence interval.
    sensitivity: SensitivityRange | None = None
    deltas: list[MetricDelta]
    model_deltas: list[MetricDelta]
    observed_queue: list[QueueSample]
    baseline_queue: list[QueueSample]
    simulated_queue: list[QueueSample]
    #: Downsampled vehicle paths of the modified run, for the corridor animation.
    tracks: list[SimulatedTrack]
    #: The same for the baseline, so both can be replayed on one clock.
    baseline_tracks: list[SimulatedTrack] = Field(default_factory=list)
    notes: list[str]
    disclaimer: str


class DeleteResult(BaseModel):
    """What a delete actually removed - the UI shows these numbers."""

    analysis_id: str
    deleted_files: int
    bytes_freed: int
    message: str


class ExportManifest(BaseModel):
    """Describes an export so the file is self-explanatory when re-opened."""

    analysis_id: str
    source: Source
    generated_at: float
    contains_video: bool = False
    contains_trajectory_samples: bool
    privacy_note: str
    definitions: dict[str, str]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    model_loaded: bool
    device: str
    model_name: str
    message: str | None = None
    processing_mode: Literal["local", "queue"] = "local"
