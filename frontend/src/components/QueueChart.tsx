import { useCallback, useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { QueueSample, TrafficEvent } from "../types";
import { useReplay } from "../state/ReplayContext";
import { formatTimecode } from "../utils/format";
import { Panel } from "./Primitives";

interface QueueChartProps {
  data: QueueSample[];
  events?: TrafficEvent[];
  height?: number;
  color?: string;
  label?: string;
  showEvents?: boolean;
  /** Read the shared replay clock, and let a click move it. */
  interactive?: boolean;
}


/**
 * The highest sample in the series, or null when there is no series.
 *
 * The scan is seeded with the first real sample rather than a zero
 * placeholder. With a placeholder, a series that is flat at zero reports the
 * peak as t = 0 - which is off the front of the clip - the day anything reads
 * `peak.time`. Only `peak.queue` is read today, so the two agree; seeding
 * correctly makes them agree for the right reason.
 */
export function peakSample(data: QueueSample[]): QueueSample | null {
  if (data.length === 0) return null;
  return data.reduce(
    (best, sample) => (sample.queue > best.queue ? sample : best),
    data[0],
  );
}

export function QueueChart({
  data,
  events = [],
  height = 220,
  color = "#1d4ed8",
  label = "Queue length",
  showEvents = true,
  interactive = false,
}: QueueChartProps) {
  // Subscribed here rather than passed down: the cursor should re-render only
  // this chart, not the whole page, once per frame.
  const { time, seek } = useReplay();
  const cursorTime = interactive ? time : undefined;

  // This chart re-renders on every animation frame while the clip plays, so
  // everything that does not depend on `time` is computed once.
  const lastTime = useMemo(
    () => (data.length > 0 ? data[data.length - 1].time : 0),
    [data],
  );
  const peak = useMemo(() => peakSample(data), [data]);
  const peakMarks = useMemo(
    () =>
      showEvents
        ? events
            .filter((event) => event.kind === "peak")
            .map((event) => ({ key: `${event.kind}-${event.time}`, time: event.time }))
        : [],
    [events, showEvents],
  );
  const handleChartClick = useCallback(
    (state: { activeLabel?: string | number; activePayload?: unknown }) => {
      if (!interactive) return;
      const moment = Number(
        state.activeLabel ?? (state.activePayload as { time?: number })?.time,
      );
      if (Number.isFinite(moment)) seek(moment);
    },
    [interactive, seek],
  );

  if (data.length === 0) {
    return (
      <Panel className="flex items-center justify-center p-10 text-center text-[13px] text-ink-faint">
        No queue series: draw a queue region on the video to enable this chart.
      </Panel>
    );
  }
  return (
    <Panel className="px-2 pb-2 pt-3">
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart
          data={data}
          margin={{ top: 6, right: 14, left: -14, bottom: 0 }}
          onClick={interactive ? handleChartClick : undefined}
          style={{ cursor: interactive ? "crosshair" : undefined }}
        >
          <defs>
            <linearGradient id="queueFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.24} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="time"
            type="number"
            domain={[0, lastTime]}
            tickFormatter={formatTimecode}
            tickCount={7}
          />
          <YAxis allowDecimals={false} width={44} />
          <Tooltip
            labelFormatter={(value) => `t = ${formatTimecode(Number(value))}`}
            formatter={(value: number) => [value, "vehicles"]}
            contentStyle={{
              border: "1px solid #dcdcd6",
              borderRadius: 4,
              fontSize: 12,
              fontFamily: "ui-monospace, monospace",
            }}
          />
          {peakMarks.map((mark) => (
            <ReferenceLine
              key={mark.key}
              x={mark.time}
              stroke="#b45309"
              strokeDasharray="3 3"
            />
          ))}
          <Area
            type="monotone"
            dataKey="queue"
            name={label}
            stroke={color}
            strokeWidth={1.6}
            fill="url(#queueFill)"
            isAnimationActive={false}
          />
          {interactive && cursorTime !== undefined && cursorTime <= lastTime && (
            <ReferenceLine
              x={cursorTime}
              stroke="#14161a"
              strokeWidth={1.4}
              label={{
                value: `t ${formatTimecode(cursorTime)}`,
                position: "top",
                fontSize: 10,
                fill: "#14161a",
              }}
            />
          )}
          {peak && (
            <ReferenceLine
              y={peak.queue}
              stroke="#14161a"
              strokeDasharray="4 4"
              label={{
                value: `peak ${peak.queue}`,
                position: "insideStart",
                fontSize: 10,
                fill: "#14161a",
              }}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </Panel>
  );
}
