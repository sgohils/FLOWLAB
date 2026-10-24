import type { Scenario } from "../types";
import { formatFixed, formatSeconds, formatSigned, formatWithUnit } from "../utils/format";
import { Button, Label, Notice, Panel, Pill } from "./Primitives";

export interface ScenarioPreset {
  key: string;
  label: string;
  question: string;
  patch: Params;
}

type Params = {
  volume: number;
  serviceMultiplier: number;
  spreadSeconds: number;
  channels: number;
};

interface SimulationPanelProps {
  volume: number;
  serviceMultiplier: number;
  spreadSeconds: number;
  channels: number;
  onChange: (patch: Partial<Params>) => void;
  onRun: () => void;
  onReset: () => void;
  running: boolean;
  arrivalRate: number | null;
  serviceTime: number | null;
  /** True when the controls have moved since the last run. */
  stale?: boolean;
  disabled?: boolean;
  /** The experiment list, loaded from the backend. */
  presets: ScenarioPreset[];
  /** True when `presets` is the built-in list because the request failed. */
  presetsOffline: boolean;
}

/**
 * Experiments are phrased as the question a user would actually ask, so the
 * direction of every control is obvious before it is touched.
 *
 * The backend owns the numbers (GET /api/analyses/{id}/simulation/presets);
 * this table is the wording, and doubles as the offline fallback so the panel
 * still works when the request fails.
 */
const FALLBACK_PRESETS: ScenarioPreset[] = [
  {
    key: "observed",
    label: "Observed",
    question: "What does the clip actually show?",
    patch: { volume: 1, serviceMultiplier: 1, spreadSeconds: 0, channels: 1 },
  },
  {
    key: "lower_volume",
    label: "Volume -25%",
    question: "What if a quarter fewer cars arrived?",
    patch: { volume: 0.75, serviceMultiplier: 1, spreadSeconds: 0, channels: 1 },
  },
  {
    key: "faster_exit",
    label: "Exit 50% faster",
    question: "What if each vehicle took half as long at the gate?",
    patch: { volume: 1, serviceMultiplier: 1.5, spreadSeconds: 0, channels: 1 },
  },
  {
    key: "spread_arrivals",
    label: "Spread +120 s",
    question: "What if arrivals were spread over two extra minutes?",
    patch: { volume: 1, serviceMultiplier: 1, spreadSeconds: 120, channels: 1 },
  },
  {
    key: "second_channel",
    label: "Second exit lane",
    question: "What if we opened a second gate?",
    patch: { volume: 1, serviceMultiplier: 1, spreadSeconds: 0, channels: 2 },
  },
];

/** The built-in list, used when the backend cannot be reached. */
export function offlinePresets(): ScenarioPreset[] {
  return FALLBACK_PRESETS;
}

/**
 * The four numbers a scenario is built from.  Every one of them has to be a
 * real number before the scenario can be worded or run.
 */
const SCENARIO_FIELDS = [
  "volume",
  "service_multiplier",
  "spread_seconds",
  "channels",
] as const;

/**
 * True when every field the simulator would use is a finite number.  A payload
 * that is missing one, or carries a string or a NaN, is not a scenario.
 */
function hasUsableNumbers(scenario: Scenario): boolean {
  return SCENARIO_FIELDS.every((field) => Number.isFinite(scenario?.[field]));
}

/**
 * Turn a scenario served by the backend into a worded button.  A preset the
 * table does not recognise still gets a usable label built from its own
 * numbers, so a new backend preset is never silently dropped.
 *
 * A preset whose four numbers are not all finite is the one exception: it
 * cannot be worded honestly, and `describe` would format the arithmetic it did
 * do into a confident wrong label (`(undefined - 1) * 100` -> an em dash, or
 * with a null field a real-looking "-100%").  It is dropped, and the drop is
 * logged, because a malformed scenario means the backend and this table
 * disagree about the contract and that is worth seeing in the console.
 */
export function describePresets(scenarios: Scenario[]): ScenarioPreset[] {
  const usable = scenarios.filter((scenario, index) => {
    if (hasUsableNumbers(scenario)) return true;
    console.warn(
      `Scenario ${index} dropped: ${JSON.stringify(scenario)} has a non-numeric setting`,
    );
    return false;
  });
  return usable.map((scenario, index) => {
    const patch: Params = {
      volume: scenario.volume,
      serviceMultiplier: scenario.service_multiplier,
      spreadSeconds: scenario.spread_seconds,
      channels: scenario.channels,
    };
    const known = FALLBACK_PRESETS.find(
      (preset) =>
        preset.patch.volume === patch.volume &&
        preset.patch.serviceMultiplier === patch.serviceMultiplier &&
        preset.patch.spreadSeconds === patch.spreadSeconds &&
        preset.patch.channels === patch.channels,
    );
    if (known) return known;
    return {
      key: `preset-${index}`,
      label: describe(patch),
      question: "What does this combination of settings do?",
      patch,
    };
  });
}

function describe(patch: Params): string {
  const parts: string[] = [];
  if (patch.volume !== 1) parts.push(`volume ${formatSigned((patch.volume - 1) * 100, 0, "%")}`);
  if (patch.serviceMultiplier !== 1) {
    parts.push(`${formatFixed(patch.serviceMultiplier, 2)}x exit`);
  }
  if (patch.spreadSeconds > 0) parts.push(`spread +${formatWithUnit(patch.spreadSeconds, "s", 0)}`);
  if (patch.channels > 1) parts.push(`${patch.channels} exit lanes`);
  // ", " is the separator the backend's own `describe` uses (scenarios.py).
  // The wording of each part is this table's own, which is why that comment
  // above can say the numbers are the backend's and the phrasing is not.
  return parts.length > 0 ? parts.join(", ") : "Observed";
}

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
  presets,
  presetsOffline = false,
}: SimulationPanelProps) {
  const effectiveService = serviceTime ? serviceTime / serviceMultiplier : null;
  const effectiveRate = arrivalRate ? arrivalRate * volume : null;
  const current: Params = { volume, serviceMultiplier, spreadSeconds, channels };
  const activePreset = presets.find((preset) =>
    (Object.keys(preset.patch) as (keyof Params)[]).every(
      (key) => preset.patch[key] === current[key],
    ),
  );

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex items-baseline justify-between gap-2">
          <Label>Ask a question</Label>
          <div className="flex items-center gap-2">
            {presetsOffline && <Pill tone="caution">built-in presets</Pill>}
            <button
              onClick={onReset}
              className="text-[11px] text-ink-faint underline-offset-2 hover:text-ink hover:underline"
            >
              reset to observed
            </button>
          </div>
        </div>
        {presetsOffline && (
          <p className="mt-2 text-[11px] leading-relaxed text-caution">
            The backend could not be asked which experiments to offer, so this is the
            built-in list. The sliders below still drive exactly the same four
            variables, and a run is sent to the same simulator.
          </p>
        )}
        <div className="mt-2 space-y-1">
          {presets.map((preset) => {
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
                ? `${formatWithUnit(effectiveRate, "vehicles/min arriving")} (${formatSigned(
                    (volume - 1) * 100,
                    0,
                    "%",
                  )})`
                : "arrival rate not measured"
            }
            min={0.5}
            max={1.5}
            step={0.05}
            value={volume}
            display={formatSigned((volume - 1) * 100, 0, "%")}
            onChange={(value) => onChange({ volume: value })}
            disabled={disabled}
          />

          <Slider
            label="Exit processing rate"
            hint={
              effectiveService
                ? `${formatSeconds(effectiveService)} per vehicle — ${formatFixed(
                    serviceMultiplier >= 1 ? serviceMultiplier : 1 / serviceMultiplier,
                    2,
                  )}x ${serviceMultiplier >= 1 ? "faster" : "slower"} than observed`
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
                ? `same vehicles stretched over ${formatWithUnit(spreadSeconds, "s longer")}`
                : "arrivals stay on the observed timeline"
            }
            min={0}
            max={300}
            step={10}
            value={spreadSeconds}
            display={spreadSeconds > 0 ? formatSigned(spreadSeconds, 0, "s") : "Observed"}
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
