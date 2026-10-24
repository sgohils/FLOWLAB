import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { Button, Notice, Row } from "./Primitives";
import type { Analysis, Scenario, SimulationResult } from "../types";
import { formatFixed, formatNumber, formatWithUnit, vehicleLabel } from "../utils/format";
/**
 * A printable one-page analysis brief.
 *
 * It carries the evidence a reader needs to check the numbers - source, window,
 * comparison, and every assumption - and deliberately contains **no footage**:
 * only anonymous trajectories and measurements.
 */
export function PrintBrief() {
  const { analysisId } = useParams();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!analysisId) return;
    let cancelled = false;
    api
      .result(analysisId, 120)
      .then(async (result) => {
        if (cancelled) return;
        setAnalysis(result);
        // The brief always shows the baseline comparison, so the baseline
        // scenario is run for the same analysis.
        const scenario: Scenario = {
          volume: 1,
          service_multiplier: 1,
          spread_seconds: 0,
          channels: 1,
          seed: 20240517,
        };
        try {
          const simulated = await api.simulate(analysisId, scenario);
          if (!cancelled) setSimulation(simulated);
        } catch {
          if (!cancelled) setSimulation(null);
        }
      })
      .catch((caught) => {
        if (!cancelled) setError((caught as Error).message ?? "Could not load this analysis.");
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  if (error) {
    return (
      <Notice tone="error" title="Could not build the brief">
        {error}
      </Notice>
    );
  }
  if (!analysis) {
    return <p className="p-8 text-center text-[13px] text-ink-faint">Building brief…</p>;
  }

  const summary = analysis.summary;
  const regions = analysis.regions;

  return (
    <div className="mx-auto max-w-[900px] print:max-w-none">
      <div className="mb-6 flex items-center justify-between print:hidden">
        <p className="text-[12px] text-ink-faint">
          Print-friendly brief. Charts and anonymous trajectories only — no footage is
          included.
        </p>
        <Button onClick={() => window.print()}>Print / save as PDF</Button>
      </div>

      <article className="rounded-md border border-rule bg-surface p-8 print:border-0 print:p-0">
        <header className="border-b border-rule pb-4 print:border-black">
          <h1 className="text-[22px] font-medium tracking-tight text-ink">
            FLOWLAB analysis brief
          </h1>
          <p className="mt-1 font-mono text-[12px] text-ink-soft">
            {analysis.analysis_id} ·{" "}
            {analysis.source === "demo" ? "DEMO DATASET (synthetic traffic)" : "uploaded video"}
          </p>
        </header>

        <PrintSection title="Source and observation window">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[13px] sm:grid-cols-3">
            <Row label="Source" value={analysis.source === "demo" ? "Demo Dataset" : "Uploaded clip"} />
            <Row label="Duration" value={formatWithUnit(analysis.video.duration, "s")} />
            <Row label="Resolution" value={`${analysis.video.width}×${analysis.video.height}`} />
            <Row label="Source fps" value={formatNumber(analysis.video.fps)} />
            <Row label="Sampling" value={`${formatNumber(analysis.video.processed_fps)} fps`} />
            <Row label="Vehicles tracked" value={formatNumber(summary.vehicles_tracked, 0)} />
          </dl>
        </PrintSection>

        <PrintSection title="Measurement regions">
          <div className="grid gap-4 sm:grid-cols-[220px_1fr]">
            <RegionFigure analysis={analysis} />
            <dl className="space-y-1.5 text-[13px]">
              <Row
                label="Queue region"
                value={regions.queue.length >= 3 ? "drawn (polygon)" : "not defined"}
              />
              <Row
                label="Entry line"
                value={regions.entry.length === 2 ? "drawn" : "not defined"}
              />
              <Row
                label="Exit line"
                value={regions.exit.length === 2 ? "drawn" : "not defined"}
              />
              <Row label="Exit crossings counted" value={regions.exit_direction} />
              <Row
                label="Motion threshold"
                value={`${regions.speed_threshold} frame widths / s`}
              />
              <Row label="Minimum queue stay" value={`${regions.min_queue_seconds} s`} />
              <Row
                label="Region source"
                value={regions.auto_detected ? "auto-suggested" : "user drawn"}
              />
            </dl>
          </div>
        </PrintSection>

        <PrintSection title="Measured results">
          <table className="w-full border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-b border-rule text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                <th className="py-1.5 pr-3 font-medium">Quantity</th>
                <th className="py-1.5 pr-3 font-medium">Value</th>
                <th className="py-1.5 font-medium">Definition used</th>
              </tr>
            </thead>
            <tbody>
              <TableRow
                k="Peak queue"
                v={formatWithUnit(summary.peak_queue, "vehicles", 0)}
                d="most vehicles inside the queue region and below the speed threshold at one instant"
              />
              <TableRow
                k="Average queue"
                v={formatWithUnit(summary.average_queue, "vehicles")}
                d="time-average of the queue length over the clip"
              />
              <TableRow
                k="Est. wait (mean)"
                v={formatWithUnit(summary.average_wait_seconds, "s")}
                d={`time inside the region while slow; ${summary.completed_queue_visits} completed visits, ${summary.censored_queue_visits} censored and excluded`}
              />
              <TableRow
                k="Est. wait (max)"
                v={formatWithUnit(summary.max_wait_seconds, "s")}
                d="longest completed queue visit"
              />
              <TableRow
                k="Throughput"
                v={formatWithUnit(summary.throughput_per_minute, "veh/min")}
                d={`${summary.vehicles_processed} exit-line crossings / ${formatNumber(analysis.video.duration / 60, 2)} min`}
              />
              <TableRow
                k="Mean time in region"
                v={formatWithUnit(summary.average_region_seconds, "s")}
                d="inside the queue region, moving or not"
              />
              <TableRow
                k="Mean slow time"
                v={formatWithUnit(summary.mean_stopped_seconds, "s")}
                d="below the speed threshold anywhere in the scene"
              />
              <TableRow
                k="Mean traversal"
                v={formatWithUnit(summary.mean_traversal_seconds, "s")}
                d="first to last tracked sample of a vehicle"
              />
            </tbody>
          </table>
          <p className="mt-2 text-[11px] leading-relaxed text-ink-faint">
            Positions are normalised image coordinates, not a calibrated scale. Nothing in
            this brief is a physical distance or speed, and no wait time is a measured
            stopwatch value.
          </p>
        </PrintSection>

        {analysis.bottlenecks.length > 0 && (
          <PrintSection title="Bottleneck evidence">
            <table className="w-full border-collapse text-left text-[13px]">
              <thead>
                <tr className="border-b border-rule text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                  <th className="py-1.5 pr-3 font-medium">Rank</th>
                  <th className="py-1.5 pr-3 font-medium">Where</th>
                  <th className="py-1.5 pr-3 font-medium">Distinct vehicles</th>
                  <th className="py-1.5 pr-3 font-medium">Time below threshold</th>
                  <th className="py-1.5 font-medium">Mean per vehicle</th>
                </tr>
              </thead>
              <tbody>
                {analysis.bottlenecks.slice(0, 4).map((cell) => (
                  <tr key={cell.id} className="border-b border-rule-soft">
                    <td className="py-1.5 pr-3 font-mono">#{cell.id}</td>
                    <td className="py-1.5 pr-3 font-mono">
                      x {formatFixed(cell.x, 2)} · y {formatFixed(cell.y, 2)}
                    </td>
                    <td className="py-1.5 pr-3 font-mono">
                      {cell.vehicle_passes}
                      {cell.vehicle_ids.length > 0 && (
                        <span className="ml-1 text-[10px] text-ink-faint">
                          ({vehicleLabel(cell.vehicle_ids[0])}…)
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 pr-3 font-mono">
                      {formatNumber(cell.stopped_seconds)} s
                    </td>
                    <td className="py-1.5 font-mono">
                      {formatNumber(cell.mean_slowdown_seconds)} s
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[11px] leading-relaxed text-ink-faint">
              Ranked, not a severity grade. A cell is listed only when at least two
              different vehicles were measurably slowed there.
            </p>
          </PrintSection>
        )}

        {simulation && (
          <PrintSection title="Observed versus the unmodified model">
            <table className="w-full border-collapse text-left text-[13px]">
              <thead>
                <tr className="border-b border-rule text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                  <th className="py-1.5 pr-3 font-medium">Quantity</th>
                  <th className="py-1.5 pr-3 font-medium">A · Observed</th>
                  <th className="py-1.5 pr-3 font-medium">B · Baseline model</th>
                  <th className="py-1.5 font-medium">B − A</th>
                </tr>
              </thead>
              <tbody>
                <TableRow
                  k="Peak queue"
                  v={`${simulation.observed.peak_queue} / ${simulation.baseline.peak_queue}`}
                  d={`model ratio ${simulation.fidelity.ratio ?? "n/a"}`}
                />
                <TableRow
                  k="Est. wait (mean, s)"
                  v={`${formatNumber(simulation.observed.average_wait_seconds)} / ${formatNumber(simulation.baseline.average_wait_seconds)}`}
                  d="completed visits only"
                />
                <TableRow
                  k="Throughput (veh/min)"
                  v={`${formatNumber(simulation.observed.throughput_per_minute)} / ${formatNumber(simulation.baseline.throughput_per_minute)}`}
                  d={`over ${formatNumber(simulation.baseline.observation_seconds)} s`}
                />
                <TableRow
                  k="Left at window end"
                  v={`— / ${simulation.baseline.vehicles_left_at_window_end}`}
                  d="not observable in a recording"
                />
              </tbody>
            </table>
            <p className="mt-2 text-[11px] leading-relaxed text-ink-faint">
              {simulation.fidelity.note} Model outcome, not a guaranteed result.
            </p>
          </PrintSection>
        )}

        <PrintSection title="Assumptions and limitations">
          <ul className="list-disc space-y-1 pl-5 text-[12px] leading-relaxed text-ink-soft">
            <li>Fixed camera; no perspective calibration, so units are image-based.</li>
            <li>
              Queue, wait and stopped are different quantities: region + slow for at
              least {regions.min_queue_seconds}s, and below the motion threshold anywhere for
              at least {regions.min_stop_seconds}s respectively.
            </li>
            <li>
              Queue visits that began before the clip, or were still open at the end, are
              censored and excluded from the wait averages.
            </li>
            <li>
              The simulation is a single lane with one gate; it models no merges, signals or
              pedestrians.
            </li>
            <li>
              The video and the annotated video are stored locally and can contain
              identifiable people or plates; anonymous ids do not anonymise the footage.
            </li>
          </ul>
        </PrintSection>

        <PrintSection title="Configuration for reproduction">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[12px] sm:grid-cols-3">
            <Row label="Detector" value="Ultralytics YOLO11n (pretrained)" />
            <Row label="Tracker" value="ByteTrack" />
            <Row label="Classes" value="car, bus, truck, motorcycle, bicycle" />
            <Row label="Smoothing" value="exponential, 0.55, bypassed on jumps" />
            <Row label="Gap threshold" value={formatWithUnit(2.5 / regions.sample_fps, "s", 3)} />
            <Row label="Brief generated" value={new Date().toISOString().slice(0, 19).replace("T", " ")} />
          </dl>
        </PrintSection>
      </article>
    </div>
  );
}

/**
 * A ruled block of the brief.  Deliberately local: the page-level `Section` in
 * Primitives is a different visual treatment, and two components with the same
 * name in one tree is a trap.
 */
function PrintSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-rule-soft py-4 last:border-0 print:break-inside-avoid">
      <h2 className="mb-2 text-[11px] font-medium uppercase tracking-[0.16em] text-ink-faint">
        {title}
      </h2>
      {children}
    </section>
  );
}


function TableRow({ k, v, d }: { k: string; v: string; d: string }) {
  return (
    <tr className="border-b border-rule-soft last:border-0">
      <td className="py-1.5 pr-3 text-ink-soft">{k}</td>
      <td className="py-1.5 pr-3 font-mono text-ink">{v}</td>
      <td className="py-1.5 text-[11px] leading-snug text-ink-faint">{d}</td>
    </tr>
  );
}

function RegionFigure({ analysis }: { analysis: Analysis }) {
  const aspect = analysis.video.height / Math.max(1, analysis.video.width);
  const height = Math.max(60, Math.round(220 * aspect));
  const points = analysis.regions.queue
    .map(([x, y]) => `${x * 100},${y * 100}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 60" className="w-full border border-rule bg-white" style={{ maxHeight: height }}>
      <rect x="0" y="0" width="100" height="60" fill="#ffffff" />
      {analysis.regions.queue.length >= 3 && (
        <polygon points={points} fill="rgba(29,78,216,0.12)" stroke="#1d4ed8" strokeWidth="0.4" />
      )}
      {(["entry", "exit"] as const).map((name) => {
        const line = analysis.regions[name];
        if (line.length !== 2) return null;
        return (
          <line
            key={name}
            x1={line[0][0] * 100}
            y1={line[0][1] * 100}
            x2={line[1][0] * 100}
            y2={line[1][1] * 100}
            stroke={name === "entry" ? "#0f766e" : "#b45309"}
            strokeWidth="0.6"
          />
        );
      })}
      {analysis.trajectories.slice(0, 40).map((track) => (
        <polyline
          key={track.vehicle_id}
          points={track.points.map((p) => `${p.x * 100},${p.y * 100}`).join(" ")}
          fill="none"
          stroke={track.queue_seconds > 0 ? "#1d4ed8" : "#9aa0a8"}
          strokeWidth="0.18"
          opacity="0.75"
        />
      ))}
      <text x="2" y="58" fontSize="3" fill="#7b8189" fontFamily="monospace">
        image coordinates — no real-world scale
      </text>
    </svg>
  );
}
