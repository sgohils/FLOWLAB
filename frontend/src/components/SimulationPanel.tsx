import type { RegionKind } from "../types";
import { formatNumber, formatSeconds } from "../utils/format";
import { Button, Label, Notice, Panel } from "./Primitives";
import type { DrawTool } from "./VideoViewer";

interface SimulationPanelProps {
  volume: number;
  serviceMultiplier: number;
  spreadSeconds: number;
  channels: number;
  onChange: (patch: Partial<{
    volume: number;
    serviceMultiplier: number;
    spreadSeconds: number;
    channels: number;
  }>) => void;
  onRun: () => void;
  onReset: () => void;
  running: boolean;
  arrivalRate: number | null;
  serviceTime: number | null;
  /** True when the controls have moved since the last run. */
  stale?: boolean;
  disabled?: boolean;
}

const TOOLS: { key: DrawTool | "none"; label: string; hint: RegionKind }[] = [
  { key: "queue", label: "Queue region", hint: "queue" },
  { key: "entry", label: "Entry line", hint: "entry" },
  { key: "exit", label: "Exit line", hint: "exit" },
];

type Params = {
  volume: number;
  serviceMultiplier: number;
  spreadSeconds: number;
  channels: number;
};

/**
 * Experiments are phrased as the question a user would actually ask, so the
 * direction of every control is obvious before it is touched.
 */
const PRESETS: { key: string; label: string; question: string; patch: Params }[] = [
  {
    key: "observed",
    label: "Observed",
    question: "What does the clip actually show?",
    patch: { volume: 1, serviceMultiplier: 1, spreadSeconds: 0, channels: 1 },
  },
  {
    key: "spread",
    label: "Spread +120 s",
    question: "What if arrivals were spread over two extra minutes?",
    patch: { volume: 1, serviceMultiplier: 1, spreadSeconds: 120, channels: 1 },
  },
  {
    key: "faster",
    label: "Exit 50% faster",
    question: "What if each vehicle took half as long at the gate?",
    patch: { volume: 1, serviceMultiplier: 1.5, spreadSeconds: 0, channels: 1 },
  },
  {
    key: "volume",
    label: "Volume +25%",
    question: "What if a quarter more cars arrived?",
    patch: { volume: 1.25, serviceMultiplier: 1, spreadSeconds: 0, channels: 1 },
  },
  {
    key: "second",
    label: "Second exit lane",
    question: "What if we opened a second gate?",
    patch: { volume: 1, serviceMultiplier: 1, spreadSeconds: 0, channels: 2 },
  },
];

export function SimulationPanel({
  volume,
  serviceMultiplier,
  spreadSeconds,
  channels,
  onChange,
  onRun,
  onReset,
  running,
  arrivalRate,
  serviceTime,
  stale = false,
  disabled = false,
}: SimulationPanelProps) {
  const effectiveService = serviceTime ? serviceTime / serviceMultiplier : null;
  const effectiveRate = arrivalRate ? arrivalRate * volume : null;
  const current: Params = { volume, serviceMultiplier, spreadSeconds, channels };
  const activePreset = PRESETS.find((preset) =>
    (Object.keys(preset.patch) as (keyof Params)[]).every(
      (key) => preset.patch[key] === current[key],
    ),
  );

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex items-baseline justify-between">
          <Label>Ask a question</Label>
          <button
            onClick={onReset}
            className="text-[11px] text-ink-faint underline-offset-2 hover:text-ink hover:underline"
          >
            reset to observed
          </button>
        </div>
        <div className="mt-2 space-y-1">
          {PRESETS.map((preset) => {
            const active = activePreset?.key === preset.key;
            return (
              <button
                key={preset.key}
                onClick={() => onChange(preset.patch)}
                aria-pressed={active}
                className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[12px] transition-colors ${
                  active ? "bg-ink text-paper" : "text-ink-soft hover:bg-paper"
                }`}
              >
                <span className="w-[104px] shrink-0 font-mono text-[11px]">{preset.label}</span>
                <span className={active ? "text-paper/85" : "text-ink-faint"}>
                  {preset.question}
                </span>
              </button>
            );
          })}
        </div>
      </Panel>

      <Panel className="p-5">
        <div className="flex items-baseline justify-between">
          <Label>Scenario controls</Label>
          {stale && (
            <span
              className="rounded border border-caution/40 bg-caution-soft px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-caution"
              role="status"
            >
              stale — results below are from the previous run
            </span>
          )}
        </div>

        <div className="mt-5 space-y-6">
          <Slider
            label="Traffic volume"
            hint={
              effectiveRate
                ? `${formatNumber(effectiveRate)} vehicles/min arriving (${volume >= 1 ? "+" : ""}${Math.round((volume - 1) * 100)}%)`
                : "arrival rate not measured"
            }
            min={0.5}
            max={1.5}
            step={0.05}
            value={volume}
            display={`${volume >= 1 ? "+" : ""}${Math.round((volume - 1) * 100)}%`}
            onChange={(value) => onChange({ volume: value })}
            disabled={disabled}
          />

          <Slider
            label="Exit processing rate"
            hint={
              effectiveService
                ? `${formatSeconds(effectiveService)} per vehicle — ${
                    serviceMultiplier >= 1
                      ? `${serviceMultiplier.toFixed(2)}x faster than observed`
                      : `${(1 / serviceMultiplier).toFixed(2)}x slower than observed`
                  }`
                : "service time not measured"
            }
            min={0.5}
            max={2}
            step={0.05}
            value={serviceMultiplier}
            display={
              Math.abs(serviceMultiplier - 1) < 0.03
                ? "Observed"
                : serviceMultiplier > 1
                  ? "Faster"
                  : "Slower"
            }
            onChange={(value) => onChange({ serviceMultiplier: value })}
            disabled={disabled}
          />

          <Slider
            label="Arrival spread"
            hint={
              spreadSeconds > 0
                ? `same vehicles stretched over ${formatNumber(spreadSeconds)}s longer`
                : "arrivals stay on the observed timeline"
            }
            min={0}
            max={300}
            step={10}
            value={spreadSeconds}
            display={spreadSeconds > 0 ? `+${formatNumber(spreadSeconds)}s` : "Observed"}
            onChange={(value) => onChange({ spreadSeconds: value })}
            disabled={disabled}
          />

          <div>
            <div className="flex items-baseline justify-between">
              <span className="text-[13px] text-ink">Secondary exit channel</span>
              <span className="font-mono text-[12px] text-ink-soft">
                {channels === 2 ? "Enabled" : "Disabled"}
              </span>
            </div>
            <div className="mt-2 flex gap-2">
              {[1, 2].map((count) => (
                <button
                  key={count}
                  disabled={disabled}
                  onClick={() => onChange({ channels: count })}
                  className={`flex-1 rounded border px-3 py-1.5 text-[12px] transition-colors disabled:opacity-50 ${
                    channels === count
                      ? "border-ink bg-ink text-paper"
                      : "border-rule bg-surface text-ink-soft hover:border-ink-faint"
                  }`}
                >
                  {count} lane{count > 1 ? "s" : ""}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] text-ink-faint">
              A second processing lane doubles the exit capacity in the model.
            </p>
          </div>
        </div>

        <Button
          className="mt-6 w-full"
          onClick={onRun}
          disabled={running || disabled}
        >
          {running ? "Running scenario…" : "Run simulated scenario"}
        </Button>
        {disabled && (
          <p className="mt-2 text-[11px] text-ink-faint">
            Upload a video first — a scenario needs a measured arrival pattern.
          </p>
        )}
      </Panel>

      <Notice tone="caution" title="Hypothetical model">
        The simulator is a one-lane corridor calibrated from this clip. It shows
        how the same arrivals would behave under different exit capacity or
        timing. It is not a forecast and not a recommendation for the real site.
      </Notice>
    </div>
  );
}

export function RegionToolPicker({
  tool,
  onChange,
}: {
  tool: DrawTool;
  onChange: (tool: DrawTool) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {TOOLS.map((entry) => (
        <button
          key={entry.key}
          onClick={() => onChange(entry.key)}
          className={`rounded border px-3 py-1.5 text-[12px] transition-colors ${
            tool === entry.key
              ? "border-ink bg-ink text-paper"
              : "border-rule bg-surface text-ink-soft hover:border-ink-faint"
          }`}
        >
          {entry.label}
        </button>
      ))}
      {tool !== "none" && (
        <span className="text-[11px] text-ink-faint">
          {tool === "queue"
            ? "Click to place corners, double-click to close the polygon."
            : "Click two points to draw the line."}
        </span>
      )}
    </div>
  );
}

function Slider({
  label,
  hint,
  min,
  max,
  step,
  value,
  display,
  onChange,
  disabled,
}: {
  label: string;
  hint: string;
  min: number;
  max: number;
  step: number;
  value: number;
  display: string;
  onChange: (value: number) => void;
  disabled: boolean;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-[13px] text-ink">{label}</span>
        <span className="font-mono text-[12px] text-ink-soft">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-2 h-1 w-full cursor-pointer appearance-none rounded bg-rule-soft accent-[#1d4ed8] disabled:opacity-40"
      />
      <p className="mt-1.5 text-[11px] text-ink-faint">{hint}</p>
    </div>
  );
}
