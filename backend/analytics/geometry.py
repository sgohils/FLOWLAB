"""Planar geometry helpers for normalised (0-1) image coordinates.

All functions take and return coordinates in *normalised image space* so the
same code works for a 640 px preview and a 4K source video.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

Point = tuple[float, float]
Polygon = Sequence[Point]
Line = Sequence[Point]

_EPS = 1e-10


class PointLike(Protocol):
    x: float
    y: float
    time: float


def polygon_area(polygon: Polygon) -> float:
    """Shoelace formula: A = 1/2 * |sum(x_i*y_{i+1} - x_{i+1}*y_i)|."""
    if len(polygon) < 3:
        return 0.0
    total = 0.0
    for (x1, y1), (x2, y2) in zip(polygon, list(polygon[1:]) + [polygon[0]]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def polygon_centroid(polygon: Polygon) -> Point:
    """Area centroid of a simple polygon (falls back to the vertex mean)."""
    if not polygon:
        return (0.5, 0.5)
    if len(polygon) < 3:
        return (
            sum(p[0] for p in polygon) / len(polygon),
            sum(p[1] for p in polygon) / len(polygon),
        )
    area = 0.0
    cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(polygon, list(polygon[1:]) + [polygon[0]]):
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area) < _EPS:
        return (
            sum(p[0] for p in polygon) / len(polygon),
            sum(p[1] for p in polygon) / len(polygon),
        )
    area *= 0.5
    return (cx / (6.0 * area), cy / (6.0 * area))


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Ray-casting point-in-polygon test; points on the boundary count as inside.

    The boundary case matters for queue regions: vehicles routinely sit exactly
    on the edge of a user drawn polygon and should still be counted.
    """
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, list(polygon[1:]) + [polygon[0]]):
        # 1. boundary test: the point is collinear with the edge and inside its box
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if (
            abs(cross) < 1e-9
            and min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9
            and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9
        ):
            return True
        # 2. classic crossing-number test
        if (y1 > y) != (y2 > y):
            x_intersect = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_intersect:
                inside = not inside
    return inside


def point_segment_side(point: Point, a: Point, b: Point) -> float:
    """Signed side of the infinite line a->b: positive on the left."""
    return (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])


def _on_segment(point: Point, a: Point, b: Point, tolerance: float = 1e-7) -> bool:
    return (
        min(a[0], b[0]) - tolerance <= point[0] <= max(a[0], b[0]) + tolerance
        and min(a[1], b[1]) - tolerance <= point[1] <= max(a[1], b[1]) + tolerance
    )


def first_crossing_time(
    points: Sequence[PointLike],
    line: Line,
    max_gap: float,
    direction: str = "any",
) -> float | None:
    """Time at which a trajectory first crosses the finite segment ``line``.

    Each track can only be counted once (a vehicle entering the scene cannot
    cross the same measurement line twice for our purposes).  The crossing time
    is linearly interpolated between the two samples that straddle the line::

        f = |s0| / (|s0| + |s1|)   t = t0 + f * (t1 - t0)

    where ``s`` are the signed side distances.  Samples separated by more than
    ``max_gap`` seconds are not connected: a track that was lost for two seconds
    tells us nothing about where it crossed.

    ``direction`` selects the counting policy:

    ``"any"``      count the crossing in either direction
    ``"forward"``  count only crossings that go from the left side of the
                   directed line (start -> end) to its right side, which is the
                   normal direction of travel and excludes a vehicle reversing
                   back across the line.
    """
    if len(line) != 2:
        return None
    (ax, ay), (bx, by) = line[0], line[1]
    previous: PointLike | None = None
    previous_side = 0.0
    for point in points:
        side = (bx - ax) * (point.y - ay) - (by - ay) * (point.x - ax)
        if abs(side) < _EPS:
            continue  # exactly on the line: wait for a sample on the other side
        if previous is not None and side * previous_side < 0.0:
            gap = point.time - previous.time
            if 0.0 < gap <= max_gap:
                is_forward = side < previous_side
                if direction == "forward" and not is_forward:
                    previous, previous_side = point, side
                    continue
                fraction = abs(previous_side) / (abs(previous_side) + abs(side))
                cross_x = previous.x + fraction * (point.x - previous.x)
                cross_y = previous.y + fraction * (point.y - previous.y)
                if _on_segment((cross_x, cross_y), line[0], line[1]):
                    return previous.time + fraction * gap
        previous, previous_side = point, side
    return None


def line_intersection(a1: Point, a2: Point, b1: Point, b2: Point) -> Point | None:
    """Intersection of two finite segments, or ``None`` when they do not meet."""
    rx, ry = a2[0] - a1[0], a2[1] - a1[1]
    sx, sy = b2[0] - b1[0], b2[1] - b1[1]
    denominator = rx * sy - ry * sx
    if abs(denominator) < _EPS:
        return None
    t = ((b1[0] - a1[0]) * sy - (b1[1] - a1[1]) * sx) / denominator
    u = ((b1[0] - a1[0]) * ry - (b1[1] - a1[1]) * rx) / denominator
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return (a1[0] + t * rx, a1[1] + t * ry)
    return None


def simplify_polyline(points: Sequence[Point], tolerance: float) -> list[Point]:
    """Ramer-Douglas-Peucker simplification (keeps the map readable)."""
    if len(points) < 3:
        return list(points)
    first, last = points[0], points[-1]
    max_distance = 0.0
    index = 0
    for i in range(1, len(points) - 1):
        ax, ay = last[0] - first[0], last[1] - first[1]
        bx, by = points[i][0] - first[0], points[i][1] - first[1]
        norm = (ax * ax + ay * ay) ** 0.5
        distance = abs(ax * by - ay * bx) / norm if norm > _EPS else (
            (bx * bx + by * by) ** 0.5
        )
        if distance > max_distance:
            max_distance, index = distance, i
    if max_distance <= tolerance:
        return [first, last]
    left = simplify_polyline(points[: index + 1], tolerance)
    right = simplify_polyline(points[index:], tolerance)
    return left[:-1] + right
