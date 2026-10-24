import { useReplay } from "../state/ReplayContext";
import { formatTimecode } from "../utils/format";

const RATES = [0.25, 0.5, 1, 2];

/**
 * One transport for the whole analysis page: the clock is shared, so the
 * annotated video, the trajectory map, the queue chart and the event timeline
 * always agree on "now".
 */
export function ReplayTransport() {
  const { time, duration, playing, rate, toggle, seek, setRate, step, replayOnly, loading, queueAt } =
    useReplay();

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-rule bg-surface px-4 py-2.5">
      <div className="flex items-center gap-1" role="group" aria-label="Replay transport">
        <button
          onClick={toggle}
          disabled={!duration}
          aria-label={playing ? "Pause replay" : "Play replay"}
          className="rounded border border-ink bg-ink px-3 py-1 text-[12px] text-paper disabled:opacity-40"
        >
          {playing ? "Pause" : "Play"}
        </button>
        <button
          onClick={() => step(-1)}
          disabled={!duration}
          title="Back one second"
          aria-label="Step back one second"
        >
          −1s
        </button>
        <button
          onClick={() => step(1)}
          disabled={!duration}
          title="Forward one second"
          aria-label="Step forward one second"
        >
          +1s
        </button>
      </div>

      <div
        className="flex min-w-[220px] flex-1 items-center gap-3"
        role="group"
        aria-label="Replay position"
      >
        <input
          type="range"
          min={0}
          max={Math.max(duration, 0.1)}
          step={0.05}
          value={Math.min(time, duration)}
          disabled={!duration}
          onChange={(event) => seek(Number(event.target.value))}
          aria-label="Replay position"
          className="h-1 flex-1 cursor-pointer appearance-none rounded bg-rule-soft accent-[#1d4ed8] disabled:opacity-40"
        />
        <span className="w-[104px] shrink-0 font-mono text-[12px] text-ink-soft">
          {formatTimecode(time)} / {formatTimecode(duration)}
        </span>
      </div>

      <div className="flex items-center gap-1" role="group" aria-label="Playback rate">
        {RATES.map((value) => (
          <button
            key={value}
            onClick={() => setRate(value)}
            disabled={!duration}
            aria-pressed={rate === value}
            className={`rounded border px-2 py-0.5 font-mono text-[11px] disabled:opacity-40 ${
              rate === value
                ? "border-ink bg-ink text-paper"
                : "border-rule text-ink-faint hover:border-ink-faint"
            }`}
          >
            {value}×
          </button>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-3">
        {queueAt !== null && (
          <span className="font-mono text-[12px] text-ink-soft">
            queue now: <span className="text-ink">{queueAt}</span>
          </span>
        )}
        {replayOnly && (
          <span
            className="rounded border border-caution/40 bg-caution-soft px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-caution"
            title="The demo dataset has no source video. Positions come from the stored trajectories."
          >
            trajectory replay
          </span>
        )}
        {loading && <span className="text-[11px] text-ink-faint">loading replay…</span>}
      </div>
    </div>
  );
}
