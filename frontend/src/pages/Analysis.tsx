import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { AnalysisView } from "../components/AnalysisView";
import { ExportMenu } from "../components/ExportMenu";
import { ProcessingStatus } from "../components/ProcessingStatus";
import { useLatestRequest } from "../components/RegionEditor";
import type { DrawTool } from "../components/VideoViewer";
import { Button, Label, Notice, Panel } from "../components/Primitives";
import { useAnalysis } from "../state/AnalysisContext";
import { ReplayProvider } from "../state/ReplayContext";
import type { Meta, Regions } from "../types";
import { formatBytes, formatNumber } from "../utils/format";

/**
 * Page shell: routing, job status and the analysis header.  Everything that
 * needs the shared replay clock lives in `AnalysisView`, inside the provider.
 */
export default function Analysis() {
  const { analysisId: routeId } = useParams();
  const navigate = useNavigate();
  const { analysisId, analysis, job, loading, error, load, replaceAnalysis, clear } = useAnalysis();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [regions, setRegions] = useState<Regions | null>(null);
  const [tool, setTool] = useState<DrawTool>("none");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { begin, isCurrent, finish, pending } = useLatestRequest();

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  // Reload whenever the route changes.  Comparing against the cached id would
  // keep a stale analysis in memory when the same id is opened twice.
  useEffect(() => {
    if (routeId) void load(routeId);
  }, [routeId, load]);

  useEffect(() => {
    setRegions(analysis?.regions ?? null);
  }, [analysis]);

  /**
   * Every edit gets a token.  If two edits are in flight, only the newest
   * response may replace the result, so the screen can never show metrics
   * computed from a region the user has already changed.
   */
  const commitRegions = useCallback(
    async (next: Regions) => {
      if (!analysis || analysis.source === "demo") return;
      setRegions(next);
      setSaveError(null);
      const token = begin();
      try {
        const updated = await api.updateRegions(analysis.analysis_id, next);
        if (isCurrent(token)) replaceAnalysis(updated);
      } catch (caught) {
        if (isCurrent(token)) setSaveError((caught as ApiError).message);
      } finally {
        finish();
      }
    },
    [analysis, begin, isCurrent, finish, replaceAnalysis],
  );

  const removeAnalysis = async () => {
    if (!analysis || !window.confirm("Delete this analysis and all of its local files?")) {
      return;
    }
    try {
      const result = await api.delete(analysis.analysis_id);
      setNotice(result.message);
      clear();
      navigate("/");
    } catch (caught) {
      setSaveError((caught as ApiError).message);
    }
  };

  const hasVideo = Boolean(analysis && analysis.source === "video");
  const videoUrl = analysis ? api.annotatedVideoUrl(analysis.analysis_id) : "";

  if (!routeId && !analysisId) {
    return (
      <div className="mx-auto max-w-lg py-16 text-center">
        <h1 className="text-xl font-medium text-ink">No analysis open</h1>
        <p className="mt-2 text-[13px] text-ink-soft">
          Upload a traffic video, or open the demo dataset, to see the measurement
          dashboard.
        </p>
        <Button className="mt-5" onClick={() => navigate("/")}>
          Go to upload
        </Button>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-4">
        <div>
          <Label>Analysis</Label>
          <h1 className="mt-1 font-mono text-[22px] tracking-tight text-ink">
            {analysisId ?? "—"}
            {analysis?.source === "demo" && (
              <span className="ml-3 align-middle rounded border border-caution/40 bg-caution-soft px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-caution">
                Demo Dataset
              </span>
            )}
          </h1>
          {analysis && (
            <p className="mt-1.5 text-[12px] text-ink-faint">
              {analysis.video.filename} · {analysis.video.width}×{analysis.video.height} ·{" "}
              {formatNumber(analysis.video.duration)}s · {formatNumber(analysis.video.fps)} fps
              source · {formatBytes(analysis.video.size_bytes)} · sampled at{" "}
              {analysis.video.processed_fps} fps
            </p>
          )}
        </div>
        {analysis && (
          <div className="flex flex-wrap items-center gap-2">
            {hasVideo && (
              <a
                href={api.sourceVideoUrl(analysis.analysis_id)}
                className="rounded border border-rule bg-surface px-3 py-1.5 text-[12px] text-ink-soft hover:border-ink-faint"
              >
                Source video
              </a>
            )}
            <ExportMenu analysisId={analysis.analysis_id} hasVideo={hasVideo} />
            <Link
              to={`/brief/${analysis.analysis_id}`}
              className="rounded border border-rule bg-surface px-3 py-1.5 text-[12px] text-ink-soft hover:border-ink-faint"
            >
              Print brief
            </Link>
            <Button variant="ghost" onClick={removeAnalysis} disabled={pending > 0}>
              Delete
            </Button>
            <Link
              to={`/simulation/${analysis.analysis_id}`}
              className="rounded border border-ink bg-ink px-4 py-2 text-[13px] font-medium text-paper hover:bg-ink-soft"
            >
              Simulate a scenario
            </Link>
          </div>
        )}
      </div>

      {notice && (
        <div className="mb-6">
          <Notice tone="success">{notice}</Notice>
        </div>
      )}

      {error && (
        <div className="mb-6">
          <Notice tone="error" title="Could not complete this request">
            <p>{error.message}</p>
            {error.hint && <p className="mt-1 opacity-85">{error.hint}</p>}
          </Notice>
        </div>
      )}

      {loading && (
        <div className="mb-6 grid gap-4 lg:grid-cols-[minmax(0,420px)_1fr]">
          <ProcessingStatus job={job} meta={meta} filename={job?.video?.filename} />
          <Panel className="flex items-center justify-center p-10 text-[13px] text-ink-faint">
            Detection and tracking run in the background — the page stays responsive and
            the progress stages update above.
          </Panel>
        </div>
      )}

      {analysis && analysis.summary && (
        <>
          {analysis.warnings.length > 0 && (
            <div className="mb-8 space-y-2">
              {analysis.warnings.map((warning) => (
                <Notice key={warning} tone="caution">
                  {warning}
                </Notice>
              ))}
            </div>
          )}
          <ReplayProvider analysisId={analysis.analysis_id} hasVideo={hasVideo}>
            <AnalysisView
              analysis={analysis}
              hasVideo={hasVideo}
              videoUrl={videoUrl}
              regions={regions}
              tool={tool}
              onToolChange={setTool}
              onRegionsChange={setRegions}
              onCommitRegions={(next) => void commitRegions(next)}
              pending={pending}
              saveError={saveError}
              onUploadAnother={() => navigate("/")}
            />
          </ReplayProvider>
        </>
      )}
    </div>
  );
}
