"""Evidence, assumptions and the sensitivity range.

These cover the claims the interface makes about *how* a number was produced and
*how much* the output depends on an estimated parameter.
"""

from __future__ import annotations

from backend.analytics.metrics import build_analysis
from backend.models.schemas import Analysis, Evidence, Scenario, VideoInfo
from backend.simulation.simulator import run_scenario, service_time_sensitivity
from backend.tests.conftest import make_regions, make_track


def _video(duration: float = 20.0) -> VideoInfo:
    return VideoInfo(
        filename="t.mp4",
        duration=duration,
        fps=10.0,
        width=640,
        height=360,
        size_bytes=1000,
        processed_fps=10.0,
        frame_count=int(duration * 10),
    )


def _analysis(tracks=None, duration: float = 20.0) -> Analysis:
    """Build an analysis from tracks sampled at 10 fps.

    The sample rate has to match ``regions.sample_fps``: samples further apart
    than 2.5 sampling intervals are deliberately treated as tracking gaps, so
    mismatched fixtures would measure fragmentation instead of the metric.
    """
    tracks = tracks if tracks is not None else [
        make_track(
            index,
            [(0.2, 0.6)] + [(0.5, 0.6)] * 6 + [(0.8, 0.6), (0.9, 0.6)],
            step=0.1,
        )
        for index in range(1, 4)
    ]
    return build_analysis("e1", _video(duration), tracks, make_regions(), min_track_points=3)


def test_evidence_counts_line_crossings_and_visits():
    analysis = _analysis()
    evidence = analysis.evidence
    assert evidence.observation_seconds == 20.0
    assert evidence.vehicles_detected == 3
    assert evidence.vehicles_tracked == 3
    assert evidence.completed_queue_visits == 3
    assert evidence.vehicles_crossed_exit == 3
    assert evidence.vehicles_crossed_entry == 3


def test_censored_visits_are_counted_separately():
    # A vehicle still queueing when the clip ends.
    tracks = [make_track(1, [(0.5, 0.6)] * 12, step=0.1)]
    evidence = _analysis(tracks, duration=1.0).evidence
    assert evidence.completed_queue_visits == 0
    assert evidence.censored_queue_visits == 1
    assert evidence.censored_seconds > 0


def test_fragmentation_reports_gaps_and_missing_samples():
    """A track with a dropout must be visible in the evidence, not hidden."""
    from backend.models.schemas import Trajectory, TrajectoryPoint

    early = [(0.10 + 0.01 * i, 0.5) for i in range(20)]
    late = [(0.60 + 0.01 * i, 0.5) for i in range(20)]
    times = [round(0.1 * i, 3) for i in range(20)] + [round(3.0 + 0.1 * i, 3) for i in range(20)]
    points = [
        TrajectoryPoint(frame=i, time=t, x=xy[0], y=xy[1], confidence=0.9)
        for i, (t, xy) in enumerate(zip(times, early + late, strict=True))
    ]
    track = Trajectory(
        vehicle_id=1,
        vehicle_class="car",
        first_seen=points[0].time,
        last_seen=points[-1].time,
        duration=points[-1].time - points[0].time,
        path_length=0.0,
        points=points,
    )
    evidence = _analysis([track], duration=5.0).evidence
    assert evidence.gaps == 1, "the dropout must be counted"
    # 40 samples observed over a 4.9 s span that needs 49: the 1.1 s dropout is
    # about a fifth of the track.
    assert 0.15 < evidence.missing_sample_share < 0.25
    # One vehicle with a fifth of its samples missing is not enough to lean on.
    assert evidence.evidence_is_thin is True


def test_thin_evidence_is_flagged():
    tracks = [make_track(1, [(0.2, 0.6), (0.3, 0.6), (0.4, 0.6)], step=0.1)]
    evidence = _analysis(tracks, duration=0.2).evidence
    assert evidence.vehicles_tracked == 1
    assert evidence.evidence_is_thin is True


def test_missing_sample_share_is_never_negative():
    evidence = _analysis().evidence
    assert 0.0 <= evidence.missing_sample_share <= 1.0


def test_an_analysis_stored_by_an_older_build_still_loads():
    """Results already on disk must not break when the schema grows."""
    payload = _analysis().model_dump(mode="json")
    payload.pop("evidence", None)
    restored = Analysis.model_validate(payload)
    assert restored.evidence.vehicles_tracked == 0
    assert restored.summary.vehicles_tracked == 3


def test_a_result_stored_before_the_occupancy_series_still_loads():
    """The region-occupancy series was added after the first release."""
    payload = _analysis().model_dump(mode="json")
    assert payload["region_occupancy_timeseries"], "a new result must carry the series"
    payload.pop("region_occupancy_timeseries")
    restored = Analysis.model_validate(payload)
    assert restored.region_occupancy_timeseries == []
    assert restored.queue_timeseries


def test_sensitivity_range_spans_the_stated_alternative_values():
    analysis = _analysis()
    result = run_scenario(analysis, Scenario())
    sensitivity = result.sensitivity
    assert sensitivity is not None
    assert sensitivity.parameter == "exit service time"
    assert len(sensitivity.values) == 3
    assert "not a statistical confidence interval" in sensitivity.note
    low, mid, high = sensitivity.values
    assert low.service_time_seconds < mid.service_time_seconds < high.service_time_seconds
    # A slower exit cannot produce a shorter queue.
    assert low.peak_queue <= high.peak_queue
    assert low.average_wait_seconds <= high.average_wait_seconds
    assert sensitivity.peak_queue_range == (
        min(v.peak_queue for v in sensitivity.values),
        max(v.peak_queue for v in sensitivity.values),
    )


def test_sensitivity_is_absent_without_arrivals():
    analysis = _analysis()
    stripped = analysis.model_copy(update={"arrivals": []})
    assert run_scenario(stripped, Scenario()).sensitivity is None


def test_sensitivity_is_deterministic():
    analysis = _analysis()
    first = service_time_sensitivity(analysis)
    second = service_time_sensitivity(analysis)
    assert first.model_dump() == second.model_dump()


def test_evidence_defaults_are_zero_not_required():
    empty = Evidence()
    assert empty.vehicles_tracked == 0
    assert empty.evidence_is_thin is True
