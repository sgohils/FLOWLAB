"""Ground truth extraction for the synthetic demo scene.

Used by ``backend.scripts.build_demo_dataset`` to write a reference file that
the validation script can check the measurement layer against.  It has no role
in the application: the app never imports it, and a real clip gets its ground
truth from a human annotator instead.

The queue series is rebuilt with **the same predicate the analytics use** -
"inside the queue region and below the motion threshold" - from the simulator's
own per-vehicle positions.  Comparing it with the pipeline output therefore
tests the measurement code, not the detector.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..models.schemas import Regions
from .geometry import point_in_polygon


def queue_truth(
    run,
    regions: Regions,
    sample_fps: float,
    duration: float,
    project,
) -> dict[str, Any]:
    """Rebuild the measured quantities from the simulator's own state.

    `project(corridor_position, vehicle_id) -> (x, y)` must be the very same
    mapping that rendered the trajectories into image coordinates, otherwise the
    comparison would be against a different scene.
    """
    step = 1.0 / sample_fps
    size = max(1, int(np.ceil(duration / step)))
    times = np.arange(size, dtype=float) * step
    counts = np.zeros(size, dtype=int)
    in_region_seconds = {vehicle.vehicle_id: 0.0 for vehicle in run.vehicles}

    for vehicle in run.vehicles:
        path = vehicle.path  # [(time_s, corridor_position), ...]
        # A vehicle can only be inside the queue once at any instant: the
        # cursor moves forward so consecutive slow segments never count the
        # same grid sample twice.
        cursor = 0
        for index in range(len(path) - 1):
            (t0, position0), (t1, position1) = path[index], path[index + 1]
            gap = t1 - t0
            if gap <= 0:
                continue
            speed = abs(position1 - position0) / gap
            x0, y0 = project(position0, vehicle.vehicle_id)
            x1, y1 = project(position1, vehicle.vehicle_id)
            inside0 = point_in_polygon((x0, y0), regions.queue)
            inside1 = point_in_polygon((x1, y1), regions.queue)
            if inside0 and inside1:
                in_region_seconds[vehicle.vehicle_id] += gap
            if speed >= regions.speed_threshold:
                continue
            first = max(0, int(np.floor(t0 / step)), cursor)
            last = min(size - 1, int(np.floor(t1 / step)))
            for index_k in range(first, last + 1):
                moment = times[index_k]
                if not t0 <= moment <= t1:
                    continue
                fraction = (moment - t0) / gap
                point = (x0 + fraction * (x1 - x0), y0 + fraction * (y1 - y0))
                if point_in_polygon(point, regions.queue):
                    counts[index_k] += 1
                cursor = index_k + 1

    vehicles = [
        {
            "label": f"vehicle {vehicle.vehicle_id}",
            "arrival_s": round(vehicle.arrival, 2),
            "departure_s": round(vehicle.departure, 2) if vehicle.departure is not None else None,
            "wait_s": round(vehicle.wait_seconds, 2) if vehicle.departure is not None else None,
            "in_region_s": round(in_region_seconds.get(vehicle.vehicle_id, 0.0), 2),
            "state": vehicle.state,
        }
        for vehicle in run.vehicles
    ]

    return {
        "clip": "demo_school_dismissal.mp4",
        "observation_window_s": duration,
        "sampling_fps": sample_fps,
        "arrivals_s": [round(t, 2) for t in sorted(v.arrival for v in run.vehicles)],
        "departures_s": [
            round(v.departure, 2) for v in sorted(run.vehicles, key=lambda v: v.departure or 0)
        ],
        "queue_counts": [
            {"time_s": round(float(t), 2), "count": int(c)} for t, c in zip(times, counts)
        ],
        "vehicles": vehicles,
        "notes": (
            "Ground truth rebuilt from the simulator's own per-vehicle positions "
            "using the same 'inside the region and below the speed threshold' rule "
            "as the analytics. It validates the measurement layer only and says "
            "nothing about detector accuracy."
        ),
    }
