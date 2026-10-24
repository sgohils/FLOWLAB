import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { ApiHealthBanner } from "../components/ApiHealthBanner";
import { PipelineFlow } from "../components/PipelineFlow";
import { ProcessingStatus } from "../components/ProcessingStatus";
import { RecentAnalyses } from "../components/RecentAnalyses";
import { VideoUploader } from "../components/VideoUploader";
import { Button, Label, Panel, Section } from "../components/Primitives";
import { useAnalysis } from "../state/AnalysisContext";
import type { Meta, UploadResponse } from "../types";
import { formatNumber } from "../utils/format";

const STAGES = [
  {
    key: "video",
    title: "Video",
    body: "Upload footage from a fixed camera at a school gate, car park or site entrance.",
  },
  {
    key: "trajectories",
    title: "Trajectories",
    body: "YOLO detects vehicles, ByteTrack keeps an anonymous id for each one, and every position is stored as a trajectory.",
  },
  {
    key: "measurements",
    title: "Measurements",
    body: "Queue length, estimated wait, throughput and bottleneck cells are counted directly from those trajectories.",
  },
  {
    key: "simulation",
    title: "Simulation",
    body: "A corridor model calibrated from the same clip lets you test different exit rates, volumes and arrival timings.",
  },
];

export default function Home() {
  const navigate = useNavigate();
  const { openDemo, job, analysis } = useAnalysis();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);

  useEffect(() => {
    api
      .meta()
      .then(setMeta)
      .catch(() => setMeta(null));
  }, []);

  const onUploaded = (response: UploadResponse) => {
    navigate(`/analysis/${response.analysis_id}`);
  };

  const startDemo = async () => {
    setDemoBusy(true);
    setDemoError(null);
    try {
      if (!await openDemo()) {
        setDemoError("The demo could not be loaded. Please retry shortly.");
        return;
      }
      navigate("/analysis/demo");
    } catch {
      setDemoError("The demo dataset could not be loaded. Is the backend running?");
    } finally {
      setDemoBusy(false);
    }
  };

  const processing = job && job.status !== "complete" && job.status !== "error";

  return (
    <div className="mx-auto max-w-[1100px]">
      <section className="mb-14">
        <h1 className="max-w-3xl text-[34px] font-medium leading-[1.15] tracking-tight text-ink">
          See where traffic slows down. Test what happens if it changes.
        </h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
          FLOWLAB converts traffic video into anonymous vehicle trajectories,
          queue measurements, bottleneck maps and interactive traffic
          simulations. Every number is a documented calculation on vehicles —
          never on people.
        </p>
        <div className="mt-7 flex flex-wrap items-center gap-3">
          <button
            onClick={() => {
              document.getElementById("upload")?.scrollIntoView({ behavior: "smooth" });
              document.querySelector<HTMLButtonElement>("#upload button")?.focus({ preventScroll: true });
            }}
            className="inline-flex items-center rounded border border-ink bg-ink px-5 py-2.5 text-[13px] font-medium text-paper transition-colors hover:bg-ink-soft"
          >
            Analyze Traffic Video
          </button>
          <Button variant="secondary" onClick={startDemo} disabled={demoBusy}>
            {demoBusy ? "Loading demo…" : "Try Sample Analysis"}
          </Button>
          {analysis && (
            <Link
              to={`/analysis/${analysis.analysis_id}`}
              className="text-[13px] text-accent underline-offset-2 hover:underline"
            >
              Back to analysis/{analysis.analysis_id}
            </Link>
          )}
        </div>
        {demoError && (
          <p className="mt-3 text-[12px] text-red-700">{demoError}</p>
        )}
      </section>

      <section className="mb-14">
        <PipelineFlow />
      </section>

      <ApiHealthBanner />

      <div id="upload">
        <Section
          title="Upload"
          subtitle={meta?.storage_mode === "hosted"
            ? "Videos are uploaded to private cloud storage and processed by a background worker."
            : meta?.storage_mode === "local"
              ? "Videos are processed and stored on the machine running the backend."
              : "Videos are sent to the FLOWLAB backend for processing and storage."}
        >
          {processing ? (
            <ProcessingStatus
              job={job}
              meta={meta}
              filename={job?.video?.filename}
            />
          ) : (
            <VideoUploader meta={meta} onUploaded={onUploaded} />
          )}
        </Section>
      </div>

      <Section
        title="Saved analyses"
        subtitle="The most recent saved analyses, up to 100 of them. Reopen one, or delete it together with its files."
      >
        <RecentAnalyses currentId={analysis?.analysis_id ?? null} />
      </Section>

      <Section title="What you get" subtitle="Four screens, one pipeline, no black box.">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {STAGES.map((stage, index) => (
            <Panel key={stage.key} className="p-5">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[11px] text-ink-faint">
                  0{index + 1}
                </span>
                <Label>{stage.title}</Label>
              </div>
              <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
                {stage.body}
              </p>
            </Panel>
          ))}
        </div>
      </Section>

      <Section title="How the numbers are defined">
        <Panel className="divide-y divide-rule-soft">
          <Definition
            term="Queue length"
            formula="queued(t) = inside queue region AND motion < threshold ;  Q_peak = max Q(t)"
            note="A direct count, not a model output."
          />
          <Definition
            term="Estimated wait"
            formula="W_avg = Σ (t_leave − t_enter) / N"
            note="Only episodes that visibly ended inside the clip are counted."
          />
          <Definition
            term="Throughput"
            formula="Q = N / Δt   (vehicles per minute)"
            note="N = vehicles whose track crossed the exit line, Δt = clip length."
          />
          <Definition
            term="Bottleneck"
            formula="score = Σ wᵢ · normalise(componentᵢ) over an 8×6 grid"
            note="Ranks areas where vehicles repeatedly slowed down."
          />
        </Panel>
      </Section>

      <Section title="Privacy and stored footage">
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel className="p-5">
            <Label>What FLOWLAB does not do</Label>
            <ul className="mt-3 grid gap-2 text-[13px] leading-relaxed text-ink-soft">
              {[
                "Only vehicle classes are requested from the detector — there is no face, plate, identity or demographic processing anywhere in the code.",
                "Hosted deployments upload videos to private cloud storage for processing. Local deployments store videos on the machine running the backend.",
                "Vehicle ids (Car #014) are labels invented for one analysis. They are not linked to a plate, a person or another video.",
                "Exports contain measurements only — no video, no frames, no original filename, no file paths.",
              ].map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-positive" />
                  {item}
                </li>
              ))}
            </ul>
          </Panel>
          <Panel className="p-5">
            <Label>What is still true of the footage</Label>
            <ul className="mt-3 grid gap-2 text-[13px] leading-relaxed text-ink-soft">
              {[
                "The uploaded and annotated videos can contain identifiable people and number plates. An anonymous track id does not anonymise the source footage.",
                "Nothing is deleted automatically. Press Delete on an analysis to remove its uploaded video, annotated video and results from the configured storage.",
                "The processing backend downloads the YOLO model file on first use if it is not already available.",
                "Do not use footage you are not permitted to use, and keep private school footage off shared machines.",
              ].map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-caution" />
                  {item}
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </Section>

      {meta && (
        <p className="pb-4 text-[11px] text-ink-faint">
          Model {meta.model_name} · detection classes{" "}
          {formatNumber(meta.vehicle_classes.length, 0)} vehicle types · sampled at{" "}
          {meta.sample_fps} fps · stopped below {meta.speed_threshold} frame-widths
          per second for {meta.min_stop_seconds}s
        </p>
      )}
    </div>
  );
}

function Definition({
  term,
  formula,
  note,
}: {
  term: string;
  formula: string;
  note: string;
}) {
  return (
    <div className="grid gap-1 px-5 py-3.5 md:grid-cols-[180px_1fr_260px] md:items-baseline md:gap-4">
      <span className="text-[13px] font-medium text-ink">{term}</span>
      <code className="font-mono text-[12px] text-ink-soft">{formula}</code>
      <span className="text-[11px] text-ink-faint">{note}</span>
    </div>
  );
}
