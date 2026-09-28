"""Point-in-polygon and line-crossing geometry."""

from __future__ import annotations

from backend.analytics.geometry import (
    first_crossing_time,
    line_intersection,
    point_in_polygon,
    polygon_area,
    polygon_centroid,
    simplify_polyline,
)
from backend.tests.conftest import make_points


def test_point_inside_square():
    square = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
    assert point_in_polygon((0.5, 0.5), square)
    assert not point_in_polygon((0.9, 0.5), square)
    assert not point_in_polygon((0.1, 0.1), square)


def test_point_on_boundary_counts_as_inside():
    """Vehicles routinely sit exactly on a drawn edge; they must be counted."""
    square = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
    assert point_in_polygon((0.2, 0.5), square)  # left edge
    assert point_in_polygon((0.5, 0.8), square)  # top edge
    assert point_in_polygon((0.8, 0.8), square)  # corner


def test_point_in_concave_polygon():
    # A "C" shape opening to the right.
    shape = [(0.1, 0.1), (0.6, 0.1), (0.6, 0.35), (0.3, 0.35), (0.3, 0.65), (0.6, 0.65), (0.6, 0.9), (0.1, 0.9)]
    assert point_in_polygon((0.2, 0.5), shape)
    assert not point_in_polygon((0.45, 0.5), shape)  # inside the notch


def test_degenerate_polygon_never_contains():
    assert not point_in_polygon((0.5, 0.5), [])
    assert not point_in_polygon((0.5, 0.5), [(0.1, 0.1), (0.9, 0.9)])


def test_polygon_area_matches_unit_square():
    assert polygon_area([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]) == 1.0
    assert polygon_area([(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)]) == 0.25
    assert polygon_area([(0.0, 0.0), (1.0, 1.0)]) == 0.0


def test_polygon_centroid_of_square():
    cx, cy = polygon_centroid([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
    assert round(cx, 6) == 0.5
    assert round(cy, 6) == 0.5


def test_first_crossing_time_is_interpolated():
    points = make_points([(0.10, 0.5), (0.30, 0.5), (0.50, 0.5)], step=1.0)
    # The line x = 0.4 is crossed between t = 1.0 (x=0.3) and t = 2.0 (x=0.5).
    crossing = first_crossing_time(points, [(0.4, 0.0), (0.4, 1.0)], max_gap=2.0)
    assert crossing is not None
    assert abs(crossing - 1.5) < 1e-6


def test_no_crossing_when_movement_never_reaches_the_line():
    points = make_points([(0.10, 0.5), (0.20, 0.5), (0.30, 0.5)], step=1.0)
    assert first_crossing_time(points, [(0.9, 0.0), (0.9, 1.0)], max_gap=2.0) is None


def test_crossing_requires_the_finite_segment_not_the_infinite_line():
    """A vehicle passing beside the line segment must not be counted."""
    points = make_points([(0.10, 0.9), (0.50, 0.9), (0.90, 0.9)], step=1.0)
    # Vertical segment only spans y in [0.0, 0.2].
    assert first_crossing_time(points, [(0.4, 0.0), (0.4, 0.2)], max_gap=2.0) is None


def test_crossing_ignored_across_a_long_gap():
    points = make_points([(0.30, 0.5), (0.50, 0.5)], start=0.0, step=5.0)
    assert first_crossing_time(points, [(0.4, 0.0), (0.4, 1.0)], max_gap=1.0) is None
    assert first_crossing_time(points, [(0.4, 0.0), (0.4, 1.0)], max_gap=5.0) is not None


def test_each_track_crosses_a_line_only_once():
    points = make_points(
        [(0.1, 0.5), (0.5, 0.5), (0.9, 0.5), (0.5, 0.5), (0.1, 0.5)], step=1.0
    )
    assert first_crossing_time(points, [(0.4, 0.0), (0.4, 1.0)], max_gap=2.0) is not None


def test_line_intersection():
    assert line_intersection((0.0, 0.5), (1.0, 0.5), (0.5, 0.0), (0.5, 1.0)) == (0.5, 0.5)
    assert line_intersection((0.0, 0.5), (1.0, 0.5), (0.5, 0.6), (0.5, 1.0)) is None


def test_simplify_polyline_keeps_endpoints():
    line = [(0.0, 0.0), (0.25, 0.001), (0.5, 0.0), (0.75, 0.001), (1.0, 0.0)]
    simplified = simplify_polyline(line, tolerance=0.01)
    assert simplified[0] == (0.0, 0.0)
    assert simplified[-1] == (1.0, 0.0)
    assert len(simplified) < len(line)
