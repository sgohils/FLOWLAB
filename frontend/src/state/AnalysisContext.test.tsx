import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../api/client";
import type { Analysis, JobStatus } from "../types";
import { AnalysisProvider, useAnalysis } from "./AnalysisContext";

vi.mock("../api/client", () => ({
  api: { demo: vi.fn(), status: vi.fn(), result: vi.fn() },
  ApiError: class extends Error { hint = "Retry shortly"; },
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

afterEach(() => { vi.useRealTimers(); });

it("reports demo failure to the caller so Home does not navigate as if it succeeded", async () => {
  vi.mocked(api.demo).mockRejectedValue(new ApiError("Unavailable", 503));
  const { result } = renderHook(useAnalysis, { wrapper: AnalysisProvider });
  let loaded: boolean | undefined;
  await act(async () => { loaded = await result.current.openDemo(); });
  expect(loaded).toBe(false);
  expect(result.current.error?.message).toBe("Unavailable");
  expect(result.current.loading).toBe(false);
});

it("discards an earlier result after a different analysis is selected", async () => {
  const old = deferred<Analysis>();
  vi.mocked(api.demo).mockReturnValue(old.promise);
  vi.mocked(api.status).mockResolvedValue({ status: "complete" } as JobStatus);
  vi.mocked(api.result).mockResolvedValue({ analysis_id: "new" } as Analysis);
  const { result } = renderHook(useAnalysis, { wrapper: AnalysisProvider });
  let previous!: Promise<boolean>;
  act(() => { previous = result.current.load("demo"); });
  await act(async () => { await result.current.load("new"); });
  await act(async () => {
    old.resolve({ analysis_id: "demo" } as Analysis);
    await previous;
  });
  expect(result.current.analysisId).toBe("new");
  expect(result.current.analysis?.analysis_id).toBe("new");
});

it("does not restart polling when a pending status finishes after clear", async () => {
  vi.useFakeTimers();
  const status = deferred<JobStatus>();
  vi.mocked(api.status).mockReturnValue(status.promise);
  const { result } = renderHook(useAnalysis, { wrapper: AnalysisProvider });
  let pending!: Promise<boolean>;
  act(() => { pending = result.current.load("old"); });
  act(() => { result.current.clear(); });
  await act(async () => {
    status.resolve({ status: "processing" } as JobStatus);
    await pending;
  });
  expect(vi.getTimerCount()).toBe(0);
  expect(result.current.analysisId).toBeNull();
  expect(result.current.job).toBeNull();
});
