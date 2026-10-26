"""Throughput from line crossings."""

from __future__ import annotations

import pytest

from backend.analytics.throughput import (
    Crossings,
    collect_crossings,
    flow_statistics,
    headways,
    rate_per_minute,
    rolling_rate,
)
from backend.tests.conftest import ENTRY_LINE, EXIT_LINE, make_regions, make_track


def test_rate_formula():
    # 12 vehicles in 2 minutes = 6 vehicles / minute.
    assert rate_per_minute(12, 120.0) == 6.0
    assert rate_per_minute(0, 60.0) == 0.0
    assert rate_per_minute(5, 0.0) is None


def test_crossings_are_collected_once_per_vehicle():
    tracks = [
        make_track(1, [(0.2, 0.5), (0.5, 0.5), (0.9, 0.5)], step=1.0),
        make_track(2, [(0.2, 0.4), (0.5, 0.4), (0.9, 0.4)], start=2.0, step=1.0),
        # Never reaches the line: excluded.
        make_track(3, [(0.1, 0.3), (0.2, 0.3), (0.3, 0.3)], start=4.0, step=1.0),
    ]
    crossings = collect_crossings(tracks, EXIT_LINE, step=0.5)
    assert crossings.available
    assert crossings.count == 2
    assert sorted(crossings.per_vehicle) == [1, 2]


def test_missing_line_is_reported_as_unavailable():
    crossings = collect_crossings([make_track(1, [(0.2, 0.5), (0.8, 0.5)])], [], step=0.5)
    assert not crossings.available
    assert crossings.count == 0


def test_entry_and_exit_lines_are_independent():
    tracks = [make_track(1, [(0.05, 0.5), (0.3, 0.5), (0.6, 0.5), (0.9, 0.5)], step=1.0)]
    assert collect_crossings(tracks, ENTRY_LINE, 0.5).count == 1
    assert collect_crossings(tracks, EXIT_LINE, 0.5).count == 1


def test_throughput_over_the_observation_window():
    # Four vehicles leave, evenly spaced across one minute.
    times = [0.0, 15.0, 30.0, 45.0]
    tracks = [
        make_track(index, [(0.1, 0.5), (0.5, 0.5), (0.95, 0.5)], start=time, step=1.0)
        for index, time in enumerate(times, start=1)
    ]
    stats = flow_statistics(collect_crossings(tracks, EXIT_LINE, 0.5), observation_seconds=60.0)
    assert stats.count == 4
    assert stats.per_minute == 4.0
    assert abs(stats.mean_headway - 15.0) < 1e-6
    assert abs(stats.capacity_headway - 15.0) < 1e-6


def test_capacity_headway_uses_the_fastest_quarter_of_gaps():
    """A queue discharging fast should calibrate a *short* service time."""
    # Departures: three back-to-back, then a long gap.
    times = [0.0, 2.0, 4.0, 40.0]
    tracks = [
        make_track(index, [(0.2, 0.5), (0.9, 0.5)], start=time, step=1.0)
        for index, time in enumerate(times, start=1)
    ]
    stats = flow_statistics(collect_crossings(tracks, EXIT_LINE, 0.5), observation_seconds=60.0)
    assert stats.capacity_headway is not None
    assert stats.capacity_headway < stats.mean_headway
    assert stats.capacity_method == "fastest_departure_gaps"


def test_capacity_method_records_a_complete_queued_discharge_window():
    times = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 20.0, 40.0]
    stats = flow_statistics(
        Crossings(times=times, per_vehicle=dict(enumerate(times)), available=True),
        observation_seconds=60.0,
        busy_window=(0.0, 30.0),
    )
    assert stats.capacity_method == "queued_discharge"
    assert stats.capacity_headway == pytest.approx(30.0 / 7)


def test_short_queue_window_truthfully_records_the_departure_gap_fallback():
    times = [0.0, 2.0, 4.0, 40.0]
    stats = flow_statistics(
        Crossings(times=times, per_vehicle=dict(enumerate(times)), available=True),
        observation_seconds=60.0,
        busy_window=(0.0, 20.0),
    )
    assert stats.capacity_method == "fastest_departure_gaps"
    assert stats.capacity_headway == 2.0


def test_no_departure_gaps_has_no_capacity_estimation_method():
    stats = flow_statistics(
        Crossings(times=[5.0], per_vehicle={1: 5.0}, available=True),
        observation_seconds=60.0,
    )
    assert stats.capacity_headway is None
    assert stats.capacity_method is None


def test_headways_ignores_non_positive_gaps():
    assert headways([0.0, 3.0, 3.0, 7.0]) == [3.0, 4.0]


def test_rolling_rate_window():
    series = rolling_rate([0.0, 10.0, 20.0, 90.0], window_seconds=30.0, step=30.0)
    assert series[0] == (0.0, 6.0)  # three departures inside the first window
    assert series[-1][0] == 90.0


def test_regions_without_lines_produce_no_throughput():
    regions = make_regions(exit=[])
    assert regions.exit == []
    crossings = collect_crossings([make_track(1, [(0.2, 0.5), (0.9, 0.5)])], regions.exit, 0.5)
    assert not crossings.available
