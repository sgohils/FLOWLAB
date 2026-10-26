import { describe, expect, it } from "vitest";
import { simulationAnalysis, simulationFixture } from "../test/simulationFixture";
import { describeExperiment, experimentNote, peakQueueFinding, sensitivityFinding } from "./scenarioEvidence";

describe("experiment interpretation", () => {
  it("compares the changed model with its baseline, not the source measurements", () => {
    expect(peakQueueFinding(simulationFixture())).toBe("In this model, the peak queue falls by 4 vehicles.");
  });

  it("reports unchanged and worsened results without promising an improvement", () => {
    const run = simulationFixture();
    expect(peakQueueFinding({ ...run, simulated: { ...run.baseline } })).toContain("stays the same");
    expect(peakQueueFinding({ ...run, simulated: { ...run.simulated, peak_queue: 11 } })).toContain("rises by 1 vehicle.");
  });

  it("describes each returned setting and identifies the unmodified baseline", () => {
    const { scenario } = simulationFixture();
    expect(describeExperiment({ ...scenario, volume: 1, channels: 1 })).toContain("Unmodified baseline");
    expect(describeExperiment({ ...scenario, volume: 1.25, service_multiplier: 1.5, spread_seconds: 120, channels: 2 })).toBe(
      "25% more arrivals; exit processing at 1.50 times the baseline rate; arrivals spread over 120 extra seconds; 2 parallel exit channels.",
    );
  });

  it("warns when the scenario effect lies within the baseline sensitivity spread", () => {
    expect(sensitivityFinding(simulationFixture())).toContain("within that spread");
    expect(sensitivityFinding(simulationFixture())).toContain("not a confidence interval");
    expect(sensitivityFinding(simulationFixture({ sensitivity: null }))).toContain("uncertainty has not been quantified");
  });

  it("exports reproducible settings and separates effects from mismatch without exporting tracks", () => {
    const run = simulationFixture({
      scenario: { volume: 0.75, service_multiplier: 1, spread_seconds: 120, channels: 1, seed: 7 },
      tracks: [{ vehicle_id: 987654, arrival: 0, departure: 1, wait: 0, points: [[0, 0], [1, 1]] }],
    });
    run.simulated.observation_seconds = 240;
    const note = experimentNote(simulationAnalysis, run);
    expect(note).toContain("synthetic demo measurements, not real-world observations");
    expect(note).toContain('"seed":7');
    expect(note).toContain("Scenario model window: 240 s");
    expect(note).toContain("A=20; B=10; C=6; scenario effect (C-B)=−4; model mismatch (B-A)=−10");
    expect(note).toContain(run.fidelity.note);
    expect(note).toContain(run.disclaimer);
    expect(note).not.toContain("987654");
  });

  it("omits a private upload's original filename from the shareable note", () => {
    const analysis = {
      ...simulationAnalysis,
      source: "video" as const,
      video: { ...simulationAnalysis.video, filename: "private-family-school-location.mp4" },
    };
    const note = experimentNote(analysis, simulationFixture());
    expect(note).toContain("Source: video analysis");
    expect(note).not.toContain(analysis.video.filename);
  });

  it("keeps missing source wait measurements unavailable instead of treating them as zero", () => {
    const analysis = {
      ...simulationAnalysis,
      summary: { ...simulationAnalysis.summary, average_wait_seconds: null },
    };
    const run = simulationFixture();
    run.observed.average_wait_seconds = 0;
    const note = experimentNote(analysis, run);
    expect(note).toContain("Estimated mean wait (s): A=—; B=8; C=4; scenario effect (C-B)=−4; model mismatch (B-A)=—");
    expect(note).not.toContain("Estimated mean wait (s): A=0");
  });
});
