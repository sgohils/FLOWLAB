import type { TrafficEvent } from "../types";
import { useReplay } from "../state/ReplayContext";
import { formatTimecode } from "../utils/format";
import { Panel } from "./Primitives";

export function EventTimeline({ events }: { events: TrafficEvent[] }) {
  const { seek, time } = useReplay();
  if (events.length === 0) {
    return (
      <Panel className="p-6 text-[13px] text-ink-soft">
        No threshold events were triggered in this clip.
      </Panel>
    );
  }
  return (
    <Panel className="divide-y divide-rule-soft" role="group" aria-label="Threshold events">
      {events.map((event, index) => {
        const near = Math.abs(event.time - time) < 0.6;
        return (
          <button
            key={`${event.kind}-${event.time}-${index}`}
            onClick={() => seek(event.time)}
            title={`Jump the replay to ${formatTimecode(event.time)}`}
            aria-label={`Jump the replay to ${formatTimecode(event.time)}: ${event.label}`}
            aria-current={near ? "true" : undefined}
            className={`flex w-full items-start gap-4 px-4 py-2.5 text-left transition-colors hover:bg-paper ${
              near ? "bg-accent-soft" : ""
            }`}
          >
            <span className="w-12 shrink-0 font-mono text-[12px] text-ink-faint">
              {formatTimecode(event.time)}
            </span>
            <span
              aria-hidden="true"
              className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                event.kind === "peak"
                  ? "bg-ink"
                  : event.kind === "throughput_dip"
                    ? "bg-caution"
                    : "bg-rule"
              }`}
            />
            <span className="text-[13px] leading-snug text-ink-soft">{event.label}</span>
            <span className="ml-auto shrink-0 text-[10px] uppercase tracking-[0.12em] text-ink-faint">
              seek
            </span>
          </button>
        );
      })}
    </Panel>
  );
}
