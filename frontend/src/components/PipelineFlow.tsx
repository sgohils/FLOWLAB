const STEPS = [
  {
    key: "video",
    label: "Video",
    detail: "MP4 from a fixed camera",
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <rect x="2.5" y="5" width="14" height="14" rx="1.5" />
        <path d="M16.5 10.5l5-3v9l-5-3z" />
      </svg>
    ),
  },
  {
    key: "trajectories",
    label: "Trajectories",
    detail: "Anonymous vehicle ids",
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <path d="M3 18c4 0 5-12 9-12 3 0 4 6 9 6" />
        <circle cx="3" cy="18" r="1.6" />
        <circle cx="21" cy="12" r="1.6" />
      </svg>
    ),
  },
  {
    key: "measurements",
    label: "Measurements",
    detail: "Queues, waits, throughput",
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <path d="M3 20h18" />
        <path d="M5 20V12M10 20V7M15 20v-6M20 20V4" />
      </svg>
    ),
  },
  {
    key: "simulation",
    label: "Simulation",
    detail: "Change one thing, compare",
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <path d="M4 18c5-1 7-9 12-9" />
        <path d="M4 12c5-1 7-9 12-9" strokeDasharray="3 3" />
      </svg>
    ),
  },
];

export function PipelineFlow() {
  return (
    <div className="rounded-md border border-rule bg-surface">
      <div className="grid grid-cols-2 divide-rule md:grid-cols-4 md:divide-x">
        {STEPS.map((step, index) => (
          <div key={step.key} className="relative px-5 py-6">
            <div className="flex items-center gap-2.5 text-ink">
              {step.icon}
              <span className="text-[13px] font-medium">{step.label}</span>
            </div>
            <p className="mt-2 text-[12px] leading-snug text-ink-faint">{step.detail}</p>
            <span className="absolute right-4 top-5 font-mono text-[11px] text-ink-faint">
              0{index + 1}
            </span>
            {index < STEPS.length - 1 && (
              <span
                className="absolute -right-[7px] top-1/2 z-10 hidden -translate-y-1/2 text-ink-faint md:block"
                aria-hidden
              >
                →
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
