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
  load: (id: string) => Promise<boolean>;
  openDemo: () => Promise<boolean>;
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
  const generation = useRef(0);

  const stopPolling = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => () => {
    generation.current += 1;
    stopPolling();
  }, [stopPolling]);

  const load = useCallback(
    async (id: string) => {
      stopPolling();
      const request = ++generation.current;
      const current = () => request === generation.current;
      setAnalysisId(id);
      setLoading(true);
      setError(null);
      setAnalysis(null);
      setJob(null);

      const poll = async (): Promise<boolean> => {
        try {
          if (id === "demo") {
            const result = await api.demo();
            if (!current()) return false;
            setAnalysis(result);
            setLoading(false);
            return true;
          }
          const status = await api.status(id);
          if (!current()) return false;
          setJob(status);
          if (status.status === "complete") {
            const result = await api.result(id);
            if (!current()) return false;
            setAnalysis(result);
            setLoading(false);
            return true;
          }
          if (status.status === "error") {
            setError({ message: status.error ?? "Processing failed.", hint: status.hint });
            setLoading(false);
            return false;
          }
          timer.current = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
          return true;
        } catch (caught) {
          if (!current()) return false;
          setError({
            message: caught instanceof Error ? caught.message : "Could not load this analysis.",
            hint: caught instanceof ApiError ? caught.hint : null,
          });
          setLoading(false);
          return false;
        }
      };
      return poll();
    },
    [stopPolling],
  );

  const openDemo = useCallback(() => load("demo"), [load]);

  const replaceAnalysis = useCallback((next: Analysis) => {
    setAnalysis(next);
    setLoading(false);
  }, []);

  const clear = useCallback(() => {
    generation.current += 1;
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
