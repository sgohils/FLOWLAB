"""Result export.

Two rules shape this module:

1. **An export never contains footage.**  No video, no thumbnail, no frame.  A
   CSV is made of numbers that were derived from the video, not of the video.
2. **Every export is self-describing.**  The file carries the definitions used
   to compute each column, the regions in force, the model configuration and a
   privacy note, so that someone opening it in six months knows what the numbers
   mean and where they came from.

The default export is *metadata*: summary, calibration, events, bottlenecks and
per-vehicle measurements.  Trajectory samples are opt-in via ``include_points``
because they are large and, for most uses, unnecessary.
"""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass
from typing import Any

from ..models.schemas import Analysis, ExportManifest

#: Column definitions shipped with every export, so the file explains itself.
TRAJECTORY_COLUMNS = [
    "vehicle_id",
    "vehicle_class",
    "first_seen_s",
    "last_seen_s",
    "traversal_s",
    "path_length_frame_widths",
    "slow_time_s",
    "queue_region_slow_s",
    "queue_region_total_s",
    "complete_visits",
    "censored_visits",
    "mean_motion_frame_widths_per_s",
]

QUEUE_COLUMNS = ["time_s", "queue_length"]

DEFINITIONS = {
    "traversal_s": "last tracked sample minus first tracked sample of the same id",
    "path_length_frame_widths": (
        "sum of sample-to-sample distances in normalised image coordinates, "
        "where 1.0 equals the full frame width (no real-world scale)"
    ),
    "slow_time_s": (
        "time below the motion threshold anywhere in the frame, in intervals of "
        "at least min_stop_seconds"
    ),
    "queue_region_slow_s": (
        "estimated wait: time inside the queue region while below the motion "
        "threshold, for at least min_queue_seconds, completed visits only"
    ),
    "queue_region_total_s": "time inside the queue region, moving or not",
    "mean_motion_frame_widths_per_s": (
        "mean speed proxy in frame widths per second; NOT a physical speed, the "
        "camera is not calibrated"
    ),
    "queue_length": (
        "number of vehicles inside the queue region and below the motion "
        "threshold at that instant"
    ),
    "complete_visits": "queue visits that both started and ended inside the clip",
    "censored_visits": (
        "queue visits with an unknown start (vehicle already queueing at the "
        "first frame) or unknown end (still queueing at the last frame)"
    ),
    "peak_queue_vehicles": "largest simultaneous count of queued vehicles",
    "average_queue_vehicles": "time-average of the queue length over the clip",
    "average_wait_s": "mean of the completed queue visits (see queue_region_slow_s)",
    "max_wait_s": "longest completed queue visit",
    "average_queue_region_time_s": "mean time vehicles spend inside the region, moving or not",
    "throughput_veh_per_min": (
        "vehicles crossing the exit line divided by the clip duration in minutes"
    ),
    "entry_veh_per_min": (
        "vehicles crossing the entry line divided by the clip duration in minutes"
    ),
    "vehicles_crossed_exit": "vehicles whose trajectory crossed the exit line",
}

PRIVACY_NOTE = (
    "This export contains derived measurements only. It contains no video, no "
    "image, no face and no number plate data. The original filename and the "
    "local file paths are omitted because a filename can contain identifying "
    "information. Vehicle ids are anonymous labels created for a single "
    "analysis and are not linked to any person or vehicle."
)

#: Video fields kept in an export.  ``filename``, ``annotated_path`` and
#: ``annotated_url`` are dropped on purpose - a filename such as
#: "St Marys dismissal 2026-03-04.mp4" is identifying metadata.
VIDEO_FIELDS = ("duration", "fps", "width", "height", "frame_count", "processed_fps", "size_bytes")


@dataclass(frozen=True, slots=True)
class ExportBundle:
    """One export rendered as bytes plus a suggested filename."""

    filename: str
    media_type: str
    content: bytes


def build_summary_json(analysis: Analysis, include_points: bool = False) -> ExportBundle:
    """The full result as a single JSON document (no raw points by default)."""
    payload = analysis.model_dump(mode="json")
    if not include_points:
        for track in payload["trajectories"]:
            track["points"] = []
    # Strip identifying file metadata from the copy that leaves the machine.
    payload["video"] = {
        key: payload["video"][key]
        for key in VIDEO_FIELDS
        if key in payload["video"]
    }
    payload["video"]["source"] = "uploaded clip (filename omitted from export)"
    manifest = ExportManifest(
        analysis_id=analysis.analysis_id,
        source=analysis.source,
        generated_at=time.time(),
        contains_trajectory_samples=include_points,
        privacy_note=PRIVACY_NOTE,
        definitions=DEFINITIONS,
    )
    body = {
        "manifest": manifest.model_dump(mode="json"),
        "analysis": payload,
    }
    content = json.dumps(body, indent=2, separators=(",", ": ")).encode("utf-8")
    return ExportBundle(
        filename=f"flowlab-{analysis.analysis_id}-summary.json",
        media_type="application/json",
        content=content,
    )


def build_trajectories_csv(analysis: Analysis) -> ExportBundle:
    """One row per vehicle: durations, queue times and censoring counts."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(TRAJECTORY_COLUMNS)
    writer.writerow(["# units: seconds, frame widths, frame widths per second"])
    for track in sorted(analysis.trajectories, key=lambda t: t.vehicle_id):
        completed = sum(
            1
            for visit in analysis.queue_visits
            if visit.vehicle_id == track.vehicle_id and visit.complete
        )
        censored = sum(
            1
            for visit in analysis.queue_visits
            if visit.vehicle_id == track.vehicle_id and not visit.complete
        )
        writer.writerow(
            [
                track.vehicle_id,
                track.vehicle_class,
                f"{track.first_seen:.2f}",
                f"{track.last_seen:.2f}",
                f"{track.duration:.2f}",
                f"{track.path_length:.4f}",
                f"{track.stopped_seconds:.2f}",
                f"{track.queue_seconds:.2f}",
                f"{track.region_seconds:.2f}",
                completed,
                censored,
                f"{track.mean_speed:.4f}",
            ]
        )
    return ExportBundle(
        filename=f"flowlab-{analysis.analysis_id}-vehicles.csv",
        media_type="text/csv",
        content=buffer.getvalue().encode("utf-8"),
    )


def build_queue_csv(analysis: Analysis) -> ExportBundle:
    """The queue length time series and the events that were derived from it."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(QUEUE_COLUMNS)
    for sample in analysis.queue_timeseries:
        writer.writerow([f"{sample.time:.2f}", sample.queue])
    return ExportBundle(
        filename=f"flowlab-{analysis.analysis_id}-queue.csv",
        media_type="text/csv",
        content=buffer.getvalue().encode("utf-8"),
    )


def build_events_csv(analysis: Analysis) -> ExportBundle:
    """Events, bottlenecks and stops - the evidence behind the headline numbers."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["time_s", "kind", "label", "value"])
    for event in analysis.events:
        writer.writerow([f"{event.time:.2f}", event.kind, event.label, event.value])
    writer.writerow([])
    writer.writerow(["# bottlenecks (rank, not severity)"])
    writer.writerow(
        [
            "rank",
            "x_normalised",
            "y_normalised",
            "distinct_vehicles",
            "slow_time_s",
            "mean_slow_s_per_vehicle",
        ]
    )
    for bottleneck in analysis.bottlenecks:
        writer.writerow(
            [
                bottleneck.id,
                f"{bottleneck.x:.4f}",
                f"{bottleneck.y:.4f}",
                bottleneck.vehicle_passes,
                f"{bottleneck.stopped_seconds:.2f}",
                f"{bottleneck.mean_slowdown_seconds:.2f}",
            ]
        )
    writer.writerow([])
    writer.writerow(["# stopped intervals (duration >= min_stop_seconds)"])
    writer.writerow(["vehicle_id", "start_s", "end_s", "duration_s", "region"])
    for stop in analysis.stops:
        writer.writerow(
            [
                stop.vehicle_id,
                f"{stop.start:.2f}",
                f"{stop.end:.2f}",
                f"{stop.duration:.2f}",
                stop.region,
            ]
        )
    return ExportBundle(
        filename=f"flowlab-{analysis.analysis_id}-events.csv",
        media_type="text/csv",
        content=buffer.getvalue().encode("utf-8"),
    )


def measurements_payload(analysis: Analysis) -> dict[str, Any]:
    """The headline numbers with their units, used by the API metadata route."""
    summary = analysis.summary
    return {
        "analysis_id": analysis.analysis_id,
        "source": analysis.source,
        "observation_window_s": analysis.video.duration,
        "vehicles_detected": summary.vehicles_detected,
        "vehicles_tracked": summary.vehicles_tracked,
        "vehicles_crossed_exit": summary.vehicles_processed,
        "peak_queue_vehicles": summary.peak_queue,
        "average_queue_vehicles": summary.average_queue,
        "average_wait_s": summary.average_wait_seconds,
        "max_wait_s": summary.max_wait_seconds,
        "average_queue_region_time_s": summary.average_region_seconds,
        "throughput_veh_per_min": summary.throughput_per_minute,
        "entry_veh_per_min": summary.entry_per_minute,
        "bottleneck_count": summary.bottleneck_count,
        "complete_queue_visits": summary.completed_queue_visits,
        "censored_queue_visits": summary.censored_queue_visits,
        "definitions": DEFINITIONS,
        "privacy_note": PRIVACY_NOTE,
    }
