"""Replay timeline: uniform-in-time samples, explicit tracking gaps.

The point of this module is honesty about what is known at any instant.  If a
vehicle's track was lost, the payload must say so instead of letting the client
draw a straight line through the gap.

These tests read the payload the way the player does - a vehicle's known
positions are exactly the union of its ``segments`` - and the small readers at
the top of this file are *test* helpers.  The backend ships the wire format,
not a query API over it: nothing in the API or the analysis pipeline asks
"where was vehicle 7 at t=3.0", so a reader for that belongs next to the
assertions that need it rather than in ``backend.analytics.timeline``.
"""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

import pytest

from backend.analytics.timeline import build_timeline
from backend.models.schemas import Regions, Trajectory, TrajectoryPoint
from backend.tests.conftest import make_track

# --------------------------------------------------------------- payload readers


def known_intervals(timeline: dict, vehicle_id: int) -> list[tuple[float, float]]:
    """The instants over which the payload claims to know a vehicle's position."""
    for vehicle in timeline["vehicles"]:
        if vehicle["id"] == vehicle_id:
            return [
                (segment["t"][0], segment["t"][-1])
                for segment in vehicle["segments"]
                if segment["t"]
            ]
    return []


def position_at(timeline: dict, vehicle_id: int, moment: float) -> tuple[float, float] | None:
    """Position from the nearest segment, or ``None`` where the payload is silent.

    ``None`` inside a tracking gap is the whole point: the caller must hide the
    vehicle rather than draw it somewhere invented.
    """
    for vehicle in timeline["vehicles"]:
        if vehicle["id"] != vehicle_id:
            continue
        for segment in vehicle["segments"]:
            times = segment["t"]
            if not times or not times[0] <= moment <= times[-1]:
                continue
            index = max(i for i, t in enumerate(times) if t <= moment)
            xs, ys = segment["x"], segment["y"]
            if index + 1 == len(times):
                return (xs[index], ys[index])
            span = times[index + 1] - times[index]
            fraction = 0.0 if span <= 0 else (moment - times[index]) / span
            return (
                xs[index] + fraction * (xs[index + 1] - xs[index]),
                ys[index] + fraction * (ys[index + 1] - ys[index]),
            )
        return None
    return None


def queue_at(timeline: dict, moment: float) -> int | None:
    """Queue length at the nearest sample, or ``None`` before the clip starts."""
    samples = timeline["queue"]
    if not samples or moment < samples[0]["t"]:
        return None
    return int(min(samples, key=lambda sample: abs(sample["t"] - moment))["q"])


def sample_count(timeline: dict) -> int:
    """Total position samples in the payload."""
    return sum(
        len(segment["t"]) for vehicle in timeline["vehicles"] for segment in vehicle["segments"]
    )


# ------------------------------------------------------------------- fixtures


def _regions(**overrides) -> Regions:
    values = {
        "queue": [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
        "entry": [(0.0, 0.0), (0.0, 1.0)],
        "exit": [(1.0, 0.0), (1.0, 1.0)],
        "speed_threshold": 0.012,
        "min_stop_seconds": 1.5,
        "min_queue_seconds": 0.5,
        "sample_fps": 10.0,
    }
    values.update(overrides)
    return Regions(**values)


def _driving(vehicle_id: int = 1, count: int = 50, step: float = 0.1) -> Trajectory:
    positions = [(0.1 + 0.015 * index, 0.5) for index in range(count)]
    return make_track(vehicle_id, positions, step=step)


def _track_with_gap(vehicle_id: int) -> Trajectory:
    """Tracked 0-1.5 s, lost for 6 s, tracked again from 7.5 s."""
    early = [(0.10 + 0.02 * index, 0.5) for index in range(16)]  # 0.0 - 1.5 s
    late = [(0.60 + 0.02 * index, 0.5) for index in range(8)]  # 7.5 - 8.3 s
    times = [round(0.1 * index, 3) for index in range(len(early))] + [
        round(7.5 + 0.1 * index, 3) for index in range(len(late))
    ]
    points = [
        TrajectoryPoint(frame=index, time=time, x=x, y=y, confidence=0.9)
        for index, (time, (x, y)) in enumerate(zip(times, early + late, strict=True))
    ]
    return Trajectory(
        vehicle_id=vehicle_id,
        vehicle_class="car",
        first_seen=points[0].time,
        last_seen=points[-1].time,
        duration=points[-1].time - points[0].time,
        path_length=0.0,
        points=points,
    )


# ------------------------------------------------- the shared parity contract
#
# ``backend/tests/fixtures/timeline_sample.json`` is the single artefact that the
# producer and the consumer both assert against.
#
# ``build_timeline`` (here) and ``positionAt`` / ``queueAt`` (frontend, in
# ``frontend/src/state/ReplayContext.tsx``) are two independent implementations of
# the same question - "what did the payload say at t = 1.5?" - and a JSON payload
# is the only thing they share.  Nothing ran them against each other: the frontend
# test pinned a hand-captured literal, so ``build_timeline`` could change its
# output and the frontend would keep passing against a shape the backend no longer
# produces.  Replay would then draw vehicles at the wrong place or report the
# wrong queue length with **no failing test**: the interface would just be quietly
# wrong.
#
# This section is the *producer* half of that contract.  It rebuilds the payload
# from the inputs below and asserts it is exactly the committed fixture, so a
# change in ``build_timeline`` fails here.  ``frontend/src/state/
# timelinePayload.test.ts`` is the *consumer* half: it reads the same committed
# file and asserts ``positionAt`` / ``queueAt`` agree at the instants pinned
# below.
#
# REGENERATING THE FIXTURE
# -----------------------
# If ``test_committed_fixture_is_exactly_what_the_producer_builds`` fails, then
# ``build_timeline``'s output changed.  That is a behaviour change and has to be
# *understood* before anything else happens:
#
#   1. read the diff and name the instants that moved, and by how much;
#   2. work out why the producer changed (a new rounding rule, a different
#      resampling step, a changed gap threshold, a reordered key);
#   3. check the moved instants against the intent the fixture exists to pin: a
#      position inside a tracking gap must stay *absent*, a parked vehicle must
#      stay still, the queue series must not collapse to all-zero;
#   4. only then regenerate the fixture, and record in the commit message which
#      instants changed and why.
#
# Never regenerate the fixture to turn a red test green.  The fixture is the
# contract, and regenerating it to absorb an unexplained change deletes the only
# evidence that the two implementations had started to disagree.

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "timeline_sample.json"

#: Long enough for a queue to build and a vehicle to be lost, short enough that
#: the committed JSON can still be read by eye.
FIXTURE_DURATION = 4.0
FIXTURE_HZ = 4.0


def _parity_track(
    vehicle_id: int,
    samples: list[tuple[float, float, float]],
    *,
    queue_seconds: float = 0.0,
    stopped_seconds: float = 0.0,
) -> Trajectory:
    """One synthetic track from ``(time, x, y)`` triples at the analysis' own rate."""
    points = [
        TrajectoryPoint(frame=index * 10, time=round(time, 3), x=x, y=y, confidence=0.9)
        for index, (time, x, y) in enumerate(samples)
    ]
    return Trajectory(
        vehicle_id=vehicle_id,
        vehicle_class="car",
        first_seen=points[0].time,
        last_seen=points[-1].time,
        duration=round(points[-1].time - points[0].time, 2),
        path_length=0.0,
        queue_seconds=queue_seconds,
        stopped_seconds=stopped_seconds,
        points=points,
    )


def _parity_tracks() -> list[Trajectory]:
    """Three tracks, each chosen to break a naive reading of the payload.

    * **vehicle 3** - stop-and-go.  Moves until 1.2 s, sits still at (0.75, 0.5)
      until 3.1 s, then moves off the right-hand edge of the polygon.  It is
      inside the queue region throughout, so it joins the queue series halfway
      through the clip while its own positions stay perfectly flat: a consumer
      cannot infer "queued" from "moving", and must not infer "moving" from
      "queued".
    * **vehicle 7** - a real tracking gap.  Tracked 0.0-0.5 s, lost for 0.6 s
      (more than the 0.25 s threshold), tracked again 1.1-2.0 s.  Two segments,
      and the window between them is genuinely *unknown*: a reader has to answer
      null there instead of inventing motion across the dropout.  Its second
      segment also starts at t = 1.1, which is **off** the 0.25 s transport grid,
      so a consumer that assumes a uniform grid for the whole track is caught as
      well.
    * **vehicle 11** - parked for the whole clip at (0.5, 0.5).  Zero speed, so
      it is the queue from early on and it makes the queue series non-zero.

    All three sit inside the queue polygon of :func:`_regions`, so the queue
    series really counts them rather than being trivially zero everywhere.
    """
    tenth = [round(0.1 * index, 3) for index in range(40)]
    return [
        _parity_track(
            3,
            [(t, round(0.15 + 0.5 * t, 5), 0.5) for t in tenth[:13]]
            + [(t, 0.75, 0.5) for t in tenth[13:32]]
            + [(t, round(0.75 + 0.5 * (t - 3.2), 5), 0.5) for t in tenth[32:]],
            queue_seconds=1.9,
            stopped_seconds=1.9,
        ),
        _parity_track(
            7,
            [(t, round(0.2 + 0.3 * t, 5), 0.8) for t in tenth[:6]]
            + [
                (round(1.1 + 0.1 * index, 3), round(0.5 + 0.03 * index, 5), 0.8)
                for index in range(10)
            ],
        ),
        _parity_track(
            11,
            [(t, 0.5, 0.5) for t in tenth],
            queue_seconds=3.9,
            stopped_seconds=3.9,
        ),
    ]


def _parity_timeline() -> dict:
    """The payload both halves of the contract are written against."""
    return build_timeline(_parity_tracks(), _regions(), FIXTURE_DURATION, FIXTURE_HZ)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------- tests


def test_segments_are_uniform_in_time():
    timeline = build_timeline([_driving()], _regions(), duration=6.0, hz=4.0)
    segment = timeline["vehicles"][0]["segments"][0]
    times = segment["t"]
    assert times[0] == pytest.approx(0.0, abs=1e-6)
    deltas = [round(b - a, 3) for a, b in pairwise(times)]
    # Every interval is the transport step (the last one may be shorter).
    assert set(deltas[:-1]) == {0.25}
    assert deltas[-1] <= 0.25 + 1e-6


def test_a_tracking_gap_splits_the_track_and_position_is_unknown_inside_it():
    """The core promise: no invented motion across a dropout."""
    track = _track_with_gap(7)
    timeline = build_timeline([track], _regions(), duration=10.0, hz=5.0)
    vehicle = timeline["vehicles"][0]
    assert len(vehicle["segments"]) == 2
    assert timeline["track_gaps"] == 1
    assert vehicle["segments"][0]["t"][-1] <= 1.6
    assert vehicle["segments"][1]["t"][0] >= 7.4

    # What is known is exactly the union of the segments - the dropout window
    # belongs to neither of them, so no reader can return a position for it.
    intervals = known_intervals(timeline, 7)
    assert len(intervals) == 2
    assert position_at(timeline, 7, 1.0) is not None
    assert position_at(timeline, 7, 8.0) is not None
    for moment in (3.0, 4.5, 6.0, 7.0):
        assert position_at(timeline, 7, moment) is None, f"invented a position at t={moment}"
        assert not any(start <= moment <= end for start, end in intervals)


def test_known_intervals_never_overlap_so_a_moment_is_unambiguous():
    """Overlapping segments would let a reader pick either answer at a gap edge."""
    track = _track_with_gap(7)
    timeline = build_timeline([track], _regions(), duration=10.0, hz=5.0)
    intervals = known_intervals(timeline, 7)
    assert intervals[0][1] < intervals[1][0]


def test_positions_match_the_source_samples_inside_a_segment():
    track = _driving(3, count=30, step=0.1)
    timeline = build_timeline([track], _regions(), duration=3.0, hz=10.0)
    for point in track.points:
        found = position_at(timeline, 3, point.time)
        assert found is not None
        assert found[0] == pytest.approx(point.x, abs=0.01)
        assert found[1] == pytest.approx(point.y, abs=0.01)


def test_position_before_the_clip_or_after_it_is_unknown():
    timeline = build_timeline([_driving(5, 20, 0.1)], _regions(), duration=2.0, hz=5.0)
    assert position_at(timeline, 5, 5.0) is None  # clip is only 2 s long
    assert position_at(timeline, 99, 0.5) is None  # unknown vehicle id


def test_queue_series_matches_the_measured_peak():
    """The replay curve must not disagree with the reported metric."""
    tracks = [make_track(index, [(0.5, 0.5)] * 12, step=0.1) for index in range(1, 5)]
    tracks.append(_driving(9, 60, 0.1))
    regions = _regions(min_queue_seconds=0.0)
    timeline = build_timeline(tracks, regions, duration=6.0, hz=4.0)
    replay_peak = max(sample["q"] for sample in timeline["queue"])
    assert replay_peak == 4, "the four stationary vehicles are the queue"


def test_queue_grid_starts_at_zero_and_is_uniform_in_time():
    """There is no sample before the clip starts, so a reader cannot show a
    queue length for an instant that was never observed."""
    timeline = build_timeline([_driving()], _regions(), duration=4.0, hz=4.0)
    samples = timeline["queue"]
    assert samples[0]["t"] == 0.0
    times = [sample["t"] for sample in samples]
    deltas = [round(b - a, 3) for a, b in pairwise(times)]
    assert set(deltas[:-1]) == {0.25}
    assert times[-1] < 4.0
    assert queue_at(timeline, -1.0) is None
    assert queue_at(timeline, 1.0) == samples[4]["q"]


def test_payload_size_is_bounded_by_the_requested_resolution():
    tracks = [_driving(index, 100, 0.1) for index in range(1, 11)]
    coarse = build_timeline(tracks, _regions(), duration=10.0, hz=1.0)
    fine = build_timeline(tracks, _regions(), duration=10.0, hz=10.0)
    assert sample_count(fine) > sample_count(coarse) * 5
    assert fine["hz"] == 10.0 and coarse["hz"] == 1.0


def test_every_segment_is_aligned_and_never_runs_backwards():
    timeline = build_timeline(
        [_driving(2, 40, 0.1), _track_with_gap(3)], _regions(), duration=9.0, hz=4.0
    )
    for vehicle in timeline["vehicles"]:
        for segment in vehicle["segments"]:
            assert len(segment["t"]) == len(segment["x"]) == len(segment["y"])
            times = segment["t"]
            assert times == sorted(times)
            assert all(b > a for a, b in pairwise(times))


def test_very_many_vehicles_are_capped_but_reported(monkeypatch):
    """A pathological clip stays responsive, and the omission is disclosed."""
    from backend.analytics import timeline as timeline_module

    monkeypatch.setattr(timeline_module, "MAX_VEHICLES", 10)
    tracks = [_driving(index, 6, 0.1) for index in range(1, 12)]
    built = build_timeline(tracks, _regions(), duration=0.6, hz=5.0)
    assert len(built["vehicles"]) == 10
    assert built["vehicles_omitted"] == 1


def test_resolution_is_clamped_to_a_sane_range():
    regions = _regions()
    assert build_timeline([], regions, 1.0, hz=0.1)["hz"] == 1.0
    assert build_timeline([], regions, 1.0, hz=99.0)["hz"] == 15.0

# ------------------------------------- the instants the frontend also asserts
#
# The tables below are the contract's payload-side half.  ``frontend/src/state/
# timelinePayload.test.ts`` asserts exactly these ``(vehicle, instant) -> answer``
# pairs through the frontend's own ``positionAt`` / ``queueAt``, so the producer
# and the consumer are pinned to the same numbers instead of to two private
# literals that can drift apart unnoticed.  The fixture file is the only thing
# they share: nothing here imports the frontend, nothing there imports this.
#
# Regenerate the fixture with:
#
#     python -c "import json, pathlib; from backend.tests.test_timeline import \
#       _parity_timeline, FIXTURE_PATH; \
#       FIXTURE_PATH.write_text(json.dumps(_parity_timeline(), indent=2) + chr(10), \
#         encoding='utf-8', newline=chr(10))"
#
# and only after reading the note on regeneration at the top of this section.

#: ``(vehicle_id, instant) -> position or None``.  ``None`` is the honest answer
#: outside a vehicle's lifetime and *inside* a tracking gap; it is never a
#: position interpolated across the dropout.
PINNED_POSITIONS: dict[tuple[int, float], tuple[float, float] | None] = {
    # Vehicle 3: one contiguous segment, 0.0-3.9 s.
    (3, -0.25): None,  # before the first sample
    (3, 0.0): (0.15, 0.5),  # exactly on the first sample
    (3, 0.125): (0.2125, 0.5),  # midpoint of the first interval, both axes
    (3, 0.5): (0.4, 0.5),  # exactly on a sample boundary
    (3, 1.625): (0.75, 0.5),  # deep inside the stopped stretch: no motion at all
    (3, 3.9): (1.1, 0.5),  # the last sample, on the short off-grid tail
    (3, 4.25): None,  # after the last sample
    # Vehicle 7: two segments, 0.0-0.5 s and 1.1-2.0 s, with a real dropout between.
    (7, 0.5): (0.35, 0.8),  # the last known position before the gap
    (7, 0.625): None,  # just inside the gap
    (7, 1.0): None,  # inside the gap
    (7, 1.075): None,  # 0.025 s before the track returns: the near miss
    (7, 1.1): (0.5, 0.8),  # the first sample after the gap, off the 0.25 s grid
    (7, 1.475): (0.6125, 0.8),  # interpolated inside the second segment
    (7, 2.5): None,  # the vehicle's lifetime ended, the clip has not
    # Vehicle 11: parked for the whole clip.
    (11, 0.0): (0.5, 0.5),
    (11, 1.4): (0.5, 0.5),
    (11, 3.9): (0.5, 0.5),
    # An id that is not in the payload at all.
    (404, 0.5): None,
}

#: ``instant -> queue length or None``.  The series runs 0.0-3.75 s in 0.25 s
#: steps and steps 0 -> 1 -> 2 -> 1, so it is not accidentally constant and each
#: edge is pinned from both sides.
PINNED_QUEUE: dict[float, int | None] = {
    -0.2: None,  # before the first sample: nothing was ever measured there
    0.0: 0,  # exactly on the first sample
    0.3: 0,  # nearest sample is 0.25
    0.45: 1,  # nearest sample is 0.5
    0.5: 1,  # exactly on a sample, and the first non-zero one
    1.625: 1,  # nearest sample is 1.5
    1.7: 2,  # nearest sample is 1.75: the count steps up
    3.4: 1,  # nearest sample is 3.5: the count steps back down
    3.75: 1,  # the last sample
    5.0: 1,  # after the series ends, the last known count is held
}


def test_committed_fixture_is_exactly_what_the_producer_builds():
    """The producer half of the contract: ``build_timeline`` has not drifted.

    If this fails, the fixture on disk no longer describes what the backend
    emits, and the frontend's assertions against it are describing a payload
    that no analysis will ever produce.  Read the note at the top of the parity
    section before regenerating anything.
    """
    assert _parity_timeline() == _load_fixture()


def test_the_fixture_is_reproducible_byte_for_byte():
    """So "regenerate the fixture" is a command, not an act of editing.

    If this fails while the test above passes, the committed file was hand
    reformatted rather than generated, and the diff on the next real change will
    be unreadable.
    """
    regenerated = json.dumps(_parity_timeline(), indent=2) + "\n"
    assert FIXTURE_PATH.read_text(encoding="utf-8") == regenerated, (
        "regenerate it from _parity_timeline() rather than by hand"
    )


def test_the_fixture_still_pins_every_adversarial_case():
    """A regeneration must not quietly drop the cases the fixture exists for."""
    fixture = _load_fixture()
    # More than one vehicle, so a search that is trivially linear still has to
    # pick the right one.
    assert [vehicle["id"] for vehicle in fixture["vehicles"]] == [3, 7, 11]
    # A real tracking gap, and only one.
    assert fixture["track_gaps"] == 1
    assert known_intervals(fixture, 7) == [(0.0, 0.5), (1.1, 2.0)]
    # A parked vehicle: every sample identical, which is what makes it a queue.
    parked = next(v for v in fixture["vehicles"] if v["id"] == 11)
    assert len(set(parked["segments"][0]["x"])) == 1
    # The queue series is non-zero, starts at zero, and changes more than once.
    counts = [sample["q"] for sample in fixture["queue"]]
    assert counts[0] == 0 and max(counts) == 2 and len(set(counts)) == 3
    # The gap really is unanswerable, and the second segment really is off-grid.
    assert [segment["t"][0] for segment in fixture["vehicles"][1]["segments"]] == [0.0, 1.1]


def test_the_pinned_instants_read_the_same_way_from_the_committed_fixture():
    """These are the numbers ``positionAt`` / ``queueAt`` are held to.

    The tables above are duplicated as literals in
    ``frontend/src/state/timelinePayload.test.ts``.  Change one of them here and
    change the matching expectation there in the same commit.
    """
    fixture = _load_fixture()
    for (vehicle_id, moment), expected in PINNED_POSITIONS.items():
        found = position_at(fixture, vehicle_id, moment)
        if expected is None:
            assert found is None, (
                f"vehicle {vehicle_id} at t={moment}: no position is known there, "
                f"but the fixture offers {found}"
            )
        else:
            assert found == pytest.approx(expected), f"vehicle {vehicle_id} at t={moment}"

    for moment, expected in PINNED_QUEUE.items():
        found = queue_at(fixture, moment)
        if expected is None:
            assert found is None, f"no queue was measured at t={moment}, but got {found}"
        else:
            assert found == expected, f"queue length at t={moment}"