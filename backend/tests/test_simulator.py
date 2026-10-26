"""Digital twin: calibration, scenario transforms and the corridor simulator."""

from __future__ import annotations

from itertools import pairwise

import pytest

from backend.models.schemas import QueueSample, Scenario
from backend.simulation.scenarios import build_arrivals, describe, plan_scenario
from backend.simulation.simulator import count_queue, resample, simulate
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


def test_calibration_does_not_claim_fast_departures_prove_a_queue_or_gate_capacity():
    result = calibrate(
        observation_seconds=25.0,
        arrival_times=[0.0, 3.0, 6.0],
        departure_times=[1.0, 7.0, 9.0, 20.0, 20.109],
        departure_capacity_headway=0.109,
        departure_capacity_method="fastest_departure_gaps",
        traversals=[5.0, 6.0],
        free_flow_candidates=[5.0, 6.0],
        mean_wait_seconds=None,
        vehicles_used=5,
    )
    assert result.service_time_seconds == 1.0
    explanation = " ".join(result.notes)
    assert "fastest quarter of positive gaps" in explanation
    assert "does not establish saturated exit capacity" in explanation
    assert "multiple lanes" in explanation
    assert "0.109s" in explanation
    assert "model uses 1.0s" in explanation
    assert "model assumption, not a measurement" in explanation


def test_calibration_does_not_claim_a_model_floor_when_the_estimate_is_above_it():
    result = calibrate(
        observation_seconds=60.0,
        arrival_times=BASE_ARRIVALS,
        departure_times=[10.0, 13.0, 16.0],
        departure_capacity_headway=3.0,
        traversals=[10.0, 12.0],
        free_flow_candidates=[10.0],
        mean_wait_seconds=2.0,
        vehicles_used=3,
    )
    assert result.service_time_seconds == 3.0
    assert not any("minimum service time" in note for note in result.notes)


def test_calibration_records_queued_discharge_only_when_the_method_says_so():
    result = calibrate(
        observation_seconds=60.0,
        arrival_times=BASE_ARRIVALS,
        departure_times=[10.0, 13.0, 16.0],
        departure_capacity_headway=3.0,
        departure_capacity_method="queued_discharge",
        traversals=[10.0, 12.0],
        free_flow_candidates=[10.0],
        mean_wait_seconds=2.0,
        vehicles_used=3,
    )
    explanation = " ".join(result.notes)
    assert "in a complete queued-discharge window" in explanation
    assert "fastest quarter" not in explanation
    assert result.service_time_seconds == 3.0


def test_build_arrivals_reduces_volume_deterministically():
    fewer = build_arrivals(BASE_ARRIVALS, volume=0.5, spread_seconds=0.0, span=20.0, seed=1)
    assert len(fewer) == 3
    assert fewer == build_arrivals(BASE_ARRIVALS, volume=0.5, spread_seconds=0.0, span=20.0, seed=1)
    assert fewer == sorted(fewer)
    assert set(fewer).issubset(BASE_ARRIVALS)


def test_build_arrivals_increases_volume():
    more = build_arrivals(BASE_ARRIVALS, volume=1.5, spread_seconds=0.0, span=20.0, seed=7)
    assert len(more) == 9
    assert more == sorted(more)
    assert set(BASE_ARRIVALS).issubset(more)
    assert all(0 <= timestamp <= 20 for timestamp in more)


def test_build_arrivals_preserves_recorded_timestamps_and_idle_periods():
    observed = [3.12345, 4.5, 8.9, 12.0]
    assert build_arrivals(observed, volume=1, spread_seconds=0, span=60, seed=7) == observed


def test_spreading_preserves_first_arrival_and_extends_the_burst_not_its_idle_time():
    observed = [3.0, 5.0, 9.0]
    stretched = build_arrivals(observed, volume=1, spread_seconds=12, span=60, seed=7)
    assert stretched == [3.0, 9.0, 21.0]
    assert stretched[-1] - observed[-1] == 12


def test_build_arrivals_stretches_the_window():
    stretched = build_arrivals(BASE_ARRIVALS, volume=1.0, spread_seconds=60.0, span=20.0, seed=1)
    assert stretched[0] == 0.0
    assert stretched[-1] == pytest.approx(80.0, abs=0.01)


def test_build_arrivals_does_not_invent_traffic_for_an_empty_recording():
    assert build_arrivals([], volume=1.0, spread_seconds=0.0, span=10.0, seed=1) == []


def test_one_arrival_is_not_shifted_or_fabricated_by_spreading():
    assert build_arrivals([7.5], volume=1, spread_seconds=120, span=30, seed=7) == [7.5]


def test_added_arrivals_stay_within_the_window_when_the_last_arrival_is_near_the_end():
    arrivals = build_arrivals([0.99], volume=1.5, spread_seconds=0, span=1, seed=999)
    assert 0.99 in arrivals
    assert len(arrivals) == 2
    assert max(arrivals) <= 1


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
    assert any("2.00x observed exit processing rate" in note for note in plan.notes)


def test_scenario_plan_keeps_the_original_clock_and_words_percentage_changes_correctly():
    calibration = calibrate(
        observation_seconds=60,
        arrival_times=[3, 6, 9, 12],
        departure_times=[],
        departure_capacity_headway=None,
        traversals=[10],
        free_flow_candidates=[10],
        mean_wait_seconds=None,
        vehicles_used=4,
    )
    baseline = plan_scenario(Scenario(), calibration, [3, 6, 9, 12])
    assert baseline.arrival_times == [3, 6, 9, 12]
    assert baseline.window_seconds == 60
    reduced = plan_scenario(Scenario(volume=0.75), calibration, [3, 6, 9, 12])
    assert reduced.label == "volume -25%"
    assert any("Traffic volume -25%: 3 vehicles instead of 4" in note for note in reduced.notes)
    assert reduced.arrival_times == [3, 6, 9]
    assert describe(Scenario(spread_seconds=120)) == "spread +120s"
    assert describe(Scenario(channels=2)) == "second exit lane"


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


def test_completions_after_the_window_do_not_count_as_throughput_or_remove_unserved_vehicles():
    run = _run([0.0, 0.5, 1.0], window_seconds=5.0, service_time=10.0, tail_seconds=100)
    assert any(vehicle.departure is not None for vehicle in run.vehicles)
    assert run.departures_in_window == 0
    assert run.throughput_per_minute == 0
    assert run.unserved == 3
    assert run.total_delay_seconds == 0


def test_window_metrics_do_not_depend_on_the_extra_path_recording_tail():
    inputs = {"window_seconds": 15.0, "free_flow_seconds": 2.0, "service_time": 3.0}
    short = simulate([0, 0.5, 1, 1.5, 2], tail_seconds=0, **inputs)
    long = simulate([0, 0.5, 1, 1.5, 2], tail_seconds=100, **inputs)
    assert [vehicle.departure for vehicle in short.vehicles] != [
        vehicle.departure for vehicle in long.vehicles
    ]
    assert short.departures_in_window == long.departures_in_window
    assert short.unserved == long.unserved
    assert short.average_wait == long.average_wait
    assert short.max_wait == long.max_wait
    assert short.throughput_per_minute == long.throughput_per_minute
    assert short.total_delay_seconds == long.total_delay_seconds
    assert short.average_queue == long.average_queue


def test_a_cleared_corridor_still_counts_zero_queue_for_the_rest_of_the_window():
    run = _run([0.0], window_seconds=60, free_flow_seconds=2, service_time=2)
    assert run.vehicles[0].departure is not None
    assert run.vehicles[0].departure < 10
    assert run.queue_series[-1].time >= 60
    assert run.queue_series[-1].queue == 0


def test_resampling_keeps_the_state_at_exact_timestamps_instead_of_lagging_one_sample():
    series = [
        QueueSample(time=0, queue=1),
        QueueSample(time=0.5, queue=2),
        QueueSample(time=1, queue=3),
    ]
    samples = resample(series, [0, 0.25, 0.5, 0.75, 1])
    assert [sample.queue for sample in samples] == [1, 1, 2, 2, 3]
