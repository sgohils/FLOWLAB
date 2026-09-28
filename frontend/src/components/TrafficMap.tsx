import { useMemo, useState } from "react";
import { useReplay } from "../state/ReplayContext";
import type { Analysis, Trajectory } from "../types";
import { formatClassName, formatNumber, vehicleLabel } from "../utils/format";
import { Label, Panel, Pill } from "./Primitives";

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
  const { positionAt, time, timeline } = useReplay();
  const highlight = useMemo(() => new Set(highlightIds), [highlightIds]);
  // Aspect ratio of the source frame, so the plot is not distorted.
  const aspect = analysis.video.height / Math.max(1, analysis.video.width);
  const VIEW = {
    width: VIEW_WIDTH,
    height: Math.max(320, Math.min(900, Math.round(VIEW_WIDTH * aspect))),
  };
  const maxHeat = useMemo(
    () => Math.max(...analysis.heat_grid.map((cell) => cell.value), 0.0001),
    [analysis.heat_grid],
  );

  /**
   * Positions at the shared clock.  With many tracks only the selection and
   * the bottleneck highlights are drawn, so the map stays responsive.
   */
  const livePositions = useMemo(() => {
    if (!showNow || !timeline) return [];
    const all = timeline.vehicles;
    const subset =
      all.length > 120 && selectedId === null
        ? all.filter((vehicle) => highlight.has(vehicle.id))
        : all;
    const out: { id: number; x: number; y: number; queued: boolean; selected: boolean }[] = [];
    for (const vehicle of subset) {
      const point = positionAt(vehicle.id);
      if (!point) continue; // unknown inside a tracking gap: do not draw
      out.push({
        id: vehicle.id,
        x: point.x,
        y: point.y,
        queued: vehicle.queue_seconds > 0,
        selected: vehicle.id === selectedId,
      });
    }
    return out;
    // `time` is the dependency that matters: positionAt reads it internally.
  }, [showNow, timeline, positionAt, selectedId, highlight, time]);

  const selected = trajectories.find((track) => track.vehicle_id === selectedId) ?? null;
  const active = hovered ?? selectedId;

  const path = (track: Trajectory) =>
    track.points
      .map((point, index) => `${index === 0 ? "M" : "L"}${(point.x * VIEW.width).toFixed(1)},${(point.y * VIEW.height).toFixed(1)}`)
      .join(" ");

  return (
    <div className={`grid gap-4 lg:grid-cols-[1fr_260px] ${className}`}>
      <Panel className="relative overflow-hidden">
        <svg
          viewBox={`0 0 ${VIEW.width} ${VIEW.height}`}
          className="block w-full bg-white"
          role="img"
          aria-label="Image-coordinate trajectory map of anonymous vehicles"
        >
          {/* frame + reference grid */}
          <rect
            x={0.5}
            y={0.5}
            width={VIEW.width - 1}
            height={VIEW.height - 1}
            fill="none"
            stroke="#dcdcd6"
          />
          {Array.from({ length: 9 }, (_, index) => (
            <line
              key={`v${index}`}
              x1={(VIEW.width / 8) * index}
              y1={0}
              x2={(VIEW.width / 8) * index}
              y2={VIEW.height}
              stroke="#f0f0ec"
            />
          ))}
          {Array.from({ length: 6 }, (_, index) => (
            <line
              key={`h${index}`}
              x1={0}
              y1={(VIEW.height / 6) * index}
              x2={VIEW.width}
              y2={(VIEW.height / 6) * index}
              stroke="#f0f0ec"
            />
          ))}

          {showHeat &&
            analysis.heat_grid.map((cell, index) => (
              <rect
                key={index}
                x={(cell.x - cell.width / 2) * VIEW.width}
                y={(cell.y - cell.height / 2) * VIEW.height}
                width={cell.width * VIEW.width}
                height={cell.height * VIEW.height}
                fill={`rgba(180, 83, 9, ${(cell.value / maxHeat) * 0.32})`}
              />
            ))}

          {showRegions && analysis.regions.queue.length >= 3 && (
            <polygon
              points={analysis.regions.queue
                .map(([x, y]) => `${x * VIEW.width},${y * VIEW.height}`)
                .join(" ")}
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
                x1={line[0][0] * VIEW.width}
                y1={line[0][1] * VIEW.height}
                x2={line[1][0] * VIEW.width}
                y2={line[1][1] * VIEW.height}
                stroke={name === "entry" ? "#0f766e" : "#b45309"}
                strokeWidth={2}
              />
            );
          })}

          {analysis.bottlenecks.map((bottleneck) => (
            <g key={bottleneck.id}>
              <rect
                x={(bottleneck.x - bottleneck.width / 2) * VIEW.width}
                y={(bottleneck.y - bottleneck.height / 2) * VIEW.height}
                width={bottleneck.width * VIEW.width}
                height={bottleneck.height * VIEW.height}
                fill="none"
                stroke="#b45309"
                strokeWidth={1.5}
                strokeDasharray="4 3"
              />
              <text
                x={(bottleneck.x - bottleneck.width / 2) * VIEW.width + 6}
                y={(bottleneck.y - bottleneck.height / 2) * VIEW.height + 16}
                fontSize={13}
                fontFamily="ui-monospace, monospace"
                fill="#b45309"
              >
                B{bottleneck.id}
              </text>
            </g>
          ))}

          {/* trajectories: subtle by default, the selected one is emphasised */}
          {trajectories.map((track) => {
            const isActive = active === track.vehicle_id;
            const queued = track.queue_seconds > 0;
            const dimmed = highlight.size > 0 && !highlight.has(track.vehicle_id);
            return (
              <g key={track.vehicle_id}>
                <path
                  d={path(track)}
                  fill="none"
                  stroke={queued ? "#1d4ed8" : "#8b9098"}
                  strokeOpacity={dimmed ? 0.12 : isActive ? 1 : 0.45}
                  strokeWidth={
                    highlight.has(track.vehicle_id) ? 2.4 : isActive ? 3 : 1.4
                  }
                  strokeLinecap="round"
                />
                <path
                  d={path(track)}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={14}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHovered(track.vehicle_id)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => onSelect(track.vehicle_id === selectedId ? null : track.vehicle_id)}
                />
                {isActive && (
                  <>
                    <circle
                      cx={track.points[0].x * VIEW.width}
                      cy={track.points[0].y * VIEW.height}
                      r={5}
                      fill="#0f766e"
                    />
                    <circle
                      cx={track.points[track.points.length - 1].x * VIEW.width}
                      cy={track.points[track.points.length - 1].y * VIEW.height}
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
                    cx={item.x * VIEW.width}
                    cy={item.y * VIEW.height}
                    r={item.selected ? 7 : 4}
                    fill={item.queued ? "#1d4ed8" : "#4a4f57"}
                    stroke="#ffffff"
                    strokeWidth={item.selected ? 2 : 1}
                    vectorEffect="non-scaling-stroke"
                  />
                  {item.selected && (
                    <text
                      x={item.x * VIEW.width + 10}
                      y={item.y * VIEW.height - 8}
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
                  value={`${formatNumber(selected.duration)} s (first → last sighting)`}
                />
                <Row
                  label="Path length"
                  value={`${(selected.path_length * 100).toFixed(1)}% of frame width`}
                />
                <Row
                  label="Slow time"
                  value={`${formatNumber(selected.stopped_seconds)} s anywhere in frame`}
                />
                <Row
                  label="In queue region"
                  value={`${formatNumber(selected.queue_seconds)} s slow · ${formatNumber(
                    selected.region_seconds,
                  )} s total`}
                />
                <Row
                  label="Mean motion"
                  value={`${(selected.mean_speed * 100).toFixed(1)}% frame width / s`}
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
                  className={`flex w-full items-center justify-between px-1 py-1.5 text-left text-[12px] transition-colors hover:bg-paper ${
                    track.vehicle_id === selectedId ? "bg-accent-soft" : ""
                  }`}
                >
                  <span className="font-mono text-ink-soft">
                    {vehicleLabel(track.vehicle_id)}
                  </span>
                  <span className="flex items-center gap-2 text-ink-faint">
                    {track.queue_seconds > 0 && (
                      <Pill tone="accent">queued {track.queue_seconds.toFixed(0)}s</Pill>
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

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-ink-faint">{label}</dt>
      <dd className="font-mono text-ink">{value}</dd>
    </div>
  );
}

