import type { Analysis, Scenario, SimulationResult } from "../types";
import { formatNumber, formatSigned } from "./format";

type ObservedMetric = "peak_queue" | "average_queue" | "average_wait_seconds" | "max_wait_seconds" | "throughput_per_minute";

/** Older simulation responses coerce missing source measurements to zero. */
export function observedMetricValue(analysis: Analysis, result: SimulationResult, metric: ObservedMetric): number | null {
  return analysis.summary[metric] === null ? null : result.observed[metric];
}

/** Describe the settings returned by the simulator, never the next slider state. */
export function describeExperiment(scenario: Scenario): string {
  const changes: string[] = [];
  if (scenario.volume !== 1) {
    changes.push(`${formatNumber(Math.abs(scenario.volume - 1) * 100)}% ${scenario.volume < 1 ? "fewer" : "more"} arrivals`);
  }
  if (scenario.service_multiplier !== 1) {
    changes.push(`exit processing at ${formatNumber(scenario.service_multiplier, 2)} times the baseline rate`);
  }
  if (scenario.spread_seconds > 0) {
    changes.push(`arrivals spread over ${formatNumber(scenario.spread_seconds)} extra seconds`);
  }
  if (scenario.channels !== 1) {
    changes.push(`${formatNumber(scenario.channels, 0)} parallel exit channels`);
  }
  return changes.length ? `${changes.join("; ")}.` : "Unmodified baseline: replay the original arrival pattern with one exit channel.";
}

export function peakQueueFinding(result: SimulationResult): string {
  const delta = result.simulated.peak_queue - result.baseline.peak_queue;
  if (delta === 0) return "In this model, the peak queue stays the same.";
  return `In this model, the peak queue ${delta < 0 ? "falls" : "rises"} by ${formatNumber(Math.abs(delta), 0)} vehicle${Math.abs(delta) === 1 ? "" : "s"}.`;
}

export function sensitivityFinding(result: SimulationResult): string {
  const range = result.sensitivity;
  if (!range) return "No sensitivity range was returned for this run. Model uncertainty has not been quantified here.";
  const spread = range.peak_queue_range[1] - range.peak_queue_range[0];
  const change = Math.abs(result.simulated.peak_queue - result.baseline.peak_queue);
  const withinSpread = spread > 0 && change > 0 && change <= spread;
  return `Varying baseline service time produced peak queues from ${formatNumber(range.peak_queue_range[0], 0)} to ${formatNumber(range.peak_queue_range[1], 0)} vehicles. This is a sensitivity range, not a confidence interval.${withinSpread ? " The scenario's peak-queue change is within that spread, so its size may depend on the service-time assumption." : ""}`;
}

/** A small, readable evidence artifact without video or individual trajectories. */
export function experimentNote(analysis: Analysis, result: SimulationResult): string {
  const metricLines = [
    ["Peak queue (vehicles)", "peak_queue"],
    ["Estimated mean wait (s)", "average_wait_seconds"],
    ["Throughput (vehicles/min)", "throughput_per_minute"],
  ] as const;
  return [
    "FLOWLAB experiment evidence",
    `Analysis: ${analysis.analysis_id}`,
    `Source: ${analysis.source === "demo" ? "synthetic demo dataset" : analysis.sample ? `real video example - ${analysis.sample.title}` : "video analysis"}`,
    ...(analysis.sample ? [
      `Footage credit: ${analysis.sample.author}`,
      `Footage source: ${analysis.sample.source_url}`,
      `Footage license: ${analysis.sample.license} (${analysis.sample.license_url})`,
      ...analysis.sample.processing_notes,
    ] : []),
    `Recorded/source window: ${formatNumber(result.observed.observation_seconds)} s`,
    `Baseline model window: ${formatNumber(result.baseline.observation_seconds)} s`,
    `Scenario model window: ${formatNumber(result.simulated.observation_seconds)} s`,
    "",
    "CHANGE TESTED",
    describeExperiment(result.scenario),
    `Settings: ${JSON.stringify(result.scenario)}`,
    `Calibration: ${JSON.stringify(result.calibration)}`,
    "",
    "THREE SEPARATE COMPARISONS",
    `A: ${analysis.source === "demo" ? "synthetic demo measurements, not real-world observations" : "video-derived measurements, subject to detection and region errors"}.`,
    "B: unmodified baseline model. C: model with the change applied.",
    "Unavailable source measurements are shown as —, not zero; no source-model mismatch is calculated for them.",
    ...metricLines.map(([label, metric]) => {
      const observed = observedMetricValue(analysis, result, metric);
      return `${label}: A=${formatNumber(observed)}; B=${formatNumber(result.baseline[metric])}; C=${formatNumber(result.simulated[metric])}; scenario effect (C-B)=${formatSigned(result.simulated[metric] - result.baseline[metric])}; model mismatch (B-A)=${formatSigned(observed === null ? null : result.baseline[metric] - observed)}`;
    }),
    "",
    "INTERPRETATION AND LIMITS",
    peakQueueFinding(result),
    "Scenario effects compare C with B; they are not measured changes at a real site.",
    result.fidelity.note,
    sensitivityFinding(result),
    ...(result.sensitivity ? [
      `Sensitivity method: ${result.sensitivity.method}`,
      result.sensitivity.note,
      `Sensitivity test values: ${JSON.stringify(result.sensitivity.values)}`,
    ] : []),
    result.disclaimer,
    ...result.notes,
    ...analysis.warnings,
    "",
    "BEFORE A REAL-WORLD DECISION",
    "Verify counts against permissioned source footage, review the chosen regions, and check the gate-capacity assumption with site staff. This is a hypothesis to test, not a guaranteed benefit or a traffic-engineering recommendation.",
  ].join("\n");
}
