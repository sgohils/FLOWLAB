import { useCallback, useRef, useState } from "react";
import type { Analysis, Regions } from "../types";
import { Label, Notice, Panel } from "./Primitives";
import type { DrawTool } from "./VideoViewer";

type RegionName = "queue" | "entry" | "exit";

const TOOLS: { key: DrawTool; label: string; help: string }[] = [
  {
    key: "queue",
    label: "Queue region",
    help: "Click to place corners, double-click (or press Enter) to close the polygon.",
  },
  {
    key: "entry",
    label: "Entry line",
    help: "Click two points. Vehicles crossing it count as arrivals.",
  },
  {
    key: "exit",
    label: "Exit line",
    help: "Click two points. Vehicles crossing it count as departures.",
  },
];

interface RegionEditorProps {
  regions: Regions | null;
  tool: DrawTool;
  onToolChange: (tool: DrawTool) => void;
  onChange: (regions: Regions) => void;
  onCommit: () => void;
  saving: boolean;
  error: string | null;
  editable: boolean;
}

/**
 * Region editing with a keyboard path: the same three tools, but every tool
 * also has a numeric fallback so a region can be defined without a mouse.
 */
export function RegionEditor({
  regions,
  tool,
  onToolChange,
  onChange,
  onCommit,
  saving,
  error,
  editable,
}: RegionEditorProps) {
  const [coordinate, setCoordinate] = useState("0.50, 0.60");
  const [directionTarget, setDirectionTarget] = useState<"entry" | "exit">("exit");

  const applyRegion = useCallback(
    (name: RegionName, points: number[][]) => {
      if (!regions) return;
      onChange({ ...regions, [name]: points } as Regions);
      onCommit();
    },
    [regions, onChange, onCommit],
  );

  const parseCoordinates = (): number[][] => {
    const numbers = coordinate
      .split(/[,\s]+/)
      .map((part) => Number(part))
      .filter((value) => Number.isFinite(value));
    if (numbers.length % 2 !== 0 || numbers.length < 2) return [];
    if (numbers.some((value) => value < 0 || value > 1)) return [];
    const points: number[][] = [];
    for (let index = 0; index < numbers.length; index += 2) {
      points.push([numbers[index], numbers[index + 1]]);
    }
    return points;
  };

  const applyFromInput = () => {
    if (tool === "none") return;
    const points = parseCoordinates();
    if (points.length === 0) return;
    if (tool === "queue" && points.length < 3) return;
    if (tool !== "queue" && points.length !== 2) return;
    applyRegion(tool, points);
  };

  if (!editable || !regions) return null;

  return (
    <Panel className="space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Label>Measure regions</Label>
        <div className="flex flex-wrap gap-1.5">
          {TOOLS.map((entry) => (
            <button
              key={entry.key}
              onClick={() => onToolChange(entry.key)}
              aria-pressed={tool === entry.key}
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
            <button
              onClick={() => {
                applyRegion(tool, []);
                onToolChange("none");
              }}
              className="rounded border border-rule px-3 py-1.5 text-[12px] text-ink-soft hover:border-ink-faint"
            >
              Clear {tool}
            </button>
          )}        </div>
        {saving && (
          <span className="text-[12px] text-ink-faint" role="status">
            Recomputing metrics…
          </span>
        )}
      </div>

      {tool !== "none" && (
        <p className="text-[12px] text-ink-soft">{TOOLS.find((t) => t.key === tool)?.help}</p>
      )}

      <div className="flex flex-wrap items-end gap-2 border-t border-rule-soft pt-3">
        <div className="flex-1 min-w-[220px]">
          <label className="block text-[11px] text-ink-faint" htmlFor="region-coordinates">
            Or type coordinates (0–1, x then y)
          </label>
          <input
            id="region-coordinates"
            value={coordinate}
            onChange={(event) => setCoordinate(event.target.value)}
            className="mt-1 w-full rounded border border-rule bg-surface px-2 py-1.5 font-mono text-[12px] text-ink"
            placeholder="0.40,0.55 0.99,0.55 0.99,0.99 0.40,0.99"
          />
        </div>
        <button
          onClick={applyFromInput}
          disabled={tool === "none"}
          className="rounded border border-rule bg-surface px-3 py-1.5 text-[12px] text-ink-soft hover:border-ink-faint disabled:opacity-40"
        >
          Apply to {tool}
        </button>
      </div>

      <div className="flex flex-wrap items-end gap-4 border-t border-rule-soft pt-3">
        <div>
          <span className="block text-[11px] text-ink-faint">Count crossings</span>
          <div className="mt-1 flex gap-1.5">
            {(["entry", "exit"] as const).map((name) => (
              <button
                key={name}
                onClick={() => setDirectionTarget(name)}
                aria-pressed={directionTarget === name}
                className={`rounded border px-2.5 py-1 text-[11px] ${
                  directionTarget === name
                    ? "border-ink text-ink"
                    : "border-rule text-ink-faint"
                }`}
              >
                {name}
              </button>
            ))}
          </div>
        </div>
        <label className="flex items-center gap-2 text-[12px] text-ink-soft">
          <input
            type="checkbox"
            checked={regions[`${directionTarget}_direction` as const] === "forward"}
            onChange={(event) => {
              onChange({
                ...regions,
                [`${directionTarget}_direction`]: event.target.checked ? "forward" : "any",
              } as Regions);
              onCommit();
            }}
          />
          {directionTarget} line: only count forward crossings
        </label>
        <div className="min-w-[220px] flex-1">
          <label className="block text-[11px] text-ink-faint" htmlFor="min-queue-seconds">
            Minimum queue time before a vehicle counts (s)
          </label>
          <input
            id="min-queue-seconds"
            type="number"
            min={0}
            max={60}
            step={0.1}
            value={regions.min_queue_seconds}
            onChange={(event) => {
              const value = Number(event.target.value);
              if (Number.isFinite(value)) {
                onChange({ ...regions, min_queue_seconds: value } as Regions);
                onCommit();
              }
            }}
            className="mt-1 w-28 rounded border border-rule bg-surface px-2 py-1.5 font-mono text-[12px] text-ink"
          />
        </div>
      </div>

      {error && (
        <Notice tone="error" title="That region was rejected">
          {error}
        </Notice>
      )}
      {regions.auto_detected && (
        <Notice tone="info" title="Suggested regions — check them before trusting the numbers">
          These were proposed from where vehicles actually slowed down, not drawn by a
          person. Redraw anything that does not match the part of the scene you care
          about; the metrics update immediately.
        </Notice>
      )}
    </Panel>
  );
}

/** Tracks the newest request so a slow response cannot overwrite a newer edit. */
export function useLatestRequest() {
  const newest = useRef(0);
  const inFlight = useRef(0);
  const [pending, setPending] = useState(0);

  const begin = useCallback(() => {
    newest.current += 1;
    inFlight.current += 1;
    setPending(inFlight.current);
    return newest.current;
  }, []);

  const isCurrent = useCallback((token: number) => token === newest.current, []);

  const finish = useCallback(() => {
    inFlight.current = Math.max(0, inFlight.current - 1);
    setPending(inFlight.current);
  }, []);

  return { begin, isCurrent, finish, pending };
}

export function staleNotice(analysis: Analysis | null, pendingEdits: number) {
  if (!analysis || pendingEdits === 0) return null;
  return (
    <Notice tone="caution" title="Recomputing">
      The metrics below still show the previous regions until the update finishes.
    </Notice>
  );
}
