import type { SimulationResult } from "../types";

export interface ComparisonPoint {
  time: number;
  observed: number | null;
  baseline: number | null;
  simulated: number | null;
}

/** Arrival spreading can extend C beyond A and B; retain that whole window. */
export function comparisonSeries(result: SimulationResult): ComparisonPoint[] {
  const observed = new Map(result.observed_queue.map(({ time, queue }) => [time, queue]));
  const baseline = new Map(result.baseline_queue.map(({ time, queue }) => [time, queue]));
  const simulated = new Map(result.simulated_queue.map(({ time, queue }) => [time, queue]));
  const times = new Set([...observed.keys(), ...baseline.keys(), ...simulated.keys()]);
  return [...times].sort((a, b) => a - b).map((time) => ({
    time,
    observed: observed.get(time) ?? null,
    baseline: baseline.get(time) ?? null,
    simulated: simulated.get(time) ?? null,
  }));
}
