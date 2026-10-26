import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import demo from "../../../backend/demo/sample_analysis.json";
import { api, ApiError } from "../api/client";
import { AnalysisProvider } from "../state/AnalysisContext";
import type { Analysis } from "../types";
import { simulationFixture } from "../test/simulationFixture";
import Simulation from "./Simulation";

vi.mock("../api/client", () => ({
  api: { demo: vi.fn(), presets: vi.fn(), simulate: vi.fn() },
  ApiError: class extends Error { hint = "Retry shortly"; },
}));
vi.mock("../components/CorridorComparison", () => ({ CorridorComparison: () => null }));
vi.mock("../components/CorridorMap", () => ({ CorridorMap: () => null }));
vi.mock("recharts", () => ({
  ResponsiveContainer: () => null,
  LineChart: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  Line: () => null,
}));

beforeEach(() => {
  vi.mocked(api.demo).mockResolvedValue(demo as unknown as Analysis);
  vi.mocked(api.presets).mockReturnValue(new Promise(() => {}));
});

function renderDemo() {
  render(<MemoryRouter initialEntries={["/simulation/demo"]}>
    <AnalysisProvider><Routes>
      <Route path="/simulation/:analysisId" element={<Simulation />} />
    </Routes></AnalysisProvider>
  </MemoryRouter>);
}

it("shows preset loading without claiming the backend failed", async () => {
  renderDemo();
  await screen.findByText("Loading presets…");
  expect(screen.queryByText("built-in presets")).not.toBeInTheDocument();
  expect(screen.queryByText(/backend could not be asked/)).not.toBeInTheDocument();
});

it("shows the analysis failure and a retry instead of leaving disabled controls unexplained", async () => {
  vi.mocked(api.demo).mockRejectedValue(new ApiError("Demo unavailable", 503));
  renderDemo();
  await screen.findByText("Demo unavailable");
  expect(screen.getByRole("button", { name: "Retry loading analysis" })).toBeInTheDocument();
  expect(api.presets).not.toHaveBeenCalled();
  expect(screen.queryByText("built-in presets")).not.toBeInTheDocument();
});

it("uses a fallback only after the preset request fails", async () => {
  vi.mocked(api.presets).mockRejectedValue(new Error("Unavailable"));
  renderDemo();
  await screen.findByText("built-in presets");
  expect(screen.queryByText("Loading presets…")).not.toBeInTheDocument();
});

it("uses the backend presets when available", async () => {
  vi.mocked(api.presets).mockResolvedValue([
    { volume: 1, service_multiplier: 1, spread_seconds: 0, channels: 1, seed: 20240517 },
  ]);
  renderDemo();
  await waitFor(() => expect(api.presets).toHaveBeenCalledWith("demo"));
  await waitFor(() => expect(screen.queryByText("Loading presets…")).not.toBeInTheDocument());
  expect(screen.queryByText("built-in presets")).not.toBeInTheDocument();
});

it("shows unavailable source waits as missing and suppresses their model mismatch", async () => {
  const analysis = structuredClone(demo) as unknown as Analysis;
  analysis.summary.average_wait_seconds = null;
  analysis.summary.max_wait_seconds = null;
  vi.mocked(api.demo).mockResolvedValue(analysis);
  const run = simulationFixture({
    model_deltas: [{
      metric: "average_wait_seconds", label: "Avg wait", unit: "s",
      observed: 0, simulated: 8, absolute: 8, percent: null, lower_is_better: true,
    }],
  });
  run.observed.average_wait_seconds = 0;
  run.observed.max_wait_seconds = 0;
  vi.mocked(api.simulate).mockResolvedValue(run);
  const user = userEvent.setup();
  renderDemo();
  await waitFor(() => expect(screen.getByRole("button", { name: "Run simulated scenario" })).toBeEnabled());
  await user.click(screen.getByRole("button", { name: "Run simulated scenario" }));
  await screen.findByText("Source measurement unavailable");
  const mean = screen.getByRole("row", { name: "Est. wait, mean (s) — 8 4" });
  expect(within(mean).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["Est. wait, mean (s)", "—", "8", "4"]);
  expect(screen.getByRole("row", { name: "Est. wait, max (s) — 18 18" })).toBeInTheDocument();
});
