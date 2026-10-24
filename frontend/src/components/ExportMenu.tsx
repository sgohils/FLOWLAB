import { useEffect, useId, useRef, useState } from "react";
import { api } from "../api/client";
import { Label } from "./Primitives";

interface ExportMenuProps {
  analysisId: string;
  hasVideo: boolean;
}

/**
 * Exports are measurements only - no video, no filename, no local paths.
 * The menu says so once, next to the buttons, because a CSV that leaves the
 * machine should never be a surprise.
 */
export function ExportMenu({ analysisId, hasVideo }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const firstItem = useRef<HTMLAnchorElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    // Opening moves focus into the menu; Escape gives it back to the trigger,
    // so a keyboard user never ends up with focus on a removed element.
    firstItem.current?.focus();
    const onClick = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };

  const items = [
    { label: "Summary (JSON)", href: api.exportUrl.summary(analysisId), note: "metadata" },
    { label: "Per-vehicle (CSV)", href: api.exportUrl.vehicles(analysisId), note: "metadata" },
    { label: "Queue series (CSV)", href: api.exportUrl.queue(analysisId), note: "metadata" },
    { label: "Events & bottlenecks (CSV)", href: api.exportUrl.events(analysisId), note: "metadata" },
    {
      label: "Headline numbers (JSON)",
      href: api.exportUrl.measurements(analysisId),
      note: "metadata",
    },
    {
      label: "Trajectory samples (JSON)",
      href: api.exportUrl.summary(analysisId, true),
      note: "large",
    },
  ];

  return (
    <div className="relative" ref={container}>
      <button
        ref={trigger}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={panelId}
        className="rounded border border-rule bg-surface px-3 py-1.5 text-[12px] text-ink-soft hover:border-ink-faint"
      >
        Export ▾
      </button>
      {open && (
        <div
          id={panelId}
          className="absolute right-0 z-40 mt-1 w-72 rounded-md border border-rule bg-surface p-3 shadow-sm"
        >
          <Label>Export measurements</Label>
          <ul className="mt-2 space-y-1">
            {items.map((item, index) => (
              <li key={item.label}>
                <a
                  ref={index === 0 ? firstItem : undefined}
                  href={item.href}
                  onClick={close}
                  className="flex items-center justify-between rounded px-2 py-1.5 text-[12px] text-ink hover:bg-paper"
                >
                  <span>{item.label}</span>
                  <span className="text-[10px] uppercase tracking-[0.1em] text-ink-faint">
                    {item.note}
                  </span>
                </a>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-rule-soft pt-2 text-[10px] leading-relaxed text-ink-faint">
            Exports contain measurements only: no video, no frames, no filename and
            no local file paths.
            {hasVideo ? " Delete the analysis to remove the footage itself." : ""}
          </p>
        </div>
      )}
    </div>
  );
}
