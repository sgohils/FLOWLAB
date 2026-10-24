import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { TimelinePayload } from "../types";

interface ReplayValue {
  /** Timeline payload, or null while loading. */
  timeline: TimelinePayload | null;
  loading: boolean;
  error: string | null;
  /** Current playback position in seconds. */
  time: number;
  duration: number;
  playing: boolean;
  rate: number;
  /** True when there is no source video: the transport drives the clock. */
  replayOnly: boolean;
  /**
   * True when the clip has more vehicles than the map can draw as live dots.
   * A consumer that would otherwise draw one marker per vehicle uses this to
   * draw a bounded sample instead - and says in its own interface that it has
   * done so, because a quietly half-drawn map reads as a broken map.
   */
  manyVehicles: boolean;
  seek: (moment: number) => void;
  /** Report the video's own clock back to the shared timeline. */
  reportTime: (moment: number) => void;
  setPlaying: (playing: boolean) => void;
  toggle: () => void;
  setRate: (rate: number) => void;
  step: (delta: number) => void;
  /** Position of a vehicle at `time`, or null when unknown (inside a gap). */
  positionAt: (vehicleId: number) => { x: number; y: number } | null;
  queueAt: number | null;
  selectedVehicleId: number | null;
  selectVehicle: (id: number | null) => void;
  selectedBottleneckId: number | null;
  selectBottleneck: (id: number | null) => void;
  /** A video element to keep in sync, if one is playing on the page. */
  registerVideo: (element: HTMLVideoElement | null) => void;
}

const ReplayContext = createContext<ReplayValue | null>(null);

/** Above this many vehicles the live dots are limited to the selection. */
const MANY_VEHICLES = 120;

/**
 * Position of a vehicle at `time`, or null when it is unknown.
 *
 * A track that was lost comes back as several segments, and the position
 * between two segments is genuinely unknown: the vehicle is hidden there
 * rather than drawn somewhere invented.  Inside one segment the samples are
 * uniform in time, so a binary search finds the bracketing pair and the
 * position is linearly interpolated.
 */
export function positionAt(
  timeline: TimelinePayload,
  vehicleId: number,
  time: number,
): { x: number; y: number } | null {
  const vehicle = timeline.vehicles.find((item) => item.id === vehicleId);
  if (!vehicle) return null;
  for (const segment of vehicle.segments) {
    const times = segment.t;
    if (times.length === 0) continue;
    if (time < times[0] || time > times[times.length - 1]) continue;
    // Binary search for the bracketing pair.
    let low = 0;
    let high = times.length - 1;
    while (low < high - 1) {
      const middle = (low + high) >> 1;
      if (times[middle] <= time) low = middle;
      else high = middle;
    }
    const span = times[high] - times[low];
    const fraction = span <= 0 ? 0 : (time - times[low]) / span;
    return {
      x: segment.x[low] + fraction * (segment.x[high] - segment.x[low]),
      y: segment.y[low] + fraction * (segment.y[high] - segment.y[low]),
    };
  }
  // No segment covers this instant: the track was lost here.
  return null;
}

/**
 * Queue length at the nearest sampled instant, or null when there is no sample
 * to read.
 *
 * The series itself is built by the backend's `build_timeline`, which starts it
 * at t = 0, so in practice this branch only guards a payload that does not.
 * Before the first sample the queue is genuinely unknown, so it reads as
 * nothing rather than as a confident zero.
 */
export function queueAt(timeline: TimelinePayload, time: number): number | null {
  if (!timeline.queue.length) return null;
  if (time < timeline.queue[0].t) return null;
  let best = timeline.queue[0];
  for (const sample of timeline.queue) {
    if (Math.abs(sample.t - time) < Math.abs(best.t - time)) best = sample;
    if (sample.t > time) break;
  }
  return best.q;
}

export function ReplayProvider({
  analysisId,
  hasVideo,
  children,
}: {
  analysisId: string | null;
  hasVideo: boolean;
  children: ReactNode;
}) {
  const [timeline, setTimeline] = useState<TimelinePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | null>(null);
  const [selectedBottleneckId, setSelectedBottleneckId] = useState<number | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const frame = useRef<number | null>(null);
  const lastTick = useRef<number>(0);

  const duration = timeline?.duration ?? 0;

  useEffect(() => {
    if (!analysisId) {
      setTimeline(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .timeline(analysisId, 4)
      .then((payload) => {
        if (cancelled) return;
        setTimeline(payload);
        setTime(0);
        setPlaying(false);
      })
      .catch((caught) => {
        if (!cancelled) setError((caught as Error).message ?? "Replay data unavailable.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  /** Keep the clock running when there is no video to drive it. */
  useEffect(() => {
    if (!playing || hasVideo || !duration) return;
    lastTick.current = performance.now();
    const tick = () => {
      const now = performance.now();
      const delta = (now - lastTick.current) / 1000;
      lastTick.current = now;
      setTime((current) => {
        const next = current + delta * rate;
        if (next >= duration) {
          setPlaying(false);
          return duration;
        }
        return next;
      });
      frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      frame.current = null;
    };
  }, [playing, hasVideo, duration, rate]);

  const seek = useCallback(
    (moment: number) => {
      const clamped = Math.max(0, Math.min(moment, duration || moment));
      setTime(clamped);
      const video = videoRef.current;
      if (video && Number.isFinite(video.duration)) {
        video.currentTime = Math.min(clamped, video.duration);
      }
    },
    [duration],
  );

  const reportTime = useCallback((moment: number) => {
    // The video is the clock when one is playing; the shared timeline follows.
    setTime(moment);
  }, []);

  const toggle = useCallback(() => {
    setPlaying((current) => {
      const next = !current;
      const video = videoRef.current;
      if (video) {
        if (next) {
          if (video.currentTime >= (video.duration || 0) - 0.05) video.currentTime = 0;
          void video.play().catch(() => setPlaying(false));
        } else {
          video.pause();
        }
      }
      return next;
    });
  }, []);

  const setRateSafe = useCallback((value: number) => {
    setRate(value);
    const video = videoRef.current;
    if (video) video.playbackRate = value;
  }, []);

  const step = useCallback(
    (delta: number) => {
      setPlaying(false);
      videoRef.current?.pause();
      seek(time + delta);
    },
    [seek, time],
  );

  const position = useCallback(
    (vehicleId: number) => (timeline ? positionAt(timeline, vehicleId, time) : null),
    [timeline, time],
  );

  const queueValue = useMemo(
    () => (timeline ? queueAt(timeline, time) : null),
    [timeline, time],
  );

  const registerVideo = useCallback(
    (element: HTMLVideoElement | null) => {
      videoRef.current = element;
      if (element) element.playbackRate = rate;
    },
    [rate],
  );

  // Annotated as ReplayValue so a field that is added to the value but not to
  // the interface is a compile error rather than a silently ignored export.
  const value = useMemo<ReplayValue>(
    () => ({
      timeline,
      loading,
      error,
      time,
      duration,
      playing,
      rate,
      replayOnly: !hasVideo,
      manyVehicles: (timeline?.vehicles.length ?? 0) > MANY_VEHICLES,
      seek,
      reportTime,
      setPlaying,
      toggle,
      setRate: setRateSafe,
      step,
      positionAt: position,
      queueAt: queueValue,
      selectedVehicleId,
      selectVehicle: setSelectedVehicleId,
      selectedBottleneckId,
      selectBottleneck: setSelectedBottleneckId,
      registerVideo,
    }),
    [
      timeline,
      loading,
      error,
      time,
      duration,
      playing,
      rate,
      hasVideo,
      seek,
      reportTime,
      toggle,
      setRateSafe,
      step,
      position,
      queueValue,
      selectedVehicleId,
      selectedBottleneckId,
      registerVideo,
    ],
  );

  return <ReplayContext.Provider value={value}>{children}</ReplayContext.Provider>;
}

export function useReplay(): ReplayValue {
  const context = useContext(ReplayContext);
  if (!context) throw new Error("useReplay must be used inside <ReplayProvider>");
  return context;
}
