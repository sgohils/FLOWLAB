import demo from "../../../backend/demo/sample_analysis.json";
import type { Analysis, SimulationMetrics, SimulationResult } from "../types";

export const simulationAnalysis = demo as unknown as Analysis;

function metrics(overrides: Partial<SimulationMetrics>): SimulationMetrics {
  return {
    vehicles: 30,
    peak_queue: 10,
    average_queue: 4,
    average_wait_seconds: 8,
    max_wait_seconds: 18,
    throughput_per_minute: 10,
    total_delay_seconds: 240,
    observation_seconds: 120,
    vehicles_left_at_window_end: 3,
    ...overrides,
  };
}

export function simulationFixture(overrides: Partial<SimulationResult> = {}): SimulationResult {
  return {
    analysis_id: "demo",
    scenario: { volume: 0.75, service_multiplier: 1, spread_seconds: 0, channels: 1, seed: 7 },
    calibration: simulationAnalysis.calibration,
    observed: metrics({ peak_queue: 20, average_wait_seconds: 15 }),
    baseline: metrics({}),
    simulated: metrics({ peak_queue: 6, average_wait_seconds: 4, throughput_per_minute: 12 }),
    fidelity: {
      peak_queue_observed: 20,
      peak_queue_model: 10,
      average_wait_observed: 15,
      average_wait_model: 8,
      ratio: 0.5,
      note: "The baseline underestimates the observed peak queue.",
    },
    sensitivity: {
      parameter: "service_time_seconds",
      method: "Vary baseline service time.",
      baseline_value: 4,
      values: [],
      peak_queue_range: [8, 14],
      average_wait_range: [5, 11],
      note: "Assumption test, not a statistical interval.",
    },
    deltas: [],
    model_deltas: [],
    observed_queue: [],
    baseline_queue: [],
    simulated_queue: [],
    tracks: [],
    baseline_tracks: [],
    notes: ["25% fewer arrivals."],
    disclaimer: "A model outcome is not a guaranteed result.",
    ...overrides,
  };
}
