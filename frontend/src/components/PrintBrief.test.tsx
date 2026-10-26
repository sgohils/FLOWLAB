import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { simulationAnalysis, simulationFixture } from "../test/simulationFixture";
import type { Analysis } from "../types";
import { PrintBrief } from "./PrintBrief";

vi.mock("../api/client", () => ({ api: { result: vi.fn(), simulate: vi.fn() } }));

beforeEach(() => {
  vi.mocked(api.simulate).mockResolvedValue(simulationFixture());
});

function renderBrief(analysis: Analysis) {
  vi.mocked(api.result).mockResolvedValue(analysis);
  return render(<MemoryRouter initialEntries={[`/brief/${analysis.analysis_id}`]}>
    <Routes><Route path="/brief/:analysisId" element={<PrintBrief />} /></Routes>
  </MemoryRouter>);
}

it("credits real sample footage and describes precomputed measurements accurately", async () => {
  const analysis: Analysis = {
    ...simulationAnalysis,
    analysis_id: "real-sample",
    source: "video",
    sample: {
      title: "Traffic on a public road",
      description: "A licensed, fixed-camera traffic clip.",
      author: "Example camera operator",
      source_url: "https://example.org/traffic-source",
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
      processing_notes: ["Precomputed with the app's detector; no manual ground-truth validation is claimed."],
      video_url: "/demo/real.mp4",
      annotated_video_url: "/demo/real-annotated.mp4",
      poster_url: "/demo/real.jpg",
    },
  };
  renderBrief(analysis);
  await screen.findByRole("heading", { name: "FLOWLAB analysis brief" });
  expect(screen.getByText(/real public-road footage; precomputed analysis/)).toBeInTheDocument();
  expect(screen.getByText(/Footage by Example camera operator/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: analysis.sample!.source_url })).toHaveAttribute("href", analysis.sample!.source_url);
  expect(screen.getByRole("link", { name: "CC BY 4.0" })).toHaveAttribute("href", analysis.sample!.license_url);
  expect(screen.getByText(analysis.sample!.processing_notes[0])).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Video-derived measurements" })).toBeInTheDocument();
  expect(screen.queryByText(/stored locally/)).not.toBeInTheDocument();
  expect(screen.getByText(/Created by Shlok Gohil/)).toHaveTextContent("GA-07");
});

it("labels the synthetic demo without presenting it as real footage", async () => {
  renderBrief(simulationAnalysis);
  await screen.findByRole("heading", { name: "Synthetic demo measurements" });
  expect(screen.getByText(/synthetic traffic dataset/)).toBeInTheDocument();
  expect(screen.queryByText(/real public-road footage/)).not.toBeInTheDocument();
});

it("keeps ordinary uploads distinct from the bundled sample", async () => {
  renderBrief({ ...simulationAnalysis, source: "video" });
  await screen.findByRole("heading", { name: "Video-derived measurements" });
  expect(screen.getByText(/demo · uploaded video/)).toBeInTheDocument();
  expect(screen.queryByText(/precomputed analysis/)).not.toBeInTheDocument();
  expect(screen.getByText(/Original and annotated footage/)).toHaveTextContent("Keep private uploads restricted");
});

it("aligns the source, baseline and signed difference under their own table headers", async () => {
  renderBrief(simulationAnalysis);
  const table = await screen.findByRole("table", { name: "Observed and baseline model comparison" });
  expect(within(table).getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
    "Quantity", "A · Synthetic demo", "B · Baseline model", "B − A",
  ]);
  const peak = within(table).getByRole("row", { name: "Peak queue (vehicles) 20 10 −10" });
  expect(within(peak).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["20", "10", "−10"]);
  const wait = within(table).getByRole("row", { name: "Est. wait (mean, s) 15 8 −7" });
  expect(within(wait).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["15", "8", "−7"]);
  const left = within(table).getByRole("row", { name: "Left at window end — 3 —" });
  expect(within(left).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["—", "3", "—"]);
});

it("keeps an unmeasured source wait unavailable in the model comparison", async () => {
  renderBrief({
    ...simulationAnalysis,
    source: "video",
    summary: { ...simulationAnalysis.summary, average_wait_seconds: null, completed_queue_visits: 0 },
  });
  const table = await screen.findByRole("table", { name: "Observed and baseline model comparison" });
  const wait = within(table).getByRole("row", { name: "Est. wait (mean, s) — 8 —" });
  expect(within(wait).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["—", "8", "—"]);
});

it("keeps bottom-of-frame regions inside the printed figure", async () => {
  renderBrief({
    ...simulationAnalysis,
    video: { ...simulationAnalysis.video, width: 960, height: 494 },
    regions: { ...simulationAnalysis.regions, queue: [[0.1, 0.9], [0.9, 0.9], [0.9, 0.99]] },
  });
  const figure = await screen.findByRole("img", { name: "Measurement regions in the complete video frame" });
  const [, , width, height] = figure.getAttribute("viewBox")!.split(" ").map(Number);
  expect(width / height).toBeCloseTo(960 / 494);
  const vertices = figure.querySelector("polygon")!.getAttribute("points")!.split(" ").map((pair) => pair.split(",").map(Number));
  expect(vertices.every(([x, y]) => x <= width && y <= height)).toBe(true);
  expect(vertices[2][1] / height).toBeCloseTo(0.99);
});
