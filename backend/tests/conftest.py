"""Shared pytest fixtures and synthetic-trajectory factories.

The data directory is redirected to a temporary folder *before* any backend
module is imported, so the test run never touches a developer's real analyses.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("FLOWLAB_DATA_DIR", tempfile.mkdtemp(prefix="flowlab-tests-"))
os.environ.setdefault("FLOWLAB_MIN_TRACK_POINTS", "3")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from backend.models.schemas import Regions, Trajectory, TrajectoryPoint  # noqa: E402

#: A queue region covering the middle of the frame.
QUEUE_REGION = [(0.30, 0.30), (0.90, 0.30), (0.90, 0.95), (0.30, 0.95)]
#: A vertical entry line near the left edge and an exit line near the right.
ENTRY_LINE = [(0.15, 0.0), (0.15, 1.0)]
EXIT_LINE = [(0.85, 0.0), (0.85, 1.0)]


def make_points(
    positions: list[tuple[float, float]],
    start: float = 0.0,
    step: float = 0.5,
    frame_step: int = 5,
) -> list[TrajectoryPoint]:
    """Build trajectory points from ``(x, y)`` pairs, computing speed."""
    points: list[TrajectoryPoint] = []
    for index, (x, y) in enumerate(positions):
        speed = 0.0
        if index:
            previous = points[-1]
            elapsed = points[-1].time - previous.time
            if elapsed > 0:
                speed = float(np.hypot(x - previous.x, y - previous.y) / elapsed)
        points.append(
            TrajectoryPoint(
                frame=index * frame_step,
                time=round(start + index * step, 3),
                x=round(x, 5),
                y=round(y, 5),
                confidence=0.9,
                bbox=[round(x - 0.02, 5), round(y - 0.02, 5), round(x + 0.02, 5), round(y + 0.02, 5)],
                speed=round(speed, 5),
            )
        )
    return points


def make_track(
    vehicle_id: int,
    positions: list[tuple[float, float]],
    start: float = 0.0,
    step: float = 0.5,
    vehicle_class: str = "car",
) -> Trajectory:
    points = make_points(positions, start=start, step=step)
    return Trajectory(
        vehicle_id=vehicle_id,
        vehicle_class=vehicle_class,
        first_seen=points[0].time,
        last_seen=points[-1].time,
        duration=round(points[-1].time - points[0].time, 2),
        path_length=0.0,
        points=points,
    )


def drive_through(
    start_x: float,
    y: float = 0.6,
    stop_at: float | None = None,
    stop_seconds: float = 0.0,
    step: float = 0.5,
) -> list[tuple[float, float]]:
    """Positions that move right at a constant speed, optionally stopping.

    Speed is 0.1 normalised units per second, i.e. clearly above the default
    0.012 stopped threshold.
    """
    positions: list[tuple[float, float]] = []
    x = start_x
    stopped = False
    while x <= 0.95:
        positions.append((round(x, 4), y))
        if stop_at is not None and not stopped and x >= stop_at:
            stopped = True
            # Stay still for stop_seconds, sampled at the same rate.
            for _ in range(int(stop_seconds / step)):
                positions.append((round(x, 4), y))
        x += 0.1 * step
    positions.append((0.95, y))
    return positions


def make_regions(**overrides) -> Regions:
    values: dict = {
        "queue": list(QUEUE_REGION),
        "entry": list(ENTRY_LINE),
        "exit": list(EXIT_LINE),
        "speed_threshold": 0.012,
        "min_stop_seconds": 1.5,
        "sample_fps": 10.0,
    }
    values.update(overrides)
    return Regions(**values)


@pytest.fixture()
def regions() -> Regions:
    return make_regions()


@pytest.fixture()
def tmp_video(tmp_path):
    """Factory writing a small synthetic clip (blank frames by default)."""

    def _make(name: str = "clip.mp4", seconds: float = 3.0, fps: float = 10.0, draw=None) -> str:
        path = tmp_path / name
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 180)
        )
        if not writer.isOpened():
            pytest.skip("OpenCV cannot write MP4 files on this machine")
        for index in range(int(seconds * fps)):
            frame = np.full((180, 320, 3), 40, dtype=np.uint8)
            if draw is not None:
                draw(frame, index)
            writer.write(frame)
        writer.release()
        return str(path)

    return _make
