"""Analysis orchestrator: tracks + regions -> the complete result object.

This is the single place where the metrics are defined and assembled, so the
live pipeline, the "recompute after drawing a region" endpoint and the demo
dataset all produce identically shaped results.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from statistics import fmean

import numpy as np

from ..config import settings
from ..models.schemas import (
    Analysis,
    Regions,
    Source,
    StopInterval,
    Summary,
    Trajectory,
    VideoInfo,
)
from ..simulation.traffic_model import calibrate
from .bottlenecks import analyze_grid, heat_cells
from .events import build_events
from .geometry import point_in_polygon
from .motion import detect_stops, mean_or_none, path_length
from .queue_detection import build_queue_series, max_track_gap, visits_from_episodes
from .throughput import Crossings, collect_crossings, flow_statistics, rolling_rate
from .wait_time import WaitStats, wait_statistics

#: Rolling window used to describe throughput over time (seconds).
ROLLING_WINDOW = 30.0
#: At most this many queue samples are returned to the client.
MAX_QUEUE_SAMPLES = 900


def build_analysis(
    analysis_id: str,
    video: VideoInfo,
    tracks: list[Trajectory],
    regions: Regions,
    source: Source = "video",
    created_at: float | None = None,
    min_track_points: int | None = None,
) -> Analysis:
    """Measure one clip.

    ``tracks`` may contain short detection fragments; tracks shorter than
    ``min_track_points`` samples are counted as *detected* but not *tracked*.
    """
    minimum = min_track_points if min_track_points is not None else settings.min_track_points
    duration = video.duration
    step = 1.0 / max(1.0, min(regions.sample_fps, video.fps or regions.sample_fps))
    max_gap = max_track_gap(step)

    detected = len(tracks)
    kept = [track for track in tracks if len(track.points) >= minimum]
    kept.sort(key=lambda track: track.vehicle_id)

    # --- 1. per-vehicle motion statistics ---------------------------------
    stops: list[StopInterval] = []
    for track in kept:
        track.path_length = round(path_length(track.points), 5)
        track_stops = detect_stops(track, regions.speed_threshold, regions.min_stop_seconds, max_gap, regions.queue)
        stops.extend(track_stops)
        track.stopped_seconds = round(sum(stop.duration for stop in track_stops), 2)
        track.mean_speed = round(mean_or_none([point.speed for point in track.points]) or 0.0, 5)
        track.first_seen = track.points[0].time
        track.last_seen = track.points[-1].time
        track.duration = round(track.last_seen - track.first_seen, 2)

    # --- 2. queue series and queue episodes -------------------------------
    series = build_queue_series(kept, regions, duration, step)
    episodes = series.episodes if series else []
    for track in kept:
        track.queue_seconds = round(
            sum(episode.duration for episode in episodes if episode.vehicle_id == track.vehicle_id), 2
        )
        # Region residence: time inside the queue polygon whether or not the
        # vehicle was moving.  Reported separately from the wait so the two are
        # never confused.
        track.region_seconds = round(_region_seconds(track.points, regions, max_gap), 2)
    waits = wait_statistics(episodes)

    # --- 3. entry / exit line crossings -----------------------------------
    entry = collect_crossings(kept, regions.entry, step, regions.entry_direction)
    exit_ = collect_crossings(kept, regions.exit, step, regions.exit_direction)
    # The window in which a queue was present: the exit ran at full capacity
    # there, which is what calibrates the service rate of the digital twin.
    busy_window = _busy_window(series, exit_.times)
    entry_stats = flow_statistics(entry, duration)
    exit_stats = flow_statistics(exit_, duration, busy_window)
    # A missing line means "not measured", which is None - not zero.
    entry_rate = entry_stats.per_minute if entry.available else None
    exit_rate = exit_stats.per_minute if exit_.available else None
    # A missing entry line *or* a line nobody crossed falls back to first
    # sightings, so the digital twin always has an arrival pattern to replay.
    if entry.available and entry.times:
        arrivals = entry.times
    else:
        arrivals = [track.first_seen for track in kept]
    rolling = rolling_rate(exit_.times, ROLLING_WINDOW, max(step, 1.0))

    # --- 4. bottlenecks ----------------------------------------------------
    cells, bottlenecks = analyze_grid(
        tracks=kept,
        regions=regions,
        stops=stops,
        cols=settings.bottleneck_cols,
        rows=settings.bottleneck_rows,
        max_gap=max_gap,
        min_passes=settings.bottleneck_min_passes,
        max_cells=settings.bottleneck_max_cells,
    )

    # --- 5. event timeline -------------------------------------------------
    events = build_events(
        queue_series=series.to_samples() if series else [],
        rolling_rates=rolling,
        arrival_times=arrivals,
        stops=stops,
        peak_queue=series.peak if series else 0,
        duration=duration,
    )

    # --- 6. digital twin calibration --------------------------------------
    traversals = [track.duration for track in kept if track.duration > 0]
    free_flow_candidates = [
        track.duration for track in kept if track.queue_seconds <= 1e-6 and track.duration > 0
    ]
    calibration = calibrate(
        observation_seconds=duration,
        arrival_times=arrivals,
        departure_times=exit_.times,
        departure_capacity_headway=exit_stats.capacity_headway,
        traversals=traversals,
        free_flow_candidates=free_flow_candidates,
        mean_wait_seconds=waits.average,
        vehicles_used=len(kept),
    )

    summary = _summary(
        detected=detected,
        kept=kept,
        series=series,
        waits=waits,
        entry_rate=entry_rate,
        exit_rate=exit_rate,
        exit_count=exit_.count,
        traversals=traversals,
        stops=stops,
        bottlenecks=bottlenecks,
        censored=waits.censored,
    )

    analysis = Analysis(
        analysis_id=analysis_id,
        source=source,
        video=video,
        regions=regions,
        summary=summary,
        calibration=calibration,
        trajectories=kept,
        queue_timeseries=series.to_samples(MAX_QUEUE_SAMPLES) if series else [],
        bottlenecks=bottlenecks,
        events=events,
        stops=sorted(stops, key=lambda stop: stop.start),
        queue_visits=visits_from_episodes(episodes),
        arrivals=[round(value, 3) for value in sorted(arrivals)],
        departures=[round(value, 3) for value in exit_.times],
        warnings=_warnings(regions, detected, kept, exit_.available, entry, waits),
        created_at=created_at if created_at is not None else time.time(),
        heat_grid=heat_cells(cells),
    )
    return analysis


#: Key used to keep the *unfiltered* tracks inside the stored result file.
#: Re-measuring after a region change must see exactly the same input as the
#: first run, otherwise "vehicles detected" would silently change.
RAW_TRACKS_KEY = "__raw_tracks__"


def serialise_analysis(analysis: Analysis, raw_tracks: Sequence[Trajectory] | None = None) -> dict:
    """JSON payload for storage, optionally keeping every raw track."""
    payload = analysis.model_dump(mode="json")
    if raw_tracks is not None:
        payload[RAW_TRACKS_KEY] = [track.model_dump(mode="json") for track in raw_tracks]
    return payload


def deserialise_analysis(payload: dict) -> tuple[Analysis, list[Trajectory]]:
    """Split a stored payload into the analysis and the tracks to re-measure."""
    data = dict(payload)
    raw = data.pop(RAW_TRACKS_KEY, None)
    analysis = Analysis.model_validate(data)
    tracks = (
        [Trajectory.model_validate(item) for item in raw] if raw else analysis.trajectories
    )
    return analysis, tracks


#: A queue of one vehicle is ambiguous (a car pausing at a kerb looks the same
#: as a car joining a queue), so the exit capacity is only measured while at
#: least this many vehicles are waiting.
MIN_BUSY_QUEUE = 2


def _region_seconds(points, regions: Regions, max_gap: float) -> float:
    """Seconds a track spent inside the queue polygon, moving or not."""
    if not regions.has_queue:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        a, b = points[index], points[index + 1]
        gap = b.time - a.time
        if gap <= 0 or gap > max_gap:
            continue
        if point_in_polygon((a.x, a.y), regions.queue) and point_in_polygon(
            (b.x, b.y), regions.queue
        ):
            total += gap
    return total


def _busy_window(series, departures: list[float]) -> tuple[float, float] | None:
    """Saturation window: the period during which the exit is at full capacity.

    Measured the same way a traffic engineer measures saturation flow: take the
    longest stretch where a real queue existed, and stop as soon as the queue
    has been **half discharged**.  Until that moment the exit - not the arrival
    rate - is what limits the system, so ``window / departures`` is the service
    time of the gate.  Including the tail of the episode would measure the
    arrival rate instead.
    """
    if series is None or series.counts.size == 0 or len(departures) < 2:
        return None
    busy = series.counts >= MIN_BUSY_QUEUE
    if not busy.any():
        return None

    # Longest contiguous run of "a queue exists".
    best_start = best_end = current_start = None
    for index, flag in enumerate(busy):
        if flag and current_start is None:
            current_start = index
        elif not flag and current_start is not None:
            if best_start is None or index - current_start > best_end - best_start:
                best_start, best_end = current_start, index - 1
            current_start = None
    if current_start is not None and (
        best_start is None or len(busy) - current_start > best_end - best_start
    ):
        best_start, best_end = current_start, len(busy) - 1
    if best_start is None or best_end is None or best_end <= best_start:
        return None

    counts = series.counts[best_start : best_end + 1]
    peak_index = int(np.argmax(counts))
    half = counts[peak_index] / 2.0
    # Search forward from the peak (an early dip must not end the window).
    stop = best_end
    for offset in range(peak_index + 1, len(counts)):
        if counts[offset] < half:
            stop = best_start + offset
            break
    if stop <= best_start:
        return None
    return (float(series.times[best_start]), float(series.times[stop]))


def _summary(
    *,
    detected: int,
    kept: list[Trajectory],
    series,
    waits,
    entry_rate: float | None,
    exit_rate: float | None,
    exit_count: int,
    traversals: list[float],
    stops: list[StopInterval],
    bottlenecks: list,
    censored: int,
) -> Summary:
    stopped_per_vehicle = [track.stopped_seconds for track in kept]
    return Summary(
        vehicles_detected=detected,
        vehicles_tracked=len(kept),
        vehicles_processed=exit_count,
        vehicles_incomplete=censored,
        peak_queue=series.peak if series else None,
        average_queue=round(series.average, 2) if series else None,
        median_queue=round(series.median_value, 2) if series else None,
        queue_duration_seconds=round(series.occupied_seconds, 2) if series else None,
        average_wait_seconds=waits.average,
        median_wait_seconds=waits.median,
        max_wait_seconds=waits.maximum,
        average_region_seconds=(
            round(fmean(track.region_seconds for track in kept if track.region_seconds > 0), 2)
            if any(track.region_seconds > 0 for track in kept)
            else None
        ),
        throughput_per_minute=round(exit_rate, 2) if exit_rate is not None else None,
        entry_per_minute=round(entry_rate, 2) if entry_rate is not None else None,
        mean_traversal_seconds=round(fmean(traversals), 2) if traversals else None,
        mean_stopped_seconds=round(fmean(stopped_per_vehicle), 2) if stopped_per_vehicle else None,
        bottleneck_count=len(bottlenecks),
        completed_queue_visits=waits.count,
        censored_queue_visits=waits.censored,
    )


def _warnings(
    regions: Regions,
    detected: int,
    kept: list[Trajectory],
    exit_available: bool,
    entry: Crossings,
    waits: WaitStats,
) -> list[str]:
    """User-facing caveats.  Every measurement that is missing says why."""
    messages: list[str] = []
    if not kept:
        messages.append(
            "No vehicles were detected in this video. Try footage with a fixed camera, "
            "better lighting, a visible roadway, and vehicles filling more of the frame."
        )
        return messages
    if not regions.has_queue:
        messages.append("No queue region is defined, so queue length and wait time are unavailable.")
    if not exit_available:
        messages.append("No exit line is defined, so throughput cannot be measured.")
    if not entry.available:
        messages.append(
            "No entry line is defined, so arrival times fall back to first sightings "
            "and the simulated arrival pattern is approximate."
        )
    elif not entry.times:
        messages.append(
            "No vehicle crossed the entry line; arrival times fall back to first sightings, "
            "so the simulated arrival pattern is approximate."
        )
    if waits.censored:
        messages.append(
            f"{waits.censored} queue visit(s) were still in progress when the clip ended "
            "and are excluded from wait averages."
        )
    lost = detected - len(kept)
    if lost > 0:
        messages.append(
            f"{lost} short detection fragment(s) were discarded as noise "
            f"(fewer than {settings.min_track_points} samples)."
        )
    return messages


