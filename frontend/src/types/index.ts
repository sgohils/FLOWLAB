/**
 * TypeScript mirrors of the Pydantic schemas in backend/models/schemas.py.
 * Every geometry value is normalised (0-1) relative to the video frame.
 */

export type Point = [number, number];
export type Polygon = Point[];
export type Line = Point[];

export type AnalysisSource = "video" | "demo";
export type JobState = "queued" | "processing" | "complete" | "error";
export type StageState = "pending" | "active" | "done" | "error";

export type CrossingDirection = "any" | "forward";

export interface Regions {
  queue: Polygon;
  entry: Line;
  exit: Line;
  conflict: Polygon;
  speed_threshold: number;
  min_stop_seconds: number;
  /** How long a vehicle must stay inside the queue region while slow to count. */
  min_queue_seconds: number;
  sample_fps: number;
  entry_direction: CrossingDirection;
  exit_direction: CrossingDirection;
  auto_detected: boolean;
}

/** A queue region is usable once it has at least three corners. */
export function hasQueueRegion(regions: Regions | null | undefined): boolean {
  // Array.isArray as well as the length: a record written by an older version
  // can carry a queue that is not a list, and that should read as "not drawn"
  // rather than take the page down.
  return Boolean(regions && Array.isArray(regions.queue) && regions.queue.length >= 3);
}

export interface VideoInfo {
  filename: string;
  duration: number;
  fps: number;
  width: number;
  height: number;
  size_bytes: number;
  processed_fps: number;
  frame_count: number;
  annotated_path: string | null;
  annotated_url: string | null;
}

export interface TrajectoryPoint {
  frame: number;
  time: number;
  x: number;
  y: number;
  confidence: number;
  bbox: number[];
  speed: number;
}

export interface Trajectory {
  vehicle_id: number;
  vehicle_class: string;
  first_seen: number;
  last_seen: number;
  /** Traversal time: first to last tracked sample, gaps included. */
  duration: number;
  path_length: number;
  /** Time below the motion threshold anywhere in the scene. */
  stopped_seconds: number;
  /** Time inside the queue region while slow - the basis of the wait estimate. */
  queue_seconds: number;
  /** Time inside the queue region, moving or not. */
  region_seconds: number;
  mean_speed: number;
  points: TrajectoryPoint[];
}

export interface QueueSample {
  time: number;
  queue: number;
}

export interface StopInterval {
  vehicle_id: number;
  start: number;
  end: number;
  duration: number;
  x: number;
  y: number;
  region: "queue" | "scene";
}

export interface QueueVisit {
  vehicle_id: number;
  start: number;
  end: number | null;
  duration: number | null;
  complete: boolean;
}

export interface Bottleneck {
  id: number;
  x: number;
  y: number;
  width: number;
  height: number;
  vehicle_passes: number;
  /** Anonymous ids measured as slowed in this cell (evidence for the count). */
  vehicle_ids: number[];
  stopped_seconds: number;
  mean_slowdown_seconds: number;
  occupancy_seconds: number;
  score: number;
}

export interface HeatCell {
  x: number;
  y: number;
  width: number;
  height: number;
  value: number;
  vehicle_passes: number;
}

export interface TrafficEvent {
  time: number;
  kind: string;
  label: string;
  value: number | null;
}

export interface Summary {
  vehicles_detected: number;
  vehicles_tracked: number;
  vehicles_processed: number;
  vehicles_incomplete: number;
  peak_queue: number | null;
  average_queue: number | null;
  median_queue: number | null;
  queue_duration_seconds: number | null;
  average_wait_seconds: number | null;
  median_wait_seconds: number | null;
  max_wait_seconds: number | null;
  average_region_seconds: number | null;
  throughput_per_minute: number | null;
  entry_per_minute: number | null;
  mean_traversal_seconds: number | null;
  mean_stopped_seconds: number | null;
  bottleneck_count: number;
  completed_queue_visits: number;
  censored_queue_visits: number;
}

export interface Calibration {
  arrival_rate_per_minute: number;
  mean_arrival_headway_seconds: number;
  service_time_seconds: number;
  mean_traversal_seconds: number;
  free_flow_seconds: number;
  mean_queue_visit_seconds: number;
  observation_seconds: number;
  vehicles_used: number;
  notes: string[];
}

export interface Analysis {
  sample?: {
    title: string;
    description: string;
    author: string;
    source_url: string;
    license: string;
    license_url: string;
    processing_notes: string[];
    video_url: string;
    annotated_video_url: string;
    poster_url: string;
  } | null;
  analysis_id: string;
  source: AnalysisSource;
  video: VideoInfo;
  regions: Regions;
  summary: Summary;
  calibration: Calibration;
  evidence: EvidenceFacts;
  trajectories: Trajectory[];
  queue_timeseries: QueueSample[];
  /**
   * Vehicles geometrically inside the queue region at each instant, ignoring
   * speed - the quantity a human annotator can reproduce by pausing a frame.
   */
  region_occupancy_timeseries: QueueSample[];
  bottlenecks: Bottleneck[];
  heat_grid: HeatCell[];
  events: TrafficEvent[];
  stops: StopInterval[];
  queue_visits: QueueVisit[];
  arrivals: number[];
  departures: number[];
  warnings: string[];
  created_at: number;
}

export interface StageStatus {
  key: string;
  label: string;
  status: StageState;
  progress: number;
  detail: string | null;
}

export interface JobStatus {
  analysis_id: string;
  status: JobState;
  stage: string;
  progress: number;
  stages: StageStatus[];
  error: string | null;
  hint: string | null;
  video: VideoInfo | null;
  created_at: number;
  updated_at: number;
}

export interface AnalysisListItem {
  read_only?: boolean;
  analysis_id: string;
  filename: string;
  source: AnalysisSource;
  status: string;
  created_at: number;
  duration: number;
  vehicles_tracked: number;
  peak_queue: number | null;
  throughput_per_minute: number | null;
}

export interface Scenario {
  volume: number;
  service_multiplier: number;
  spread_seconds: number;
  channels: number;
  seed: number;
}

export interface SimulationMetrics {
  vehicles: number;
  peak_queue: number;
  average_queue: number;
  average_wait_seconds: number;
  max_wait_seconds: number;
  throughput_per_minute: number;
  total_delay_seconds: number;
  observation_seconds: number;
  /** Still in the corridor when the window ends (meaningless for a recording). */
  vehicles_left_at_window_end: number;
}

export interface MetricDelta {
  metric: string;
  label: string;
  unit: string;
  observed: number;
  simulated: number;
  absolute: number;
  percent: number | null;
  lower_is_better: boolean;
}

export interface SimulatedTrack {
  vehicle_id: number;
  arrival: number;
  departure: number | null;
  wait: number | null;
  points: [number, number][];
}

export interface ModelFidelity {
  peak_queue_observed: number;
  peak_queue_model: number;
  average_wait_observed: number;
  average_wait_model: number;
  ratio: number | null;
  note: string;
}

export interface SimulationResult {
  analysis_id: string;
  scenario: Scenario;
  calibration: Calibration;
  /** A - what the camera measured. */
  observed: SimulationMetrics;
  /** B - the unmodified model replaying the observed arrivals. */
  baseline: SimulationMetrics;
  /** C - the model with the scenario applied. */
  simulated: SimulationMetrics;
  fidelity: ModelFidelity;
  sensitivity: SensitivityRange | null;
  /** Scenario effect: C compared with B. */
  deltas: MetricDelta[];
  /** Model mismatch: B compared with A. */
  model_deltas: MetricDelta[];
  observed_queue: QueueSample[];
  baseline_queue: QueueSample[];
  simulated_queue: QueueSample[];
  tracks: SimulatedTrack[];
  baseline_tracks: SimulatedTrack[];
  notes: string[];
  disclaimer: string;
}

export interface EvidenceFacts {
  observation_seconds: number;
  sampling_fps: number;
  vehicles_detected: number;
  vehicles_tracked: number;
  vehicles_crossed_entry: number;
  vehicles_crossed_exit: number;
  completed_queue_visits: number;
  censored_queue_visits: number;
  censored_seconds: number;
  registered_stops: number;
  slow_seconds_total: number;
  tracks: number;
  short_fragments: number;
  gaps: number;
  missing_sample_share: number;
}

export interface SensitivityPoint {
  service_time_seconds: number;
  peak_queue: number;
  average_wait_seconds: number;
  throughput_per_minute: number;
  vehicles_left_at_window_end: number;
}

export interface SensitivityRange {
  parameter: string;
  method: string;
  baseline_value: number;
  values: SensitivityPoint[];
  peak_queue_range: [number, number];
  average_wait_range: [number, number];
  note: string;
}

export interface DeleteResult {
  analysis_id: string;
  deleted_files: number;
  bytes_freed: number;
  message: string;
}

/**
 * Replay payload.  A track split into several `segments` was lost in between:
 * the position is unknown there, so nothing is drawn and no vehicle is shown.
 */
export interface TimelinePayload {
  duration: number;
  hz: number;
  sampling_fps: number;
  gap_threshold_s: number;
  track_gaps: number;
  vehicles: {
    id: number;
    class: string;
    queue_seconds: number;
    stopped_seconds: number;
    segments: { t: number[]; x: number[]; y: number[] }[];
  }[];
  queue: { t: number; q: number }[];
  vehicles_omitted: number;
  note: string;
}

export interface Health {
  status: "ok" | "degraded";
  model_loaded: boolean;
  device: string;
  model_name: string;
  message: string | null;
  processing_mode?: "local" | "queue";
}

export interface Meta {
  storage_mode?: "local" | "hosted";
  model_name: string;
  device: string;
  vehicle_classes: string[];
  sample_fps: number;
  speed_threshold: number;
  min_stop_seconds: number;
  allowed_extensions: string[];
  max_upload_mb: number;
  max_duration_seconds: number;
  stages: { key: string; label: string }[];
}


export interface UploadResponse {
  analysis_id: string;
  video: VideoInfo;
  status_url: string;
  result_url: string;
  message: string;
}
