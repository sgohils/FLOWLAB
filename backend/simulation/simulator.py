"""A deliberately simple 1-D microscopic digital twin.

The corridor is a single lane of normalised length ``1.0``: vehicles enter at
``x = 0`` and are processed at the gate ``x = 1``.  Longitudinal movement uses a
reduced Intelligent Driver Model (IDM)::

    s*(v, dv) = s0 + max(0, v*T + v*dv / (2*sqrt(a*b)))
    dv/dt     = a * (1 - (v/v0)^4 - (s/s*)^2)

with ``v0`` (free-flow speed) taken from the observed free-flow travel time and
``a``, ``b``, ``s0``, ``T`` set to standard car-following values scaled to the
corridor length.  The gate is modelled as a virtual stopped leader: whenever
all ``channels`` are busy, the first vehicle in line has to stop at ``x = 1``
and a queue forms behind it - which is exactly the mechanism we want to study.

Why not a queueing formula?  Because the metrics the UI compares
(peak queue, average wait, throughput) are then measured from simulated
*vehicle states* with the same definitions used for the video, so "observed vs
simulated" compares like with like.

The model is deterministic: no randomness anywhere, so running the same
scenario twice gives byte-identical results.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import sqrt
from statistics import fmean
from typing import Literal

from ..models.schemas import (
    Analysis,
    MetricDelta,
    ModelFidelity,
    QueueSample,
    Scenario,
    SensitivityPoint,
    SensitivityRange,
    SimulatedTrack,
    SimulationMetrics,
    SimulationResult,
)
from .scenarios import plan_scenario

#: Integration step of the model, in seconds.
TIME_STEP = 0.1
#: A vehicle slower than this fraction of free-flow speed counts as stopped.
STOP_SPEED_RATIO = 0.15
#: Minimum bumper-to-bumper gap along the corridor (2% of corridor length).
MIN_GAP = 0.02
#: Desired time headway to the leader, in seconds.
TIME_HEADWAY = 1.0
#: Position within which a vehicle is considered to be at the gate.  The
#: approach is where vehicles stop while every processing lane is busy.
GATE_TOLERANCE = 0.01
GATE_STOP = 1.0 - GATE_TOLERANCE

VehicleState = Literal["ENTERING", "MOVING", "QUEUED", "EXITING", "DONE"]


@dataclass(slots=True)
class SimVehicle:
    vehicle_id: int
    arrival: float
    position: float = 0.0
    speed: float = 0.0
    state: VehicleState = "ENTERING"
    channel: int | None = None
    service_end: float | None = None
    departure: float | None = None
    waiting_since: float | None = None
    wait_seconds: float = 0.0
    path: list[tuple[float, float]] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.state != "DONE"


@dataclass(frozen=True, slots=True)
class SimulationRun:
    vehicles: list[SimVehicle]
    queue_series: list[QueueSample]
    peak_queue: int
    average_queue: float
    average_wait: float
    max_wait: float
    throughput_per_minute: float
    total_delay_seconds: float
    departures_in_window: int
    window_seconds: float
    arrival_count: int
    free_flow_seconds: float
    unserved: int


def simulate(
    arrival_times: Sequence[float],
    *,
    window_seconds: float,
    free_flow_seconds: float,
    service_time: float,
    channels: int = 1,
    output_step: float = 0.5,
    tail_seconds: float | None = None,
) -> SimulationRun:
    """Run the corridor model and return vehicles plus the queue time series."""
    free_flow = max(2.0, free_flow_seconds)
    free_speed = 1.0 / free_flow  # corridor units per second
    max_accel = 0.6 * free_speed
    comfortable_decel = 1.6 * max_accel
    window = max(window_seconds, 1.0)
    tail = tail_seconds if tail_seconds is not None else 4.0 * free_flow + 10.0 * service_time
    horizon = window + tail

    pending = sorted(float(t) for t in arrival_times)
    vehicles: list[SimVehicle] = []
    next_id = 1

    moment = 0.0
    queue_samples: list[QueueSample] = []
    next_output = 0.0
    last_time = 0.0

    while moment <= horizon:
        # -- inject vehicles whose arrival time has come --------------------
        while pending and pending[0] <= moment + 1e-9:
            vehicles.append(
                SimVehicle(
                    vehicle_id=next_id,
                    arrival=pending.pop(0),
                    speed=0.6 * free_speed,  # vehicles join the corridor moving
                )
            )
            next_id += 1

        active = [v for v in vehicles if v.is_active]
        if not active and not pending:
            break
        # Positions are already ordered because vehicles never overtake.
        active.sort(key=lambda v: v.position)

        # -- leader lookup -------------------------------------------------
        # Vehicles being served sit *at* the gate: they are no longer in the
        # lane, so the next vehicle can pull up alongside and take another
        # channel.  Vehicles are already ordered front to back, and vehicles
        # sharing a position are bumper to bumper, so the group structure can
        # be found in a single linear scan.
        leaders: list[int | None] = [None] * len(active)
        lane = [index for index, vehicle in enumerate(active) if vehicle.state != "EXITING"]
        groups: list[list[int]] = []
        cursor = 0
        while cursor < len(lane):
            start = cursor
            position = active[lane[cursor]].position
            while (
                cursor + 1 < len(lane)
                and active[lane[cursor + 1]].position - position <= 1e-6
            ):
                cursor += 1
            groups.append(lane[start : cursor + 1])
            cursor += 1
        for group_index, group in enumerate(groups):
            ahead = groups[group_index + 1][0] if group_index + 1 < len(groups) else None
            # Vehicles sharing a position are bumper to bumper, so each one
            # follows the vehicle directly in front of it; the front vehicle of
            # the group follows the head of the next group.
            for member_index, index in enumerate(group):
                if member_index == 0:
                    leaders[index] = ahead
                else:
                    leaders[index] = group[member_index - 1]

        busy_channels = sum(1 for v in active if v.state == "EXITING")
        gate_free = busy_channels < channels

        # -- longitudinal update -------------------------------------------
        # Front to back, so the vehicle ahead has already been moved this step
        # and can be used as an up-to-date leader.
        for index in range(len(active) - 1, -1, -1):
            vehicle = active[index]
            if vehicle.state == "EXITING":
                vehicle.position = 1.0
                vehicle.speed = 0.0
                if vehicle.service_end is not None and moment >= vehicle.service_end:
                    vehicle.state = "DONE"
                    vehicle.departure = vehicle.service_end
                continue

            leader_index = leaders[index]
            leader = active[leader_index] if leader_index is not None else None
            if leader is None and not gate_free:
                # Every processing lane is busy: stop at the gate approach.
                gap = max(GATE_STOP - vehicle.position, 1e-4)
                leader_speed = 0.0
            elif leader is None:
                gap = float("inf")
                leader_speed = 0.0
            else:
                gap = max(leader.position - vehicle.position, 1e-4)
                leader_speed = leader.speed

            relative_speed = vehicle.speed - leader_speed
            desired_gap = MIN_GAP + max(
                0.0,
                vehicle.speed * TIME_HEADWAY
                + vehicle.speed * relative_speed / (2.0 * sqrt(max_accel * comfortable_decel)),
            )
            gap_ratio = 0.0 if gap == float("inf") else (desired_gap / gap) ** 2
            acceleration = max_accel * (
                1.0 - (vehicle.speed / free_speed) ** 4 - min(gap_ratio, 25.0)
            )
            acceleration = max(-4.0 * max_accel, min(max_accel, acceleration))
            vehicle.speed = max(0.0, vehicle.speed + acceleration * TIME_STEP)
            vehicle.position = min(1.0, vehicle.position + vehicle.speed * TIME_STEP)
            if leader is not None:
                # Hard safety net: the 0.1 s step must never let a follower
                # tunnel through its leader.
                vehicle.position = min(vehicle.position, max(0.0, leader.position - MIN_GAP))

            if vehicle.position >= GATE_STOP:
                vehicle.position = 1.0
                vehicle.speed = 0.0
                if gate_free:
                    gate_free = False
                    vehicle.state = "EXITING"
                    vehicle.channel = busy_channels
                    busy_channels += 1
                    vehicle.service_end = moment + service_time
                    if vehicle.waiting_since is not None:
                        vehicle.wait_seconds = moment - vehicle.waiting_since
                        vehicle.waiting_since = None
                continue

            was_stopped = vehicle.state in {"ENTERING", "QUEUED"}
            if vehicle.speed < STOP_SPEED_RATIO * free_speed:
                vehicle.state = "QUEUED"
                if vehicle.waiting_since is None:
                    vehicle.waiting_since = moment
            else:
                vehicle.state = "MOVING"
                if was_stopped and vehicle.waiting_since is not None:
                    vehicle.wait_seconds += moment - vehicle.waiting_since
                    vehicle.waiting_since = None

        # -- sampling -------------------------------------------------------
        while next_output <= moment + 1e-9:
            queue_samples.append(
                QueueSample(time=round(next_output, 3), queue=count_queue(active))
            )
            for vehicle in active:
                if vehicle.state != "DONE":
                    vehicle.path.append((round(moment, 2), round(vehicle.position, 4)))
            next_output += output_step
        last_time = moment
        moment += TIME_STEP

    # Close out waits that were still running when the run ended.
    for vehicle in vehicles:
        if vehicle.state in {"ENTERING", "QUEUED", "MOVING"} and vehicle.waiting_since is not None:
            vehicle.wait_seconds += last_time - vehicle.waiting_since
            vehicle.waiting_since = None

    # One pass instead of three comprehensions: the ``is None`` test is made
    # where it is used, so ``departure`` is a float below.  A vehicle still in
    # the corridor at the end of the run has no departure time and cannot
    # contribute a delay.
    waited: list[float] = []
    completed: list[SimVehicle] = []
    total_delay = 0.0
    for vehicle in vehicles:
        if vehicle.departure is None:
            continue
        completed.append(vehicle)
        if vehicle.wait_seconds > 0:
            waited.append(vehicle.wait_seconds)
        total_delay += max(0.0, (vehicle.departure - vehicle.arrival) - free_flow)
    in_window = [v for v in completed if v.arrival <= window + 1e-9]
    queue_values = [sample.queue for sample in queue_samples if sample.time <= window + 1e-9]

    return SimulationRun(
        vehicles=vehicles,
        queue_series=queue_samples,
        peak_queue=max(queue_values) if queue_values else 0,
        average_queue=round(fmean(queue_values), 2) if queue_values else 0.0,
        average_wait=round(fmean(waited), 2) if waited else 0.0,
        max_wait=round(max(waited), 2) if waited else 0.0,
        throughput_per_minute=round(len(in_window) * 60.0 / window, 2) if window > 0 else 0.0,
        total_delay_seconds=round(total_delay, 2),
        departures_in_window=len(in_window),
        window_seconds=round(window, 2),
        arrival_count=len(vehicles),
        free_flow_seconds=round(free_flow, 2),
        unserved=len(vehicles) - len(completed),
    )


def count_queue(active: Sequence[SimVehicle]) -> int:
    """Vehicles that are currently stopped and have not been processed yet."""
    return sum(1 for v in active if v.state in {"QUEUED", "ENTERING"})


def build_tracks(run: SimulationRun, limit: int) -> list[SimulatedTrack]:
    """Down-sampled vehicle paths for the corridor visualisation.

    Paths are recorded once per output sample, so they are already coarse; we
    only thin them out again when the fleet is large.
    """
    tracks: list[SimulatedTrack] = []
    stride = max(1, len(run.vehicles) // max(1, limit))
    for index, vehicle in enumerate(run.vehicles):
        if index % stride:
            continue
        tracks.append(
            SimulatedTrack(
                vehicle_id=vehicle.vehicle_id,
                arrival=round(vehicle.arrival, 2),
                departure=round(vehicle.departure, 2) if vehicle.departure is not None else None,
                wait=round(vehicle.wait_seconds, 2) if vehicle.departure is not None else None,
                points=[[when, position] for when, position in vehicle.path],
            )
        )
    return tracks


# --------------------------------------------------------------------------------------
# Scenario orchestration: observed vs simulated
# --------------------------------------------------------------------------------------

DISCLAIMER = (
    "Simulated scenario. This is a simplified corridor model calibrated from the "
    "clip, not a prediction or a recommendation for the real site."
)


def resample(series: Sequence[QueueSample], times: Sequence[float]) -> list[QueueSample]:
    """Nearest-sample resampling so both curves can share one time axis."""
    if not series or not times:
        return []
    source_times = [sample.time for sample in series]
    out: list[QueueSample] = []
    cursor = 0
    for moment in times:
        while cursor + 1 < len(source_times) and source_times[cursor + 1] < moment:
            cursor += 1
        out.append(QueueSample(time=round(moment, 3), queue=series[cursor].queue))
    return out


def _observed_metrics(analysis: Analysis) -> SimulationMetrics:
    summary = analysis.summary
    total_wait = sum(visit.duration or 0.0 for visit in analysis.queue_visits if visit.complete)
    return SimulationMetrics(
        vehicles=summary.vehicles_tracked,
        peak_queue=summary.peak_queue or 0,
        average_queue=round(summary.average_queue or 0.0, 2),
        average_wait_seconds=round(summary.average_wait_seconds or 0.0, 2),
        max_wait_seconds=round(summary.max_wait_seconds or 0.0, 2),
        throughput_per_minute=round(summary.throughput_per_minute or 0.0, 2),
        total_delay_seconds=round(total_wait, 2),
        observation_seconds=round(analysis.video.duration, 2),
        # "Left at window end" has no meaning for a recording: the clip simply
        # stops, so it is reported as unavailable by leaving the count at zero
        # and saying so in the comparison notes.
        vehicles_left_at_window_end=0,
    )


def _simulated_metrics(run: SimulationRun) -> SimulationMetrics:
    return SimulationMetrics(
        vehicles=run.arrival_count,
        peak_queue=run.peak_queue,
        average_queue=run.average_queue,
        average_wait_seconds=run.average_wait,
        max_wait_seconds=run.max_wait,
        throughput_per_minute=run.throughput_per_minute,
        total_delay_seconds=run.total_delay_seconds,
        observation_seconds=run.window_seconds,
        vehicles_left_at_window_end=run.unserved,
    )


_METRIC_LABELS: tuple[tuple[str, str, str, bool], ...] = (
    ("peak_queue", "Peak queue", "vehicles", True),
    ("average_queue", "Average queue", "vehicles", True),
    ("average_wait_seconds", "Avg wait", "s", True),
    ("max_wait_seconds", "Maximum wait", "s", True),
    ("throughput_per_minute", "Throughput", "veh/min", False),
)


def _deltas(observed: SimulationMetrics, simulated: SimulationMetrics) -> list[MetricDelta]:
    deltas: list[MetricDelta] = []
    for attribute, label, unit, lower_is_better in _METRIC_LABELS:
        before = float(getattr(observed, attribute))
        after = float(getattr(simulated, attribute))
        difference = after - before
        percent = round(difference / before * 100.0, 1) if before else None
        deltas.append(
            MetricDelta(
                metric=attribute,
                label=label,
                unit=unit,
                observed=round(before, 2),
                simulated=round(after, 2),
                absolute=round(difference, 2),
                percent=percent,
                lower_is_better=lower_is_better,
            )
        )
    return deltas


def _fidelity(observed: SimulationMetrics, baseline_run: SimulationRun) -> ModelFidelity:
    """How well the *unmodified* model reproduces the observed clip.

    The baseline always replays the original arrival series, so a scenario that
    changed the volume or the timing cannot inflate its own fidelity number.
    """
    ratio = None
    if observed.peak_queue:
        ratio = round(baseline_run.peak_queue / observed.peak_queue, 3)
    if ratio is None:
        note = (
            "The observed peak queue is zero, so the model cannot be compared on "
            "that metric."
        )
    elif 0.75 <= ratio <= 1.33:
        note = (
            "Replaying the observed arrivals through the unmodified model "
            "reproduces the observed peak queue within 25%."
        )
    else:
        note = (
            "The unmodified model reproduces the observed peak queue with a factor of "
            f"{ratio:.2f}. Read scenario results as the change from this baseline, "
            "not as absolute predictions for the site."
        )
    return ModelFidelity(
        peak_queue_observed=observed.peak_queue,
        peak_queue_model=baseline_run.peak_queue,
        average_wait_observed=observed.average_wait_seconds,
        average_wait_model=baseline_run.average_wait,
        ratio=ratio,
        note=note,
    )


def service_time_sensitivity(
    analysis: Analysis,
    factors: Sequence[float] = (0.75, 1.0, 1.5),
) -> SensitivityRange:
    """Re-run the baseline under alternative exit service times.

    Exit service time is the one parameter the application *estimates* rather
    than counts, so its influence is worth showing.  The factors are stated
    explicitly: this is a range of model outcomes under assumed values, not a
    confidence interval, and no probability is implied.
    """
    calibration = analysis.calibration
    baseline_service = max(0.5, calibration.service_time_seconds)
    points: list[SensitivityPoint] = []
    for factor in factors:
        service = round(baseline_service * factor, 3)
        run = simulate(
            list(analysis.arrivals),
            window_seconds=calibration.observation_seconds,
            free_flow_seconds=calibration.free_flow_seconds,
            service_time=service,
            channels=1,
            output_step=1.0 / 10.0,
        )
        points.append(
            SensitivityPoint(
                service_time_seconds=service,
                peak_queue=run.peak_queue,
                average_wait_seconds=run.average_wait,
                throughput_per_minute=run.throughput_per_minute,
                vehicles_left_at_window_end=run.unserved,
            )
        )
    return SensitivityRange(
        parameter="exit service time",
        method=(
            "Baseline re-run with the estimated service time multiplied by "
            + ", ".join(f"{factor:g}" for factor in factors)
            + ". All other inputs unchanged."
        ),
        baseline_value=baseline_service,
        values=points,
        peak_queue_range=(
            min(point.peak_queue for point in points),
            max(point.peak_queue for point in points),
        ),
        average_wait_range=(
            round(min(point.average_wait_seconds for point in points), 2),
            round(max(point.average_wait_seconds for point in points), 2),
        ),
        note=(
            "This shows how much the model output depends on an estimated "
            "parameter. It is not a statistical confidence interval and implies "
            "no probability."
        ),
    )


def run_scenario(
    analysis: Analysis,
    scenario: Scenario,
    max_samples: int = 600,
    max_tracks: int = 10,
) -> SimulationResult:
    """Run one scenario and return it next to the observed metrics."""
    calibration = analysis.calibration
    plan = plan_scenario(scenario, calibration, analysis.arrivals)
    step = 1.0 / max(5.0, analysis.regions.sample_fps)
    run = simulate(
        plan.arrival_times,
        window_seconds=plan.window_seconds,
        free_flow_seconds=calibration.free_flow_seconds,
        service_time=plan.service_time,
        channels=plan.channels,
        output_step=step,
    )

    # --- B: the unmodified model, replaying the observed arrival series -----
    baseline_plan = plan_scenario(Scenario(), calibration, list(analysis.arrivals))
    baseline_run = simulate(
        baseline_plan.arrival_times,
        window_seconds=baseline_plan.window_seconds,
        free_flow_seconds=calibration.free_flow_seconds,
        service_time=baseline_plan.service_time,
        channels=baseline_plan.channels,
        output_step=step,
    )

    observed_queue = list(analysis.queue_timeseries)
    # All three curves share the observed time axis when one exists, so the
    # comparison is over an explicitly identical window.
    if observed_queue:
        grid = [sample.time for sample in observed_queue]
        baseline_queue = resample(baseline_run.queue_series, grid)
        simulated_queue = resample(run.queue_series, grid)
    else:
        baseline_queue = baseline_run.queue_series
        simulated_queue = run.queue_series
    stride = max(1, len(observed_queue) // max_samples) if observed_queue else 1
    observed_queue = observed_queue[::stride]
    baseline_queue = baseline_queue[::stride]
    simulated_queue = simulated_queue[::stride]

    observed = _observed_metrics(analysis)
    baseline = _simulated_metrics(baseline_run)
    simulated = _simulated_metrics(run)

    notes = list(plan.notes)
    notes.append(
        "Simulated queue = vehicles stopped in the corridor. The video queue "
        "region is the equivalent area in the real scene."
    )
    if run.unserved:
        notes.append(
            f"{run.unserved} simulated vehicles were still in the corridor when the "
            "observation window ended; they are excluded from the wait statistics."
        )
    if not analysis.arrivals:
        notes.append(
            "No entry line was defined, so arrival times come from first sightings; "
            "the simulated arrival pattern is therefore approximate."
        )
    if abs(observed.observation_seconds - simulated.observation_seconds) > 0.5:
        notes.append(
            "The scenario changed the length of the arrival window, so the throughput "
            "numbers cover different durations and are not directly comparable."
        )

    return SimulationResult(
        analysis_id=analysis.analysis_id,
        scenario=scenario,
        calibration=calibration,
        observed=observed,
        baseline=baseline,
        simulated=simulated,
        fidelity=_fidelity(observed, baseline_run),
        sensitivity=(
            service_time_sensitivity(analysis)
            if analysis.arrivals
            else None
        ),
        # Scenario effect: modified model vs unmodified model.
        deltas=_deltas(baseline, simulated),
        # Model mismatch: unmodified model vs what the camera measured.
        model_deltas=_deltas(observed, baseline),
        observed_queue=observed_queue,
        baseline_queue=baseline_queue,
        simulated_queue=simulated_queue,
        tracks=build_tracks(run, max_tracks),
        baseline_tracks=build_tracks(baseline_run, max_tracks),
        notes=notes,
        disclaimer=DISCLAIMER,
    )
