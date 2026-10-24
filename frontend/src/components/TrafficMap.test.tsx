import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MAX_LIVE_DOTS, pickLiveVehicles, TrafficMap } from "./TrafficMap";
import { ReplayProvider } from "../state/ReplayContext";
import { api } from "../api/client";
import type { Analysis, TimelinePayload } from "../types";

vi.mock("../api/client", () => ({ api: { timeline: vi.fn() } }));

const timelineMock = vi.mocked(api.timeline);

type Vehicle = TimelinePayload["vehicles"][number];

function vehicles(count: number): Vehicle[] {
  return Array.from({ length: count }, (_, index) => ({
    id: index,
    class: "car",
    queue_seconds: 0,
    stopped_seconds: 0,
    segments: [{ t: [0, 1], x: [index / 1000, index / 1000 + 0.5], y: [0.5, 0.5] }],
  }));
}

const none = new Set<number>();

/** Just the fields TrafficMap reads. */
function analysis(count: number): Analysis {
  return {
    analysis_id: "busy",
    video: { width: 640, height: 480 },
    regions: { queue: [], entry: [], exit: [] },
    heat_grid: [],
    bottlenecks: [],
    warnings: [],
    trajectories: vehicles(count).map((vehicle) => ({
      vehicle_id: vehicle.id,
      vehicle_class: "car",
      duration: 1,
      path_length: 0,
      stopped_seconds: 0,
      queue_seconds: 0,
      region_seconds: 0,
      mean_speed: 0,
      first_seen: 0,
      last_seen: 1,
      points: [{ x: 0, y: 0.5, time: 0 }],
    })),
  } as unknown as Analysis;
}

function timeline(count: number): TimelinePayload {
  return {
    duration: 1,
    hz: 4,
    sampling_fps: 10,
    gap_threshold_s: 0.25,
    track_gaps: 0,
    vehicles: vehicles(count),
    queue: [{ t: 0, q: 0 }],
    vehicles_omitted: 0,
    note: "",
  };
}

/**
 * The bug these cover: above the drawing threshold, with no vehicle selected
 * and no bottleneck chosen, the live map filtered down to the highlight set -
 * which is empty - and drew nothing at all, on a busy upload.
 */
describe("pickLiveVehicles", () => {
  it("draws every vehicle for a clip that fits", () => {
    const list = vehicles(26);
    expect(pickLiveVehicles(list, none, null, MAX_LIVE_DOTS)).toEqual(
      list.map((v) => v.id),
    );
  });

  it("still draws something when the clip is too big to draw", () => {
    const picked = pickLiveVehicles(vehicles(121), none, null, MAX_LIVE_DOTS);
    expect(picked.length).toBeGreaterThan(0);
  });

  it("keeps the number of dots within the limit", () => {
    for (const count of [121, 200, 400, 1000]) {
      expect(pickLiveVehicles(vehicles(count), none, null, MAX_LIVE_DOTS).length)
        .toBeLessThanOrEqual(MAX_LIVE_DOTS);
    }
  });

  it("spreads the sample over the clip rather than taking one end", () => {
    // The first 120 of 400 would all be the earliest arrivals: a map of the
    // start of the clip, which is not what the user is watching.
    const picked = pickLiveVehicles(vehicles(400), none, null, MAX_LIVE_DOTS);
    expect(picked[0]).toBe(0);
    expect(picked[picked.length - 1]).toBeGreaterThan(300);
  });

  it("picks the same vehicles every frame, so the dots do not flicker", () => {
    const list = vehicles(300);
    const first = pickLiveVehicles(list, none, null, MAX_LIVE_DOTS);
    expect(pickLiveVehicles(list, none, null, MAX_LIVE_DOTS)).toEqual(first);
  });

  it("always draws the vehicles the user asked to see", () => {
    const picked = pickLiveVehicles(vehicles(400), new Set([0, 7, 299]), 137, MAX_LIVE_DOTS);
    expect(picked).toContain(7);
    expect(picked).toContain(299);
    expect(picked).toContain(137);
  });

  it("still returns a sample when only a highlight is asked for", () => {
    // The old code answered exactly this case with an empty list.
    const picked = pickLiveVehicles(vehicles(400), new Set([5, 6]), null, MAX_LIVE_DOTS);
    expect(picked.length).toBeGreaterThan(2);
    expect(picked).toContain(5);
    expect(picked).toContain(6);
  });

  it("ignores a highlight naming a vehicle that is not in the payload", () => {
    const picked = pickLiveVehicles(vehicles(200), new Set([9999]), null, MAX_LIVE_DOTS);
    expect(picked).not.toContain(9999);
    expect(picked.length).toBeGreaterThan(0);
  });

  it("bounds the sampled part, not the ones the user singled out", () => {
    // 60 highlighted vehicles on a 400-vehicle clip: the sample is capped and
    // the singled-out ones are kept, so the total is the two added together.
    const highlight = new Set(Array.from({ length: 60 }, (_, i) => i));
    const picked = pickLiveVehicles(vehicles(400), highlight, null, MAX_LIVE_DOTS);
    const sampled = picked.length - 60;
    expect(sampled).toBeLessThanOrEqual(MAX_LIVE_DOTS);
    expect(picked.length).toBe(60 + sampled);
    for (const id of highlight) expect(picked).toContain(id);
  });

  it("keeps the original payload order", () => {
    const picked = pickLiveVehicles(vehicles(400), none, 250, MAX_LIVE_DOTS);
    expect([...picked].sort((a, b) => a - b)).toEqual(picked);
  });

  it("handles an empty or tiny clip", () => {
    expect(pickLiveVehicles([], none, null, MAX_LIVE_DOTS)).toEqual([]);
    expect(pickLiveVehicles(vehicles(1), none, null, MAX_LIVE_DOTS)).toEqual([0]);
  });
});

function renderMap(count: number, highlightIds: number[] = []) {
  return render(
    <ReplayProvider analysisId="busy" hasVideo={false}>
      <TrafficMap
        analysis={analysis(count)}
        selectedId={null}
        onSelect={() => {}}
        showHeat={false}
        showRegions={false}
        showNow
        highlightIds={highlightIds}
      />
    </ReplayProvider>,
  );
}

/** Dots are <circle> inside the group labelled as the live positions. */
function dotCount(container: HTMLElement): number {
  const group = container.querySelector("g[aria-label*='current replay time']");
  return group?.querySelectorAll("circle").length ?? 0;
}

describe("TrafficMap, a busy clip with nothing selected", () => {
  beforeEach(() => {
    timelineMock.mockReset();
  });

  it("draws live dots instead of an empty map", async () => {
    // 26 vehicles is the bundled demo and is not thinned; 300 is a busy upload.
    timelineMock.mockResolvedValue(timeline(300));
    const { container } = renderMap(300);
    await waitFor(() => expect(dotCount(container)).toBeGreaterThan(0));
    expect(dotCount(container)).toBeLessThanOrEqual(MAX_LIVE_DOTS);
  });

  it("says out loud that it is showing a subset", async () => {
    timelineMock.mockResolvedValue(timeline(300));
    renderMap(300);
    const notice = await screen.findByText(/Thinned to \d+ of 300 vehicles/);
    expect(notice).toBeInTheDocument();
    expect(notice.textContent).toMatch(/keep the replay/);
    expect(notice.textContent).toMatch(/narrow it/);
  });

  it("says nothing about thinning when it is drawing them all", async () => {
    timelineMock.mockResolvedValue(timeline(26));
    const { container } = renderMap(26);
    await waitFor(() => expect(dotCount(container)).toBe(26));
    expect(screen.queryByText(/Thinned to/)).not.toBeInTheDocument();
  });

  it("still draws the whole fleet when a bottleneck is selected", async () => {
    timelineMock.mockResolvedValue(timeline(300));
    const { container } = renderMap(300, [1, 2, 3]);
    await waitFor(() => expect(dotCount(container)).toBeGreaterThan(3));
    expect(dotCount(container)).toBeLessThanOrEqual(MAX_LIVE_DOTS);
  });

  it("tells a screen reader the map is thinned, since the SVG hides its contents", async () => {
    timelineMock.mockResolvedValue(timeline(300));
    renderMap(300);
    // Before the timeline lands the map is not thinned yet, so the label has to
    // be read only once it has.
    await screen.findByText(/Thinned to \d+ of 300 vehicles/);
    const map = screen.getByRole("img", { name: /trajectory map/i });
    expect(map).toHaveAccessibleName(/of 300 vehicles are shown/);
    expect(map).toHaveAccessibleName(/thinned/);
  });
});
