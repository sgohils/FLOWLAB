"""Heuristic suggestions for the measurement regions.

A user who just uploaded a clip would otherwise have to draw three regions
before seeing a single number.  FLOWLAB therefore proposes a starting geometry
from the trajectories themselves, and clearly labels it as *auto-detected* in
the UI so it can be corrected:

* **queue region** - the bounding box of the grid cells where the most slow
  vehicle-time was measured (the same accumulation the bottleneck grid uses).
* **entry line** - a segment perpendicular to the mean travel direction, placed
  through the median position of the first sightings.
* **exit line**  - the same construction at the median last-sighting position.

These are heuristics, not measurements: every number in the app is still
computed from the regions the user ends up using.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import hypot
from statistics import median

from ..config import Settings
from ..config import settings as default_settings
from ..models.schemas import Regions, Trajectory, VideoInfo
from .motion import segment_speed

#: Half-length of a suggested line, as a fraction of the frame.
LINE_HALF_LENGTH = 0.42
#: Grid used to locate the slow-vehicle hotspot.
_CELL = 0.1


def suggest_regions(
    tracks: Sequence[Trajectory],
    video: VideoInfo,
    settings: Settings | None = None,
) -> Regions:
    """Return suggested regions (possibly empty when there is no evidence)."""
    settings = settings or default_settings
    regions = Regions(
        speed_threshold=settings.speed_threshold,
        min_stop_seconds=settings.min_stop_seconds,
        sample_fps=settings.sample_fps,
    )
    usable = [track for track in tracks if len(track.points) >= 3]
    if not usable:
        return regions

    queue_polygon = _queue_polygon(usable, settings)
    direction = _mean_direction(usable, settings)
    entry = _line_through(usable, direction, first=True)
    exit_line = _line_through(usable, direction, first=False)
    return regions.model_copy(
        update={"queue": queue_polygon, "entry": entry, "exit": exit_line}
    )


def _queue_polygon(tracks: Sequence[Trajectory], settings: Settings) -> list[tuple[float, float]]:
    """Bounding box of the cells with the most accumulated slow time."""
    slow: dict[tuple[int, int], float] = {}
    vehicles: dict[tuple[int, int], set[int]] = {}
    for track in tracks:
        points = track.points
        for index in range(len(points) - 1):
            a, b = points[index], points[index + 1]
            gap = b.time - a.time
            if gap <= 0 or gap > 1.0:
                continue
            if segment_speed(a, b) >= settings.speed_threshold:
                continue
            key = (int((a.x + b.x) / 2 / _CELL), int((a.y + b.y) / 2 / _CELL))
            slow[key] = slow.get(key, 0.0) + gap
            vehicles.setdefault(key, set()).add(track.vehicle_id)
    if not slow:
        return []

    ranked = sorted(
        slow.items(),
        key=lambda item: (item[1], len(vehicles.get(item[0], ()))),
        reverse=True,
    )
    best = ranked[0]
    if best[1] < settings.min_stop_seconds or len(vehicles.get(best[0], ())) < 2:
        return []

    # Include neighbouring cells that carry a meaningful share of the peak so
    # the region covers a queue rather than a single parking spot.
    threshold = best[1] * 0.25
    chosen = {key for key, value in slow.items() if value >= threshold}
    x0 = min((key[0] for key in chosen), default=0) * _CELL
    y0 = min((key[1] for key in chosen), default=0) * _CELL
    x1 = (max((key[0] for key in chosen), default=0) + 1) * _CELL
    y1 = (max((key[1] for key in chosen), default=0) + 1) * _CELL
    pad = _CELL
    x0 = max(0.0, x0 - pad)
    y0 = max(0.0, y0 - pad)
    x1 = min(1.0, x1 + pad)
    y1 = min(1.0, y1 + pad)
    if (x1 - x0) < _CELL or (y1 - y0) < _CELL:
        return []
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _mean_direction(tracks: Sequence[Trajectory], settings: Settings) -> tuple[float, float]:
    """Unit vector of the average direction of travel (moves only)."""
    dx = dy = 0.0
    for track in tracks:
        points = track.points
        for index in range(len(points) - 1):
            a, b = points[index], points[index + 1]
            if segment_speed(a, b) < settings.speed_threshold:
                continue
            dx += b.x - a.x
            dy += b.y - a.y
    norm = hypot(dx, dy)
    if norm < 1e-6:
        return (1.0, 0.0)
    return (dx / norm, dy / norm)


def _line_through(
    tracks: Sequence[Trajectory],
    direction: tuple[float, float],
    first: bool,
) -> list[tuple[float, float]]:
    """A segment perpendicular to travel, crossing most trajectories.

    Positions are projected on the travel axis.  The entry line sits at the
    10th percentile of the first sightings and the exit line at the 90th
    percentile of the last sightings, so the large majority of vehicles
    actually cross both of them.
    """
    dx, dy = direction
    positions = [track.points[0] if first else track.points[-1] for track in tracks if track.points]
    if not positions:
        return []
    projections = [dx * point.x + dy * point.y for point in positions]
    ordered = sorted(projections)
    percentile = 0.1 if first else 0.9
    index = max(0, min(len(ordered) - 1, round(percentile * (len(ordered) - 1))))
    target = ordered[index]
    band = [
        point
        for point, projection in zip(positions, projections, strict=True)
        if abs(projection - target) <= 0.05
    ]
    group = band or [positions[index]]
    cx = median(point.x for point in group)
    cy = median(point.y for point in group)
    nx, ny = -dy, dx
    return [
        (
            min(1.0, max(0.0, cx + nx * LINE_HALF_LENGTH)),
            min(1.0, max(0.0, cy + ny * LINE_HALF_LENGTH)),
        ),
        (
            min(1.0, max(0.0, cx - nx * LINE_HALF_LENGTH)),
            min(1.0, max(0.0, cy - ny * LINE_HALF_LENGTH)),
        ),
    ]
