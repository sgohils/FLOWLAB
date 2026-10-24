import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReplayProvider, positionAt, queueAt, useReplay } from "./ReplayContext";
import { api } from "../api/client";
import type { TimelinePayload } from "../types";

vi.mock("../api/client", () => ({
  api: { timeline: vi.fn() },
}));

const timelineMock = vi.mocked(api.timeline);

/**
 * One vehicle tracked from 0 s to 2 s, moving linearly from x=0 to x=2, and a
 * second one lost between 0.5 s and 1.5 s and then seen again.  This is the
 * shape the backend serves: uniform samples, split into segments at a gap.
 */
function fixture(): TimelinePayload {
  return {
    duration: 2,
    hz: 4,
    sampling_fps: 10,
    gap_threshold_s: 0.25,
    track_gaps: 1,
    vehicles: [
      {
        id: 1,
        class: "car",
        queue_seconds: 0,
        stopped_seconds: 0,
        segments: [{ t: [0, 0.5, 1, 1.5, 2], x: [0, 0.5, 1, 1.5, 2], y: [0, 0, 0, 0, 0] }],
      },
      {
        id: 2,
        class: "truck",
        queue_seconds: 3.5,
        stopped_seconds: 1,
        segments: [
          { t: [0, 0.5], x: [10, 10], y: [10, 10] },
          { t: [1.5, 2], x: [20, 20], y: [20, 20] },
        ],
      },
    ],
    queue: [
      { t: 0, q: 0 },
      { t: 0.5, q: 2 },
      { t: 1, q: 4 },
      { t: 1.5, q: 1 },
    ],
    vehicles_omitted: 0,
    note: "",
  };
}

describe("positionAt", () => {
  const timeline = fixture();

  /** The same payload with one vehicle's segments replaced. */
  function withSegments(segments: TimelinePayload["vehicles"][number]["segments"]) {
    return {
      ...timeline,
      vehicles: [{ ...timeline.vehicles[0]!, segments }],
    } satisfies TimelinePayload;
  }

  it("returns a sample exactly and interpolates between two", () => {
    expect(positionAt(timeline, 1, 0.5)).toEqual({ x: 0.5, y: 0 });
    expect(positionAt(timeline, 1, 2)).toEqual({ x: 2, y: 0 });
    expect(positionAt(timeline, 1, 0.25)).toEqual({ x: 0.25, y: 0 });
    expect(positionAt(timeline, 1, 1.75)).toEqual({ x: 1.75, y: 0 });
  });

  it("interpolates on both axes", () => {
    const diagonal: TimelinePayload = {
      ...timeline,
      vehicles: [{ ...timeline.vehicles[0]!, segments: [{ t: [0, 1], x: [0, 1], y: [0, 4] }] }],
    };
    expect(positionAt(diagonal, 1, 0.5)).toEqual({ x: 0.5, y: 2 });
  });

  it("is null for an unknown vehicle, outside its lifetime, or in no vehicles at all", () => {
    expect(positionAt(timeline, 99, 0.5)).toBeNull();
    expect(positionAt(timeline, 1, -0.1)).toBeNull();
    expect(positionAt(timeline, 1, 2.1)).toBeNull();
    expect(positionAt({ ...timeline, vehicles: [] }, 1, 0.5)).toBeNull();
  });

  it("is null inside a tracking gap, rather than inventing motion", () => {
    // Vehicle 2 is unknown between 0.5 s and 1.5 s: it must not be drawn
    // somewhere interpolated across the gap.
    expect(positionAt(timeline, 2, 0)).toEqual({ x: 10, y: 10 });
    expect(positionAt(timeline, 2, 0.5)).toEqual({ x: 10, y: 10 });
    expect(positionAt(timeline, 2, 0.75)).toBeNull();
    expect(positionAt(timeline, 2, 1)).toBeNull();
    expect(positionAt(timeline, 2, 1.25)).toBeNull();
    expect(positionAt(timeline, 2, 1.5)).toEqual({ x: 20, y: 20 });
  });

  it("handles a degenerate segment without reading past either end", () => {
    // An empty segment and a segment holding a single sample.
    const degenerate = withSegments([{ t: [], x: [], y: [] }, { t: [1], x: [7], y: [8] }]);
    expect(positionAt(degenerate, 1, 1)).toEqual({ x: 7, y: 8 });
    expect(positionAt(degenerate, 1, 0.9)).toBeNull();

    // A single-sample segment next to a normal one.
    const mixed = withSegments([{ t: [1], x: [7], y: [8] }, { t: [0, 1], x: [0, 1], y: [0, 1] }]);
    expect(positionAt(mixed, 1, 1)).toEqual({ x: 7, y: 8 });
    expect(positionAt(mixed, 1, 0.5)).toEqual({ x: 0.5, y: 0.5 });
  });
});

describe("queueAt", () => {
  const timeline = fixture();

  it("returns the count at a sampled instant", () => {
    expect(queueAt(timeline, 0)).toBe(0);
    expect(queueAt(timeline, 0.5)).toBe(2);
    expect(queueAt(timeline, 1)).toBe(4);
  });

  it("picks the nearest sample between two instants", () => {
    expect(queueAt(timeline, 0.6)).toBe(2);
    expect(queueAt(timeline, 0.9)).toBe(4);
    // 1.4 s is nearer the sample at 1.5 s than the one at 1.0 s.
    expect(queueAt(timeline, 1.4)).toBe(1);
  });

  it("holds the last known count after the queue series ends", () => {
    expect(queueAt(timeline, 1.9)).toBe(1);
    expect(queueAt(timeline, 2)).toBe(1);
  });

  it("is null before the clip starts, or when there is no queue series", () => {
    expect(queueAt(timeline, -0.2)).toBeNull();
    expect(queueAt({ ...timeline, queue: [] }, 0.5)).toBeNull();
  });
});

/** Reports the context so the provider's wiring can be asserted, not just its maths. */
function Probe() {
  const replay = useReplay();
  const first = replay.positionAt(1);
  return (
    <div>
      <span data-testid="time">{replay.time.toFixed(2)}</span>
      <span data-testid="queue">{String(replay.queueAt)}</span>
      <span data-testid="position">{first ? first.x.toFixed(2) : "none"}</span>
      <span data-testid="gap">{replay.positionAt(2) ? "known" : "unknown"}</span>
      <span data-testid="many">{String(replay.manyVehicles)}</span>
      <button onClick={() => replay.seek(1.25)}>seek</button>
    </div>
  );
}

describe("ReplayProvider", () => {
  beforeEach(() => {
    timelineMock.mockReset();
    timelineMock.mockResolvedValue(fixture());
  });

  it("refuses to be read outside a provider", () => {
    // React logs the thrown error; the assertion is that it is thrown at all.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/ReplayProvider/);
    spy.mockRestore();
  });

  it("loads the timeline and publishes the clock at the start", async () => {
    render(
      <ReplayProvider analysisId="abc" hasVideo={false}>
        <Probe />
      </ReplayProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("queue")).toHaveTextContent("0"));
    expect(timelineMock).toHaveBeenCalledWith("abc", 4);
    expect(screen.getByTestId("time")).toHaveTextContent("0.00");
    expect(screen.getByTestId("position")).toHaveTextContent("0.00");
  });

  it("moves the clock, the queue and the positions together on seek", async () => {
    render(
      <ReplayProvider analysisId="abc" hasVideo={false}>
        <Probe />
      </ReplayProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("queue")).toHaveTextContent("0"));
    screen.getByRole("button", { name: "seek" }).click();
    // 1.25 s is between two samples of vehicle 1, inside the gap of vehicle 2,
    // and nearest the queue sample at 1.0 s.
    await waitFor(() => expect(screen.getByTestId("time")).toHaveTextContent("1.25"));
    expect(screen.getByTestId("position")).toHaveTextContent("1.25");
    expect(screen.getByTestId("queue")).toHaveTextContent("4");
    expect(screen.getByTestId("gap")).toHaveTextContent("unknown");
  });

  it("reports manyVehicles only above the drawing threshold", async () => {
    const { unmount } = render(
      <ReplayProvider analysisId="abc" hasVideo={false}>
        <Probe />
      </ReplayProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("many")).toHaveTextContent("false"));
    unmount();

    timelineMock.mockResolvedValue({
      ...fixture(),
      vehicles: Array.from({ length: 121 }, (_, index) => ({
        id: index,
        class: "car",
        queue_seconds: 0,
        stopped_seconds: 0,
        segments: [{ t: [0, 1], x: [0, 1], y: [0, 1] }],
      })),
    });
    render(
      <ReplayProvider analysisId="def" hasVideo={false}>
        <Probe />
      </ReplayProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("many")).toHaveTextContent("true"));
  });

  it("does not load a timeline without an analysis", async () => {
    render(
      <ReplayProvider analysisId={null} hasVideo={false}>
        <Probe />
      </ReplayProvider>,
    );
    expect(timelineMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("queue")).toHaveTextContent("null");
  });
});
