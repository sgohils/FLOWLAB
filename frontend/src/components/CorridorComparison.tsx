import { useEffect, useMemo, useRef, useState } from "react";
import type { SimulatedTrack, SimulationResult } from "../types";
import { Label, Panel } from "./Primitives";
import { formatTimecode } from "../utils/format";

interface CorridorComparisonProps {
  result: SimulationResult;
  height?: number;
}

const RATES = [1, 2, 4];

/**
 * Baseline and modified corridor models on one clock.
 *
 * Both panels are drawn from the simulator's own recorded states, so the
 * animation cannot show an improvement the model did not produce: if the two
 * runs are identical, the two panels look identical.
 */
export function CorridorComparison({ result, height = 190 }: CorridorComparisonProps) {
  const duration = Math.max(
    result.baseline.observation_seconds,
    result.simulated.observation_seconds,
  );
  // Start where the corridor is actually busy: at t = 0 every vehicle is still
  // at the entry, which makes the two lanes look identical and proves nothing.
  const [time, setTime] = useState(() => Math.min(60, duration * 0.3));
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const frame = useRef<number | null>(null);
  const last = useRef<number>(0);

  useEffect(() => {
    setTime(Math.min(60, duration * 0.3));
    setPlaying(false);
  }, [result.analysis_id, JSON.stringify(result.scenario)]);

  useEffect(() => {
    if (!playing) return;
    last.current = performance.now();
    const tick = () => {
      const now = performance.now();
      const delta = ((now - last.current) / 1000) * rate;
      last.current = now;
      setTime((current) => {
        const next = current + delta;
        if (next >= duration) {
          setPlaying(false);
          return duration;
        }
        return next;
      });
      frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [playing, rate, duration]);

  const baseline = useMemo(
    () => project(result.baseline_tracks ?? [], time),
    [result.baseline_tracks, time],
  );
  const modified = useMemo(() => project(result.tracks ?? [], time), [result.tracks, time]);
  const identical =
    baseline.length === modified.length &&
    baseline.every((item, index) => item.x === modified[index]?.x);

  return (
    <Panel className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <Label>Corridor models on one clock</Label>
        <div className="flex items-center gap-2 text-[12px] text-ink-soft">
          <button
            onClick={() => setPlaying((value) => !value)}
            className="rounded border border-ink bg-ink px-2.5 py-1 text-[11px] text-paper"
          >
            {playing ? "Pause" : "Play"}
          </button>
          <input
            type="range"
            min={0}
            max={Math.max(duration, 0.1)}
            step={0.05}
            value={Math.min(time, duration)}
            onChange={(event) => {
              setPlaying(false);
              setTime(Number(event.target.value));
            }}
            aria-label="Corridor animation position"
            className="h-1 w-40 cursor-pointer appearance-none rounded bg-rule-soft accent-[#1d4ed8]"
          />
          <span className="w-[92px] font-mono text-[11px]">
            {formatTimecode(time)} / {formatTimecode(duration)}
          </span>
          {RATES.map((value) => (
            <button
              key={value}
              onClick={() => setRate(value)}
              aria-pressed={rate === value}
              className={`rounded border px-1.5 font-mono text-[10px] ${
                rate === value ? "border-ink text-ink" : "border-rule text-ink-faint"
              }`}
            >
              {value}×
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Lane
          title="B · Baseline model"
          caption={`${result.baseline.vehicles} vehicles · peak queue ${result.baseline.peak_queue}`}
          vehicles={baseline}
          height={height}
          accent="#4a4f57"
        />
        <Lane
          title="C · Modified scenario"
          caption={`${result.simulated.vehicles} vehicles · peak queue ${result.simulated.peak_queue}`}
          vehicles={modified}
          height={height}
          accent="#b45309"
        />
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">
        {identical
          ? "Both runs are identical at this instant: the change you made does not move these vehicles within the window shown."
          : "Each square is one simulated vehicle. Horizontal position is its progress along the corridor; the vertical position is the gate, where vehicles are processed."}{" "}
        Remaining at the end of the window: baseline {result.baseline.vehicles_left_at_window_end},
        scenario {result.simulated.vehicles_left_at_window_end}.
      </p>
    </Panel>
  );
}

function Lane({
  title,
  caption,
  vehicles,
  height,
  accent,
}: {
  title: string;
  caption: string;
  vehicles: { x: number; queued: boolean; unknown: boolean }[];
  height: number;
  accent: string;
}) {
  return (
    <div className="rounded border border-rule bg-paper p-3">
      <div className="flex items-baseline justify-between">
        <span className="text-[12px] font-medium text-ink">{title}</span>
        <span className="font-mono text-[10px] text-ink-faint">{caption}</span>
      </div>
      <svg viewBox="0 0 100 44" className="mt-2 w-full" style={{ height }} preserveAspectRatio="none">
        <rect x="0" y="0" width="100" height="44" fill="#ffffff" />
        <line x1="0" y1="26" x2="100" y2="26" stroke="#dcdcd6" strokeWidth="1" />
        <rect x="92" y="4" width="2" height="40" fill="#14161a" opacity="0.75" />
        <text x="93" y="43" fontSize="3.2" fill="#7b8189" fontFamily="monospace">
          gate
        </text>
        {vehicles.map((vehicle, index) => (
          <rect
            key={index}
            x={vehicle.x * 92}
            y={vehicle.queued ? 12 : 30}
            width="2.4"
            height="6"
            fill={vehicle.unknown ? "#c9ccd1" : accent}
            opacity={vehicle.unknown ? 0.5 : 0.95}
          />
        ))}
      </svg>
      <div className="mt-1 flex items-center gap-3 text-[10px] text-ink-faint">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2" style={{ background: accent }} /> moving
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2" style={{ background: accent, opacity: 0.5 }} />
          stopped / queued
        </span>
        <span>entry →</span>
      </div>
    </div>
  );
}

/** Map recorded vehicle paths onto the current instant. */
function project(tracks: SimulatedTrack[], time: number) {
  return (tracks ?? []).map((track) => {
    const points = track.points ?? [];
    if (!points.length) return { x: 0, queued: false, unknown: true };
    if (time < points[0][0] || time > points[points.length - 1][0]) {
      return { x: 0, queued: false, unknown: true };
    }
    let low = 0;
    let high = points.length - 1;
    while (low < high - 1) {
      const middle = (low + high) >> 1;
      if (points[middle][0] <= time) low = middle;
      else high = middle;
    }
    const [t0, x0] = points[low];
    const [t1, x1] = points[high];
    const fraction = t1 <= t0 ? 0 : (time - t0) / (t1 - t0);
    const x = x0 + fraction * (x1 - x0);
    // "Queued" means the vehicle is in the last stretch and barely moving.
    const queued = x > 0.7 && (x1 - x0) < 0.01;
    return { x, queued, unknown: false };
  });
}
