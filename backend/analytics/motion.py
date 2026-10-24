"""Motion primitives: speed proxies and stopped-vehicle detection.

Because there is no camera calibration, speed is expressed as a *pixel-motion
proxy*: normalised units per second, i.e. the fraction of the frame width a
vehicle covers each second.  It is only ever used for comparisons
("this vehicle moved slower than that one"), never converted to km/h.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from math import hypot
from statistics import fmean

from ..models.schemas import StopInterval, Trajectory, TrajectoryPoint


def segment_speed(previous: TrajectoryPoint, point: TrajectoryPoint) -> float:
    """v = distance / dt in normalised units per second."""
    elapsed = point.time - previous.time
    if elapsed <= 0:
        return 0.0
    return hypot(point.x - previous.x, point.y - previous.y) / elapsed


def path_length(points: Sequence[TrajectoryPoint]) -> float:
    """Total travelled distance in normalised units (sum of segment lengths)."""
    return sum(
        hypot(b.x - a.x, b.y - a.y) for a, b in pairwise(points)
    )


def mean_or_none(values: Sequence[float]) -> float | None:
    return fmean(values) if len(values) else None


@dataclass(frozen=True, slots=True)
class StopSegment:
    """A contiguous slow-motion interval for a single vehicle."""

    vehicle_id: int
    start: float
    end: float
    x: float
    y: float
    in_queue: bool


def detect_stops(
    track: Trajectory,
    speed_threshold: float,
    min_stop_seconds: float,
    max_gap: float,
    queue_polygon: Sequence[tuple[float, float]] = (),
) -> list[StopInterval]:
    """Find intervals where a vehicle barely moves for at least ``min_stop_seconds``.

    A stop starts at the first sample whose motion stays below the threshold and
    ends at the first sample that exceeds it.  The interval is reported only if
    it lasted long enough, which filters out detection jitter on moving cars.
    """
    points = track.points
    stops: list[StopInterval] = []
    start_index: int | None = None
    last_index = 0

    for index in range(1, len(points)):
        previous, point = points[index - 1], points[index]
        gap = point.time - previous.time
        if gap <= 0 or gap > max_gap:
            # Track discontinuity: close the open stop and skip the gap.
            if start_index is not None:
                _append_stop(
                    stops, track, points, start_index, last_index, min_stop_seconds, queue_polygon
                )
                start_index = None
            continue
        if segment_speed(previous, point) < speed_threshold:
            if start_index is None:
                start_index, last_index = index, index
            else:
                last_index = index
        else:
            if start_index is not None:
                _append_stop(
                    stops, track, points, start_index, last_index, min_stop_seconds, queue_polygon
                )
                start_index = None
    if start_index is not None:
        _append_stop(stops, track, points, start_index, last_index, min_stop_seconds, queue_polygon)
    return stops


def _append_stop(
    stops: list[StopInterval],
    track: Trajectory,
    points: Sequence[TrajectoryPoint],
    start_index: int,
    end_index: int,
    min_stop_seconds: float,
    queue_polygon: Sequence[tuple[float, float]],
) -> None:
    from .geometry import point_in_polygon

    start_time = points[start_index - 1].time
    end_time = points[end_index].time
    duration = end_time - start_time
    if duration + 1e-9 < min_stop_seconds:
        return
    window = points[start_index : end_index + 1] or [points[end_index]]
    x = fmean(p.x for p in window)
    y = fmean(p.y for p in window)
    in_queue = bool(queue_polygon) and any(
        point_in_polygon((p.x, p.y), queue_polygon) for p in window
    )
    stops.append(
        StopInterval(
            vehicle_id=track.vehicle_id,
            start=start_time,
            end=end_time,
            duration=duration,
            x=round(x, 5),
            y=round(y, 5),
            region="queue" if in_queue else "scene",
        )
    )
