"""Algorithmic event timeline.

Every entry is produced by a threshold rule on the measured time series - no
model, no natural language generation.  Each rule is a small, readable function
so a reader can predict the timeline from the charts.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import median

import numpy as np

from ..models.schemas import QueueSample, StopInterval, TrafficEvent


def _first_where(series: Sequence[QueueSample], predicate) -> float | None:
    for sample in series:
        if predicate(sample.queue):
            return sample.time
    return None


def _plural(count: int) -> str:
    return "vehicle" if count == 1 else "vehicles"


def build_events(
    queue_series: Sequence[QueueSample],
    rolling_rates: Sequence[tuple[float, float]],
    arrival_times: Sequence[float],
    stops: Sequence[StopInterval],
    peak_queue: int,
    duration: float,
) -> list[TrafficEvent]:
    events: list[TrafficEvent] = []

    if arrival_times:
        events.append(
            TrafficEvent(
                time=round(arrival_times[0], 2),
                kind="first_arrival",
                label="First tracked vehicle appeared in the measurement area",
                value=round(arrival_times[0], 2),
            )
        )

    if queue_series and peak_queue > 0:
        # Threshold milestones scale with the observed peak so short clips do
        # not produce meaningless "queue of 10" events.
        milestone = max(3, round(peak_queue * 0.5))
        moment = _first_where(queue_series, lambda q: q >= milestone)
        if moment is not None:
            events.append(
                TrafficEvent(
                    time=moment,
                    kind="queue_threshold",
                    label=f"Queue exceeded {milestone} {_plural(milestone)}",
                    value=float(milestone),
                )
            )
        peak_time = _first_where(queue_series, lambda q: q >= peak_queue)
        if peak_time is not None:
            events.append(
                TrafficEvent(
                    time=peak_time,
                    kind="peak",
                    label=f"Peak queue reached: {peak_queue} {_plural(peak_queue)}",
                    value=float(peak_queue),
                )
            )
        clearing = _first_where(
            queue_series, lambda q: q < max(2, peak_queue * 0.5)
        )
        if clearing is not None and peak_time is not None and clearing > peak_time:
            events.append(
                TrafficEvent(
                    time=clearing,
                    kind="clearing",
                    label="Queue began clearing",
                    value=float(peak_queue),
                )
            )
        empty = _first_where(queue_series, lambda q: q == 0)
        if empty is not None and peak_time is not None and empty > peak_time:
            events.append(
                TrafficEvent(
                    time=empty,
                    kind="cleared",
                    label="Queue cleared",
                    value=0.0,
                )
            )

    dip = _throughput_dip(rolling_rates)
    if dip is not None:
        moment, value = dip
        events.append(
            TrafficEvent(
                time=moment,
                kind="throughput_dip",
                label="Throughput fell below half of the rolling baseline",
                value=value,
            )
        )

    if stops:
        longest = max(stops, key=lambda stop: stop.duration)
        events.append(
            TrafficEvent(
                time=round(longest.start, 2),
                kind="longest_stop",
                label=(
                    f"Longest observed stop: {longest.duration:.1f}s "
                    f"(Vehicle {longest.vehicle_id:03d}, {longest.region} area)"
                ),
                value=round(longest.duration, 2),
            )
        )

    events = [event for event in events if 0.0 <= event.time <= duration + 1e-6]
    events.sort(key=lambda event: (event.time, event.kind))
    return events


def _throughput_dip(rolling_rates: Sequence[tuple[float, float]]) -> tuple[float, float] | None:
    """First time the rolling rate drops under half of the window's median."""
    values = [rate for _, rate in rolling_rates]
    if len(values) < 4:
        return None
    baseline = median(values)
    if baseline <= 0:
        return None
    threshold = baseline * 0.5
    for index, (moment, rate) in enumerate(rolling_rates):
        if rate < threshold and 0 < index < len(rolling_rates) - 1:
            window = np.array(values[max(0, index - 1) : index + 2])
            if rate == window.min():
                return moment, rate
    return None
