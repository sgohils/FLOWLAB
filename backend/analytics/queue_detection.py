"""Queue measurement.

Definition used everywhere in FLOWLAB (and mirrored by the simulator)::

    queued(t) = vehicle is inside the Queue Region  AND  speed_proxy(t) < threshold

    queue_length(t) = sum over vehicles of queued(t)
    Q_peak = max_t queue_length(t)

No model is involved: the number is a direct count of slow vehicles inside a
polygon the user drew on the frame.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import floor
from statistics import fmean, median

import numpy as np

from ..models.schemas import QueueSample, QueueVisit, Regions, Trajectory
from .geometry import point_in_polygon
from .motion import segment_speed

#: Never merge samples that are further apart than this; a track that was lost
#: for two seconds should not create a phantom "stopped" interval.
MAX_TRACK_GAP_FACTOR = 2.5


def max_track_gap(step: float) -> float:
    return step * MAX_TRACK_GAP_FACTOR


@dataclass(frozen=True, slots=True)
class QueueEpisode:
    """One continuous stay of a vehicle inside the queue region while slow."""

    vehicle_id: int
    start: float
    end: float
    complete: bool

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(slots=True)
class QueueSeries:
    step: float
    times: np.ndarray
    counts: np.ndarray
    episodes: list[QueueEpisode] = field(default_factory=list)

    @property
    def peak(self) -> int:
        return int(self.counts.max()) if self.counts.size else 0

    @property
    def average(self) -> float:
        return float(fmean(self.counts)) if self.counts.size else 0.0

    @property
    def median_value(self) -> float:
        return float(median(self.counts)) if self.counts.size else 0.0

    @property
    def occupied_seconds(self) -> float:
        return float(np.count_nonzero(self.counts) * self.step)

    def to_samples(self, limit: int | None = None) -> list[QueueSample]:
        """Convert to the JSON payload, optionally downsampled for the chart."""
        if self.counts.size == 0:
            return []
        if limit and self.counts.size > limit:
            stride = int(np.ceil(self.counts.size / limit))
            times, counts = self.times[::stride], self.counts[::stride]
        else:
            times, counts = self.times, self.counts
        return [
            QueueSample(time=round(float(t), 3), queue=int(c))
            for t, c in zip(times, counts)
        ]


def build_queue_series(
    tracks: Sequence[Trajectory],
    regions: Regions,
    duration: float,
    step: float,
) -> QueueSeries | None:
    """Sample ``queue_length(t)`` on a fixed time grid.

    A vehicle contributes to every grid instant covered by a slow segment that
    lies inside the polygon.  Interpolating the contact point between samples
    keeps the series smooth even at 10 fps.

    A vehicle must also have been slow *continuously* for
    ``regions.min_queue_seconds`` before it is counted.  A single noisy sample
    (a detection flicker) therefore cannot create a phantom queue, which keeps
    the queue definition consistent with the stop definition.
    """
    if not regions.has_queue or duration <= 0 or not tracks:
        return None
    # The grid covers [0, duration): the final instant is the start of the last
    # sampling interval, so no artificial "empty" sample sits at the end.
    size = max(1, int(np.ceil(duration / step)))
    times = np.arange(size, dtype=float) * step
    counts = np.zeros(size, dtype=np.int32)
    max_gap = max_track_gap(step)
    episodes: list[QueueEpisode] = []
    hold = max(0.0, regions.min_queue_seconds)

    for track in tracks:
        points = track.points
        # A vehicle can only be counted once per grid instant, so the segments
        # of a track are walked in time order and the counting cursor only ever
        # moves forward.
        cursor = 0
        slow_since: float | None = None
        for index in range(len(points) - 1):
            a, b = points[index], points[index + 1]
            gap = b.time - a.time
            if gap <= 0 or gap > max_gap:
                slow_since = None
                continue
            if segment_speed(a, b) >= regions.speed_threshold:
                slow_since = None
                continue
            if slow_since is None:
                slow_since = a.time
            if b.time - slow_since < hold - 1e-9:
                continue  # not slow for long enough yet
            first = max(0, floor(a.time / step), cursor)
            last = min(size - 1, floor(b.time / step))
            for k in range(first, last + 1):
                moment = times[k]
                if not a.time <= moment <= b.time:
                    continue
                fraction = (moment - a.time) / gap
                x = a.x + fraction * (b.x - a.x)
                y = a.y + fraction * (b.y - a.y)
                if point_in_polygon((x, y), regions.queue):
                    counts[k] += 1
                # Move the cursor past this instant: a vehicle can only be in
                # the queue once at any moment, and the next segment of the
                # same track starts where this one ended.
                cursor = k + 1
        episodes.extend(track_episodes(track, regions, max_gap))
    return QueueSeries(step=step, times=times, counts=counts, episodes=episodes)


def track_episodes(
    track: Trajectory,
    regions: Regions,
    max_gap: float,
) -> list[QueueEpisode]:
    """Contiguous in-region + slow intervals for a single vehicle.

    Censoring rules, which decide whether a visit is allowed into the wait
    statistics at all:

    * **left censored** - the visit begins at the very first tracked sample. We
      never saw the vehicle arrive, so its true wait is at least what we
      measured but could be far longer.  Excluded from the averages.
    * **right censored** - the visit is still open when the track ends (clip
      ended, or the id was lost).  Excluded from the averages.
    * **complete** - the vehicle was observed outside the region before the
      visit and then left it, so the duration is a real measurement.
    """
    points = track.points
    episodes: list[QueueEpisode] = []
    open_start: float | None = None
    open_end = 0.0
    first_time = points[0].time if points else 0.0

    def close(end_time: float, complete: bool) -> None:
        nonlocal open_start
        if open_start is not None:
            # A visit that starts on the first tracked sample has no known
            # entry time: it is censored, not completed.
            left_censored = abs(open_start - first_time) < 1e-9
            duration = end_time - open_start
            # Same duration rule as the queue length series, so the two can
            # never disagree about whether a vehicle was "queued".
            if duration + 1e-9 >= max(0.0, regions.min_queue_seconds):
                episodes.append(
                    QueueEpisode(
                        vehicle_id=track.vehicle_id,
                        start=round(open_start, 3),
                        end=round(end_time, 3),
                        complete=complete and not left_censored,
                    )
                )
            open_start = None

    for index in range(len(points) - 1):
        a, b = points[index], points[index + 1]
        gap = b.time - a.time
        if gap <= 0 or gap > max_gap:
            close(a.time, False)
            continue
        slow = segment_speed(a, b) < regions.speed_threshold
        if slow and point_in_polygon((a.x, a.y), regions.queue):
            if open_start is None:
                open_start = a.time
            open_end = b.time
        else:
            # The vehicle was seen leaving the queue or speeding up again.  The
            # episode ends at the *start* of that moving segment, which is the
            # last instant we know the vehicle was still slow.
            close(a.time, True)
    if open_start is not None:
        close(open_end, False)
    return episodes


def visits_from_episodes(episodes: Sequence[QueueEpisode]) -> list[QueueVisit]:
    return [
        QueueVisit(
            vehicle_id=episode.vehicle_id,
            start=episode.start,
            end=episode.end if episode.complete else None,
            duration=round(episode.duration, 2) if episode.complete else None,
            complete=episode.complete,
        )
        for episode in sorted(episodes, key=lambda e: (e.start, e.vehicle_id))
    ]
