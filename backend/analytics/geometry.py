"""Analytics-facing name for the shared geometry primitives.

The implementations moved to :mod:`backend.geometry` because the pydantic
schemas need the same primitives and cannot import from ``analytics`` (see the
docstring there for the import cycle).  Analytics code keeps importing from
this module, so the "which layer owns geometry" question has exactly one
answer and :mod:`backend.analytics` stays the public face of the layer.

Nothing is defined here: every name below is the *same object* as in
:mod:`backend.geometry`, so a measurement cannot silently disagree with a
schema validation because of two copies of a shoelace loop.
"""

from __future__ import annotations

from ..geometry import (
    Line,
    Point,
    PointLike,
    Polygon,
    first_crossing_time,
    line_intersection,
    point_in_polygon,
    point_segment_side,
    polygon_area,
    polygon_centroid,
    simplify_polyline,
)

__all__ = [
    "Line",
    "Point",
    "PointLike",
    "Polygon",
    "first_crossing_time",
    "line_intersection",
    "point_in_polygon",
    "point_segment_side",
    "polygon_area",
    "polygon_centroid",
    "simplify_polyline",
]
