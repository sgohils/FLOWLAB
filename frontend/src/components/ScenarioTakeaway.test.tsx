import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { simulationAnalysis, simulationFixture } from "../test/simulationFixture";
import { ScenarioTakeaway } from "./ScenarioTakeaway";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("shows the tested change with simulated outcomes and the source mismatch", () => {
  render(<ScenarioTakeaway analysis={simulationAnalysis} result={simulationFixture()} stale={false} />);
  expect(screen.getByRole("heading", { name: "In this model, the peak queue falls by 4 vehicles." })).toBeInTheDocument();
  expect(screen.getByText(/25% fewer arrivals/)).toBeInTheDocument();
  expect(screen.getByText(/A comes from the synthetic demo dataset/)).toHaveTextContent("B and C are simulated");
  expect(screen.getByText(/Check against the source/)).toHaveTextContent("10 vehicles versus 20 in A");
});

it("labels stale results and explains different observation windows", () => {
  const run = simulationFixture();
  run.simulated.observation_seconds = 240;
  render(<ScenarioTakeaway analysis={{ ...simulationAnalysis, source: "video" }} result={run} stale />);
  expect(screen.getByText("Experiment takeaway · previous run")).toBeInTheDocument();
  expect(screen.getByText(/A comes from the video analysis/)).toHaveTextContent("240 s versus 120 s");
});

it("downloads a readable evidence note and releases the object URL", async () => {
  const create = vi.fn(() => "blob:experiment");
  const revoke = vi.fn();
  const OriginalURL = URL;
  vi.stubGlobal("URL", class extends OriginalURL {
    static override createObjectURL = create;
    static override revokeObjectURL = revoke;
  });
  const links: HTMLAnchorElement[] = [];
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    links.push(this);
  });
  const user = userEvent.setup();
  render(<ScenarioTakeaway analysis={simulationAnalysis} result={simulationFixture()} stale={false} />);
  await user.click(screen.getByRole("button", { name: "Download experiment note" }));
  expect(create).toHaveBeenCalledWith(expect.any(Blob));
  expect(click).toHaveBeenCalledOnce();
  const link = links[0];
  expect(link.download).toBe("flowlab-demo-experiment.txt");
  expect(link.href).toBe("blob:experiment");
  await vi.waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:experiment"), { timeout: 1500 });
});
