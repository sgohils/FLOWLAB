"""End-to-end analytics: trajectories in, complete result out."""

from __future__ import annotations

import pytest

from backend.analytics.metrics import build_analysis
from backend.analytics.suggestions import suggest_regions
from backend.models.schemas import Regions, VideoInfo
from backend.tests.conftest import drive_through, make_regions, make_track

DURATION = 30.0
#: The synthetic tracks below are sampled at 10 fps, the same rate the analysis
#: is told about.  Samples further apart than 2.5x the step are deliberately
#: ignored by the analytics, so the two must always agree.
SAMPLE_FPS = 10.0
STEP = 0.1


def _video() -> VideoInfo:
    return VideoInfo(
        filename="test.mp4",
        duration=DURATION,
        fps=10.0,
        width=1280,
        height=720,
        size_bytes=1024,
        processed_fps=SAMPLE_FPS,
        frame_count=int(DURATION * 10),
    )


def _regions() -> Regions:
    return make_regions(sample_fps=SAMPLE_FPS)


def _scene() -> list:
    """Six vehicles: three queue in the middle, three drive straight through."""
    tracks = []
    for index in range(1, 4):
        tracks.append(
            make_track(
                index,
                drive_through(0.05, y=0.6, stop_at=0.55, stop_seconds=4.0, step=STEP),
                step=STEP,
            )
        )
    for index in range(4, 7):
        tracks.append(
            make_track(index, drive_through(0.05, y=0.9, step=STEP), step=STEP)
        )
    return tracks


def test_build_analysis_produces_consistent_measurements():
    analysis = build_analysis("test1", _video(), _scene(), _regions(), min_track_points=3)
    summary = analysis.summary
    assert summary.vehicles_detected == 6
    assert summary.vehicles_tracked == 6
    assert summary.peak_queue is not None and summary.peak_queue >= 1
    assert summary.peak_queue <= summary.vehicles_tracked
    assert summary.average_queue is not None and summary.average_queue <= summary.peak_queue
    assert summary.throughput_per_minute is not None
    assert summary.entry_per_minute is not None
    assert analysis.queue_timeseries
    assert max(sample.queue for sample in analysis.queue_timeseries) == summary.peak_queue


def test_short_fragments_are_discarded_but_counted():
    tracks = [*_scene(), make_track(99, [(0.2, 0.6), (0.3, 0.6)], step=STEP)]
    analysis = build_analysis("test2", _video(), tracks, _regions(), min_track_points=3)
    assert analysis.summary.vehicles_detected == 7
    assert analysis.summary.vehicles_tracked == 6
    assert any("fragment" in warning for warning in analysis.warnings)


def test_no_vehicles_produces_a_helpful_warning():
    analysis = build_analysis("test3", _video(), [], _regions(), min_track_points=3)
    assert analysis.summary.vehicles_tracked == 0
    assert any("No vehicles" in warning for warning in analysis.warnings)
    assert analysis.queue_timeseries == []


def test_missing_regions_are_explained():
    analysis = build_analysis("test4", _video(), _scene(), Regions(), min_track_points=3)
    warnings = " ".join(analysis.warnings)
    assert "queue region" in warnings
    assert "exit line" in warnings
    assert "entry line" in warnings
    assert analysis.summary.peak_queue is None
    assert analysis.summary.throughput_per_minute is None
    # Without lines, arrivals fall back to first sightings so the twin can run.
    assert len(analysis.arrivals) == 6


def test_events_reference_real_moments():
    analysis = build_analysis("test5", _video(), _scene(), _regions(), min_track_points=3)
    assert analysis.events
    for event in analysis.events:
        assert 0.0 <= event.time <= DURATION
    assert any(event.kind == "peak" for event in analysis.events)


def test_bottlenecks_are_inside_the_frame():
    analysis = build_analysis("test6", _video(), _scene(), _regions(), min_track_points=3)
    assert analysis.bottlenecks
    for bottleneck in analysis.bottlenecks:
        assert 0.0 <= bottleneck.x <= 1.0
        assert 0.0 <= bottleneck.y <= 1.0
        assert bottleneck.vehicle_passes >= 1
    assert all(cell.value >= 0.0 for cell in analysis.heat_grid)


def test_trajectory_details_are_measured():
    analysis = build_analysis("test7", _video(), _scene(), _regions(), min_track_points=3)
    queued = [track for track in analysis.trajectories if track.queue_seconds > 0]
    assert queued, "the queuing vehicles should have a queue time"
    for track in queued:
        assert track.path_length > 0
        assert track.stopped_seconds >= 0.0
        assert track.points[0].time < track.points[-1].time


def test_calibration_is_derived_from_the_scene():
    analysis = build_analysis("test8", _video(), _scene(), _regions(), min_track_points=3)
    calibration = analysis.calibration
    assert calibration.arrival_rate_per_minute > 0
    assert calibration.service_time_seconds > 0
    assert calibration.vehicles_used == 6
    assert calibration.notes


def test_suggested_regions_cover_the_slow_cluster():
    """The auto-detected queue region must contain the vehicles that stop."""
    tracks = [
        make_track(
            index, drive_through(0.05, y=0.6, stop_at=0.5, stop_seconds=5.0, step=STEP), step=STEP
        )
        for index in range(1, 6)
    ]
    suggested = suggest_regions(tracks, _video())
    assert suggested.has_queue
    from backend.analytics.geometry import point_in_polygon

    for track in tracks:
        middle = track.points[len(track.points) // 2]
        assert point_in_polygon((middle.x, middle.y), suggested.queue)
    assert len(suggested.entry) == 2
    assert len(suggested.exit) == 2


def test_suggested_regions_need_more_than_one_vehicle():
    """A single stationary vehicle is not a bottleneck - it is a parked car."""
    one = [make_track(1, [(0.5, 0.5)] * 6, step=STEP)]
    assert suggest_regions(one, _video()).queue == []


def test_suggested_lines_sit_across_the_travel_direction():
    tracks = [
        make_track(index, drive_through(0.05, y=0.6, step=STEP), step=STEP) for index in range(1, 5)
    ]
    suggested = suggest_regions(tracks, _video())
    assert len(suggested.entry) == 2 and len(suggested.exit) == 2
    for line in (suggested.entry, suggested.exit):
        (x0, y0), (x1, y1) = line
        # The suggested line is perpendicular to the (horizontal) travel axis.
        assert abs(x1 - x0) < 1e-6
        assert abs(y1 - y0) > 0.1


@pytest.mark.parametrize("volume", [0.5, 0.75, 1.0, 1.25, 1.5])
def test_analysis_is_reproducible(volume):
    """Region changes must be deterministic: same tracks, same numbers."""
    from backend.simulation.scenarios import build_arrivals

    tracks = _scene()
    first = build_analysis("v", _video(), tracks, _regions(), min_track_points=3)
    arrivals = build_arrivals(first.arrivals, volume, 0.0, DURATION, 7)
    assert arrivals == build_arrivals(first.arrivals, volume, 0.0, DURATION, 7)


def test_remeasuring_with_new_regions_keeps_every_vehicle():
    """Regression: discarded fragments must survive a region change.

    The first pass reports "detected" from *all* fragments; if only the
    filtered trajectories were stored, redrawing a region would silently
    change that number.
    """
    from backend.analytics.metrics import deserialise_analysis, serialise_analysis

    tracks = [
        *_scene(),
        make_track(90, [(0.2, 0.6), (0.25, 0.6)], step=STEP),
        make_track(91, [(0.3, 0.6), (0.4, 0.6), (0.45, 0.6)], step=STEP),
    ]
    first = build_analysis("r", _video(), tracks, _regions(), min_track_points=3)
    assert first.summary.vehicles_detected == 8
    assert first.summary.vehicles_tracked == 7

    stored, restored = deserialise_analysis(serialise_analysis(first, raw_tracks=tracks))
    assert stored.summary.vehicles_detected == 8

    # Move the region somewhere the queuing vehicles never stop: the queue
    # measurement must change while the vehicle counts do not.
    elsewhere = _regions().model_copy(
        update={"queue": [(0.88, 0.30), (0.99, 0.30), (0.99, 0.95), (0.88, 0.95)]}
    )
    second = build_analysis("r", _video(), restored, elsewhere, min_track_points=3)
    assert second.summary.vehicles_detected == 8
    assert second.summary.vehicles_tracked == 7
    assert any("fragment" in warning for warning in second.warnings)
    assert first.summary.peak_queue and first.summary.peak_queue > 0
    assert second.summary.peak_queue == 0
