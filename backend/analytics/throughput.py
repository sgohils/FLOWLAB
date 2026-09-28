"""Throughput from line crossings.

    throughput = N / dt        (vehicles per minute)

where ``N`` is the number of anonymous vehicles whose trajectory crosses the
exit line and ``dt`` is the observation window of the clip in minutes.

The same module provides the *capacity headway* (the typical gap between two
consecutive departures) which is what calibrates the exit service rate of the
digital twin.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean, median

from ..models.schemas import Trajectory
from .geometry import first_crossing_time
from .queue_detection import max_track_gap


@dataclass(frozen=True, slots=True)
class Crossings:
    """Crossing times for one measurement line."""

    times: list[float]
    per_vehicle: dict[int, float]
    available: bool

    @property
    def count(self) -> int:
        return len(self.times)


def collect_crossings(
    tracks: Sequence[Trajectory],
    line: Sequence[tuple[float, float]],
    step: float,
    direction: str = "any",
) -> Crossings:
    """First crossing of ``line`` per vehicle, honouring the counting policy."""
    if len(line) != 2:
        return Crossings(times=[], per_vehicle={}, available=False)
    max_gap = max_track_gap(step)
    per_vehicle: dict[int, float] = {}
    for track in tracks:
        moment = first_crossing_time(track.points, line, max_gap, direction=direction)
        if moment is not None:
            per_vehicle[track.vehicle_id] = moment
    return Crossings(
        times=sorted(per_vehicle.values()),
        per_vehicle=per_vehicle,
        available=True,
    )


def rate_per_minute(count: int, window_seconds: float) -> float | None:
    """Q = N / dt with dt expressed in minutes."""
    if window_seconds <= 0:
        return None
    return count * 60.0 / window_seconds


#: Rolling window used for the rolling throughput series, in seconds.
ROLLING_WINDOW = 30.0


def headways(times: Sequence[float]) -> list[float]:
    return [b - a for a, b in zip(times, times[1:]) if b - a > 0]


@dataclass(frozen=True, slots=True)
class FlowStats:
    count: int
    per_minute: float | None
    mean_headway: float | None
    median_headway: float | None
    #: Fastest quarter of the gaps - a proxy for the processing capacity.
    capacity_headway: float | None


def flow_statistics(
    crossings: Crossings,
    observation_seconds: float,
    busy_window: tuple[float, float] | None = None,
) -> FlowStats:
    """Flow numbers for one measurement line.

    ``capacity_headway`` is the *service time* of the exit, estimated as

        service_time = window / vehicles_leaving_the_window

    over a rolling window that lies entirely inside a queue episode.  While a
    queue exists the exit - not the arrival rate - limits the system, so this
    is the observed capacity.  Counting crossings (rather than measuring the
    gap between them) also makes the estimate robust to a measurement line
    that cuts across several lanes at slightly different moments.
    """
    gaps = headways(crossings.times)
    capacity: float | None = None
    if busy_window is not None and crossings.count >= 2:
        start, end = busy_window
        rates = [
            rate
            for moment, rate in rolling_rate(
                crossings.times, ROLLING_WINDOW, ROLLING_WINDOW
            )
            if moment >= start and moment + ROLLING_WINDOW <= end
        ]
        if rates:
            capacity = 60.0 / max(rates)
    if capacity is None and gaps:
        # No queue episode to measure: fall back to the fastest quarter of the
        # observed gaps, which at least bounds the capacity from below.
        ordered = sorted(gaps)
        cutoff = max(1, int(len(ordered) * 0.25))
        capacity = fmean(ordered[:cutoff])
    return FlowStats(
        count=crossings.count,
        per_minute=rate_per_minute(crossings.count, observation_seconds),
        mean_headway=fmean(gaps) if gaps else None,
        median_headway=median(gaps) if gaps else None,
        capacity_headway=capacity,
    )


def rolling_rate(times: Sequence[float], window_seconds: float, step: float) -> list[tuple[float, float]]:
    """Vehicles per minute in a sliding window, used by the event timeline."""
    if not times or window_seconds <= 0:
        return []
    series: list[tuple[float, float]] = []
    end_time = times[-1]
    moment = 0.0
    while moment <= end_time:
        start = moment
        finish = moment + window_seconds
        count = sum(1 for t in times if start <= t <= finish)
        series.append((round(moment, 3), round(count * 60.0 / window_seconds, 3)))
        moment += step
    return series
