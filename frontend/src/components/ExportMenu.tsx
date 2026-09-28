import { useEffect, useRef, useState } from "react";
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

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const items = [
    { label: "Summary (JSON)", href: api.exportUrl.summary(analysisId), note: "metadata" },
    { label: "Per-vehicle (CSV)", href: api.exportUrl.vehicles(analysisId), note: "metadata" },
    { label: "Queue series (CSV)", href: api.exportUrl.queue(analysisId), note: "metadata" },
    { label: "Events & bottlenecks (CSV)", href: api.exportUrl.events(analysisId), note: "metadata" },
    {
      label: "Trajectory samples (JSON)",
      href: api.exportUrl.summary(analysisId, true),
      note: "large",
    },
  ];

  return (
    <div className="relative" ref={container}>
      <button
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded border border-rule bg-surface px-3 py-1.5 text-[12px] text-ink-soft hover:border-ink-faint"
      >
        Export ▾
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-1 w-72 rounded-md border border-rule bg-surface p-3 shadow-sm"
        >
          <Label>Export measurements</Label>
          <ul className="mt-2 space-y-1">
            {items.map((item) => (
              <li key={item.label}>
                <a
                  role="menuitem"
                  href={item.href}
                  onClick={() => setOpen(false)}
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
