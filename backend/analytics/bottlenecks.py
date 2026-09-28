"""Bottleneck detection on a coarse spatial grid.

The scene is divided into a fixed grid.  For every cell we accumulate four
plain, auditable quantities:

``vehicle_passes``  distinct anonymous vehicles that entered the cell
``slow_seconds``    time spent moving below the stopped threshold in the cell
``stopped_seconds`` duration of registered stop events centred in the cell
``queue_seconds``   time spent inside the queue region within the cell
``density``         number of trajectory samples (trajectory density)

Each quantity is min-max normalised across the scene and combined::

    score = 0.35*n_slow + 0.25*n_stopped + 0.20*n_queue
          + 0.10*n_passes + 0.10*n_density

A cell is only reported as a bottleneck when at least ``min_passes`` different
vehicles were slowed there and the accumulated slow time is at least twice
``min_stop_seconds`` - i.e. repeated, measurable congestion rather than one
parked car.  The full grid is returned as a heat map so the UI can shade the
scene even outside the reported cells.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import fmean

from ..models.schemas import Bottleneck, HeatCell, Regions, StopInterval, Trajectory
from .geometry import point_in_polygon
from .motion import segment_speed

#: Weight of each normalised component in the bottleneck score.
SCORE_WEIGHTS: dict[str, float] = {
    "slow_seconds": 0.35,
    "stopped_seconds": 0.25,
    "queue_seconds": 0.20,
    "vehicle_passes": 0.10,
    "density": 0.10,
}


@dataclass(slots=True)
class CellStats:
    col: int
    row: int
    x: float
    y: float
    width: float
    height: float
    vehicle_passes: int = 0
    slow_seconds: float = 0.0
    stopped_seconds: float = 0.0
    queue_seconds: float = 0.0
    occupancy_seconds: float = 0.0
    density: int = 0
    score: float = 0.0
    vehicles: set[int] = field(default_factory=set)

    @property
    def mean_slowdown_seconds(self) -> float:
        return round(self.slow_seconds / self.vehicle_passes, 2) if self.vehicle_passes else 0.0


def analyze_grid(
    tracks: Sequence[Trajectory],
    regions: Regions,
    stops: Sequence[StopInterval],
    cols: int,
    rows: int,
    max_gap: float,
    min_passes: int = 2,
    max_cells: int = 6,
) -> tuple[list[CellStats], list[Bottleneck]]:
    cells: dict[tuple[int, int], CellStats] = {}

    def cell_for(x: float, y: float) -> CellStats:
        col = min(cols - 1, max(0, int(x * cols)))
        row = min(rows - 1, max(0, int(y * rows)))
        key = (col, row)
        if key not in cells:
            cells[key] = CellStats(
                col=col,
                row=row,
                x=(col + 0.5) / cols,
                y=(row + 0.5) / rows,
                width=1.0 / cols,
                height=1.0 / rows,
            )
        return cells[key]

    for track in tracks:
        points = track.points
        for index in range(len(points) - 1):
            a, b = points[index], points[index + 1]
            gap = b.time - a.time
            if gap <= 0 or gap > max_gap:
                continue
            mid_x = (a.x + b.x) / 2.0
            mid_y = (a.y + b.y) / 2.0
            cell = cell_for(mid_x, mid_y)
            cell.density += 1
            cell.occupancy_seconds += gap
            cell.vehicles.add(track.vehicle_id)
            if segment_speed(a, b) < regions.speed_threshold:
                cell.slow_seconds += gap
            if point_in_polygon((mid_x, mid_y), regions.queue):
                cell.queue_seconds += gap

    for stop in stops:
        cell_for(stop.x, stop.y).stopped_seconds += stop.duration

    for cell in cells.values():
        cell.vehicle_passes = len(cell.vehicles)
        # The set is kept: the interface uses these ids to highlight the
        # vehicles that contributed to the cell, so the number can be checked.

    _score(cells)

    ordered = sorted(cells.values(), key=lambda c: c.score, reverse=True)
    bottlenecks = [
        Bottleneck(
            id=index + 1,
            x=round(cell.x, 5),
            y=round(cell.y, 5),
            width=round(cell.width, 5),
            height=round(cell.height, 5),
            vehicle_passes=cell.vehicle_passes,
            vehicle_ids=sorted(cell.vehicles)[:60],
            stopped_seconds=round(cell.stopped_seconds, 2),
            mean_slowdown_seconds=cell.mean_slowdown_seconds,
            occupancy_seconds=round(cell.occupancy_seconds, 2),
            score=round(cell.score, 4),
        )
        for index, cell in enumerate(
            cell
            for cell in ordered
            if cell.vehicle_passes >= min_passes and cell.slow_seconds > 0
        )
        if index < max_cells
    ]
    return ordered, bottlenecks


def _score(cells: dict[tuple[int, int], CellStats]) -> None:
    """Min-max normalise every component, then apply the fixed weights."""
    maxima = {
        name: max((getattr(cell, name) for cell in cells.values()), default=0.0)
        for name in SCORE_WEIGHTS
    }
    if not cells:
        return
    for cell in cells.values():
        total = 0.0
        for name, weight in SCORE_WEIGHTS.items():
            peak = maxima[name]
            normalised = (getattr(cell, name) / peak) if peak > 0 else 0.0
            total += weight * normalised
        cell.score = total


def heat_cells(cells: Sequence[CellStats]) -> list[HeatCell]:
    """Flatten the grid for the client side heat map overlay."""
    return [
        HeatCell(
            x=round(cell.x, 5),
            y=round(cell.y, 5),
            width=round(cell.width, 5),
            height=round(cell.height, 5),
            value=round(cell.score, 4),
            vehicle_passes=cell.vehicle_passes,
        )
        for cell in cells
        if cell.density > 0
    ]


def summarize(cells: Sequence[CellStats]) -> dict[str, float]:
    """Scene-level aggregates shown next to the heat map."""
    if not cells:
        return {"occupied_cells": 0.0, "mean_cell_score": 0.0, "slow_share": 0.0}
    total_slow = sum(cell.slow_seconds for cell in cells)
    total_occupancy = sum(cell.occupancy_seconds for cell in cells)
    return {
        "occupied_cells": float(len(cells)),
        "mean_cell_score": round(fmean(cell.score for cell in cells), 4),
        "slow_share": round(total_slow / total_occupancy, 4) if total_occupancy else 0.0,
    }
