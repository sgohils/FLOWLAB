"""Ground truth extraction for the synthetic demo scene.

Used by ``backend.scripts.build_demo_dataset`` to write a reference file that
the validation script can check the measurement layer against.  It has no role
in the application: the app never imports it, and a real clip gets its ground
truth from a human annotator instead.

Two count series are written from one walk, because two different quantities
need a ground truth of their own:

* ``queue_counts`` - the **slow** rule: inside the queue region and below the
  motion threshold.  This is the definition behind the wait estimate.
* ``occupancy_counts`` - the **occupancy** rule: inside the queue region at any
  speed, with no hold.  That is what a person pausing the frame would count, so
  it is the series a hand-taken annotation can be compared against.

Comparing either series against the other would measure a difference in
definition rather than the measurement code.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from ..models.schemas import Regions
from ..simulation.simulator import SimulationRun
from .geometry import point_in_polygon

#: ``project(corridor_position, vehicle_id) -> (x, y)``.
Project = Callable[[float, int], tuple[float, float]]


def _walk_track(
    path: Sequence[tuple[float, float]],
    vehicle_id: int,
    regions: Regions,
    times: np.ndarray,
    step: float,
    project: Project,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Count one vehicle's grid instants under both counting rules.

    The two rules differ only in whether the segment must also be slow, so the
    geometry is walked once.  Each rule keeps its own forward-only cursor: a
    vehicle can only be inside the region once at any instant however many of
    its segments cover that instant, and the slow rule's cursor has to skip
    precisely the segments the speed filter rejected.

    Returns the slow-rule counts, the occupancy counts and the seconds the
    vehicle spent inside the region.
    """
    size = int(times.size)
    slow_counts = np.zeros(size, dtype=int)
    occupancy_counts = np.zeros(size, dtype=int)
    slow_cursor = 0
    occupancy_cursor = 0
    in_region_seconds = 0.0

    for index in range(len(path) - 1):
        (t0, position0), (t1, position1) = path[index], path[index + 1]
        gap = t1 - t0
        if gap <= 0:
            continue
        speed = abs(position1 - position0) / gap
        x0, y0 = project(position0, vehicle_id)
        x1, y1 = project(position1, vehicle_id)
        if point_in_polygon((x0, y0), regions.queue) and point_in_polygon(
            (x1, y1), regions.queue
        ):
            in_region_seconds += gap
        first = max(0, int(np.floor(t0 / step)))
        last = min(size - 1, int(np.floor(t1 / step)))
        for moment_index in range(first, last + 1):
            moment = times[moment_index]
            if not t0 <= moment <= t1:
                continue
            fraction = (moment - t0) / gap
            point = (x0 + fraction * (x1 - x0), y0 + fraction * (y1 - y0))
            inside = point_in_polygon(point, regions.queue)
            if moment_index >= occupancy_cursor:
                if inside:
                    occupancy_counts[moment_index] += 1
                occupancy_cursor = moment_index + 1
            if speed >= regions.speed_threshold or moment_index < slow_cursor:
                continue
            if inside:
                slow_counts[moment_index] += 1
            slow_cursor = moment_index + 1
    return slow_counts, occupancy_counts, in_region_seconds


def queue_truth(
    run: SimulationRun,
    regions: Regions,
    sample_fps: float,
    duration: float,
    project: Project,
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
    occupancy = np.zeros(size, dtype=int)
    in_region_seconds = {vehicle.vehicle_id: 0.0 for vehicle in run.vehicles}

    for vehicle in run.vehicles:
        slow_counts, occupancy_counts, seconds = _walk_track(
            vehicle.path, vehicle.vehicle_id, regions, times, step, project
        )
        counts += slow_counts
        occupancy += occupancy_counts
        in_region_seconds[vehicle.vehicle_id] = seconds

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
            round(v.departure or 0.0, 2)
            for v in sorted(run.vehicles, key=lambda v: v.departure or 0)
        ],
        "queue_counts": [
            {"time_s": round(float(t), 2), "count": int(c)}
            for t, c in zip(times, counts, strict=True)
        ],
        "occupancy_counts": [
            {"time_s": round(float(t), 2), "count": int(c)}
            for t, c in zip(times, occupancy, strict=True)
        ],
        "vehicles": vehicles,
        "notes": (
            "Ground truth rebuilt from the simulator's own per-vehicle positions. "
            "occupancy_counts applies the same purely geometric rule as the "
            "application's region occupancy series (inside the region, any speed, "
            "no hold), so it is the like-for-like ground truth for a hand-taken "
            "count. queue_counts applies the 'inside the region and below the speed "
            "threshold' rule as the analytics do and is the ground truth for the "
            "slow count. It validates the measurement layer only and says nothing "
            "about detector accuracy."
        ),
    }
