"""Timeline data for the synchronised replay.

The analysis endpoint returns trajectories thinned for the map, which is fine
for drawing a path but *not* for replay: after thinning, the interval between
consecutive samples can exceed the tracking-gap threshold, so a genuine
one-sample dropout becomes indistinguishable from the thinning itself.  A
replay built on that would invent motion across a gap and claim to know a
position it does not know.

This module builds the representation the player needs instead:

* samples are taken on a uniform time grid, so the wire format has a known
  resolution regardless of track length;
* every track is split into **segments** at tracking gaps, and the gap between
  two segments means *the position is unknown there* - the client must not
  draw motion across it and must not show a vehicle inside it.

The queue series is recomputed from the same full-resolution tracks at the
analysis' own sampling rate and then picked at the nearest instant, so the
replay curve cannot disagree with the reported peak queue.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise
from math import floor
from typing import Any

import numpy as np

from ..models.schemas import Regions, Trajectory
from .queue_detection import build_queue_series, max_track_gap

#: Default transport resolution for the replay, in samples per second.
DEFAULT_HZ = 4.0
MAX_HZ = 15.0
MIN_HZ = 1.0
#: Upper bound on vehicles returned, to keep a pathological clip responsive.
MAX_VEHICLES = 400


def _segments_for(
    points: Sequence, max_gap: float
) -> list[tuple[list[float], list[float], list[float]]]:
    """Split one track into (times, xs, ys) segments at tracking gaps."""
    if not points:
        return []
    times: list[float] = [points[0].time]
    xs: list[float] = [points[0].x]
    ys: list[float] = [points[0].y]
    segments: list[tuple[list[float], list[float], list[float]]] = []
    for previous, current in pairwise(points):
        gap = current.time - previous.time
        if gap <= 0 or gap > max_gap:
            # The track was lost: close this segment and start a new one.
            segments.append((times, xs, ys))
            times, xs, ys = [], [], []
        times.append(current.time)
        xs.append(current.x)
        ys.append(current.y)
    if times:
        segments.append((times, xs, ys))
    return segments


def _resample_segment(
    times: Sequence[float], xs: Sequence[float], ys: Sequence[float], step: float
) -> tuple[list[float], list[float], list[float]]:
    """Uniform-in-time resampling of one contiguous segment.

    Linear interpolation inside a segment is legitimate: the vehicle really did
    travel between two samples that are at most ``2.5 / sampling_fps`` apart.
    It is only ever applied *within* a segment, never across a gap.
    """
    if len(times) < 2:
        return [round(t, 3) for t in times], [round(x, 5) for x in xs], [round(y, 5) for y in ys]
    start, end = times[0], times[-1]
    count = max(1, floor((end - start) / step + 1e-9) + 1)
    out_t: list[float] = []
    out_x: list[float] = []
    out_y: list[float] = []
    index = 0
    for k in range(count):
        moment = start + k * step
        if moment > end + 1e-9:
            break
        while index + 1 < len(times) and times[index + 1] < moment:
            index += 1
        if index + 1 >= len(times):
            out_t.append(round(moment, 3))
            out_x.append(round(xs[-1], 5))
            out_y.append(round(ys[-1], 5))
            continue
        span = times[index + 1] - times[index]
        fraction = 0.0 if span <= 0 else (moment - times[index]) / span
        out_t.append(round(moment, 3))
        out_x.append(round(xs[index] + fraction * (xs[index + 1] - xs[index]), 5))
        out_y.append(round(ys[index] + fraction * (ys[index + 1] - ys[index]), 5))
    # Floating point can leave the final sample just short of the true end, and
    # the player should be able to seek to the last known position.
    if not out_t or (end - out_t[-1]) > step * 0.5:
        out_t.append(round(end, 3))
        out_x.append(round(xs[-1], 5))
        out_y.append(round(ys[-1], 5))
    return out_t, out_x, out_y


def build_timeline(
    tracks: Sequence[Trajectory],
    regions: Regions,
    duration: float,
    hz: float = DEFAULT_HZ,
) -> dict[str, Any]:
    """Build the replay payload for one analysis.

    ``tracks`` must be the **full-resolution** trajectories (the stored ones),
    not the thinned copies sent to the map.
    """
    hz = max(MIN_HZ, min(MAX_HZ, hz))
    sample_fps = max(1e-6, float(regions.sample_fps))
    step = 1.0 / hz
    max_gap = max_track_gap(1.0 / sample_fps)

    # Queue at the analysis' own resolution, then pick the nearest sample for
    # transport: this keeps the curve identical to the reported metrics.
    native = build_queue_series(tracks, regions, duration, 1.0 / sample_fps)
    native_times: np.ndarray = native.times if native else np.array([])
    native_counts: np.ndarray = native.counts if native else np.array([])
    queue: list[dict[str, Any]] = []
    if native_times.size:
        cursor = 0
        moment = 0.0
        while moment < duration:
            while cursor + 1 < native_times.size and native_times[cursor + 1] < moment:
                cursor += 1
            queue.append({"t": round(moment, 3), "q": int(native_counts[cursor])})
            moment += step

    ordered = sorted(tracks, key=lambda t: t.vehicle_id)[:MAX_VEHICLES]
    vehicles: list[dict[str, Any]] = []
    total_gaps = 0
    for track in ordered:
        segments = []
        for times, xs, ys in _segments_for(track.points, max_gap):
            if not times:
                continue
            resampled_t, resampled_x, resampled_y = _resample_segment(times, xs, ys, step)
            segments.append({"t": resampled_t, "x": resampled_x, "y": resampled_y})
        if len(segments) > 1:
            total_gaps += len(segments) - 1
        if segments:
            vehicles.append(
                {
                    "id": track.vehicle_id,
                    "class": track.vehicle_class,
                    "queue_seconds": track.queue_seconds,
                    "stopped_seconds": track.stopped_seconds,
                    "segments": segments,
                }
            )

    return {
        "duration": round(duration, 3),
        "hz": hz,
        "sampling_fps": round(sample_fps, 3),
        "gap_threshold_s": round(max_gap, 3),
        "track_gaps": total_gaps,
        "vehicles": vehicles,
        "queue": queue,
        "vehicles_omitted": max(0, len(tracks) - len(ordered)),
        "note": (
            "Samples are uniform in time. A track is split into several segments "
            "where tracking was lost: the position is unknown in between, so no "
            "motion is drawn and no vehicle is shown there."
        ),
    }
