"""Queue length, stopped detection and estimated wait time."""

from __future__ import annotations

from backend.analytics.motion import detect_stops, segment_speed
from backend.analytics.queue_detection import build_queue_series, track_episodes
from backend.analytics.wait_time import wait_statistics
from backend.tests.conftest import drive_through, make_regions, make_track


def _series(tracks, regions, duration, step=0.5):
    return build_queue_series(tracks, regions, duration, step)


def test_queue_counts_only_slow_vehicles_inside_the_region():
    regions = make_regions()
    # Moving vehicle inside the queue region: never queued.
    moving = make_track(1, [(x, 0.6) for x in (0.4, 0.5, 0.6, 0.7)], step=1.0)
    # Stopped vehicle inside the queue region.
    stopped = make_track(2, [(0.5, 0.6)] * 6, step=1.0)
    # Stopped vehicle outside the queue region (y = 0.1 is above it).
    outside = make_track(3, [(0.5, 0.1)] * 6, step=1.0)

    series = _series([moving, stopped, outside], regions, duration=5.0, step=0.5)
    assert series is not None
    # Only vehicle 2 is queued: moving traffic and out-of-region stops are
    # excluded, so the count never rises above 1 although three tracks exist.
    assert set(series.counts.tolist()) == {1}
    assert series.peak == 1
    assert series.average == 1.0  # present for the whole window


def test_queue_peak_counts_simultaneous_vehicles():
    regions = make_regions()
    tracks = [make_track(index, [(0.5, 0.5)] * 8, step=0.5) for index in range(1, 6)]
    series = _series(tracks, regions, duration=4.0, step=0.5)
    assert series is not None
    assert series.peak == 5
    assert series.average == 5.0


def test_peak_queue_can_never_exceed_the_vehicle_count():
    """Regression test: a vehicle must not be counted twice at one instant."""
    regions = make_regions(speed_threshold=0.05, sample_fps=10.0)
    tracks = [make_track(index, drive_through(0.32, stop_at=0.6, stop_seconds=2.0)) for index in range(1, 6)]
    series = _series(tracks, regions, duration=12.0, step=0.1)
    assert series is not None
    assert series.peak <= len(tracks)


def test_queue_requires_a_region():
    regions = make_regions(queue=[])
    tracks = [make_track(1, [(0.5, 0.6)] * 5, step=0.5)]
    assert _series(tracks, regions, duration=3.0) is None


def test_queue_ignores_track_gaps():
    regions = make_regions()
    # A track with a 20 second hole: the vehicle must not count as queued for it.
    points = [(0.5, 0.6)] * 4 + [(0.5, 0.6)] * 4
    stopped = make_track(1, points, step=1.0)
    late = make_track(2, [(0.5, 0.6)] * 4, start=20.0, step=1.0)
    series = _series([stopped, late], regions, duration=24.0, step=0.5)
    assert series is not None
    # The second vehicle is only queued in its own window, never bridged.
    assert series.peak == 1


def test_median_and_occupied_duration():
    regions = make_regions()
    # Vehicle 1 is queued for 2 s, vehicle 2 for 1 s.
    tracks = [make_track(1, [(0.5, 0.6)] * 4, step=0.5), make_track(2, [(0.5, 0.6)] * 2, step=0.5)]
    series = _series(tracks, regions, duration=4.0, step=0.5)
    assert series is not None
    assert list(series.counts) == [2, 2, 1, 1, 0, 0, 0, 0]
    assert series.median_value == 0.5
    assert series.occupied_seconds == 2.0


def test_detect_stops_reports_long_stops_only():
    track = make_track(1, drive_through(0.30, y=0.6, stop_at=0.6, stop_seconds=3.0, step=0.5))
    polygon = [(0.3, 0.3), (0.9, 0.3), (0.9, 0.9), (0.3, 0.9)]
    stops = detect_stops(track, speed_threshold=0.012, min_stop_seconds=1.5, max_gap=1.25, queue_polygon=polygon)
    assert len(stops) == 1
    assert stops[0].duration == 3.0
    assert stops[0].region == "queue"


def test_detect_stops_ignores_short_pauses():
    track = make_track(1, drive_through(0.30, y=0.6, stop_at=0.6, stop_seconds=0.5, step=0.5))
    assert detect_stops(track, 0.012, 1.5, 1.25, [(0.3, 0.3), (0.9, 0.3), (0.9, 0.9), (0.3, 0.9)]) == []


def test_episodes_and_wait_statistics():
    regions = make_regions()
    # Both vehicles approach from OUTSIDE the region (x < 0.30), stop inside it
    # and then drive on, so both visits have a known start and a known end.
    first = make_track(1, [(0.2, 0.6)] + [(0.5, 0.6)] * 6 + [(0.6, 0.6), (0.7, 0.6)], step=1.0)
    second = make_track(2, [(0.2, 0.6)] + [(0.5, 0.6)] * 4 + [(0.6, 0.6), (0.7, 0.6)], step=1.0)
    episodes = track_episodes(first, regions, 1.25) + track_episodes(second, regions, 1.25)
    stats = wait_statistics(episodes)
    assert stats.count == 2
    # A visit ends at the last sample known to be slow, which is the start of
    # the first moving segment: t=6.0 for vehicle 1 and t=4.0 for vehicle 2.
    assert sorted(episode.duration for episode in episodes) == [3.0, 5.0]
    assert stats.average == 4.0
    assert stats.maximum == 5.0
    assert stats.censored == 0


def test_visit_that_starts_at_the_first_frame_is_censored():
    """A vehicle already queueing when the clip starts has an unknown entry time."""
    regions = make_regions()
    already_queued = make_track(1, [(0.5, 0.6)] * 6 + [(0.6, 0.6), (0.7, 0.6)], step=1.0)
    episodes = track_episodes(already_queued, regions, 1.25)
    assert len(episodes) == 1
    assert episodes[0].complete is False
    stats = wait_statistics(episodes)
    assert stats.count == 0
    assert stats.censored == 1
    assert stats.average is None


def test_repeated_visits_are_separate_episodes():
    regions = make_regions()
    track = make_track(
        1,
        [(0.5, 0.6)] * 3 + [(0.2, 0.6)] * 2 + [(0.5, 0.6)] * 3 + [(0.7, 0.6), (0.9, 0.6)],
        step=1.0,
    )
    episodes = track_episodes(track, regions, 1.25)
    assert len(episodes) == 2
    # The first visit starts on the very first frame, so only the second one
    # has a known entry time and may enter the wait statistics.
    assert [episode.complete for episode in episodes] == [False, True]


def test_short_slow_pass_does_not_create_a_visit():
    """min_queue_seconds keeps single-sample detector jitter out of the metrics."""
    strict = make_regions(min_queue_seconds=2.0)
    track = make_track(1, [(0.2, 0.6)] + [(0.5, 0.6)] * 2 + [(0.7, 0.6)], step=1.0)
    assert track_episodes(track, strict, 1.25) == []
    lenient = make_regions(min_queue_seconds=0.0)
    assert len(track_episodes(track, lenient, 1.25)) == 1


def test_queue_series_also_applies_the_duration_threshold():
    """The queue length and the wait visits must agree about 'queued'."""
    tracks = [make_track(1, [(0.2, 0.6)] + [(0.5, 0.6)] * 2 + [(0.7, 0.6)], step=1.0)]
    lenient = build_queue_series(tracks, make_regions(min_queue_seconds=0.0), 4.0, 0.5)
    strict = build_queue_series(tracks, make_regions(min_queue_seconds=3.0), 4.0, 0.5)
    assert lenient is not None and lenient.peak == 1
    assert strict is not None and strict.peak == 0


def test_region_residence_is_measured_separately_from_being_slow():
    """A vehicle can be inside the region while still moving."""
    from backend.analytics.metrics import _region_seconds
    from backend.analytics.motion import segment_speed

    regions = make_regions()
    # Creeping: inside the region the whole time but always above the threshold.
    creeping = make_track(1, [(0.35, 0.6), (0.45, 0.6), (0.55, 0.6), (0.65, 0.6)], step=1.0)
    assert _region_seconds(creeping.points, regions, 1.25) == 3.0
    assert segment_speed(creeping.points[0], creeping.points[1]) > regions.speed_threshold


def test_censored_episodes_are_excluded_from_averages():
    regions = make_regions()
    # The clip ends while the vehicle is still queueing.
    still_queued = make_track(1, [(0.5, 0.6)] * 5, step=1.0)
    episodes = track_episodes(still_queued, regions, 1.25)
    stats = wait_statistics(episodes)
    assert stats.count == 0
    assert stats.censored == 1
    assert stats.average is None


def test_segment_speed_is_distance_over_time():
    points = make_track(1, [(0.0, 0.0), (0.1, 0.0)], step=1.0).points
    assert abs(segment_speed(points[0], points[1]) - 0.1) < 1e-6
    assert segment_speed(points[0], points[0]) == 0.0
