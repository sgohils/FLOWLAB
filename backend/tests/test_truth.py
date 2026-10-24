"""The synthetic ground truth and the comparison that consumes it.

The reference file has to carry a ground truth for *both* counting rules, and
the validation script has to say which one it used: a residual against the
reference's occupancy counts is a real measurement difference, while one against
a ``queue_counts`` series whose rule the file does not declare may be nothing
more than the speed-and-hold definition gap. Comparing the two silently would
produce a large and meaningless number.
"""

from __future__ import annotations

import pytest

from backend.analytics.metrics import build_analysis
from backend.models.schemas import Analysis, VideoInfo
from backend.scripts.build_demo_dataset import build_trajectories, ground_truth, measurement_regions
from backend.scripts.validate_against_reference import (
    OCCUPANCY_DEFINITION,
    QUEUED_DEFINITION,
    UNTYPED_REFERENCE_DEFINITION,
    build_report,
    render_markdown,
)
from backend.tests.conftest import make_regions, make_track


@pytest.fixture(scope="module")
def reference() -> dict:
    """The bundled demo's ground truth, rebuilt in-process."""
    _, run = build_trajectories()
    return ground_truth(run, measurement_regions())


def _analysis() -> Analysis:
    """Three vehicles parked inside the region for the whole clip."""
    tracks = [
        make_track(
            index,
            [(0.2, 0.6)] + [(0.5, 0.6)] * 6 + [(0.8, 0.6), (0.9, 0.6)],
            step=0.1,
        )
        for index in range(1, 4)
    ]
    video = VideoInfo(
        filename="t.mp4",
        duration=20.0,
        fps=10.0,
        width=640,
        height=360,
        size_bytes=1000,
        processed_fps=10.0,
        frame_count=200,
    )
    return build_analysis("t", video, tracks, make_regions(), min_track_points=3)


def _series(counts: list[int]) -> list[dict]:
    """A reference series on the 1 s grid, in the hand-written file's format."""
    return [{"time_s": float(index), "count": count} for index, count in enumerate(counts)]


def test_reference_carries_an_occupancy_series_as_well(reference):
    occupancy = reference["occupancy_counts"]
    slow = reference["queue_counts"]
    assert occupancy, "the reference must carry the occupancy ground truth too"
    assert len(occupancy) == len(slow)
    assert [point["time_s"] for point in occupancy] == [
        point["time_s"] for point in slow
    ], "both series must sit on the same instants to be comparable"


def test_occupancy_is_the_looser_of_the_two_rules(reference):
    """No speed threshold and no hold, so it can only count the same or more."""
    occupancy = reference["occupancy_counts"]
    slow = reference["queue_counts"]
    assert max(point["count"] for point in occupancy) >= max(
        point["count"] for point in slow
    )
    assert sum(point["count"] for point in occupancy) > sum(
        point["count"] for point in slow
    ), "a moving vehicle inside the region is counted by occupancy only"


def test_validation_prefers_the_occupancy_reference_when_the_file_has_one():
    analysis = _analysis()
    report = build_report(
        {
            "queue_counts": _series([0, 0, 0]),
            "occupancy_counts": _series([50, 50, 50]),
        },
        analysis,
        0.0,
        None,
    )
    primary = report["queue_series"]
    assert primary["compares_against"] == OCCUPANCY_DEFINITION
    assert report["queue_length_app_definition"]["compares_against"] == QUEUED_DEFINITION
    # Two different reference series, so two different error figures: if the
    # primary block had silently used the slow reference these would agree.
    assert primary["mean_absolute_error"] != report["queue_length_app_definition"][
        "mean_absolute_error"
    ]


def test_a_reference_with_only_queue_counts_still_validates():
    """A file with only ``queue_counts`` must still produce a full report."""
    analysis = _analysis()
    report = build_report({"queue_counts": _series([50, 50, 50])}, analysis, 0.0, None)
    primary = report["queue_series"]
    assert OCCUPANCY_DEFINITION in primary["compares_against"]
    assert UNTYPED_REFERENCE_DEFINITION in primary["compares_against"]
    assert primary["mean_absolute_error"] > 0
    assert "compared against:" in render_markdown(report)


def test_a_result_stored_before_the_occupancy_series_says_so():
    """The fallback has to be labelled, not silent."""
    analysis = _analysis().model_copy(update={"region_occupancy_timeseries": []})
    report = build_report(
        {
            "queue_counts": _series([0, 0, 0]),
            "occupancy_counts": _series([0, 0, 0]),
        },
        analysis,
        0.0,
        None,
    )
    label = report["queue_series"]["compares_against"]
    assert label.startswith(QUEUED_DEFINITION)
    assert "no occupancy series" in label


def test_a_reference_without_any_count_series_has_no_queue_block():
    report = build_report({}, _analysis(), 0.0, None)
    assert "queue_series" not in report
