"""Replay timeline: uniform-in-time samples, explicit tracking gaps.

The point of this module is honesty about what is known at any instant.  If a
vehicle's track was lost, the payload must say so instead of letting the client
draw a straight line through the gap.
"""

from __future__ import annotations

import pytest

from backend.analytics.timeline import (
    build_timeline,
    position_at,
    queue_at,
    timeline_sample_count,
)
from backend.models.schemas import Regions, Trajectory, TrajectoryPoint
from backend.tests.conftest import make_track


def _regions(**overrides) -> Regions:
    values = dict(
        queue=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
        entry=[(0.0, 0.0), (0.0, 1.0)],
        exit=[(1.0, 0.0), (1.0, 1.0)],
        speed_threshold=0.012,
        min_stop_seconds=1.5,
        min_queue_seconds=0.5,
        sample_fps=10.0,
    )
    values.update(overrides)
    return Regions(**values)


def _driving(vehicle_id: int = 1, count: int = 50, step: float = 0.1) -> object:
    positions = [(0.1 + 0.015 * index, 0.5) for index in range(count)]
    return make_track(vehicle_id, positions, step=step)


def _track_with_gap(vehicle_id: int) -> object:
    """Tracked 0-1.5 s, lost for 6 s, tracked again from 7.5 s."""
    early = [(0.10 + 0.02 * index, 0.5) for index in range(16)]  # 0.0 - 1.5 s
    late = [(0.60 + 0.02 * index, 0.5) for index in range(8)]  # 7.5 - 8.3 s
    times = [round(0.1 * index, 3) for index in range(len(early))] + [
        round(7.5 + 0.1 * index, 3) for index in range(len(late))
    ]
    points = [
        TrajectoryPoint(frame=index, time=time, x=x, y=y, confidence=0.9)
        for index, (time, (x, y)) in enumerate(zip(times, early + late))
    ]
    return Trajectory(
        vehicle_id=vehicle_id,
        vehicle_class="car",
        first_seen=points[0].time,
        last_seen=points[-1].time,
        duration=points[-1].time - points[0].time,
        path_length=0.0,
        points=points,
    )


def test_segments_are_uniform_in_time():
    timeline = build_timeline([_driving()], _regions(), duration=6.0, hz=4.0)
    segment = timeline["vehicles"][0]["segments"][0]
    times = segment["t"]
    assert times[0] == pytest.approx(0.0, abs=1e-6)
    deltas = [round(b - a, 3) for a, b in zip(times, times[1:])]
    # Every interval is the transport step (the last one may be shorter).
    assert set(deltas[:-1]) == {0.25}
    assert deltas[-1] <= 0.25 + 1e-6


def test_a_tracking_gap_splits_the_track_and_position_is_unknown_inside_it():
    """The core promise: no invented motion across a dropout."""
    track = _track_with_gap(7)
    timeline = build_timeline([track], _regions(), duration=10.0, hz=5.0)
    vehicle = timeline["vehicles"][0]
    assert len(vehicle["segments"]) == 2
    assert timeline["track_gaps"] == 1
    assert vehicle["segments"][0]["t"][-1] <= 1.6
    assert vehicle["segments"][1]["t"][0] >= 7.4

    # Known inside each segment, unknown in between - and never invented.
    assert position_at(timeline, 7, 1.0) is not None
    assert position_at(timeline, 7, 8.0) is not None
    for moment in (3.0, 4.5, 6.0, 7.0):
        assert position_at(timeline, 7, moment) is None, f"invented a position at t={moment}"


def test_positions_match_the_source_samples_inside_a_segment():
    track = _driving(3, count=30, step=0.1)
    timeline = build_timeline([track], _regions(), duration=3.0, hz=10.0)
    for point in track.points:
        found = position_at(timeline, 3, point.time)
        assert found is not None
        assert found[0] == pytest.approx(point.x, abs=0.01)
        assert found[1] == pytest.approx(point.y, abs=0.01)


def test_position_before_the_clip_or_after_it_is_unknown():
    timeline = build_timeline([_driving(5, 20, 0.1)], _regions(), duration=2.0, hz=5.0)
    assert position_at(timeline, 5, 5.0) is None  # clip is only 2 s long
    assert position_at(timeline, 99, 0.5) is None  # unknown vehicle id


def test_queue_series_matches_the_measured_peak():
    """The replay curve must not disagree with the reported metric."""
    tracks = [make_track(index, [(0.5, 0.5)] * 12, step=0.1) for index in range(1, 5)]
    tracks.append(_driving(9, 60, 0.1))
    regions = _regions(min_queue_seconds=0.0)
    timeline = build_timeline(tracks, regions, duration=6.0, hz=4.0)
    replay_peak = max(sample["q"] for sample in timeline["queue"])
    assert replay_peak == 4, "the four stationary vehicles are the queue"


def test_queue_is_unavailable_before_the_clip_starts():
    timeline = build_timeline([_driving()], _regions(), duration=4.0, hz=4.0)
    assert queue_at(timeline, -1.0) is None
    assert queue_at(timeline, 1.0) is not None


def test_payload_size_is_bounded_by_the_requested_resolution():
    tracks = [_driving(index, 100, 0.1) for index in range(1, 11)]
    coarse = build_timeline(tracks, _regions(), duration=10.0, hz=1.0)
    fine = build_timeline(tracks, _regions(), duration=10.0, hz=10.0)
    assert timeline_sample_count(fine) > timeline_sample_count(coarse) * 5
    assert fine["hz"] == 10.0 and coarse["hz"] == 1.0


def test_very_many_vehicles_are_capped_but_reported(monkeypatch):
    """A pathological clip stays responsive, and the omission is disclosed."""
    from backend.analytics import timeline as timeline_module

    monkeypatch.setattr(timeline_module, "MAX_VEHICLES", 10)
    tracks = [_driving(index, 6, 0.1) for index in range(1, 12)]
    built = build_timeline(tracks, _regions(), duration=0.6, hz=5.0)
    assert len(built["vehicles"]) == 10
    assert built["vehicles_omitted"] == 1


def test_resolution_is_clamped_to_a_sane_range():
    regions = _regions()
    assert build_timeline([], regions, 1.0, hz=0.1)["hz"] == 1.0
    assert build_timeline([], regions, 1.0, hz=99.0)["hz"] == 15.0
