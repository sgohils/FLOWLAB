import { useMemo, useState } from "react";
import { useReplay } from "../state/ReplayContext";
import type { Analysis, TimelinePayload } from "../types";
import {
  formatClassName,
  formatNumber,
  formatPercent,
  formatWithUnit,
  vehicleLabel,
} from "../utils/format";
import { Label, Panel, Pill, Row } from "./Primitives";

interface TrafficMapProps {
  analysis: Analysis;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  showHeat: boolean;
  showRegions: boolean;
  /** Draw each vehicle at the shared replay clock. */
  showNow?: boolean;
  /** Vehicle ids to highlight because a bottleneck was selected. */
  highlightIds?: number[];
  className?: string;
}

const VIEW_WIDTH = 1000;

/** One vehicle drawn at the replay clock. */
type LiveDot = { id: number; x: number; y: number; queued: boolean; selected: boolean };

/**
 * Live dots drawn at once.  Past this the map thins them instead of stalling
 * the replay; the footer then says how many are shown, because a map that is
 * quietly showing half the traffic looks like a map that is not working.
 */
export const MAX_LIVE_DOTS = 120;

/**
 * Which vehicles get a live dot at the replay clock.
 *
 * Everything, when the clip is small enough.  Above `limit`, a fixed stride
 * over the order the payload arrives in: the same set of vehicles on every
 * frame, so the dots do not flicker as the clock runs, and spread across the
 * whole clip rather than crowded into whichever end happened to be listed
 * first.
 *
 * A bottleneck highlight or a selected vehicle is always kept and is never
 * sampled away - those are the ones the user asked to see.  So the bound is on
 * the sampled part: at most `limit` plus the number of vehicles the user has
 * singled out, which is the one case where exceeding it is the right answer.
 */
export function pickLiveVehicles(
  vehicles: TimelinePayload["vehicles"],
  highlight: ReadonlySet<number>,
  selectedId: number | null,
  limit: number,
): number[] {
  if (vehicles.length <= limit) return vehicles.map((vehicle) => vehicle.id);
  const singled = new Set<number>([...highlight].filter((id) => Number.isFinite(id)));
  if (selectedId !== null) singled.add(selectedId);
  const keep = new Set<number>(singled);
  const stride = Math.max(1, Math.ceil(vehicles.length / limit));
  vehicles.forEach((vehicle, index) => {
    if (singled.has(vehicle.id)) {
      keep.add(vehicle.id);
      return;
    }
    if (index % stride === 0 && keep.size < limit) keep.add(vehicle.id);
  });
  return vehicles.filter((vehicle) => keep.has(vehicle.id)).map((vehicle) => vehicle.id);
}

/**
 * Simplified top-down movement map.
 *
 * Coordinates are the normalised image coordinates of the source frame, so the
 * map is a direct "unrolled" view of the camera image - no calibration, no
 * claimed real-world scale.  A note in the footer says so explicitly.
 */
export function TrafficMap({
  analysis,
  selectedId,
  onSelect,
  showHeat,
  showRegions,
  showNow = false,
  highlightIds = [],
  className = "",
}: TrafficMapProps) {
  const [hovered, setHovered] = useState<number | null>(null);
  const trajectories = analysis.trajectories;
  const { positionAt, time, timeline, manyVehicles } = useReplay();
  const highlight = useMemo(() => new Set(highlightIds), [highlightIds]);
  // Aspect ratio of the source frame, so the plot is not distorted.
  const aspect = analysis.video.height / Math.max(1, analysis.video.width);
  const viewHeight = Math.max(
    320,
    Math.min(900, Math.round(VIEW_WIDTH * aspect)),
  );
  // Flattened once instead of per render: these change only with the analysis.
  const view = useMemo(
    () => ({ width: VIEW_WIDTH, height: viewHeight }),
    [viewHeight],
  );
  const maxHeat = useMemo(
    () => Math.max(...analysis.heat_grid.map((cell) => cell.value), 0.0001),
    [analysis.heat_grid],
  );
  const heatCells = useMemo(
    () =>
      analysis.heat_grid.map((cell) => ({
        key: `${cell.x}-${cell.y}`,
        x: (cell.x - cell.width / 2) * view.width,
        y: (cell.y - cell.height / 2) * view.height,
        width: cell.width * view.width,
        height: cell.height * view.height,
        fill: `rgba(180, 83, 9, ${(cell.value / maxHeat) * 0.32})`,
      })),
    [analysis.heat_grid, view, maxHeat],
  );
  const queueOutline = useMemo(
    () =>
      analysis.regions.queue
        .map(([x, y]) => `${x * view.width},${y * view.height}`)
        .join(" "),
    [analysis.regions.queue, view],
  );
  /** One SVG path per vehicle, built once: the replay clock must not rebuild them. */
  const trackPaths = useMemo(
    () =>
      analysis.trajectories.map((track) => ({
        vehicleId: track.vehicle_id,
        queued: track.queue_seconds > 0,
        first: track.points[0] ?? { x: 0, y: 0 },
        last: track.points[track.points.length - 1] ?? { x: 0, y: 0 },
        d: track.points
          .map(
            (point, index) =>
              `${index === 0 ? "M" : "L"}${(point.x * view.width).toFixed(1)},${(
                point.y * view.height
              ).toFixed(1)}`,
          )
          .join(" "),
      })),
    [analysis.trajectories, view],
  );

  /**
   * Positions at the shared clock.  A busy clip draws a bounded sample of the
   * fleet rather than one marker per vehicle, so the replay keeps running; the
   * counts come back with it so the footer can say the map is thinned, instead
   * of leaving the user to wonder whether the missing dots are a bug.
   */
  const live = useMemo(() => {
    const empty = { dots: [] as LiveDot[], total: 0, drawn: 0 };
    if (!showNow || !timeline) return empty;
    const all = timeline.vehicles;
    const wanted = new Set(
      pickLiveVehicles(all, highlight, selectedId, manyVehicles ? MAX_LIVE_DOTS : all.length),
    );
    const dots: LiveDot[] = [];
    for (const vehicle of all) {
      if (!wanted.has(vehicle.id)) continue;
      const point = positionAt(vehicle.id);
      if (!point) continue; // unknown inside a tracking gap: do not draw
      dots.push({
        id: vehicle.id,
        x: point.x,
        y: point.y,
        queued: vehicle.queue_seconds > 0,
        selected: vehicle.id === selectedId,
      });
    }
    return { dots, total: all.length, drawn: dots.length };
    // `time` is the dependency that matters: positionAt reads it internally.
  }, [showNow, timeline, positionAt, selectedId, highlight, time, manyVehicles]);
  const livePositions = live.dots;
  const thinned = live.drawn > 0 && live.drawn < live.total;

  const selected = trajectories.find((track) => track.vehicle_id === selectedId) ?? null;
  const active = hovered ?? selectedId;
  const empty = trajectories.length === 0;

  if (empty) {
    return (
      <Panel className="flex min-h-[240px] flex-col items-center justify-center p-8 text-center">
        <p className="text-[13px] font-medium text-ink">Nothing to plot</p>
        <p className="mt-2 max-w-md text-[12px] leading-relaxed text-ink-faint">
          {analysis.warnings[0] ??
            "No vehicle survived long enough to be tracked in this clip, so there are no paths to draw."}{" "}
          The map fills in as soon as an analysis tracks vehicles; the metric cards
          above say which measurements are unavailable as a result.
        </p>
      </Panel>
    );
  }

  return (
    <div className={`grid gap-4 lg:grid-cols-[1fr_260px] ${className}`}>
      <Panel className="relative overflow-hidden">
        <svg
          viewBox={`0 0 ${view.width} ${view.height}`}
          className="block w-full bg-white"
          role="img"
          aria-label={
            thinned
              ? `Image-coordinate trajectory map of anonymous vehicles. ${live.drawn} of ${live.total} vehicles are shown: the map is thinned to keep the replay smooth.`
              : "Image-coordinate trajectory map of anonymous vehicles"
          }
        >
          {/* frame + reference grid */}
          <rect
            x={0.5}
            y={0.5}
            width={view.width - 1}
            height={view.height - 1}
            fill="none"
            stroke="#dcdcd6"
          />
          {Array.from({ length: 9 }, (_, index) => (
            <line
              key={`v${index}`}
              x1={(view.width / 8) * index}
              y1={0}
              x2={(view.width / 8) * index}
              y2={view.height}
              stroke="#f0f0ec"
            />
          ))}
          {Array.from({ length: 6 }, (_, index) => (
            <line
              key={`h${index}`}
              x1={0}
              y1={(view.height / 6) * index}
              x2={view.width}
              y2={(view.height / 6) * index}
              stroke="#f0f0ec"
            />
          ))}

          {showHeat &&
            heatCells.map((cell) => (
              <rect
                key={cell.key}
                x={cell.x}
                y={cell.y}
                width={cell.width}
                height={cell.height}
                fill={cell.fill}
              />
            ))}

          {showRegions && analysis.regions.queue.length >= 3 && (
            <polygon
              points={queueOutline}
              fill="rgba(29,78,216,0.07)"
              stroke="#1d4ed8"
              strokeWidth={1.5}
              strokeDasharray="7 5"
            />
          )}

          {(["entry", "exit"] as const).map((name) => {
            const line = analysis.regions[name];
            if (line.length !== 2) return null;
            return (
              <line
                key={name}
                x1={line[0][0] * view.width}
                y1={line[0][1] * view.height}
                x2={line[1][0] * view.width}
                y2={line[1][1] * view.height}
                stroke={name === "entry" ? "#0f766e" : "#b45309"}
                strokeWidth={2}
              />
            );
          })}

          {analysis.bottlenecks.map((bottleneck) => (
            <g key={bottleneck.id}>
              <rect
                x={(bottleneck.x - bottleneck.width / 2) * view.width}
                y={(bottleneck.y - bottleneck.height / 2) * view.height}
                width={bottleneck.width * view.width}
                height={bottleneck.height * view.height}
                fill="none"
                stroke="#b45309"
                strokeWidth={1.5}
                strokeDasharray="4 3"
              />
              <text
                x={(bottleneck.x - bottleneck.width / 2) * view.width + 6}
                y={(bottleneck.y - bottleneck.height / 2) * view.height + 16}
                fontSize={13}
                fontFamily="ui-monospace, monospace"
                fill="#b45309"
              >
                B{bottleneck.id}
              </text>
            </g>
          ))}

          {/* trajectories: subtle by default, the selected one is emphasised */}
          {trackPaths.map((track) => {
            const isActive = active === track.vehicleId;
            const dimmed = highlight.size > 0 && !highlight.has(track.vehicleId);
            return (
              <g key={track.vehicleId}>
                <path
                  d={track.d}
                  fill="none"
                  stroke={track.queued ? "#1d4ed8" : "#8b9098"}
                  strokeOpacity={dimmed ? 0.12 : isActive ? 1 : 0.45}
                  strokeWidth={
                    highlight.has(track.vehicleId) ? 2.4 : isActive ? 3 : 1.4
                  }
                  strokeLinecap="round"
                />
                {/* Invisible wide hit area.  The vehicle list below is the
                    keyboard-reachable way to select the same vehicle. */}
                <path
                  d={track.d}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={14}
                  aria-hidden="true"
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHovered(track.vehicleId)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => onSelect(track.vehicleId === selectedId ? null : track.vehicleId)}
                />
                {isActive && (
                  <>
                    <circle
                      cx={track.first.x * view.width}
                      cy={track.first.y * view.height}
                      r={5}
                      fill="#0f766e"
                    />
                    <circle
                      cx={track.last.x * view.width}
                      cy={track.last.y * view.height}
                      r={5}
                      fill="#b45309"
                    />
                  </>
                )}
              </g>
            );
          })}
          {/* Live positions: one dot per vehicle at the shared replay clock.
              A vehicle inside a tracking gap has no known position, so it is
              deliberately not drawn - nothing is invented between samples. */}
          {showNow && livePositions.length > 0 && (
            <g aria-label="Vehicle positions at the current replay time">
              {livePositions.map((item) => (
                <g key={item.id}>
                  <circle
                    cx={item.x * view.width}
                    cy={item.y * view.height}
                    r={item.selected ? 7 : 4}
                    fill={item.queued ? "#1d4ed8" : "#4a4f57"}
                    stroke="#ffffff"
                    strokeWidth={item.selected ? 2 : 1}
                    vectorEffect="non-scaling-stroke"
                  />
                  {item.selected && (
                    <text
                      x={item.x * view.width + 10}
                      y={item.y * view.height - 8}
                      fontSize={12}
                      fontFamily="ui-monospace, monospace"
                      fill="#14161a"
                      stroke="#ffffff"
                      strokeWidth={3}
                      paintOrder="stroke"
                    >
                      #{String(item.id).padStart(3, "0")}
                    </text>
                  )}
                </g>
              ))}
            </g>
          )}
        </svg>
        <div className="flex flex-wrap items-center gap-4 border-t border-rule px-4 py-2 text-[11px] text-ink-faint">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#0f766e]" /> start
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#b45309]" /> end
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-[2px] w-4 bg-[#1d4ed8]" /> queued vehicle
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full border border-white bg-[#4a4f57] ring-1 ring-[#dcdcd6]" />
            position now
          </span>
          <span>Image-coordinate map of the camera frame — no real-world scale.</span>
          {thinned && (
            <span className="font-medium text-caution">
              Thinned to {live.drawn} of {live.total} vehicles to keep the replay
              smooth — select a vehicle or a bottleneck to narrow it.
            </span>
          )}
        </div>
      </Panel>

      <div className="space-y-3">
        <Panel className="p-4">
          <Label>Vehicle inspector</Label>
          {selected ? (
            <div className="mt-3 space-y-2 text-[13px]">
              <p className="font-mono text-[15px] text-ink">
                {vehicleLabel(selected.vehicle_id)}
              </p>
              <dl className="space-y-1.5">
                <Row label="Type" value={formatClassName(selected.vehicle_class)} />
                <Row
                  label="Traversal time"
                  value={`${formatWithUnit(selected.duration, "s")} (first → last sighting)`}
                />
                <Row
                  label="Path length"
                  value={`${formatPercent(selected.path_length)} of frame width`}
                />
                <Row
                  label="Slow time"
                  value={`${formatWithUnit(selected.stopped_seconds, "s")} anywhere in frame`}
                />
                <Row
                  label="In queue region"
                  value={`${formatWithUnit(selected.queue_seconds, "s")} slow · ${formatWithUnit(
                    selected.region_seconds,
                    "s",
                  )} total`}
                />
                <Row
                  label="Mean motion"
                  value={`${formatPercent(selected.mean_speed)} frame width / s`}
                />
              </dl>
            </div>
          ) : (
            <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
              Click a path on the map to inspect that vehicle. Paths are
              simplified for display; all numbers come from the full-resolution
              trajectory.
            </p>
          )}
        </Panel>

        <Panel className="max-h-[280px] overflow-y-auto p-4 scroll-thin">
          <Label>Tracked vehicles</Label>
          <ul className="mt-2 divide-y divide-rule-soft">
            {trajectories.slice(0, 60).map((track) => (
              <li key={track.vehicle_id}>
                <button
                  onClick={() =>
                    onSelect(track.vehicle_id === selectedId ? null : track.vehicle_id)
                  }
                  aria-pressed={track.vehicle_id === selectedId}
                  className={`flex w-full items-center justify-between px-1 py-1.5 text-left text-[12px] transition-colors hover:bg-paper ${
                    track.vehicle_id === selectedId ? "bg-accent-soft" : ""
                  }`}
                >
                  <span className="font-mono text-ink-soft">
                    {vehicleLabel(track.vehicle_id)}
                  </span>
                  <span className="flex items-center gap-2 text-ink-faint">
                    {track.queue_seconds > 0 && (
                      <Pill tone="accent">queued {formatNumber(track.queue_seconds, 0)}s</Pill>
                    )}
                    <span>{formatClassName(track.vehicle_class)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
