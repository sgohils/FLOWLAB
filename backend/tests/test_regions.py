"""Region validation and the measurement-line counting policy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models.schemas import MIN_POLYGON_AREA, Regions
from backend.tests.conftest import EXIT_LINE, make_regions, make_track

# ----------------------------------------------------------------- validation


def test_simple_polygon_is_accepted():
    regions = make_regions()
    assert regions.has_queue
    assert regions.queue[0] == (0.30, 0.30)


def test_polygon_with_too_few_points_is_rejected():
    with pytest.raises(ValidationError, match="at least three points"):
        Regions(queue=[(0.1, 0.1), (0.5, 0.5)])


def test_self_intersecting_polygon_is_rejected():
    """A bow tie makes inside/outside undefined, so it must not be accepted."""
    with pytest.raises(ValidationError, match="crosses over itself"):
        Regions(queue=[(0.1, 0.1), (0.9, 0.2), (0.2, 0.8), (0.8, 0.9)])


def test_concave_but_simple_polygon_is_accepted():
    """A "C" shape is a perfectly valid measurement region."""
    shape = [
        (0.1, 0.1),
        (0.6, 0.1),
        (0.6, 0.35),
        (0.3, 0.35),
        (0.3, 0.65),
        (0.6, 0.65),
        (0.6, 0.9),
        (0.1, 0.9),
    ]
    assert Regions(queue=shape).has_queue


def test_repeated_vertices_are_rejected():
    with pytest.raises(ValidationError, match="repeated points"):
        Regions(queue=[(0.1, 0.1), (0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)])


def test_repeated_closing_vertex_is_allowed():
    """Closing a polygon by repeating the first point is a normal drawing style."""
    square = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)]
    assert Regions(queue=square).has_queue


def test_tiny_polygon_is_rejected_with_a_reason():
    with pytest.raises(ValidationError, match="too small"):
        Regions(queue=[(0.10, 0.10), (0.11, 0.10), (0.11, 0.11), (0.10, 0.11)])
    assert MIN_POLYGON_AREA == 0.002


def test_degenerate_line_is_rejected():
    with pytest.raises(ValidationError, match="two distinct points"):
        Regions(exit=[(0.5, 0.5), (0.5, 0.5)])


def test_out_of_frame_coordinates_are_rejected():
    with pytest.raises(ValidationError):
        Regions(queue=[(0.1, 0.1), (1.4, 0.1), (1.4, 0.9), (0.1, 0.9)])


# ------------------------------------------------------------- counting policy


def test_forward_direction_ignores_a_reverse_crossing():
    from backend.analytics.throughput import collect_crossings

    # The line runs bottom -> top, so its left side is the left of the frame.
    # A vehicle driving left to right crosses it "forward"; one driving right to
    # left crosses it backwards.
    line = [(0.5, 0.0), (0.5, 1.0)]
    left_to_right = make_track(1, [(0.2, 0.9), (0.5, 0.9), (0.8, 0.9)], step=1.0)
    right_to_left = make_track(2, [(0.8, 0.1), (0.5, 0.1), (0.2, 0.1)], step=1.0)

    both = collect_crossings([left_to_right, right_to_left], line, step=1.0)
    assert both.count == 2  # default policy counts either direction

    directed = collect_crossings(
        [left_to_right, right_to_left], line, step=1.0, direction="forward"
    )
    assert directed.count == 1
    assert list(directed.per_vehicle) == [1]  # only the left-to-right vehicle


def test_line_is_finite_not_an_infinite_line():
    from backend.analytics.throughput import collect_crossings

    # Both vehicles pass x = 0.5, but the segment only spans y in [0.0, 0.2].
    segment = [(0.5, 0.0), (0.5, 0.2)]
    inside = make_track(1, [(0.2, 0.1), (0.5, 0.1), (0.8, 0.1)], step=1.0)
    outside = make_track(2, [(0.2, 0.9), (0.5, 0.9), (0.8, 0.9)], step=1.0)
    crossings = collect_crossings([inside, outside], segment, step=1.0)
    assert crossings.count == 1
    assert list(crossings.per_vehicle) == [1]


def test_each_vehicle_crosses_a_line_at_most_once():
    from backend.analytics.throughput import collect_crossings

    # A vehicle that crosses, turns around and crosses back is still one count.
    wiggling = make_track(
        1, [(0.1, 0.5), (0.5, 0.5), (0.9, 0.5), (0.5, 0.5), (0.1, 0.5)], step=1.0
    )
    crossings = collect_crossings([wiggling], EXIT_LINE, step=1.0)
    assert crossings.count == 1


def test_jitter_along_the_line_does_not_double_count():
    """A sample sitting exactly on the line must not create two crossings."""
    from backend.analytics.throughput import collect_crossings

    on_the_line = make_track(
        1, [(0.6, 0.5), (0.85, 0.5), (0.85, 0.5), (0.95, 0.5)], step=0.5
    )
    crossings = collect_crossings([on_the_line], EXIT_LINE, step=1.0)
    assert crossings.count == 1
    # The samples sitting exactly on the line are skipped, so the crossing is
    # interpolated across the samples that actually straddle it.
    assert 0.0 < crossings.times[0] < 1.5


def test_crossing_is_not_bridged_across_a_tracking_gap():
    from backend.analytics.throughput import collect_crossings

    gapped = make_track(1, [(0.6, 0.5), (0.95, 0.5)], step=5.0)
    assert collect_crossings([gapped], EXIT_LINE, step=1.0).count == 0
    assert collect_crossings([gapped], EXIT_LINE, step=5.0).count == 1


def test_direction_field_is_carried_on_the_region():
    regions = make_regions(exit_direction="forward", entry_direction="any")
    assert regions.exit_direction == "forward"
    assert Regions().exit_direction == "any"
