"""Calibration of the simplified digital twin.

Everything the simulator needs is estimated from the analysed footage:

``arrival_rate``      N / dt over the arrival series (vehicles per minute)
``arrival_headway``   mean gap between consecutive arrivals
``service_time``      typical gap between consecutive *departures* - this is
                      the capacity of the exit, and it is what a scenario can
                      improve by adding a channel or speeding up processing
``free_flow_seconds`` travel time of vehicles that never queued - converted
                      into the simulated free-flow speed
``mean_traversal``    mean observed time from first to last sighting

All of these are averages with clearly stated fallbacks, and every fallback is
reported in ``Calibration.notes`` so the UI can show the assumption.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean, median
from statistics import quantiles

from ..models.schemas import Calibration

#: Used only when the footage contains no usable line crossings at all.
FALLBACK_SERVICE_TIME = 3.0
MIN_SERVICE_TIME = 1.0


def calibrate(
    *,
    observation_seconds: float,
    arrival_times: Sequence[float],
    departure_times: Sequence[float],
    departure_capacity_headway: float | None,
    traversals: Sequence[float],
    free_flow_candidates: Sequence[float],
    mean_wait_seconds: float | None,
    vehicles_used: int,
) -> Calibration:
    notes: list[str] = []
    minutes = max(observation_seconds, 1e-6) / 60.0

    arrival_gaps = [b - a for a, b in zip(arrival_times, arrival_times[1:]) if b - a > 0]
    headway = fmean(arrival_gaps) if arrival_gaps else None
    arrival_rate = (len(arrival_times) / minutes) if arrival_times else 0.0
    if headway is None:
        notes.append("Not enough arrivals to estimate an arrival headway.")
        headway = 60.0

    service_time = departure_capacity_headway
    if service_time is None:
        service_time = FALLBACK_SERVICE_TIME
        notes.append(
            "Exit service time could not be measured (no exit line, or no queue to "
            f"measure the discharge rate); the simulator uses a default of "
            f"{service_time:.1f}s."
        )
    else:
        notes.append(
            "Exit service time = 60 / (highest vehicles-per-minute actually leaving "
            "the exit while a queue was present). A queue keeps the exit at full "
            "capacity, so this is the observed discharge rate; it is a lower bound "
            "on the true processing time."
        )
    service_time = max(MIN_SERVICE_TIME, round(service_time, 3))

    traversals = [t for t in traversals if t > 0]
    if not traversals:
        mean_traversal = max(observation_seconds / 6.0, 10.0)
        notes.append("No complete trajectories; traversal time was assumed from the clip length.")
    else:
        mean_traversal = fmean(traversals)

    if free_flow_candidates:
        free_flow = max(2.0, float(median(free_flow_candidates)))
        notes.append("Free-flow time = median travel time of vehicles that never queued.")
    elif traversals:
        free_flow = max(2.0, float(quantiles(traversals, n=20)[0]))
        notes.append(
            "No vehicle completed a queue-free trip; free-flow time = 20th "
            "percentile of all traversal times."
        )
    else:
        free_flow = max(2.0, mean_traversal * 0.5)
        notes.append("Free-flow time fell back to half of the mean traversal time.")

    return Calibration(
        arrival_rate_per_minute=round(arrival_rate, 3),
        mean_arrival_headway_seconds=round(headway, 3),
        service_time_seconds=service_time,
        mean_traversal_seconds=round(mean_traversal, 2),
        free_flow_seconds=round(free_flow, 2),
        mean_queue_visit_seconds=round(mean_wait_seconds, 2) if mean_wait_seconds else 0.0,
        observation_seconds=round(observation_seconds, 2),
        vehicles_used=vehicles_used,
        notes=notes,
    )
