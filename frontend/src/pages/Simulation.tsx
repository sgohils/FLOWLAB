import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ApiError, api } from "../api/client";
import { CorridorComparison } from "../components/CorridorComparison";
import { CorridorMap } from "../components/CorridorMap";
import type { ScenarioPreset } from "../components/SimulationPanel";
import { describePresets, offlinePresets, SimulationPanel } from "../components/SimulationPanel";
import { Button, Label, Notice, Panel, Row, Section } from "../components/Primitives";
import { useAnalysis } from "../state/AnalysisContext";
import type { Scenario, SimulationResult } from "../types";
import {
  deltaTone,
  formatNumber,
  formatSigned,
  formatTimecode,
  formatWithUnit,
} from "../utils/format";

const DEFAULTS = {
  volume: 1,
  serviceMultiplier: 1,
  spreadSeconds: 0,
  channels: 1,
};

export default function Simulation() {
  const { analysisId: routeId } = useParams();
  const navigate = useNavigate();
  const { analysisId, analysis, load } = useAnalysis();
  const [params, setParams] = useState(DEFAULTS);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<{ message: string; hint: string | null } | null>(null);
  const [presets, setPresets] = useState<ScenarioPreset[]>(() => offlinePresets());
  const [presetsOffline, setPresetsOffline] = useState(true);

  useEffect(() => {
    if (routeId) void load(routeId);
  }, [routeId, load]);

  /**
   * The backend owns which experiments it offers, so ask it rather than
   * hard-coding the list.  The built-in list stays as the offline fallback.
   */
  useEffect(() => {
    if (!analysisId) return;
    let cancelled = false;
    api
      .presets(analysisId)
      .then((scenarios) => {
        if (cancelled) return;
        // describePresets drops anything it cannot word honestly, so an all
        // malformed payload has to fall through to the built-in list rather
        // than leave the panel with no experiments at all.
        const described = describePresets(scenarios);
        if (!described.length) throw new Error("no usable presets returned");
        setPresets(described);
        setPresetsOffline(false);
      })
      .catch(() => {
        if (cancelled) return;
        setPresets(offlinePresets());
        setPresetsOffline(true);
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  const run = async () => {
    if (!analysisId) return;
    setRunning(true);
    setError(null);
    const scenario: Scenario = {
      volume: params.volume,
      service_multiplier: params.serviceMultiplier,
      spread_seconds: params.spreadSeconds,
      channels: params.channels,
      seed: 20240517,
    };
    try {
      setResult(await api.simulate(analysisId, scenario));
    } catch (caught) {
      const apiError = caught as ApiError;
      setError({ message: apiError.message, hint: apiError.hint });
    } finally {
      setRunning(false);
    }
  };

  if (!analysisId && !routeId) {
    return (
      <div className="mx-auto max-w-lg py-16 text-center">
        <h1 className="text-xl font-medium text-ink">No analysis to simulate</h1>
        <p className="mt-2 text-[13px] text-ink-soft">
          A scenario needs a measured arrival pattern. Upload a video first, or
          open the demo dataset.
        </p>
        <div className="mt-5 flex justify-center gap-2">
          <Button onClick={() => navigate("/")}>Upload a video</Button>
          <Button
            variant="secondary"
            onClick={() => {
              void load("demo");
              navigate("/simulation/demo");
            }}
          >
            Open demo dataset
          </Button>
        </div>
      </div>
    );
  }

  const observed = result?.observed;
  const simulated = result?.simulated;

  /**
   * Results are stale as soon as a control moves away from the values that
   * produced them.  Comparing against the *returned* scenario (not local state)
   * keeps this correct even if the same scenario is re-run.
   */
  const stale = Boolean(
    result &&
      (result.scenario.volume !== params.volume ||
        result.scenario.service_multiplier !== params.serviceMultiplier ||
        result.scenario.spread_seconds !== params.spreadSeconds ||
        result.scenario.channels !== params.channels),
  );

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-4">
        <div>
          <Label>Simulation</Label>
          <h1 className="mt-1 font-mono text-[22px] tracking-tight text-ink">
            observed vs simulated
            {analysis?.source === "demo" && (
              <span className="ml-3 align-middle rounded border border-caution/40 bg-caution-soft px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-caution">
                Demo Dataset
              </span>
            )}
          </h1>
          <p className="mt-1.5 text-[12px] text-ink-faint">
            One corridor, one gate. Change one variable, keep everything else at
            the observed values.
          </p>
        </div>
        {analysis && (
          <Link
            to={`/analysis/${analysis.analysis_id}`}
            className="rounded border border-rule bg-surface px-3 py-1.5 text-[12px] text-ink-soft hover:border-ink-faint"
          >
            Back to analysis
          </Link>
        )}
      </div>

      {error && (
        <div className="mb-6">
          <Notice tone="error" title="The scenario could not run">
            <p>{error.message}</p>
            {error.hint && <p className="mt-1 opacity-85">{error.hint}</p>}
          </Notice>
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-[340px_1fr]">
        <div>
          <Section title="Controls">
            <SimulationPanel
              volume={params.volume}
              serviceMultiplier={params.serviceMultiplier}
              spreadSeconds={params.spreadSeconds}
              channels={params.channels}
              onChange={(patch) => setParams((current) => ({ ...current, ...patch }))}
              onRun={run}
              onReset={() => setParams(DEFAULTS)}
              running={running}
              arrivalRate={analysis?.calibration.arrival_rate_per_minute ?? null}
              serviceTime={analysis?.calibration.service_time_seconds ?? null}
              stale={stale}
              disabled={!analysis}
              presets={presets}
              presetsOffline={presetsOffline}
            />
          </Section>

          {analysis && (
            <Section title="Observed baseline">
              <Panel className="p-4">
                <dl className="space-y-1.5 text-[13px]">
                  <Row
                    label="Arrival rate"
                    value={formatWithUnit(analysis.calibration.arrival_rate_per_minute, "/min")}
                  />
                  <Row
                    label="Exit service time"
                    value={formatWithUnit(analysis.calibration.service_time_seconds, "s")}
                  />
                  <Row
                    label="Free-flow time"
                    value={formatWithUnit(analysis.calibration.free_flow_seconds, "s")}
                  />
                  <Row label="Vehicles in clip" value={formatNumber(analysis.calibration.vehicles_used, 0)} />
                </dl>
                <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">
                  Arrival times come from {analysis.regions.entry.length === 2 ? "the entry line" : "first sightings (no entry line defined)"}.
                </p>
              </Panel>
            </Section>
          )}
        </div>

        <div>
          <Section
            title="Results"
            data-testid="results-state"
            data-result={result ? "ready" : running ? "running" : "empty"}
            data-error={error ? "yes" : "no"}
            subtitle={
              result
                ? "Hypothetical simulated scenario — a model output, not a measurement."
                : "Run a scenario to compare."
            }
          >
            {!result && !running && (
              <Panel className="flex h-full min-h-[220px] items-center justify-center p-10 text-center text-[13px] text-ink-faint">
                Pick one of the questions on the left and run it. The baseline run
                replays the observed arrivals, so you can see how much of any
                difference is the model's own error.
              </Panel>
            )}

            {result && observed && simulated && (
              <div className="space-y-6">
                {stale && (
                  <Notice tone="caution" title="These results are from the previous run">
                    A control has moved. Run the scenario again to update the comparison.
                  </Notice>
                )}
                <div>
                  <Label>Scenario effect — modified model (C) vs baseline model (B)</Label>
                  <p className="mt-1 text-[12px] text-ink-faint">
                    What the change you made does, holding everything else at the observed
                    values.
                  </p>
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                  {result.deltas.map((delta) => (
                    <Panel key={delta.metric} className="p-4">
                      <Label>{delta.label}</Label>
                      <div className="mt-3 flex items-baseline gap-2">
                        <span className="font-mono text-[22px] leading-none text-ink">
                          {formatNumber(delta.simulated)}
                        </span>
                        <span className="text-[11px] text-ink-faint">{delta.unit}</span>
                      </div>
                      <p
                        className={`mt-2 font-mono text-[12px] ${
                          deltaTone(delta.absolute, delta.lower_is_better) === "good"
                            ? "text-positive"
                            : deltaTone(delta.absolute, delta.lower_is_better) === "bad"
                              ? "text-caution"
                              : "text-ink-faint"
                        }`}
                      >
                        {formatSigned(delta.absolute)} vs baseline
                        {delta.percent !== null && ` (${formatSigned(delta.percent, 0, "%")})`}
                      </p>
                    </Panel>
                  ))}
                </div>

                <Panel className="p-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <Label>Model mismatch — baseline model (B) vs observed footage (A)</Label>
                    <span className="text-[11px] text-ink-faint">
                      Shown separately: this is the model's error, not the effect of your
                      change.
                    </span>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                    {result.model_deltas.map((delta) => (
                      <div key={delta.metric} className="rounded border border-rule-soft px-3 py-2">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="text-[11px] text-ink-faint">{delta.label}</span>
                          <span className="font-mono text-[12px] text-ink-soft">
                            {formatNumber(delta.observed)} → {formatNumber(delta.simulated)}
                          </span>
                        </div>
                        <p className="mt-1 font-mono text-[11px] text-ink-faint">
                          {formatSigned(delta.absolute)} {delta.unit}
                        </p>
                      </div>
                    ))}
                  </div>
                </Panel>

                <Panel className="px-3 py-4">
                  <div className="px-2">
                    <Label>Three-way summary</Label>
                    <p className="mt-1 text-[12px] text-ink-faint">
                      All three over the same observation window
                      ({formatNumber(observed.observation_seconds)} s). "Left at end" is the
                      number of vehicles still inside the corridor when the window ends;
                      for a recording it is not observable, so it is shown as —.
                    </p>
                    <table className="mt-3 w-full border-collapse text-left text-[12px]">
                      <thead>
                        <tr className="border-b border-rule text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                          <th className="py-1.5 pr-3 font-medium">Metric</th>
                          <th className="py-1.5 pr-3 font-medium">A · Observed</th>
                          <th className="py-1.5 pr-3 font-medium">B · Baseline</th>
                          <th className="py-1.5 pr-3 font-medium">C · Scenario</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono text-ink">
                        <SummaryRow
                          label="Peak queue (vehicles)"
                          a={String(observed.peak_queue)}
                          b={String(result.baseline.peak_queue)}
                          c={String(simulated.peak_queue)}
                        />
                        <SummaryRow
                          label="Est. wait, mean (s)"
                          a={formatNumber(observed.average_wait_seconds)}
                          b={formatNumber(result.baseline.average_wait_seconds)}
                          c={formatNumber(simulated.average_wait_seconds)}
                        />
                        <SummaryRow
                          label="Est. wait, max (s)"
                          a={formatNumber(observed.max_wait_seconds)}
                          b={formatNumber(result.baseline.max_wait_seconds)}
                          c={formatNumber(simulated.max_wait_seconds)}
                        />
                        <SummaryRow
                          label="Throughput (veh/min)"
                          a={formatNumber(observed.throughput_per_minute)}
                          b={formatNumber(result.baseline.throughput_per_minute)}
                          c={formatNumber(simulated.throughput_per_minute)}
                        />
                        <SummaryRow
                          label="Left at window end"
                          a="—"
                          b={String(result.baseline.vehicles_left_at_window_end)}
                          c={String(simulated.vehicles_left_at_window_end)}
                        />
                      </tbody>
                    </table>
                  </div>
                </Panel>

                <Panel className="px-3 py-4">
                  <div className="px-2">
                    <Label>Queue length over time — A observed, B baseline, C modified</Label>
                    <p className="mt-1 text-[12px] text-ink-faint">
                      The model has a single waiting point at the gate, while the video queue
                      region is an area of the scene, so the two curves are not expected to
                      match exactly.
                    </p>
                  </div>
                  <ComparisonChart result={result} />
                </Panel>

                <div className="grid gap-4 lg:grid-cols-2">
                  <Panel className="p-4">
                    <Label>What the scenario changed</Label>
                    <ul className="mt-2 space-y-1.5 text-[12px] leading-relaxed text-ink-soft">
                      {result.notes.map((note) => (
                        <li key={note}>— {note}</li>
                      ))}
                    </ul>
                  </Panel>
                  <Panel className="p-4">
                    <Label>How well the model reproduces the clip</Label>
                    <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">
                      {result.fidelity.note}
                    </p>
                    <dl className="mt-3 space-y-1 text-[12px]">
                      <Row
                        label="Observed peak queue (A)"
                        value={formatWithUnit(result.fidelity.peak_queue_observed, "vehicles")}
                      />
                      <Row
                        label="Baseline model peak queue (B)"
                        value={formatWithUnit(result.fidelity.peak_queue_model, "vehicles")}
                      />
                      <Row
                        label="Observed mean wait (A)"
                        value={formatWithUnit(result.fidelity.average_wait_observed, "s")}
                      />
                      <Row
                        label="Baseline model mean wait (B)"
                        value={formatWithUnit(result.fidelity.average_wait_model, "s")}
                      />
                    </dl>
                  </Panel>
                </div>

                {result.sensitivity && (
                  <Panel className="p-4">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <Label>Sensitivity range — {result.sensitivity.parameter}</Label>
                      <span className="font-mono text-[11px] text-ink-faint">
                        baseline {formatNumber(result.sensitivity.baseline_value)} s
                      </span>
                    </div>
                    <p className="mt-2 text-[11px] leading-relaxed text-ink-faint">
                      {result.sensitivity.method} {result.sensitivity.note}
                    </p>
                    <table className="mt-3 w-full border-collapse text-left text-[12px]">
                      <thead>
                        <tr className="border-b border-rule text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                          <th className="py-1.5 pr-3 font-medium">Service time</th>
                          <th className="py-1.5 pr-3 font-medium">Peak queue</th>
                          <th className="py-1.5 pr-3 font-medium">Mean wait</th>
                          <th className="py-1.5 font-medium">Throughput</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.sensitivity.values.map((point) => (
                          <tr
                            key={point.service_time_seconds}
                            className="border-b border-rule-soft last:border-0"
                          >
                            <td className="py-1.5 pr-3 font-mono">
                              {formatNumber(point.service_time_seconds)} s
                            </td>
                            <td className="py-1.5 pr-3 font-mono">{point.peak_queue}</td>
                            <td className="py-1.5 pr-3 font-mono">
                              {formatNumber(point.average_wait_seconds)} s
                            </td>
                            <td className="py-1.5 font-mono">
                              {formatNumber(point.throughput_per_minute)}/min
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="mt-3 text-[11px] leading-relaxed text-ink-soft">
                      Across those alternatives the baseline peak queue ranges from{" "}
                      <span className="font-mono">{result.sensitivity.peak_queue_range[0]}</span> to{" "}
                      <span className="font-mono">{result.sensitivity.peak_queue_range[1]}</span>{" "}
                      vehicles and the mean wait from{" "}
                      <span className="font-mono">
                        {formatNumber(result.sensitivity.average_wait_range[0])} s
                      </span>{" "}
                      to{" "}
                      <span className="font-mono">
                        {formatNumber(result.sensitivity.average_wait_range[1])} s
                      </span>
                      . Any scenario effect smaller than that spread should not be
                      read as a real difference.
                    </p>
                  </Panel>
                )}
              </div>
            )}
          </Section>

          {result && (
            <Section
              title="Watch the two models"
              subtitle="The same corridor, the same arrivals, one change - drawn from the simulator's own recorded states."
            >
              <div className="space-y-6">
                <CorridorMap result={result} />
                <CorridorComparison result={result} />
              </div>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

interface ComparisonPoint {
  time: number;
  observed: number;
  baseline: number | null;
  simulated: number | null;
}

function ComparisonChart({ result }: { result: SimulationResult }) {
  // Recharts re-reads `data` on every render, and this page re-renders whenever
  // a control moves, so the series is built once per result rather than per
  // render.
  const data = useMemo<ComparisonPoint[]>(
    () =>
      result.observed_queue.map((sample, index) => ({
        time: sample.time,
        observed: sample.queue,
        baseline: result.baseline_queue[index]?.queue ?? null,
        simulated: result.simulated_queue[index]?.queue ?? null,
      })),
    [result],
  );
  const lastTime = data.length > 0 ? data[data.length - 1].time : 1;
  return (
    <div className="h-[280px] w-full">
      <Comparison data={data} maxTime={lastTime} />
    </div>
  );
}

const MARGIN = { top: 8, right: 16, left: -16, bottom: 0 };
const TOOLTIP_STYLE = {
  border: "1px solid #dcdcd6",
  borderRadius: 4,
  fontSize: 12,
  fontFamily: "ui-monospace, monospace",
};
const LEGEND_STYLE = { fontSize: 12, paddingTop: 6 };
const LABEL_FORMATTER = (value: unknown) => `t = ${formatTimecode(Number(value))}`;

function Comparison({ data, maxTime }: { data: ComparisonPoint[]; maxTime: number }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={MARGIN}>
        <CartesianGrid strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="time"
          type="number"
          domain={[0, maxTime]}
          tickFormatter={formatTimecode}
          tickCount={7}
        />
        <YAxis allowDecimals={false} width={44} />
        <Tooltip labelFormatter={LABEL_FORMATTER} contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={LEGEND_STYLE} />
        <Line
          type="monotone"
          dataKey="observed"
          name="A · Observed"
          stroke="#1d4ed8"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="baseline"
          name="B · Baseline model"
          stroke="#4a4f57"
          strokeWidth={1.6}
          strokeDasharray="2 3"
          dot={false}
          isAnimationActive={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="simulated"
          name="C · Modified model"
          stroke="#b45309"
          strokeWidth={2}
          strokeDasharray="6 4"
          dot={false}
          isAnimationActive={false}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}


function SummaryRow({
  label,
  a,
  b,
  c,
}: {
  label: string;
  a: string;
  b: string;
  c: string;
}) {
  return (
    <tr className="border-b border-rule-soft last:border-0">
      <td className="py-1.5 pr-3 font-sans text-ink-soft">{label}</td>
      <td className="py-1.5 pr-3">{a}</td>
      <td className="py-1.5 pr-3 text-ink-soft">{b}</td>
      <td className="py-1.5 font-medium text-caution">{c}</td>
    </tr>
  );
}
