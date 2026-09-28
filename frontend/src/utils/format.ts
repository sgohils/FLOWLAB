/** Small formatting helpers shared by the metric cards, charts and tables. */

export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(digits);
}

export function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value < 60) return `${value.toFixed(1)} s`;
  const minutes = Math.floor(value / 60);
  return `${minutes}m ${(value - minutes * 60).toFixed(0)}s`;
}

export function formatTimecode(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "--:--";
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatClassName(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export function vehicleLabel(id: number): string {
  return `Vehicle ${String(id).padStart(3, "0")}`;
}

export function deltaTone(
  delta: number,
  lowerIsBetter: boolean,
): "good" | "bad" | "flat" {
  if (Math.abs(delta) < 0.01) return "flat";
  const improved = lowerIsBetter ? delta < 0 : delta > 0;
  return improved ? "good" : "bad";
}
