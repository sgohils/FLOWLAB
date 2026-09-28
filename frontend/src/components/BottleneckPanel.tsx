import type { Bottleneck, HeatCell } from "../types";
import { formatNumber } from "../utils/format";
import { Label, Panel } from "./Primitives";

export function BottleneckPanel({
  bottlenecks,
  heat,
  selectedId,
  onSelect,
}: {
  bottlenecks: Bottleneck[];
  heat: HeatCell[];
  selectedId?: number | null;
  onSelect?: (id: number | null) => void;
}) {
  if (bottlenecks.length === 0) {
    return (
      <Panel className="p-6 text-[13px] leading-relaxed text-ink-soft">
        No bottleneck cell met the reporting threshold. A cell is only reported
        when at least two different vehicles were measurably slowed there, so a
        single stopped vehicle is not reported as congestion.
      </Panel>
    );
  }
  const worst = Math.max(...heat.map((cell) => cell.value), 0.0001);
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {bottlenecks.map((bottleneck) => {
          const selected = selectedId === bottleneck.id;
          const Wrapper = onSelect ? "button" : "div";
          return (
            <Wrapper
              key={bottleneck.id}
              onClick={onSelect ? () => onSelect(selected ? null : bottleneck.id) : undefined}
              aria-pressed={onSelect ? selected : undefined}
              className={`p-4 text-left ${onSelect ? "transition-colors hover:border-ink" : ""} ${
                selected ? "border-ink bg-accent-soft/40" : "border-rule"
              }`}
            >
              <div className="flex items-baseline justify-between">
                <Label>Rank {bottleneck.id} of {bottlenecks.length}</Label>
                <span
                  className="font-mono text-[11px] text-ink-faint"
                  title="Relative ranking of this cell against the other cells. It is not a measured severity or a congestion grade."
                >
                  index {bottleneck.score.toFixed(2)}
                </span>
              </div>
              <dl className="mt-3 space-y-1.5 text-[13px]">
                <Row label="Where" value={`x ${bottleneck.x.toFixed(2)} · y ${bottleneck.y.toFixed(2)}`} />
                <Row label="Distinct vehicles slowed" value={String(bottleneck.vehicle_passes)} />
                <Row label="Time below threshold" value={`${formatNumber(bottleneck.stopped_seconds)} s`} />
                <Row
                  label="Mean per vehicle"
                  value={`${formatNumber(bottleneck.mean_slowdown_seconds)} s`}
                />
                <Row label="Time in region" value={`${formatNumber(bottleneck.occupancy_seconds)} s`} />
              </dl>
              {onSelect && (
                <p className="mt-2 text-[11px] text-ink-faint">
                  {selected
                    ? "Highlighting the vehicles measured as slowed here."
                    : "Select to highlight the contributing vehicles."}
                </p>
              )}
            </Wrapper>
          );
        })}
      </div>

      <Panel className="p-4">
        <Label>Slow-down density (whole scene)</Label>
        <div className="mt-3 grid grid-cols-8 gap-1" style={{ gridAutoRows: "1fr" }}>
          {heat.map((cell, index) => (
            <div
              key={index}
              title={`index ${cell.value.toFixed(2)} · ${cell.vehicle_passes} distinct vehicles`}
              className="aspect-[4/3] rounded-[2px] border border-rule-soft"
              style={{
                backgroundColor: `rgba(180, 83, 9, ${(cell.value / worst) * 0.75})`,
              }}
            />
          ))}
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">
          Each cell of the 8×6 grid accumulates five observable quantities: time below
          the speed threshold, duration of registered stops, time inside the queue
          region, distinct vehicles, and trajectory samples. The index is a fixed
          weighting of those, min–max normalised across the scene. It ranks areas
          relative to each other — it is not a measured severity and not a congestion
          grade. A cell is listed above only when at least two different vehicles were
          slowed there.
        </p>
      </Panel>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-ink-faint">{label}</dt>
      <dd className="font-mono text-ink">{value}</dd>
    </div>
  );
}
