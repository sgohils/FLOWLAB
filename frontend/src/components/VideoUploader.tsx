import { useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { Meta, UploadResponse } from "../types";
import {
  formatBytes,
  formatPercent,
  formatWithUnit,
} from "../utils/format";
import { Button, Notice, Panel } from "./Primitives";

interface VideoUploaderProps {
  meta: Meta | null;
  onUploaded: (response: UploadResponse) => void;
}

type Phase = "idle" | "uploading" | "done";

export function VideoUploader({ meta, onUploaded }: VideoUploaderProps) {
  const input = useRef<HTMLInputElement>(null);
  const uploading = useRef(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<{ message: string; hint: string | null } | null>(null);
  const [fileInfo, setFileInfo] = useState<{ name: string; size: number } | null>(null);

  const allowed = meta?.allowed_extensions ?? [".mp4", ".mov"];
  const maxMb = meta?.max_upload_mb ?? 250;

  const submit = async (file: File) => {
    if (uploading.current) return;
    const problem = validate(file);
    if (problem) {
      setError({ message: problem, hint: null });
      return;
    }
    uploading.current = true;
    setError(null);
    setFileInfo({ name: file.name, size: file.size });
    setPhase("uploading");
    setProgress(0);
    try {
      const response = await api.upload(file, setProgress);
      setPhase("done");
      onUploaded(response);
    } catch (caught) {
      const apiError = caught as ApiError;
      setError({ message: apiError.message, hint: apiError.hint });
      setPhase("idle");
    } finally {
      uploading.current = false;
    }
  };

  const validate = (file: File): string | null => {
    const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
    if (!allowed.includes(extension)) {
      return `“${extension}” is not a supported format. Use ${allowed.join(", ")}.`;
    }
    if (file.size > maxMb * 1024 * 1024) {
      return `That file is ${formatBytes(file.size)}; the limit is ${formatWithUnit(
        maxMb,
        "MB",
        0,
      )}.`;
    }
    return null;
  };

  return (
    <div className="space-y-4">
      <Panel className="p-6">
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            const file = event.dataTransfer.files?.[0];
            if (!file) return;
            void submit(file);
          }}
          className={`flex flex-col items-center justify-center rounded-md border border-dashed px-6 py-12 text-center transition-colors ${
            dragging ? "border-accent bg-accent-soft" : "border-rule bg-paper"
          }`}
        >
          <p className="text-[15px] font-medium text-ink">Drop a traffic video here</p>
          <p className="mt-1 text-[13px] text-ink-soft">
            or select a file from this computer
          </p>
          <p className="mt-3 text-[11px] text-ink-faint">
            {allowed.join(" · ")} — up to {maxMb} MB,{" "}
            {meta
              ? formatWithUnit(meta.max_duration_seconds / 60, "min", 0)
              : "15 min"}{" "}
            maximum.
            Fixed camera footage works best.
          </p>
          <input
            ref={input}
            type="file"
            accept={allowed.join(",")}
            className="hidden"
            aria-label="Traffic video"
            disabled={phase === "uploading"}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) void submit(file);
            }}
          />
          <Button className="mt-5" disabled={phase === "uploading"} onClick={() => input.current?.click()}>
            Choose video
          </Button>
          {phase === "uploading" && (
            <div className="mt-5 w-full max-w-sm">
              <div className="mb-1 flex justify-between text-[11px] text-ink-faint">
                <span className="truncate">{fileInfo?.name}</span>
                <span className="font-mono">{formatPercent(progress, 0)}</span>
              </div>
              <div
                className="h-1 w-full overflow-hidden rounded bg-rule-soft"
                role="progressbar"
                aria-label="Upload progress"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(progress * 100)}
              >
                <div
                  className="h-full bg-accent transition-[width] duration-200"
                  style={{ width: `${Math.max(3, progress * 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </Panel>

      {error && (
        <Notice tone="error" title="Upload rejected">
          <p>{error.message}</p>
          {error.hint && <p className="mt-1 opacity-80">{error.hint}</p>}
        </Notice>
      )}

      <p className="text-[11px] leading-relaxed text-ink-faint">
        Detection runs on the backend with{" "}
        {meta ? `${meta.model_name} ` : "a YOLO model "}
        on vehicle classes only ({meta?.vehicle_classes.join(", ") ?? "car, bus, truck, motorcycle"}).
        {" "}The clip and annotated copy stay in the backend's configured storage until
        you delete the analysis. Hosted deployments upload footage to private cloud storage.
      </p>
    </div>
  );
}
