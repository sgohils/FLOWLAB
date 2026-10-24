import { describe, expect, it } from "vitest";
import { positionAt, queueAt } from "./ReplayContext";
import type { TimelinePayload } from "../types";

/**
 * A literal payload, captured verbatim from the backend's `build_timeline`
 * rather than constructed here.
 *
 * It was produced by three tracks at the analysis' own 10 fps (so the 0.25 s
 * gap threshold applies) over a 2 s clip, with one track genuinely lost for a
 * second and one vehicle parked inside the queue region for the whole clip:
 *
 *     build_timeline(tracks, regions, duration=2.0, hz=4.0)
 *
 * The point of pinning a literal is that these two functions are a private
 * copy of a shape the backend owns. Nothing here imports the backend, so the
 * copy cannot drift by importing a drift; it can only drift by someone editing
 * this file, and this file says where the numbers came from.
 *
 * It used to be justified by a comment claiming parity with the backend's own
 * `queue_at` and `position_at`. Both were deleted from
 * `backend/analytics/timeline.py` on purpose - `backend/tests/
 * test_package_layout.py` asserts `not hasattr(timeline, "queue_at")` as a
 * "do not re-add this dead code" guard - so there is no backend function left
 * to be measured against. These expectations are the contract instead.
 */
const PAYLOAD: TimelinePayload = {
  duration: 2.0,
  hz: 4.0,
  sampling_fps: 10.0,
  gap_threshold_s: 0.25,
  track_gaps: 1,
  vehicles: [
    {
      id: 7,
      class: "car",
      queue_seconds: 0.0,
      stopped_seconds: 0.0,
      // Tracked end to end: seven samples on a 0.25 s grid.
      segments: [
        {
          t: [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5],
          x: [0.0, 0.1875, 0.375, 0.5625, 0.75, 0.9375, 1.125],
          y: [0.0, 0.0625, 0.125, 0.1875, 0.25, 0.3125, 0.375],
        },
      ],
    },
    {
      id: 9,
      class: "car",
      queue_seconds: 0.0,
      stopped_seconds: 0.0,
      // Lost between 0.5 s and 1.75 s, so two segments and a real gap.
      segments: [
        { t: [0.0, 0.25, 0.5], x: [0.1, 0.1125, 0.125], y: [0.9, 0.875, 0.85] },
        { t: [1.75, 2.0], x: [0.4, 0.425], y: [0.3, 0.2625] },
      ],
    },
    {
      id: 11,
      class: "car",
      queue_seconds: 0.0,
      stopped_seconds: 0.0,
      // Parked: identical samples, which is what makes it count as a queue.
      segments: [
        {
          t: [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
          x: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
          y: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        },
      ],
    },
  ],
  queue: [
    { t: 0.0, q: 0 },
    { t: 0.25, q: 0 },
    { t: 0.5, q: 1 },
    { t: 0.75, q: 1 },
    { t: 1.0, q: 1 },
    { t: 1.25, q: 1 },
    { t: 1.5, q: 1 },
    { t: 1.75, q: 1 },
  ],
  vehicles_omitted: 0,
  note:
    "Samples are uniform in time. A track is split into several segments where tracking was lost: the position is unknown in between, so no motion is drawn and no vehicle is shown there.",
};

describe("positionAt, against a real build_timeline payload", () => {
  it("returns a stored sample exactly", () => {
    expect(positionAt(PAYLOAD, 7, 0.5)).toEqual({ x: 0.375, y: 0.125 });
    expect(positionAt(PAYLOAD, 7, 1.5)).toEqual({ x: 1.125, y: 0.375 });
    expect(positionAt(PAYLOAD, 7, 0)).toEqual({ x: 0, y: 0 });
  });

  it("interpolates between two samples, on both axes", () => {
    // Halfway between t = 0.25 and t = 0.5 on vehicle 7.
    expect(positionAt(PAYLOAD, 7, 0.375)).toEqual({ x: 0.28125, y: 0.09375 });
    // The binary search has to walk a seven-sample segment to find this one.
    expect(positionAt(PAYLOAD, 7, 1.125)).toEqual({ x: 0.84375, y: 0.28125 });
  });

  it("reports a parked vehicle as not having moved", () => {
    for (const time of [0, 0.4, 0.9, 2]) {
      expect(positionAt(PAYLOAD, 11, time)).toEqual({ x: 0.5, y: 0.5 });
    }
  });

  it("draws nothing in a tracking gap rather than inventing motion", () => {
    expect(positionAt(PAYLOAD, 9, 0.5)).toEqual({ x: 0.125, y: 0.85 });
    expect(positionAt(PAYLOAD, 9, 0.75)).toBeNull();
    expect(positionAt(PAYLOAD, 9, 1.0)).toBeNull();
    expect(positionAt(PAYLOAD, 9, 1.5)).toBeNull();
    expect(positionAt(PAYLOAD, 9, 1.75)).toEqual({ x: 0.4, y: 0.3 });
  });

  it("is null outside a vehicle's lifetime, and for an unknown vehicle", () => {
    expect(positionAt(PAYLOAD, 7, 1.75)).toBeNull();
    expect(positionAt(PAYLOAD, 7, -0.01)).toBeNull();
    expect(positionAt(PAYLOAD, 404, 0.5)).toBeNull();
  });
});

describe("queueAt, against a real build_timeline payload", () => {
  it("returns the count at a sampled instant", () => {
    expect(queueAt(PAYLOAD, 0)).toBe(0);
    expect(queueAt(PAYLOAD, 0.25)).toBe(0);
    expect(queueAt(PAYLOAD, 0.5)).toBe(1);
    expect(queueAt(PAYLOAD, 1.75)).toBe(1);
  });

  it("picks the nearest sample between two instants", () => {
    // 0.3 s is nearer 0.25 (q=0) than 0.5 (q=1).
    expect(queueAt(PAYLOAD, 0.3)).toBe(0);
    // 0.4 s is nearer 0.5 (q=1).
    expect(queueAt(PAYLOAD, 0.4)).toBe(1);
  });

  it("holds the last known count after the series ends", () => {
    expect(queueAt(PAYLOAD, 2.0)).toBe(1);
    expect(queueAt(PAYLOAD, 5.0)).toBe(1);
  });

  it("is null before the first sample, or with no series at all", () => {
    // build_timeline always starts the series at t = 0, so this only fires on
    // a payload that starts later - and then "unknown" is the honest answer.
    expect(queueAt(PAYLOAD, -0.2)).toBeNull();
    expect(queueAt({ ...PAYLOAD, queue: [] }, 0.5)).toBeNull();
  });

  it("reports the peak the analysis reported, not a number of its own", () => {
    const peak = Math.max(...PAYLOAD.queue.map((sample) => sample.q));
    expect(peak).toBe(1);
    expect(queueAt(PAYLOAD, 1.0)).toBe(peak);
  });
});

// --------------------------------------------------------------------------------------
// These expectations above are a captured literal and they remain the fastest thing to
// read when a change breaks a search.  They are no longer the *only* defence: the
// generator they were captured from is now pinned too.  `timelineFixtureParity.test.ts`
// reads `backend/tests/fixtures/timeline_sample.json` - produced by running the real
// `build_timeline`, committed, and asserted against by `backend/tests/test_timeline.py`
// on the way in - and holds `positionAt` / `queueAt` to the same answers at the same
// instants.  So this literal can no longer drift away from the backend unnoticed: if
// `build_timeline` changes, the backend test fails and the fixture must be regenerated
// deliberately, with the reason recorded.