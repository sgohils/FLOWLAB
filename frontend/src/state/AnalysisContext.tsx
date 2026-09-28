import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, api } from "../api/client";
import type { Analysis, JobStatus } from "../types";

interface AnalysisContextValue {
  analysisId: string | null;
  analysis: Analysis | null;
  job: JobStatus | null;
  loading: boolean;
  error: { message: string; hint: string | null } | null;
  load: (id: string) => Promise<void>;
  openDemo: () => Promise<void>;
  replaceAnalysis: (analysis: Analysis) => void;
  clear: () => void;
}

const AnalysisContext = createContext<AnalysisContextValue | null>(null);

/** How often the processing status is polled while a job is running. */
const POLL_INTERVAL_MS = 1200;

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; hint: string | null } | null>(null);
  const timer = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const load = useCallback(
    async (id: string) => {
      stopPolling();
      setAnalysisId(id);
      setLoading(true);
      setError(null);
      setAnalysis(null);
      setJob(null);

      const poll = async () => {
        try {
          if (id === "demo") {
            setAnalysis(await api.demo());
            setLoading(false);
            return;
          }
          const status = await api.status(id);
          setJob(status);
          if (status.status === "complete") {
            setAnalysis(await api.result(id));
            setLoading(false);
            return;
          }
          if (status.status === "error") {
            setError({ message: status.error ?? "Processing failed.", hint: status.hint });
            setLoading(false);
            return;
          }
          timer.current = window.setTimeout(poll, POLL_INTERVAL_MS);
        } catch (caught) {
          const apiError = caught as ApiError;
          setError({
            message: apiError.message ?? "Could not load this analysis.",
            hint: apiError.hint ?? null,
          });
          setLoading(false);
        }
      };
      await poll();
    },
    [stopPolling],
  );

  const openDemo = useCallback(async () => {
    await load("demo");
  }, [load]);

  const replaceAnalysis = useCallback((next: Analysis) => {
    setAnalysis(next);
    setLoading(false);
  }, []);

  const clear = useCallback(() => {
    stopPolling();
    setAnalysisId(null);
    setAnalysis(null);
    setJob(null);
    setError(null);
    setLoading(false);
  }, [stopPolling]);

  const value = useMemo(
    () => ({ analysisId, analysis, job, loading, error, load, openDemo, replaceAnalysis, clear }),
    [analysisId, analysis, job, loading, error, load, openDemo, replaceAnalysis, clear],
  );

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis(): AnalysisContextValue {
  const context = useContext(AnalysisContext);
  if (!context) throw new Error("useAnalysis must be used inside <AnalysisProvider>");
  return context;
}
