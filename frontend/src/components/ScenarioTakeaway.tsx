import type { Analysis, SimulationResult } from "../types";
import { formatNumber, formatSigned } from "../utils/format";
import { describeExperiment, experimentNote, observedMetricValue, peakQueueFinding, sensitivityFinding } from "../utils/scenarioEvidence";
import { Button, Label, Panel } from "./Primitives";

export function ScenarioTakeaway({ analysis, result, stale }: {
  analysis: Analysis;
  result: SimulationResult;
  stale: boolean;
}) {
  const observedPeak = observedMetricValue(analysis, result, "peak_queue");
  const download = () => {
    const file = new Blob([experimentNote(analysis, result)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = `flowlab-${analysis.analysis_id.replace(/[^a-zA-Z0-9_-]/g, "_")}-experiment.txt`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <Panel className="p-5" aria-label="Experiment takeaway">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Label>Experiment takeaway{stale ? " · previous run" : ""}</Label>
          <h3 className="mt-2 text-[17px] font-medium text-ink">{peakQueueFinding(result)}</h3>
        </div>
        <Button variant="secondary" onClick={download}>Download experiment note</Button>
      </div>
      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        <strong className="font-medium text-ink">Change tested: </strong>{describeExperiment(result.scenario)}
      </p>
      <dl className="mt-4 grid gap-3 border-y border-rule-soft py-3 sm:grid-cols-3">
        {([
          ["Peak queue", "peak_queue", "vehicles"],
          ["Est. mean wait", "average_wait_seconds", "s"],
          ["Throughput", "throughput_per_minute", "vehicles/min"],
        ] as const).map(([label, metric, unit]) => (
          <div key={metric}>
            <dt className="text-[11px] text-ink-faint">{label} · baseline → scenario</dt>
            <dd className="mt-1 font-mono text-[13px] text-ink">
              {formatNumber(result.baseline[metric])} → {formatNumber(result.simulated[metric])} {unit}
            </dd>
            <p className="mt-0.5 text-[11px] text-ink-faint">
              Change: {formatSigned(result.simulated[metric] - result.baseline[metric])} {unit}
            </p>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-[12px] leading-relaxed text-ink-soft">
        {analysis.source === "demo" ? "A comes from the synthetic demo dataset." : "A comes from the video analysis, with detection and region-selection error."}{" "}
        B and C are simulated. Their difference is a hypothesis to test, not an observed improvement.
        {result.baseline.observation_seconds !== result.simulated.observation_seconds && (
          <> The scenario window is {formatNumber(result.simulated.observation_seconds)} s versus {formatNumber(result.baseline.observation_seconds)} s for the baseline; arrival spreading changes the time window as well as the queue.</>
        )}
      </p>
      <p className="mt-2 text-[12px] leading-relaxed text-ink-faint">{sensitivityFinding(result)}</p>
      <p className="mt-2 text-[12px] leading-relaxed text-ink-faint">
        Check against the source: the baseline peak queue is {formatNumber(result.baseline.peak_queue, 0)} vehicles{observedPeak === null ? "; the source peak queue is unavailable." : ` versus ${formatNumber(observedPeak, 0)} in A.`} Verify the counts and capacity assumption before proposing a change at a real site.
      </p>
      {(result.baseline.vehicles_left_at_window_end > 0 || result.simulated.vehicles_left_at_window_end > 0) && (
        <p className="mt-2 text-[12px] leading-relaxed text-ink-faint">
          Some vehicles remain at the window end. Wait averages exclude their unfinished trips, so compare the number left as well as the completed-vehicle wait.
        </p>
      )}
      <p className="mt-3 text-[11px] text-ink-faint">The note includes these results, model settings and limitations. It contains no footage or individual vehicle tracks.</p>
    </Panel>
  );
}
