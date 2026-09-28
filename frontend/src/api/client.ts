/**
 * Thin API client.  Every backend error is normalised into an ApiError that
 * carries a human message and a hint, so components never have to inspect
 * response bodies or deal with tracebacks.
 */

import type {
  Analysis,
  AnalysisListItem,
  DeleteResult,
  Health,
  JobStatus,
  Meta,
  Regions,
  Scenario,
  SimulationResult,
  TimelinePayload,
  UploadResponse,
} from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  readonly status: number;
  readonly hint: string | null;

  constructor(message: string, status: number, hint: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.hint = hint;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(
      "The FLOWLAB backend is not reachable.",
      0,
      "Start it with `uvicorn backend.main:app --port 8000` and reload.",
    );
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    let hint: string | null = null;
    try {
      const body = await response.json();
      message = body.message ?? body.detail ?? message;
      if (Array.isArray(body.detail)) {
        message = body.detail
          .map((item: { loc?: string[]; msg?: string }) =>
            `${(item.loc ?? []).slice(1).join(".")}: ${item.msg ?? "invalid"}`,
          )
          .join("; ");
      }
      hint = body.hint ?? null;
    } catch {
      /* non-JSON error body: keep the generic message */
    }
    throw new ApiError(message, response.status, hint);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  meta: () => request<Meta>("/api/meta"),
  demo: () => request<Analysis>("/api/demo"),
  analyses: () => request<AnalysisListItem[]>("/api/analyses"),

  upload: (file: File, onProgress?: (fraction: number) => void) =>
    new Promise<UploadResponse>((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      // XHR is used instead of fetch purely to report upload progress.
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}/api/uploads`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(event.loaded / event.total);
        }
      };
      xhr.onload = () => {
        try {
          const body = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(body as UploadResponse);
          } else {
            reject(
              new ApiError(
                body.message ?? body.detail ?? "The upload was rejected.",
                xhr.status,
                body.hint ?? null,
              ),
            );
          }
        } catch {
          reject(new ApiError("The upload failed unexpectedly.", xhr.status));
        }
      };
      xhr.onerror = () =>
        reject(new ApiError("The upload could not reach the server.", 0));
      xhr.send(form);
    }),

  status: (id: string) => request<JobStatus>(`/api/analyses/${id}/status`),
  result: (id: string, points = 60) =>
    request<Analysis>(`/api/analyses/${id}/result?trajectory_points=${points}`),
  /** Replay data: uniform-in-time samples, split at tracking gaps. */
  timeline: (id: string, hz = 4) =>
    request<TimelinePayload>(`/api/analyses/${id}/timeline?hz=${hz}`),
  updateRegions: (id: string, regions: Regions) =>
    request<Analysis>(`/api/analyses/${id}/regions`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ regions }),
    }),
  simulate: (id: string, scenario: Scenario) =>
    request<SimulationResult>(`/api/analyses/${id}/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario }),
    }),
  delete: (id: string) =>
    request<DeleteResult>(`/api/analyses/${id}`, { method: "DELETE" }),

  /** Export endpoints.  None of them contain video. */
  exportUrl: {
    summary: (id: string, includePoints = false) =>
      `${BASE}/api/analyses/${id}/export/summary.json?include_points=${includePoints}`,
    vehicles: (id: string) => `${BASE}/api/analyses/${id}/export/vehicles.csv`,
    queue: (id: string) => `${BASE}/api/analyses/${id}/export/queue.csv`,
    events: (id: string) => `${BASE}/api/analyses/${id}/export/events.csv`,
  },

  annotatedVideoUrl: (id: string) => `${BASE}/api/analyses/${id}/video/annotated`,
  sourceVideoUrl: (id: string) => `${BASE}/api/analyses/${id}/video/source`,
};
