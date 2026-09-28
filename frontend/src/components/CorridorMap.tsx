import type { SimulationResult } from "../types";
import { Label, Panel } from "./Primitives";

const WIDTH = 960;
const HEIGHT = 300;
const MARGIN = { top: 26, right: 24, bottom: 34, left: 44 };

/**
 * Side view of the simulated corridor: position along the lane is the
 * horizontal axis, time runs from left (entry) to right (exit).  Each line is
 * one vehicle; the drop at the right end is the moment it was processed.
 */
export function CorridorMap({ result }: { result: SimulationResult }) {
  const tracks = result.tracks.filter((track) => track.points.length > 1);
  const totalTime = Math.max(
    ...tracks.map((track) => track.points[track.points.length - 1][0]),
    result.simulated.observation_seconds,
  );
  const scaleX = (position: number) =>
    MARGIN.left + position * (WIDTH - MARGIN.left - MARGIN.right);
  const scaleT = (time: number) =>
    MARGIN.top + (time / Math.max(totalTime, 1)) * (HEIGHT - MARGIN.top - MARGIN.bottom);

  return (
    <Panel className="px-3 pb-3 pt-4">
      <div className="px-1">
        <Label>Simulated corridor — vehicle tracks over time</Label>
        <p className="mt-1 text-[12px] text-ink-faint">
          {result.tracks.length} of {result.simulated.vehicles} vehicles shown
          (every nth vehicle, to keep the drawing readable).
        </p>
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="mt-2 block w-full"
        role="img"
        aria-label="Simulated vehicle tracks over time"
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
              {fraction === 0 ? "entry" : fraction === 1 ? "gate" : fraction.toFixed(2)}
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
            {Math.round(fraction * totalTime)}s
          </text>
        ))}

        {tracks.map((track, index) => {
          const path = track.points
            .map(
              ([time, position], pointIndex) =>
                `${pointIndex === 0 ? "M" : "L"}${scaleX(position).toFixed(1)},${scaleT(time).toFixed(1)}`,
            )
            .join(" ");
          const waited = (track.wait ?? 0) > 0;
          return (
            <g key={track.vehicle_id}>
              <path
                d={path}
                fill="none"
                stroke={waited ? "#b45309" : "#1d4ed8"}
                strokeOpacity={0.5 + (index % 5) * 0.08}
                strokeWidth={1.5}
                strokeLinecap="round"
              />
              <title>
                {`Vehicle ${track.vehicle_id}: arrived ${track.arrival}s, wait ${
                  track.wait?.toFixed(1) ?? "n/a"
                }s, departed ${track.departure?.toFixed(1) ?? "still queued"}s`}
              </title>
            </g>
          );
        })}

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
          <span className="h-[2px] w-4 bg-[#1d4ed8]" /> drove without stopping
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-[2px] w-4 bg-[#b45309]" /> waited in the queue
        </span>
      </div>
    </Panel>
  );
}
