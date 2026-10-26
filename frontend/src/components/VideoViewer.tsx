import { useCallback, useEffect, useRef, useState } from "react";
import { useReplay } from "../state/ReplayContext";
import type { Point, Regions } from "../types";
import { formatTimecode } from "../utils/format";
import { Button, Label, Panel } from "./Primitives";

export type DrawTool = "none" | "queue" | "entry" | "exit";

/** An interactive queue region stays a simple polygon; see the click handler. */
const MAX_QUEUE_CORNERS = 12;

interface VideoViewerProps {
  src: string;
  poster?: string | null;
  regions: Regions;
  tool: DrawTool;
  onChange: (regions: Regions) => void;
  /** Called when the user finishes a shape, so the page can recompute. */
  onCommit?: () => void;
  editable: boolean;
}

const COLOURS: Record<Exclude<DrawTool, "none">, string> = {
  queue: "rgba(29, 78, 216, 0.16)",
  entry: "rgba(15, 118, 110, 0.18)",
  exit: "rgba(180, 83, 9, 0.18)",
};
const STROKES: Record<Exclude<DrawTool, "none">, string> = {
  queue: "#1d4ed8",
  entry: "#0f766e",
  exit: "#b45309",
};

export function VideoViewer({
  src,
  poster,
  regions,
  tool,
  onChange,
  onCommit,
  editable,
}: VideoViewerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<SVGSVGElement>(null);
  const [draft, setDraft] = useState<Point[]>([]);
  const [duration, setDuration] = useState(0);
  const [aspect, setAspect] = useState(16 / 9);
  const {
    registerVideo,
    seek,
    reportTime,
    time,
    setPlaying,
    playing: replayPlaying,
    toggle: replayToggle,
  } = useReplay();

  const toNormalized = useCallback((event: React.MouseEvent): Point | null => {
    const svg = overlayRef.current;
    if (!svg) return null;
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    if (x < -0.05 || x > 1.05 || y < -0.05 || y > 1.05) return null;
    return [Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))];
  }, []);

  const handleClick = (event: React.MouseEvent) => {
    if (!editable || tool === "none") return;
    const point = toNormalized(event);
    if (!point) return;
    if (tool === "queue") {
      const next = [...draft, point];
      // A queue region is meant to be a simple polygon; past a dozen corners
      // the shape is a scribble and the slow-membership scan gets slower.
      if (next.length <= MAX_QUEUE_CORNERS) setDraft(next);
    } else {
      if (draft.length === 1) {
        onChange({ ...regions, [tool]: [draft[0], point] });
        setDraft([]);
        onCommit?.();
      } else {
        setDraft([point]);
      }
    }
  };

  const commitQueue = useCallback(() => {
    if (tool !== "queue" || draft.length < 3) return;
    onChange({ ...regions, queue: draft });
    setDraft([]);
    onCommit?.();
  }, [draft, onChange, onCommit, regions, tool]);

  const doubleClick = (event: React.MouseEvent) => {
    if (tool !== "queue") return;
    event.preventDefault();
    commitQueue();
  };

  /**
   * The overlay is a canvas, so it carries its own keyboard path: Enter closes
   * a queue polygon and Escape abandons the draft.  Without this the help text
   * promises "press Enter" and nothing happens.
   */
  const handleOverlayKey = (event: React.KeyboardEvent) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commitQueue();
    } else if (event.key === "Escape" && draft.length > 0) {
      event.preventDefault();
      setDraft([]);
    }
  };

  const undo = useCallback(() => {
    if (draft.length === 0) return;
    setDraft(draft.slice(0, -1));
  }, [draft]);

  const clearCurrent = useCallback(() => {
    if (tool === "none") return;
    onChange({ ...regions, [tool]: [] });
    setDraft([]);
    onCommit?.();
  }, [onChange, onCommit, regions, tool]);

  const drawing = editable && tool !== "none";

  useEffect(() => {
    // Hand the element to the shared timeline so the transport bar and every
    // other panel stay in step with the video.
    registerVideo(videoRef.current);
    return () => registerVideo(null);
  }, [registerVideo, src]);

  useEffect(() => {
    setDraft([]);
  }, [tool]);

  const pointsToPath = (points: Point[]) =>
    points.map(([x, y]) => `${x.toFixed(4)},${y.toFixed(4)}`).join(" ");

  return (
    <Panel className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-rule px-4 py-2.5">
        <div className="flex items-center gap-3">
          <Label>Annotated video</Label>
          <span className="font-mono text-[11px] text-ink-faint">
            {formatTimecode(time)} / {formatTimecode(duration)}
          </span>
        </div>
        {drawing && (
          <div className="flex items-center gap-1.5">
            <Button variant="ghost" onClick={undo} disabled={draft.length === 0}>
              Undo point
            </Button>
            <Button
              variant="ghost"
              onClick={clearCurrent}
              disabled={regions[tool].length === 0}
            >
              Clear {tool}
            </Button>
          </div>
        )}
      </div>

      {/* The overlay is sized from the video's own aspect ratio so the region
          handles stay aligned with the picture, whatever the resolution. */}
      <div className="relative flex aspect-video items-center justify-center bg-ink">
        <div className="relative max-h-full max-w-full" style={{ aspectRatio: aspect }}>
          <video
            ref={videoRef}
            src={src}
            poster={poster ?? undefined}
            preload="metadata"
            className="block h-full w-full"
            onLoadedMetadata={(event) => {
              const video = event.currentTarget;
              setDuration(video.duration);
              if (video.videoWidth && video.videoHeight) {
                setAspect(video.videoWidth / video.videoHeight);
              }
            }}
            // The video is the clock when it is playing; everything else on the
            // page reads its position from the shared timeline.
            onTimeUpdate={(event) => reportTime(event.currentTarget.currentTime)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            playsInline
            aria-label="Annotated video of the analysed clip"
          />
        <svg
          ref={overlayRef}
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          className={`absolute inset-0 h-full w-full ${
            drawing ? "cursor-crosshair" : "pointer-events-none"
          }`}
          onClick={handleClick}
          onDoubleClick={doubleClick}
          onKeyDown={handleOverlayKey}
          role="img"
          tabIndex={drawing ? 0 : undefined}
          aria-label={
            drawing
              ? `Region overlay, drawing the ${tool} ${
                  tool === "queue" ? "region" : "line"
                }. ${draft.length} point(s) placed. Press Enter to finish, Escape to cancel.`
              : "Region overlay"
          }
        >
          {regions.queue.length >= 3 && (
            <polygon
              points={pointsToPath(regions.queue)}
              fill={COLOURS.queue}
              stroke={STROKES.queue}
              strokeWidth={0.0035}
              strokeDasharray="0.02 0.012"
            />
          )}
          {draft.length >= 3 && (
            <polygon
              points={pointsToPath(draft)}
              fill="rgba(29,78,216,0.08)"
              stroke={STROKES.queue}
              strokeWidth={0.0035}
            />
          )}
          {draft.map(([x, y], index) => (
            <circle
              key={index}
              cx={x}
              cy={y}
              r={0.008}
              fill="#1d4ed8"
            />
          ))}
          {(["entry", "exit"] as const).map((name) => {
            const line = regions[name];
            if (line.length !== 2) return null;
            return (
              <g key={name}>
                <line
                  x1={line[0][0]}
                  y1={line[0][1]}
                  x2={line[1][0]}
                  y2={line[1][1]}
                  stroke={STROKES[name]}
                  strokeWidth={0.004}
                />
                <text
                  x={line[0][0] + 0.02}
                  y={line[0][1] + 0.01}
                  fill={STROKES[name]}
                  fontSize={0.035}
                  fontFamily="ui-monospace, monospace"
                >
                  {name}
                </text>
              </g>
            );
          })}
          </svg>
        </div>
      </div>

      <div className="flex items-center gap-3 border-t border-rule px-4 py-2">
        {drawing && (
          <p className="sr-only" role="status" aria-live="polite">
            {tool === "queue"
              ? `Drawing the queue region. ${draft.length} point(s) placed.`
              : `Drawing the ${tool} line. ${draft.length} of 2 point(s) placed.`}
          </p>
        )}
        <Button variant="secondary" onClick={replayToggle}>
          {replayPlaying ? "Pause" : "Play"}
        </Button>
        <input
          type="range"
          min={0}
          max={Math.max(duration, 0.1)}
          step={0.05}
          value={Math.min(time, duration || 0.1)}
          onChange={(event) => seek(Number(event.target.value))}
          aria-label="Video position"
          className="h-1 flex-1 cursor-pointer appearance-none rounded bg-rule-soft accent-[#1d4ed8]"
        />
        <Button
          variant="secondary"
          onClick={() => {
            seek(0);
            replayToggle();
          }}
        >
          Replay
        </Button>
      </div>
    </Panel>
  );
}
