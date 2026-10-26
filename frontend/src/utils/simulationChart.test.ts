import { expect, it } from "vitest";
import { simulationFixture } from "../test/simulationFixture";
import { comparisonSeries } from "./simulationChart";

it("includes the extended scenario window without inventing source observations", () => {
  const run = simulationFixture({
    observed_queue: [{ time: 0, queue: 2 }, { time: 1, queue: 3 }],
    baseline_queue: [{ time: 0, queue: 1 }, { time: 1, queue: 2 }],
    simulated_queue: [{ time: 0, queue: 0 }, { time: 1, queue: 1 }, { time: 2, queue: 2 }],
  });
  expect(comparisonSeries(run)).toEqual([
    { time: 0, observed: 2, baseline: 1, simulated: 0 },
    { time: 1, observed: 3, baseline: 2, simulated: 1 },
    { time: 2, observed: null, baseline: null, simulated: 2 },
  ]);
});

it("aligns curves by timestamp rather than by sample index", () => {
  const run = simulationFixture({
    observed_queue: [{ time: 0, queue: 4 }, { time: 2, queue: 8 }],
    baseline_queue: [{ time: 1, queue: 6 }],
    simulated_queue: [],
  });
  expect(comparisonSeries(run)).toEqual([
    { time: 0, observed: 4, baseline: null, simulated: null },
    { time: 1, observed: null, baseline: 6, simulated: null },
    { time: 2, observed: 8, baseline: null, simulated: null },
  ]);
});
