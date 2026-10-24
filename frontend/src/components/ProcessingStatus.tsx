import type { JobStatus, Meta } from "../types";
import { formatNumber } from "../utils/format";
import { Panel } from "./Primitives";

const STAGE_KEYS: { key: string; label: string }[] = [
  { key: "queued", label: "Queued" },
  { key: "reading_video", label: "Reading video" },
  { key: "detecting", label: "Detecting vehicles" },
  { key: "tracking", label: "Tracking vehicles" },
  { key: "trajectories", label: "Calculating trajectories" },
  { key: "queues", label: "Analyzing queues" },
  { key: "bottlenecks", label: "Finding bottlenecks" },
  { key: "results", label: "Generating results" },
];

export function ProcessingStatus({
  job,
  meta,
  filename,
}: {
  job: JobStatus | null;
  meta: Meta | null;
  filename?: string;
}) {
  const stageByKey = new Map((job?.stages ?? []).map((stage) => [stage.key, stage]));
  const stages = meta?.stages ?? STAGE_KEYS;
  const progress = Math.round((job?.progress ?? 0) * 100);
  const current = stageByKey.get(job?.stage ?? "queued");
  const activeStage = stages.find((stage) => stageByKey.get(stage.key)?.status === "active");
  const failed = job?.status === "error";
  // One concise sentence per state change, rather than the whole panel: the
  // list is polled about once a second and would otherwise be read out in full.
  const announcement = failed
    ? `Processing stopped: ${job?.error ?? "unknown error"}`
    : job
      ? `${activeStage?.label ?? "Queued"}, ${progress} percent complete`
      : "Waiting for the worker";

  return (
    <Panel className="p-6">
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>
      <div className="mb-1 flex items-baseline justify-between gap-4">
        <h2 className="text-[15px] font-medium text-ink">
          {job?.status === "error" ? "Processing stopped" : "Processing video"}
        </h2>
        <span className="font-mono text-[13px] text-ink-soft">{formatNumber(progress, 0)}%</span>
      </div>
      {filename && (
        <p className="mb-4 truncate font-mono text-[11px] text-ink-faint">{filename}</p>
      )}

      <div
        className="h-1 w-full overflow-hidden rounded bg-rule-soft"
        role="progressbar"
        aria-label="Processing progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        aria-valuetext={`${progress} percent, ${
          failed ? "stopped" : (activeStage?.label ?? "queued")
        }`}
      >
        <div
          className={`h-full transition-[width] duration-300 ${
            failed ? "bg-red-500" : "bg-accent"
          }`}
          style={{ width: `${Math.max(2, progress)}%` }}
        />
      </div>

      <ol className="mt-5 space-y-1.5">
        {stages.map((stage, index) => {
          const state = stageByKey.get(stage.key);
          const status = state?.status ?? (index === 0 ? "pending" : "pending");
          const isActive = status === "active";
          return (
            <li key={stage.key} className="flex items-center gap-3 text-[13px]">
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                  status === "done"
                    ? "bg-positive"
                    : status === "error"
                      ? "bg-red-500"
                      : isActive
                        ? "animate-pulse-soft bg-accent"
                        : "bg-rule"
                }`}
              />
              <span
                className={
                  isActive
                    ? "text-ink"
                    : status === "done"
                      ? "text-ink-soft"
                      : "text-ink-faint"
                }
              >
                {stage.label}
              </span>
              {isActive && state?.detail && (
                <span className="truncate font-mono text-[11px] text-ink-faint">
                  {state.detail}
                </span>
              )}
            </li>
          );
        })}
      </ol>

      {job?.status === "error" && (
        <div className="mt-5 rounded border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-800">
          <p className="font-medium">{job.error}</p>
          {job.hint && <p className="mt-1 opacity-85">{job.hint}</p>}
        </div>
      )}

      {!job && (
        <p className="mt-5 text-[12px] text-ink-faint">
          {current?.detail ?? "Waiting for the worker…"}
        </p>
      )}
    </Panel>
  );
}
