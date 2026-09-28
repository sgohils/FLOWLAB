"""Trace one displayed number back to the samples that produced it.

    python -m backend.scripts.trace_metric demo peak_queue

Prints the chain: trajectory samples -> grid counting -> summary -> API, with
the same numbers the interface shows, and verifies the peak against the raw
samples by hand.
"""

from __future__ import annotations

import argparse
import sys
from urllib.request import urlopen

import numpy as np

from ..analytics.metrics import build_analysis
from ..analytics.queue_detection import build_queue_series, max_track_gap
from ..api.state import demo_analysis


def trace_demo(metric: str) -> int:
    analysis = demo_analysis()
    if analysis is None:
        print("no demo analysis available")
        return 1
    regions = analysis.regions
    duration = analysis.video.duration
    step = 1.0 / min(regions.sample_fps, analysis.video.fps)

    print("=" * 74)
    print(f"metric: {metric}   analysis: {analysis.analysis_id} (demo dataset)")
    print("=" * 74)

    print("\n1. INPUT - measurement rules in force")
    print(f"   queue polygon      : {len(regions.queue)} points")
    print(f"   speed threshold    : {regions.speed_threshold} frame widths / s")
    print(f"   minimum queue stay : {regions.min_queue_seconds} s")
    print(f"   grid step          : {step:.3f} s (sample_fps {regions.sample_fps})")
    print(f"   gap threshold      : {max_track_gap(step):.3f} s")
    print(f"   trajectories       : {len(analysis.trajectories)}")

    series = build_queue_series(analysis.trajectories, regions, duration, step)
    if series is None:
        print("\n   queue length is UNAVAILABLE: no queue region is defined")
        return 0

    print("\n2. GRID - how many vehicles are inside the region and slow, per instant")
    print(f"   grid instants      : {series.counts.size}")
    print(f"   reported peak      : {series.peak}")
    print(f"   time-average       : {series.average:.4f}")
    print(f"   occupied           : {series.occupied_seconds:.1f} s")

    peak_index = int(np.argmax(series.counts))
    peak_time = float(series.times[peak_index])
    print(f"   peak reached at    : {peak_time:.2f} s (grid index {peak_index})")

    # Independent check: rebuild that single instant from the raw samples.
    # Counted as a *set* of ids, because "how many vehicles are queued at t"
    # is a question about distinct vehicles, not about samples.
    from ..analytics.geometry import point_in_polygon
    from ..analytics.motion import segment_speed

    print("\n3. HAND CHECK - rebuild that instant from the raw samples")
    counted: set[int] = set()
    for track in analysis.trajectories:
        points = track.points
        slow_since = None
        for index in range(len(points) - 1):
            a, b = points[index], points[index + 1]
            gap = b.time - a.time
            if gap <= 0 or gap > max_track_gap(step):
                slow_since = None
                continue
            if segment_speed(a, b) >= regions.speed_threshold:
                slow_since = None
                continue
            if slow_since is None:
                slow_since = a.time
            if b.time - slow_since < regions.min_queue_seconds - 1e-9:
                continue
            if not a.time <= peak_time <= b.time:
                continue
            fraction = (peak_time - a.time) / gap
            x = a.x + fraction * (b.x - a.x)
            y = a.y + fraction * (b.y - a.y)
            if point_in_polygon((x, y), regions.queue):
                counted.add(track.vehicle_id)
                break  # one vote per vehicle
    print(f"   distinct vehicles inside the polygon and slow at t={peak_time:.2f}: "
          f"{sorted(counted)}")
    print(f"   hand count = {len(counted)}   grid count = {series.peak}")
    agree = len(counted) == int(series.counts[peak_index])
    print(f"   agreement: {'YES' if agree else 'NO - MISMATCH'}")

    print("\n4. SUMMARY - what the API returns")
    print(f"   summary.peak_queue        : {analysis.summary.peak_queue}")
    print(f"   summary.average_queue     : {analysis.summary.average_queue}")
    print(f"   queue_timeseries samples  : {len(analysis.queue_timeseries)}")
    api_max = max(sample.queue for sample in analysis.queue_timeseries)
    print(f"   max over the API series   : {api_max}")
    consistent = (
        analysis.summary.peak_queue == api_max
        and analysis.summary.peak_queue == series.peak
    )
    print(f"   summary matches series    : {'YES' if consistent else 'NO - MISMATCH'}")

    print("\n5. EVENTS - the peak is a first-class event")
    for event in analysis.events:
        if event.kind == "peak":
            print(f"   t={event.time:.2f}  {event.label}")

    return 0 if (agree and consistent) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", choices=["demo"])
    parser.add_argument("metric", choices=["peak_queue"])
    arguments = parser.parse_args()
    if arguments.analysis == "demo" and arguments.metric == "peak_queue":
        return trace_demo(arguments.metric)
    return 0


if __name__ == "__main__":
    sys.exit(main())
