import { Label, Notice, Panel, Row } from "./Primitives";
import type { Analysis } from "../types";
import { formatNumber, formatPercent, formatSeconds } from "../utils/format";

/**
 * Everything a reader needs before trusting the numbers, in one place.
 *
 * Deliberately a list of counts, not a score: there is no confidence figure
 * because none has been computed. When the evidence is thin - too few
 * vehicles, or too many missing samples - it says so instead of letting the
 * numbers look authoritative.
 */
export function EvidencePanel({ analysis }: { analysis: Analysis }) {
  const evidence = analysis.evidence;
  // Same rule as the backend, restated here so the threshold is visible in one
  // place: too few vehicles, or too many missing samples, is not enough to
  // lean on.
  const thin = evidence.tracks < 5 || evidence.missing_sample_share > 0.15;

  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Label>Evidence and assumptions</Label>
        <span className="font-mono text-[11px] text-ink-faint">
          window {formatNumber(evidence.observation_seconds)}s · sampled at{" "}
          {formatNumber(evidence.sampling_fps)} fps
        </span>
      </div>

      {evidence.tracks === 0 ? (
        <p className="mt-3 text-[12px] leading-relaxed text-ink-soft">
          This result was stored before the evidence block existed, so only the
          summary above is available. Re-run the analysis to populate it.
        </p>
      ) : (
        <>
          {thin && (
            <div className="mt-3">
              <Notice tone="caution" title="Thin evidence">
                {evidence.tracks < 5
                  ? `Only ${evidence.tracks} vehicle(s) were tracked, which is too few to compare scenarios meaningfully.`
                  : `${formatNumber(evidence.missing_sample_share * 100, 0)}% of the expected tracking samples are missing, so the trajectories are incomplete.`}{" "}
                Treat the numbers as indicative, not as a measurement to act on.
              </Notice>
            </div>
          )}

          <dl className="mt-4 grid gap-x-8 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
            <Row dense label="Vehicles detected" value={formatNumber(evidence.vehicles_detected, 0)} />
            <Row dense label="Vehicles tracked" value={formatNumber(evidence.vehicles_tracked, 0)} />
            <Row dense label="Crossed the entry line"
              value={formatNumber(evidence.vehicles_crossed_entry, 0)}
            />
            <Row dense label="Crossed the exit line"
              value={formatNumber(evidence.vehicles_crossed_exit, 0)}
            />
            <Row dense label="Queue visits (complete)"
              value={formatNumber(evidence.completed_queue_visits, 0)}
            />
            <Row dense label="Queue visits (censored)"
              value={`${formatNumber(evidence.censored_queue_visits, 0)} · ${formatSeconds(evidence.censored_seconds)}`}
            />
            <Row dense label="Registered stops" value={formatNumber(evidence.registered_stops, 0)} />
            <Row dense label="Time below threshold"
              value={formatSeconds(evidence.slow_seconds_total)}
            />
            <Row dense label="Tracking gaps" value={formatNumber(evidence.gaps, 0)} />
            <Row dense label="Missing samples"
              value={formatPercent(evidence.missing_sample_share, 1)}
            />
            <Row dense label="Short fragments dropped"
              value={formatNumber(evidence.short_fragments, 0)}
            />
            <Row dense label="Observation window"
              value={formatSeconds(evidence.observation_seconds)}
            />
          </dl>

          <p className="mt-4 text-[11px] leading-relaxed text-ink-faint">
            A <b>queue visit</b> is a continuous stay inside the queue region while
            moving below the speed threshold. A visit is <i>complete</i> only if the
            vehicle was seen entering and leaving it; one that starts on the first
            frame or ends on the last is <i>censored</i>, because its true duration is
            unknown — those are excluded from the wait averages and listed here. A{" "}
            <b>tracking gap</b> is a break longer than 2.5 sampling intervals: no
            position is assumed across it, and the replay hides the vehicle there.
          </p>
        </>
      )}
    </Panel>
  );
}
