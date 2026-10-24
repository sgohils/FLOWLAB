import { useMemo, useState } from "react";
import { BottleneckPanel } from "../components/BottleneckPanel";
import { EventTimeline } from "../components/EventTimeline";
import { EvidencePanel } from "../components/EvidencePanel";
import { MetricCard } from "../components/MetricCard";
import { QueueChart } from "../components/QueueChart";
import { ReplayTransport } from "../components/ReplayTransport";
import { RegionEditor, staleNotice } from "../components/RegionEditor";
import { TrafficMap } from "../components/TrafficMap";
import { VideoViewer } from "../components/VideoViewer";
import type { DrawTool } from "../components/VideoViewer";
import { Button, Label, Panel, Row, Section } from "../components/Primitives";
import type { MetricEvidence } from "./MetricCard";
import type { Analysis, Regions } from "../types";
import { hasQueueRegion } from "../types";
import {
  formatNumber,
  formatSeconds,
  formatWithUnit,
  vehicleLabel,
} from "../utils/format";

interface AnalysisViewProps {
  analysis: Analysis;
  hasVideo: boolean;
  videoUrl: string;
  regions: Regions | null;
  tool: DrawTool;
  onToolChange: (tool: DrawTool) => void;
  onRegionsChange: (regions: Regions) => void;
  onCommitRegions: (regions: Regions) => void;
  pending: number;
  saveError: string | null;
  onUploadAnother: () => void;
}

/**
 * Everything that reads the shared replay clock lives here, inside the
 * provider.  The video, the trajectory map, the queue chart and the event
 * timeline all read the same `time`, so they can never disagree.
 */
export function AnalysisView({
  analysis,
  hasVideo,
  videoUrl,
  regions,
  tool,
  onToolChange,
  onRegionsChange,
  onCommitRegions,
  pending,
  saveError,
  onUploadAnother,
}: AnalysisViewProps) {
  const summary = analysis.summary;
  const [showHeat, setShowHeat] = useState(true);
  const [showRegions, setShowRegions] = useState(true);
  const [bottleneckId, setBottleneckId] = useState<number | null>(null);
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | null>(null);

  // Selection lives here rather than in the replay context so the whole view is
  // not re-rendered once per frame while the clip plays.
  const bottleneckTracks = useMemo(() => {
    const cell = analysis.bottlenecks.find((item) => item.id === bottleneckId);
    return cell?.vehicle_ids ?? [];
  }, [analysis.bottlenecks, bottleneckId]);

  const evidence = useMemo(
    () => ({
      peak: whyPeakQueue(analysis),
      wait: whyWait(analysis),
      throughput: whyThroughput(analysis),
    }),
    [analysis],
  );

  // Reasons a measurement could not be made.  "Unavailable" is stated, never a
  // zero, and the control that could explain it is hidden rather than shown
  // empty.
  const reasons = useMemo(() => {
    const noTracks = summary.vehicles_tracked === 0;
    const noRegion = !hasQueueRegion(analysis.regions);
    return {
      peak: noTracks
        ? "No vehicles were detected, so no queue could be measured."
        : noRegion
          ? "No queue region is drawn, so the queue cannot be measured."
          : undefined,
      wait: noTracks
        ? "No vehicles were detected."
        : noRegion
          ? "No queue region is drawn."
          : summary.completed_queue_visits === 0
            ? `No completed visit: ${summary.censored_queue_visits} visit(s) were still open when the clip ended.`
            : undefined,
      throughput: noTracks
        ? "No vehicles were detected."
        : !analysis.regions.exit || analysis.regions.exit.length !== 2
          ? "No exit line is drawn, so departures cannot be counted."
          : undefined,
      region: noTracks
        ? "No vehicles were detected."
        : noRegion
          ? "No queue region is drawn."
          : undefined,
    };
  }, [summary, analysis.regions]);

  return (
    <>
      <div className="mb-6">
        <ReplayTransport />
      </div>

      <Section
        title="Measurements"
        subtitle={
          hasVideo
            ? "Counted directly from the anonymous trajectories. Open any card to see the evidence."
            : "Synthetic trajectories, measured with the same code as real footage."
        }
      >
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard
            label="Vehicles tracked"
            value={formatNumber(summary.vehicles_tracked, 0)}
            caption={`${formatNumber(summary.vehicles_detected, 0)} detected · ${formatNumber(
              summary.vehicles_processed,
              0,
            )} crossed the exit line`}
          />
          <MetricCard
            label="Peak queue"
            value={formatNumber(summary.peak_queue, 0)}
            unit="vehicles"
            approximate
            emphasis={(summary.peak_queue ?? 0) > 0}
            caption="most vehicles in the region and below the speed threshold at once"
            evidence={evidence.peak}
            unavailableReason={reasons.peak}
          />
          <MetricCard
            label="Average queue"
            value={formatNumber(summary.average_queue)}
            unit="vehicles"
            approximate
            caption="time-average over the whole clip"
            unavailableReason={reasons.peak}
          />
          <MetricCard
            label="Est. wait (mean)"
            value={formatNumber(summary.average_wait_seconds)}
            unit="s"
            approximate
            caption={`${formatNumber(summary.completed_queue_visits, 0)} completed visits · ${formatNumber(
              summary.censored_queue_visits,
              0,
            )} censored`}
            evidence={evidence.wait}
            unavailableReason={reasons.wait}
          />
          <MetricCard
            label="Est. wait (max)"
            value={formatNumber(summary.max_wait_seconds)}
            unit="s"
            approximate
            caption={`median ${formatNumber(summary.median_wait_seconds)}s of completed visits`}
            evidence={evidence.wait}
            unavailableReason={reasons.wait}
          />
          <MetricCard
            label="Throughput"
            value={formatNumber(summary.throughput_per_minute)}
            unit="veh/min"
            caption={
              summary.entry_per_minute
                ? `entry rate ${formatNumber(summary.entry_per_minute)}/min`
                : "no entry line defined"
            }
            evidence={evidence.throughput}
            unavailableReason={reasons.throughput}
          />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard
            label="Bottleneck cells"
            value={formatNumber(summary.bottleneck_count, 0)}
            caption="grid cells where several vehicles slowed"
          />
          <MetricCard
            label="Mean time in region"
            value={formatNumber(summary.average_region_seconds)}
            unit="s"
            approximate
            caption="inside the queue region, moving or not"
            unavailableReason={reasons.region}
          />
          <MetricCard
            label="Mean slow time"
            value={formatNumber(summary.mean_stopped_seconds)}
            unit="s"
            approximate
            caption="below the threshold anywhere in the scene"
            unavailableReason={reasons.region}
          />
          <MetricCard
            label="Time with a queue"
            value={formatSeconds(summary.queue_duration_seconds)}
            approximate
            caption="at least one vehicle queued"
          />
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">
          "Est. wait" counts time <i>inside the queue region while moving below the
          speed threshold</i>, for at least {analysis.regions.min_queue_seconds}s at a
          time. It is not a measured wait time, and it is not converted to seconds of
          real-world queueing: positions are image coordinates, not a calibrated
          scale. Visits that began before the clip or were still open at the end are
          excluded from the average and counted separately.
        </p>
      </Section>

      <Section
        title={hasVideo ? "Annotated video" : "Trajectory replay"}
        subtitle={
          hasVideo
            ? "Anonymous ids, boxes and a short trail. The clock is shared with the map and the chart below."
            : "The demo dataset has no source footage. Positions come from the stored trajectories, replayed at 4 samples per second."
        }
      >
        {hasVideo ? (
          <div className="space-y-3">
            {staleNotice(analysis, pending)}
            <VideoViewer
              src={videoUrl}
              regions={regions ?? analysis.regions}
              tool={tool}
              onChange={(next) => onCommitRegions(next)}
              editable
            />
            <RegionEditor
              regions={regions}
              tool={tool}
              onToolChange={onToolChange}
              onChange={onRegionsChange}
              onCommit={() => {
                if (regions) onCommitRegions(regions);
              }}
              saving={pending > 0}
              error={saveError}
              editable
            />
          </div>
        ) : (
          <Panel className="p-8 text-center">
            <p className="text-[13px] text-ink-soft">
              <b className="text-ink">Demo Dataset</b> — synthetic traffic, not footage
              from a real site. The replay above animates the stored trajectories so the
              measurements can be inspected; there is no video behind it.
            </p>
            <Button className="mt-4" onClick={onUploadAnother}>
              Analyse your own footage
            </Button>
          </Panel>
        )}
      </Section>

      <Section
        title="Trajectory map"
        subtitle="Image-coordinate plot of the video frame — not a plan view, and not a calibrated scale. Click a path to inspect one vehicle."
        actions={
          <div className="flex items-center gap-4 text-[12px] text-ink-soft">
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={showHeat}
                onChange={(event) => setShowHeat(event.target.checked)}
              />
              slow-down heat
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={showRegions}
                onChange={(event) => setShowRegions(event.target.checked)}
              />
              regions
            </label>
          </div>
        }
      >
        {bottleneckId !== null && (
          <div className="mb-3 flex items-center gap-3 rounded border border-caution/40 bg-caution-soft px-3 py-2 text-[12px] text-caution">
            <span>
              Highlighting {bottleneckTracks.length} vehicle
              {bottleneckTracks.length === 1 ? "" : "s"} measured as slowed in bottleneck
              cell {bottleneckId}.
            </span>
            <button
              onClick={() => setBottleneckId(null)}
              className="ml-auto underline underline-offset-2"
            >
              clear
            </button>
          </div>
        )}
        <TrafficMap
          analysis={analysis}
          selectedId={selectedVehicleId}
          onSelect={setSelectedVehicleId}
          showHeat={showHeat}
          showRegions={showRegions}
          showNow
          highlightIds={bottleneckTracks}
        />
      </Section>

      <Section
        title="Queue over time"
        subtitle="queued(t) = inside the queue region AND moving below the speed threshold. Click the chart to move the replay cursor; click an event below to jump to it."
      >
        <QueueChart
          data={analysis.queue_timeseries}
          events={analysis.events}
          height={240}
          interactive
        />
      </Section>

      <div className="grid gap-8 lg:grid-cols-2">
        <Section
          title="Detected bottlenecks"
          subtitle="Grid cells where several different vehicles slowed down. Select one to see its evidence."
        >
          <BottleneckPanel
            bottlenecks={analysis.bottlenecks}
            heat={analysis.heat_grid}
            selectedId={bottleneckId}
            onSelect={setBottleneckId}
          />
        </Section>
        <Section
          title="Event timeline"
          subtitle="Threshold rules applied to the measured series. Click an event to seek there."
        >
          <EventTimeline events={analysis.events} />
        </Section>
      </div>

      <Section
        title="How this analysis was measured"
        subtitle="Every assumption the numbers depend on."
      >
        <div className="space-y-4">
          <EvidencePanel analysis={analysis} />
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel className="p-5">
              <Label>Digital twin calibration</Label>
              <dl className="mt-3 space-y-1.5 text-[13px]">
                <Row
                  label="Arrival rate"
                  value={formatWithUnit(
                    analysis.calibration.arrival_rate_per_minute,
                    "/min",
                  )}
                />
                <Row
                  label="Mean arrival headway"
                  value={formatWithUnit(
                    analysis.calibration.mean_arrival_headway_seconds,
                    "s",
                  )}
                />
                <Row
                  label="Exit service time"
                  value={formatWithUnit(analysis.calibration.service_time_seconds, "s")}
                />
                <Row
                  label="Free-flow travel time"
                  value={formatWithUnit(analysis.calibration.free_flow_seconds, "s")}
                />
                <Row
                  label="Mean traversal"
                  value={formatWithUnit(analysis.calibration.mean_traversal_seconds, "s")}
                />
              </dl>
              <ul className="mt-3 space-y-1 text-[11px] leading-relaxed text-ink-faint">
                {analysis.calibration.notes.map((note) => (
                  <li key={note}>— {note}</li>
                ))}
              </ul>
            </Panel>
            <Panel className="p-5">
              <Label>Definitions used</Label>
              <ul className="mt-3 space-y-2 text-[12px] leading-relaxed text-ink-soft">
                <li>
                  <b className="text-ink">Queue length</b> = number of tracked vehicles
                  simultaneously inside the queue region and below the motion threshold,
                  held for at least {analysis.regions.min_queue_seconds}s (sampled at{" "}
                  {analysis.regions.sample_fps} fps).
                </li>
                <li>
                  <b className="text-ink">Estimated wait</b> = time inside the queue region
                  while slow, for visits that both started and ended inside the clip.
                  Censored visits are counted separately and excluded.
                </li>
                <li>
                  <b className="text-ink">Time in region</b> = time inside the queue region
                  whether or not the vehicle was moving.
                </li>
                <li>
                  <b className="text-ink">Throughput</b> = exit-line crossings divided by
                  the clip duration in minutes, counting each vehicle once.
                </li>
                <li>
                  <b className="text-ink">Stopped</b> = motion below{" "}
                  {analysis.regions.speed_threshold} frame-widths per second for at least{" "}
                  {analysis.regions.min_stop_seconds}s.
                </li>
              </ul>
            </Panel>
          </div>
        </div>
      </Section>
    </>
  );
}

/* ------------------------------------------------------------------ evidence */

function whyPeakQueue(analysis: Analysis): MetricEvidence {
  const peak = analysis.summary.peak_queue ?? 0;
  const events = analysis.events.filter((event) => event.kind === "peak");
  return {
    formula: "Q_peak = max over t of (vehicles inside the queue region and below the speed threshold)",
    rows: [
      ["Peak value", formatWithUnit(peak, "vehicles", 0)],
      ["First reached at", events[0] ? formatWithUnit(events[0].time, "s", 2) : "never"],
      ["Observation window", formatWithUnit(analysis.video.duration, "s")],
      ["Grid resolution", `1/${formatNumber(analysis.regions.sample_fps)} s`],
      ["Region", analysis.regions.queue.length >= 3 ? "user drawn" : "not defined"],
    ],
    note:
      peak > 0
        ? "The chart cursor shows the exact instant; the vehicles listed in the bottleneck panel contributed slow time here."
        : "No vehicle was inside the region and below the threshold at the same time.",
  };
}

function whyWait(analysis: Analysis): MetricEvidence {
  const complete = analysis.queue_visits.filter((visit) => visit.complete);
  const censored = analysis.queue_visits.filter((visit) => !visit.complete);
  const longest = complete.reduce(
    (best, visit) => ((visit.duration ?? 0) > (best.duration ?? 0) ? visit : best),
    complete[0] ?? { vehicle_id: 0, start: 0, end: 0, duration: 0, complete: true },
  );
  return {
    formula: "W = t_leave − t_enter for each queue visit; the card shows the mean and the maximum over completed visits",
    rows: [
      ["Completed visits", formatNumber(complete.length, 0)],
      ["Censored (excluded)", formatNumber(censored.length, 0)],
      [
        "Longest completed visit",
        longest?.duration
          ? `${vehicleLabel(longest.vehicle_id)}, ${formatWithUnit(longest.duration, "s")}`
          : "none",
      ],
      ["Minimum qualifying stay", formatWithUnit(analysis.regions.min_queue_seconds, "s")],
    ],
    note:
      censored.length > 0
        ? `${censored.length} visit(s) were still open, or already under way, at the start or end of the clip. Their true duration is unknown, so they are excluded from the average.`
        : "Every visit both started and ended inside the clip.",
  };
}

function whyThroughput(analysis: Analysis): MetricEvidence {
  return {
    formula: "Q = N / Δt where N is vehicles crossing the exit line (each counted once) and Δt is the clip length in minutes",
    rows: [
      ["Exit crossings", formatNumber(analysis.summary.vehicles_processed, 0)],
      ["Observation window", formatWithUnit(analysis.video.duration / 60, "min", 2)],
      ["Entry crossings", formatNumber(analysis.arrivals.length, 0)],
      [
        "Counting policy",
        analysis.regions.exit_direction === "forward" ? "forward crossings only" : "either direction",
      ],
    ],
    note:
      "The whole clip is the window, so a clip that starts and ends with a queue reports a lower rate than the instantaneous rate in the middle.",
  };
}
