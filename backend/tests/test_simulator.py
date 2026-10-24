"""Digital twin: calibration, scenario transforms and the corridor simulator."""

from __future__ import annotations

from itertools import pairwise

import pytest

from backend.models.schemas import Scenario
from backend.simulation.scenarios import build_arrivals, plan_scenario
from backend.simulation.simulator import count_queue, simulate
from backend.simulation.traffic_model import calibrate

BASE_ARRIVALS = [0.0, 4.0, 8.0, 12.0, 16.0, 20.0]


def test_calibration_derives_arrival_and_service_rates():
    result = calibrate(
        observation_seconds=60.0,
        arrival_times=BASE_ARRIVALS,
        departure_times=[10.0, 14.0, 18.0, 22.0, 26.0],
        departure_capacity_headway=3.0,
        traversals=[20.0, 22.0, 18.0, 25.0],
        free_flow_candidates=[12.0, 14.0],
        mean_wait_seconds=5.0,
        vehicles_used=6,
    )
    assert result.arrival_rate_per_minute == pytest.approx(6.0)
    assert result.mean_arrival_headway_seconds == pytest.approx(4.0)
    assert result.service_time_seconds == pytest.approx(3.0)
    assert result.free_flow_seconds == pytest.approx(13.0)
    assert result.vehicles_used == 6


def test_calibration_falls_back_and_says_so():
    result = calibrate(
        observation_seconds=30.0,
        arrival_times=[0.0],
        departure_times=[],
        departure_capacity_headway=None,
        traversals=[],
        free_flow_candidates=[],
        mean_wait_seconds=None,
        vehicles_used=1,
    )
    assert result.service_time_seconds > 0
    assert any("no exit line" in note for note in result.notes)


def test_build_arrivals_reduces_volume_deterministically():
    fewer = build_arrivals(BASE_ARRIVALS, volume=0.5, spread_seconds=0.0, span=20.0, seed=1)
    assert len(fewer) == 3
    assert fewer == build_arrivals(BASE_ARRIVALS, volume=0.5, spread_seconds=0.0, span=20.0, seed=1)
    assert fewer == sorted(fewer)


def test_build_arrivals_increases_volume():
    more = build_arrivals(BASE_ARRIVALS, volume=1.5, spread_seconds=0.0, span=20.0, seed=7)
    assert len(more) == 9
    assert more == sorted(more)


def test_build_arrivals_stretches_the_window():
    stretched = build_arrivals(BASE_ARRIVALS, volume=1.0, spread_seconds=60.0, span=20.0, seed=1)
    assert stretched[0] == 0.0
    assert stretched[-1] == pytest.approx(80.0, abs=0.01)


def test_build_arrivals_never_returns_empty():
    assert build_arrivals([], volume=1.0, spread_seconds=0.0, span=10.0, seed=1) == [0.0]


def test_plan_scenario_converts_multipliers():
    calibration = calibrate(
        observation_seconds=60.0,
        arrival_times=BASE_ARRIVALS,
        departure_times=[0.0, 4.0],
        departure_capacity_headway=4.0,
        traversals=[20.0],
        free_flow_candidates=[12.0],
        mean_wait_seconds=None,
        vehicles_used=6,
    )
    plan = plan_scenario(
        Scenario(service_multiplier=2.0, channels=2), calibration, BASE_ARRIVALS
    )
    assert plan.service_time == pytest.approx(2.0)
    assert plan.channels == 2
    assert any("second exit processing channel" in note for note in plan.notes)


# ---------------------------------------------------------------------------- simulation


def _run(arrivals, **kwargs):
    defaults = {
        "window_seconds": 120.0,
        "free_flow_seconds": 10.0,
        "service_time": 3.0,
        "channels": 1,
        "output_step": 0.5,
    }
    defaults.update(kwargs)
    return simulate(arrivals, **defaults)


def test_simulation_is_deterministic():
    first = _run(BASE_ARRIVALS)
    second = _run(BASE_ARRIVALS)
    assert [v.departure for v in first.vehicles] == [v.departure for v in second.vehicles]
    assert [s.queue for s in first.queue_series] == [s.queue for s in second.queue_series]


def test_light_traffic_never_queues():
    run = _run([0.0, 20.0, 40.0, 60.0])
    assert run.peak_queue == 0
    assert run.average_wait == 0.0
    assert run.departures_in_window == 4


def test_sustained_arrivals_over_capacity_build_a_queue():
    # 0.6 s headway (100 veh/min) against a 3 s service time (20 veh/min).
    arrivals = [round(index * 0.6, 2) for index in range(30)]
    run = _run(arrivals)
    assert run.peak_queue > 5
    assert run.average_wait > 0
    assert run.max_wait >= run.average_wait


def test_queue_never_exceeds_the_number_of_vehicles():
    arrivals = [round(index * 0.4, 2) for index in range(25)]
    run = _run(arrivals)
    assert run.peak_queue <= len(arrivals)


def test_second_channel_reduces_the_queue():
    arrivals = [round(index * 0.8, 2) for index in range(25)]
    single = _run(arrivals, channels=1)
    double = _run(arrivals, channels=2)
    assert double.peak_queue < single.peak_queue
    assert double.average_wait < single.average_wait


def test_faster_service_reduces_the_queue():
    arrivals = [round(index * 0.8, 2) for index in range(25)]
    slow = _run(arrivals, service_time=6.0)
    fast = _run(arrivals, service_time=2.0)
    assert fast.peak_queue < slow.peak_queue
    assert fast.max_wait < slow.max_wait


def test_spreading_arrivals_reduces_congestion():
    """Same number of vehicles over a longer window must queue less."""
    burst = [round(index * 0.7, 2) for index in range(20)]
    spread = [round(index * 0.7 * 3.0, 2) for index in range(20)]
    tight = _run(burst, window_seconds=60.0)
    loose = _run(spread, window_seconds=180.0)
    assert loose.peak_queue < tight.peak_queue


def test_vehicles_keep_their_order_and_gap():
    """No overtaking: a vehicle can never pass one that entered before it.

    The check runs per time step (not per sample index, because vehicles enter
    at different moments) and stops at the gate, where vehicles are served in
    parallel.
    """
    arrivals = [round(index * 0.5, 2) for index in range(20)]
    run = _run(arrivals)
    paths = {vehicle.vehicle_id: dict(vehicle.path) for vehicle in run.vehicles}
    identifiers = sorted(paths)
    for earlier_id, later_id in pairwise(identifiers):
        earlier, later = paths[earlier_id], paths[later_id]
        for moment in set(earlier) & set(later):
            if earlier[moment] >= 0.9 or later[moment] >= 0.9:
                continue  # inside the gate area
            assert earlier[moment] >= later[moment] - 1e-6, (
                f"vehicle {later_id} overtook {earlier_id} at t={moment}"
            )


def test_vehicles_depart_after_they_are_served():
    run = _run([0.0, 0.5, 1.0])
    served = [v for v in run.vehicles if v.departure is not None]
    assert len(served) == 3
    for vehicle in served:
        assert vehicle.departure >= vehicle.arrival
        assert vehicle.position == pytest.approx(1.0)


def test_count_queue_ignores_finished_vehicles():
    run = _run([0.0])
    assert count_queue([v for v in run.vehicles if v.state == "DONE"]) == 0


def test_throughput_is_reported_over_the_observation_window():
    run = _run([0.0, 10.0, 20.0, 30.0], window_seconds=60.0, service_time=2.0)
    assert run.throughput_per_minute == pytest.approx(4.0)
    assert run.window_seconds == 60.0
