"""Queue length, stopped detection and estimated wait time."""

from __future__ import annotations

from backend.analytics.motion import detect_stops, segment_speed
from backend.analytics.queue_detection import (
    build_queue_series,
    build_region_occupancy_series,
    track_episodes,
)
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
    # The sample rate has to match the grid. A segment longer than
    # max_track_gap = 2.5 grid steps is treated as a lost track and discarded,
    # so a fixture sampled at 0.5 s against a 0.1 s grid has every segment
    # dropped: the series is all zeros and this test passes without counting a
    # vehicle at all. At 0.2 s consecutive segments share grid instants, so the
    # double count it is meant to catch is reachable.
    tracks = [
        make_track(
            index,
            drive_through(0.32, stop_at=0.6, stop_seconds=2.0, step=0.2),
            step=0.2,
        )
        for index in range(1, 6)
    ]
    series = _series(tracks, regions, duration=12.0, step=0.1)
    assert series is not None
    # A peak of zero would make the assertion after it vacuous.
    assert series.peak > 0
    assert series.peak <= len(tracks)
    # All five vehicles are inside the polygon together for the whole stop, so
    # the true peak is the vehicle count and anything higher is a double count.
    assert series.peak == len(tracks)


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


def test_region_occupancy_counts_a_vehicle_that_is_moving():
    """A paused frame counts every vehicle in the polygon, so occupancy must too."""
    regions = make_regions()
    moving = make_track(1, [(0.35, 0.6), (0.45, 0.6), (0.55, 0.6), (0.65, 0.6)], step=1.0)
    # 0.1 frame widths per second against a 0.012 threshold: clearly not slow.
    assert segment_speed(moving.points[0], moving.points[1]) > regions.speed_threshold

    occupancy = build_region_occupancy_series([moving], regions, duration=3.0, step=0.5)
    queued = build_queue_series([moving], regions, duration=3.0, step=0.5)
    assert occupancy is not None
    # Four samples from 0.0 s to 3.0 s on a 0.5 s grid: every instant counts.
    assert list(occupancy.counts) == [1, 1, 1, 1, 1, 1]
    assert occupancy.peak == 1
    # The application rule filters the same vehicle out, which is exactly why
    # the two numbers are reported side by side.
    assert queued is not None
    assert queued.peak == 0


def test_region_occupancy_never_exceeds_the_vehicle_count():
    """Regression test: a vehicle must not be counted twice at one instant.

    Track samples every 0.2 s against a 0.1 s grid means each segment covers two
    or three grid instants, so a missing cursor would count one vehicle twice at
    the instant its two segments meet.
    """
    regions = make_regions(speed_threshold=0.05, sample_fps=10.0)
    tracks = [
        make_track(index, drive_through(0.32, stop_at=0.6, stop_seconds=2.0, step=0.2), step=0.2)
        for index in range(1, 6)
    ]
    occupancy = build_region_occupancy_series(tracks, regions, duration=12.0, step=0.1)
    assert occupancy is not None
    assert occupancy.peak <= len(tracks)
    # All five are inside the polygon together, so the true peak is the count.
    assert occupancy.peak == len(tracks)


def test_region_occupancy_ignores_the_minimum_queue_seconds():
    """Inside the polygon is enough; there is no hold rule in a paused frame."""
    track = make_track(1, [(0.2, 0.6), (0.5, 0.6), (0.5, 0.6), (0.8, 0.6)], step=1.0)
    # The vehicle is inside the region for exactly one slow sample, at 1.0 s to
    # 2.0 s, then it drives away.
    occupancy = build_region_occupancy_series(
        [track], make_regions(min_queue_seconds=3.0), 3.0, 0.5
    )
    assert occupancy is not None
    assert list(occupancy.counts) == [0, 1, 1, 1, 1, 1]

    # The application rule needs the hold, and a one-sample stay is shorter
    # than the default half second.
    held = build_queue_series([track], make_regions(min_queue_seconds=3.0), 3.0, 0.5)
    assert held is not None
    assert held.peak == 0
    # Lowering the hold to zero is the only change that makes the queued series
    # count it, so the difference above is the hold and not the geometry.
    lenient = build_queue_series([track], make_regions(min_queue_seconds=0.0), 3.0, 0.5)
    assert lenient is not None
    assert lenient.peak == 1


def test_region_occupancy_requires_a_region():
    regions = make_regions(queue=[])
    tracks = [make_track(1, [(0.5, 0.6)] * 5, step=0.5)]
    assert build_region_occupancy_series(tracks, regions, 3.0, 0.5) is None


def test_detect_stops_reports_long_stops_only():
    track = make_track(1, drive_through(0.30, y=0.6, stop_at=0.6, stop_seconds=3.0, step=0.5))
    polygon = [(0.3, 0.3), (0.9, 0.3), (0.9, 0.9), (0.3, 0.9)]
    stops = detect_stops(
        track, speed_threshold=0.012, min_stop_seconds=1.5, max_gap=1.25, queue_polygon=polygon
    )
    assert len(stops) == 1
    assert stops[0].duration == 3.0
    assert stops[0].region == "queue"


def test_detect_stops_ignores_short_pauses():
    track = make_track(1, drive_through(0.30, y=0.6, stop_at=0.6, stop_seconds=0.5, step=0.5))
    assert (
        detect_stops(track, 0.012, 1.5, 1.25, [(0.3, 0.3), (0.9, 0.3), (0.9, 0.9), (0.3, 0.9)])
        == []
    )


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


def test_thinned_series_never_loses_a_brief_peak():
    """The chart must not be able to contradict the metric card.

    Thinning keeps the maximum of each bucket: a peak that lasts less than one
    bucket still appears in the transported series.
    """
    import numpy as np

    from backend.analytics.queue_detection import QueueSeries

    # 1350 grid samples, a one-instant spike on an odd index, decimated to 675.
    counts = np.zeros(1350, dtype=np.int32)
    counts[101] = 7  # odd index, deliberately off the every-nth stride
    counts[700] = 4
    times = np.arange(1350, dtype=float) * 0.1
    series = QueueSeries(step=0.1, times=times, counts=counts)

    full = series.to_samples()
    thinned = series.to_samples(675)
    assert max(sample.queue for sample in thinned) == max(sample.queue for sample in full) == 7
    assert len(thinned) <= 676  # the ragged tail is kept, not dropped
    # Every-nth decimation would have lost the spike entirely.
    assert counts[::2].max() < max(counts)


def test_thinning_keeps_the_average_close_to_the_original():
    import numpy as np

    from backend.analytics.queue_detection import QueueSeries

    counts = np.tile(np.array([0, 2, 4, 6], dtype=np.int32), 300)
    times = np.arange(counts.size, dtype=float) * 0.1
    series = QueueSeries(step=0.1, times=times, counts=counts)
    thinned = series.to_samples(100)
    assert len(thinned) <= 101
    # Bucket-max never reports less than the true mean, only more.
    assert max(s.queue for s in thinned) >= counts.mean()


def test_thinned_series_is_monotonic_in_time():
    import numpy as np

    from backend.analytics.queue_detection import QueueSeries

    counts = np.sin(np.arange(500) / 7.0).astype(np.int32) * 3 + 3
    times = np.arange(500, dtype=float) * 0.1
    series = QueueSeries(step=0.1, times=times, counts=counts)
    thinned = series.to_samples(50)
    assert [s.time for s in thinned] == sorted(s.time for s in thinned)
    assert max(s.queue for s in thinned) == int(counts.max())


def test_segment_speed_is_distance_over_time():
    points = make_track(1, [(0.0, 0.0), (0.1, 0.0)], step=1.0).points
    assert abs(segment_speed(points[0], points[1]) - 0.1) < 1e-6
    assert segment_speed(points[0], points[0]) == 0.0
