import { useMemo } from "react";
import type { SimulationResult } from "../types";
import {
  formatFixed,
  formatNumber,
  formatWithUnit,
} from "../utils/format";
import { Label, Panel } from "./Primitives";

const WIDTH = 960;
const HEIGHT = 300;
const MARGIN = { top: 26, right: 24, bottom: 34, left: 44 };
/** Above this many tracks the drawing turns into a solid block, so thin it. */
const MAX_TRACKS = 120;

/**
 * Side view of the simulated corridor: position along the lane is the
 * horizontal axis, time runs from left (entry) to right (exit).  Each line is
 * one vehicle; the drop at the right end is the moment it was processed.
 */
export function CorridorMap({ result }: { result: SimulationResult }) {
  // Every path and the axis scaling are rebuilt only when the result changes,
  // not on each render of the surrounding page.
  const { totalTime, step, paths } = useMemo(() => {
    const eligible = result.tracks.filter((track) => track.points.length > 1);
    const stride = Math.max(1, Math.ceil(eligible.length / MAX_TRACKS));
    const drawn = eligible.filter((_, index) => index % stride === 0);
    const span = Math.max(
      ...drawn.map((track) => track.points[track.points.length - 1][0]),
      result.simulated.observation_seconds,
    );
    const safeSpan = Math.max(span, 1);
    const toX = (position: number) =>
      MARGIN.left + position * (WIDTH - MARGIN.left - MARGIN.right);
    const toY = (time: number) =>
      MARGIN.top + (time / safeSpan) * (HEIGHT - MARGIN.top - MARGIN.bottom);
    return {
      totalTime: span,
      step: stride,
      paths: drawn.map((track) => ({
        vehicleId: track.vehicle_id,
        waited: (track.wait ?? 0) > 0,
        d: track.points
          .map(
            ([time, position], index) =>
              `${index === 0 ? "M" : "L"}${toX(position).toFixed(1)},${toY(time).toFixed(1)}`,
          )
          .join(" "),
      })),
    };
  }, [result]);

  const scaleX = (position: number) =>
    MARGIN.left + position * (WIDTH - MARGIN.left - MARGIN.right);
  const scaleT = (time: number) =>
    MARGIN.top + (time / Math.max(totalTime, 1)) * (HEIGHT - MARGIN.top - MARGIN.bottom);

  return (
    <Panel className="px-3 pb-3 pt-4">
      <div className="px-1">
        <Label>Simulated corridor — vehicle tracks over time</Label>
        <p className="mt-1 text-[12px] text-ink-faint">
          {formatNumber(paths.length, 0)} of{" "}
          {formatNumber(result.simulated.vehicles, 0)} vehicles drawn
          {step > 1
            ? ` — every ${formatNumber(step, 0)}th track, to keep the drawing readable.`
            : "."}
        </p>
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="mt-2 block w-full"
        role="img"
        aria-label="Simulated vehicle tracks over time: position along the lane against time"
      >
        <rect
          x={MARGIN.left}
          y={MARGIN.top}
          width={WIDTH - MARGIN.left - MARGIN.right}
          height={HEIGHT - MARGIN.top - MARGIN.bottom}
          fill="#fbfbf9"
          stroke="#e9e9e4"
        />
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
          <g key={fraction}>
            <line
              x1={scaleX(fraction)}
              y1={MARGIN.top}
              x2={scaleX(fraction)}
              y2={HEIGHT - MARGIN.bottom}
              stroke="#f0f0ec"
            />
            <text
              x={scaleX(fraction)}
              y={HEIGHT - MARGIN.bottom + 14}
              fontSize={10}
              textAnchor="middle"
              fill="#7b8189"
              fontFamily="ui-monospace, monospace"
            >
              {fraction === 0 ? "entry" : fraction === 1 ? "gate" : formatFixed(fraction, 2)}
            </text>
          </g>
        ))}
        {[0, 0.5, 1].map((fraction) => (
          <text
            key={fraction}
            x={MARGIN.left - 8}
            y={scaleT(fraction * totalTime) + 3}
            fontSize={10}
            textAnchor="end"
            fill="#7b8189"
            fontFamily="ui-monospace, monospace"
          >
            {formatWithUnit(fraction * totalTime, "s", 0)}
          </text>
        ))}

        {paths.map((path, index) => (
          <g key={path.vehicleId}>
            <path
              d={path.d}
              fill="none"
              stroke={path.waited ? "#b45309" : "#1d4ed8"}
              strokeOpacity={0.5 + (index % 5) * 0.08}
              strokeWidth={1.5}
              strokeLinecap="round"
            />
            <title>
              {`Vehicle ${path.vehicleId}: ${
                path.waited ? "waited in the queue" : "drove without stopping"
              }`}
            </title>
          </g>
        ))}

        <line
          x1={scaleX(1)}
          y1={MARGIN.top}
          x2={scaleX(1)}
          y2={HEIGHT - MARGIN.bottom}
          stroke="#14161a"
          strokeDasharray="4 3"
        />
      </svg>
      <div className="flex items-center gap-4 px-1 text-[11px] text-ink-faint">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-[2px] w-4 bg-[#1d4ed8]" /> drove without stopping
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-[2px] w-4 bg-[#b45309]" /> waited in the queue
        </span>
      </div>
    </Panel>
  );
}
