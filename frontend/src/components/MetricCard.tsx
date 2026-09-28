import { useState } from "react";

export interface MetricEvidence {
  /** The formula, in plain language. */
  formula: string;
  /** Label/value pairs that reconcile with the reported number. */
  rows: [string, string][];
  /** What this number does *not* mean. */
  note: string;
}

interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
  caption?: string;
  approximate?: boolean;
  emphasis?: boolean;
  /**
   * Evidence for this value, built by the parent and memoised.  When present
   * the card offers a "why?" control - progressive disclosure, so the
   * dashboard stays readable and the evidence is one interaction away.
   */
  evidence?: MetricEvidence;
}

export function MetricCard({
  label,
  value,
  unit,
  caption,
  approximate = false,
  emphasis = false,
  evidence,
}: MetricCardProps) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className={`flex flex-col rounded-md border bg-surface ${
        emphasis ? "border-ink" : "border-rule"
      }`}
    >
      <div className="flex flex-1 flex-col justify-between px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <span className="text-[10px] font-medium uppercase tracking-[0.16em] text-ink-faint">
            {label}
          </span>
          <div className="flex items-center gap-1.5">
            {approximate && (
              <span
                className="text-[9px] uppercase tracking-[0.12em] text-ink-faint"
                title="Derived from sampled frames, not a calibrated sensor."
              >
                approx.
              </span>
            )}
            {evidence && (
              <button
                onClick={() => setOpen((current) => !current)}
                aria-expanded={open}
                title="Why this number?"
                className="rounded border border-rule px-1 text-[10px] leading-[14px] text-ink-faint transition-colors hover:border-ink hover:text-ink"
              >
                why?
              </button>
            )}
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="font-mono text-[28px] leading-none tracking-tight text-ink">
            {value}
          </span>
          {unit && <span className="text-[12px] text-ink-faint">{unit}</span>}
        </div>
        {caption && <p className="mt-2 text-[11px] leading-snug text-ink-faint">{caption}</p>}
      </div>

      {open && evidence && (
        <div className="border-t border-rule-soft px-4 py-3">
          <p className="font-mono text-[11px] leading-relaxed text-ink-soft">
            {evidence.formula}
          </p>
          <dl className="mt-2 space-y-1">
            {evidence.rows.map(([key, item]) => (
              <div key={key} className="flex items-baseline justify-between gap-3">
                <dt className="text-[11px] text-ink-faint">{key}</dt>
                <dd className="font-mono text-[11px] text-ink">{item}</dd>
              </div>
            ))}
          </dl>
          {evidence.note && (
            <p className="mt-2 text-[11px] leading-relaxed text-ink-faint">{evidence.note}</p>
          )}
        </div>
      )}
    </div>
  );
}
