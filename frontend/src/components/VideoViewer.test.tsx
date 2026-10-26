import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VideoViewer } from "./VideoViewer";
import type { Regions } from "../types";

vi.mock("../state/ReplayContext", () => ({
  useReplay: () => ({
    registerVideo: vi.fn(), seek: vi.fn(), reportTime: vi.fn(),
    time: 0, setPlaying: vi.fn(), playing: false, toggle: vi.fn(),
  }),
}));

const regions: Regions = {
  conflict: [], auto_detected: false,
  queue: [[0.56, 0.93], [0.75, 0.48], [0.98, 0.48], [0.98, 0.96]],
  entry: [[0.53, 0.88], [0.94, 0.88]],
  exit: [[0.76, 0.42], [0.99, 0.42]],
  entry_direction: "any", exit_direction: "any",
  speed_threshold: 0.006, min_stop_seconds: 1.5,
  min_queue_seconds: 0.5, sample_fps: 10,
};

describe("VideoViewer", () => {
  it("renders the measured region in the SVG's normalized coordinate space", () => {
    render(<VideoViewer src="/clip.mp4" regions={regions} tool="none" editable={false} onChange={vi.fn()} />);
    const overlay = screen.getByRole("img", { name: "Region overlay" });
    expect(overlay).toHaveAttribute("viewBox", "0 0 1 1");
    expect(overlay.querySelector("polygon")).toHaveAttribute(
      "points", "0.5600,0.9300 0.7500,0.4800 0.9800,0.4800 0.9800,0.9600",
    );
    // Region strokes use the same normalized units as their shapes.
    expect(overlay.querySelector("line")).not.toHaveAttribute("vector-effect");
  });

  it("shows the supplied real-footage poster before playback", () => {
    render(<VideoViewer src="/clip.mp4" poster="/poster.jpg" regions={regions} tool="none" editable={false} onChange={vi.fn()} />);
    expect(screen.getByLabelText("Annotated video of the analysed clip")).toHaveAttribute("poster", "/poster.jpg");
  });
});
