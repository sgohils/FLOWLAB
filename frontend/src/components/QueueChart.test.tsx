import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { peakSample, QueueChart } from "./QueueChart";
import { ReplayProvider } from "../state/ReplayContext";
import { api } from "../api/client";
import type { QueueSample } from "../types";

vi.mock("../api/client", () => ({ api: { timeline: vi.fn() } }));

// Recharts sizes itself with a ResizeObserver, which jsdom does not provide.
class NoopResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", NoopResizeObserver);

vi.mocked(api.timeline).mockResolvedValue({
  duration: 0,
  hz: 4,
  sampling_fps: 10,
  gap_threshold_s: 0.25,
  track_gaps: 0,
  vehicles: [],
  queue: [],
  vehicles_omitted: 0,
  note: "",
});

function renderChart(data: QueueSample[]) {
  return render(
    <ReplayProvider analysisId={null} hasVideo={false}>
      <QueueChart data={data} showEvents={false} />
    </ReplayProvider>,
  );
}

describe("peakSample", () => {
  it("finds the highest sample, with its own time", () => {
    const data: QueueSample[] = [
      { time: 0, queue: 1 },
      { time: 5, queue: 9 },
      { time: 10, queue: 4 },
    ];
    expect(peakSample(data)).toEqual({ time: 5, queue: 9 });
  });

  it("reports the real time of the peak on an all-zero series", () => {
    // Seeded with a zero placeholder this read t = 0, which on a series that
    // starts at 4 s points at the wrong instant entirely.
    const data: QueueSample[] = [
      { time: 4, queue: 0 },
      { time: 8, queue: 0 },
      { time: 12, queue: 0 },
    ];
    expect(peakSample(data)).toEqual({ time: 4, queue: 0 });
    expect(peakSample(data)?.time).not.toBe(0);
  });

  it("keeps the first of several samples tied at the peak", () => {
    const data: QueueSample[] = [
      { time: 1, queue: 7 },
      { time: 2, queue: 7 },
    ];
    expect(peakSample(data)).toEqual({ time: 1, queue: 7 });
  });

  it("has no peak at all when there is no series", () => {
    expect(peakSample([])).toBeNull();
  });
});

describe("QueueChart", () => {
  it("renders an empty series as an explanation, not as a chart", () => {
    renderChart([]);
    expect(screen.getByText(/No queue series/)).toBeInTheDocument();
  });

  it("renders a real series without crashing", () => {
    renderChart([
      { time: 0, queue: 0 },
      { time: 1, queue: 4 },
      { time: 2, queue: 1 },
    ]);
    expect(screen.queryByText(/No queue series/)).not.toBeInTheDocument();
  });
});
