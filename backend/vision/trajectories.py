"""Track accumulation and trajectory building.

A *track* is the set of samples that share one anonymous vehicle id.  This
module turns the per-frame detections into cleaned, smoothed trajectories that
the analytics layer can rely on.

Smoothing: the contact point is passed through an exponential filter

    x_s = alpha * x_measured + (1 - alpha) * x_previous

but the filter is bypassed whenever the vehicle jumps further than
``smoothing_jump`` (normalised units) between two samples, so real accelera-
tions and the first sample after an occlusion are never flattened out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot

from ..config import Settings, settings as default_settings
from ..models.schemas import Trajectory, TrajectoryPoint
from .detector import RawDetection


@dataclass(slots=True)
class _Buffer:
    vehicle_id: int
    class_name: str
    points: list[TrajectoryPoint] = field(default_factory=list)
    class_counts: dict[str, int] = field(default_factory=dict)
    last_x: float = 0.0
    last_y: float = 0.0
    initialised: bool = False

    @property
    def dominant_class(self) -> str:
        """Most frequently detected class for this id (ByteTrack can flip)."""
        if not self.class_counts:
            return self.class_name
        return max(self.class_counts.items(), key=lambda item: item[1])[0]


class TrackAccumulator:
    """Collects detections over time and produces trajectories."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or default_settings
        self._tracks: dict[int, _Buffer] = {}

    def update(self, frame_index: int, timestamp: float, detections: list[RawDetection]) -> None:
        for detection in detections:
            if detection.track_id is None:
                continue
            buffer = self._tracks.get(detection.track_id)
            if buffer is None:
                buffer = _Buffer(vehicle_id=detection.track_id, class_name=detection.class_name)
                self._tracks[detection.track_id] = buffer
            buffer.class_counts[detection.class_name] = buffer.class_counts.get(detection.class_name, 0) + 1
            x, y = self._smooth(buffer, detection.contact)
            speed = 0.0
            if buffer.points:
                last = buffer.points[-1]
                elapsed = timestamp - last.time
                if elapsed > 0:
                    speed = hypot(x - last.x, y - last.y) / elapsed
            buffer.points.append(
                TrajectoryPoint(
                    frame=frame_index,
                    time=round(timestamp, 3),
                    x=round(x, 5),
                    y=round(y, 5),
                    confidence=round(detection.confidence, 3),
                    bbox=[
                        round(detection.x1, 5),
                        round(detection.y1, 5),
                        round(detection.x2, 5),
                        round(detection.y2, 5),
                    ],
                    speed=round(speed, 5),
                )
            )

    def _smooth(self, buffer: _Buffer, point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        alpha = self._settings.smoothing_alpha
        if not buffer.initialised:
            buffer.initialised = True
            buffer.last_x, buffer.last_y = x, y
            return x, y
        if hypot(x - buffer.last_x, y - buffer.last_y) > self._settings.smoothing_jump:
            # Real movement (or a re-acquired track): trust the measurement.
            buffer.last_x, buffer.last_y = x, y
            return x, y
        smooth_x = alpha * x + (1.0 - alpha) * buffer.last_x
        smooth_y = alpha * y + (1.0 - alpha) * buffer.last_y
        buffer.last_x, buffer.last_y = smooth_x, smooth_y
        return smooth_x, smooth_y

    @property
    def track_count(self) -> int:
        return len(self._tracks)

    def build(self) -> list[Trajectory]:
        """Finalise every accumulated track into a :class:`Trajectory`."""
        trajectories: list[Trajectory] = []
        for buffer in self._tracks.values():
            if not buffer.points:
                continue
            points = buffer.points
            trajectories.append(
                Trajectory(
                    vehicle_id=buffer.vehicle_id,
                    vehicle_class=buffer.dominant_class,
                    first_seen=points[0].time,
                    last_seen=points[-1].time,
                    duration=round(points[-1].time - points[0].time, 2),
                    path_length=0.0,
                    stopped_seconds=0.0,
                    queue_seconds=0.0,
                    mean_speed=0.0,
                    points=points,
                )
            )
        trajectories.sort(key=lambda track: track.vehicle_id)
        return trajectories
