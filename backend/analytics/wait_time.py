"""Estimated wait time.

For every vehicle we have a set of *queue episodes* (continuous time spent
inside the queue region while moving slower than the threshold).  The wait of
an episode is simply its duration::

    wait_i = t_leave - t_enter

and the reported statistics are the usual ones::

    W_avg = sum(wait_i) / N
    W_max = max(wait_i)

Only completed episodes are used.  An episode that is still open when the clip
ends is censored (its real duration is longer than what we measured) and is
counted separately so the numbers stay honest.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean, median

from .queue_detection import QueueEpisode


@dataclass(frozen=True, slots=True)
class WaitStats:
    count: int
    average: float | None
    median: float | None
    maximum: float | None
    minimum: float | None
    censored: int
    censored_seconds: float

    @property
    def has_data(self) -> bool:
        return self.count > 0


def wait_statistics(episodes: Sequence[QueueEpisode]) -> WaitStats:
    complete = [episode.duration for episode in episodes if episode.complete]
    censored = [episode for episode in episodes if not episode.complete]
    if not complete:
        return WaitStats(
            0, None, None, None, None, len(censored), sum(e.duration for e in censored)
        )
    return WaitStats(
        count=len(complete),
        average=round(fmean(complete), 2),
        median=round(float(median(complete)), 2),
        maximum=round(max(complete), 2),
        minimum=round(min(complete), 2),
        censored=len(censored),
        censored_seconds=round(sum(episode.duration for episode in censored), 2),
    )
