# Engineering decision log

Significant decisions, in the order they were taken. Each entry states the
**problem**, the **alternatives** considered, the **chosen approach**, a
**failure case** it is exposed to, and **how it was tested**.

Entries marked **[student task]** are the ones the student should own, re-derive
or challenge; they are listed in `docs/STUDENT_CONTRIBUTIONS.md` with acceptance
criteria.

---

## D1 — A dedicated replay payload instead of the thinned trajectory list

**Problem.** The map needs whole paths, but the analysis endpoint thins each
trajectory to 60 points to keep the payload small. After thinning, the interval
between consecutive samples reached 0.4 s while the tracking-gap threshold is
0.25 s — so a genuine one-sample dropout became indistinguishable from the
thinning itself. Any replay built on that data would either hide real gaps or
invent motion across them.

**Alternatives.**
1. Raise the thinning limit and interpolate everything (simple, but dishonest
   across gaps).
2. Add a `known` flag per sample (verbose: +30 % payload, and easy for a client
   to ignore).
3. Split every track into **segments** at gaps and let the segment structure
   carry the meaning.

**Chosen.** Option 3: `GET /api/analyses/{id}/timeline?hz=4` returns uniform-in-time
samples grouped into segments, and "position unknown" is expressed by the absence
of a segment. The queue series is recomputed from the same full-resolution tracks
at the analysis' own sampling rate, so the replay curve cannot disagree with the
reported peak.

**Failure case.** A track that flickers between two cells produces many
one-sample segments; the client hides the vehicle rather than jumping it, and
`track_gaps` in the payload reports the count so the fragmentation is visible.

**Tested.** `backend/tests/test_timeline.py` (9 tests), including
`test_a_tracking_gap_splits_the_track_and_position_is_unknown_inside_it`, which
asserts that `position_at` returns `None` at four instants inside a dropout.
Payload measured at 92 KB for 26 vehicles over 135 s.

---

## D2 — Subscribing leaves to the replay clock, not the page

**Problem.** The shared clock updates 60 times a second during playback. If the
page component subscribed to the context, every chart, the map and all six metric
cards would re-render on every frame.

**Alternatives.** (1) One context for everything; (2) a store with selectors;
(3) each leaf component subscribes to the slice it needs.

**Chosen.** Option 3. `ReplayTransport`, `QueueChart`, `TrafficMap`,
`VideoViewer` and `EventTimeline` each call `useReplay()`; the page component
(`AnalysisView`) holds only selection state and passes values down.

**Failure case.** With more than 120 vehicles the map draws live dots only for
the selection and any bottleneck highlight, so a long clip stays responsive; the
cap is explicit rather than silent.

**Tested.** Measured in the browser: the map redraws 26 dots per frame at 4 Hz
transport resolution, and the cursor line in the chart updates independently.

---

## D3 — Censor a queue visit that starts on the first frame

**Problem.** A vehicle already queueing when the clip opens has an unknown entry
time. Counting its residence as a measured wait biases the average in exactly
the situation school footage usually contains.

**Alternatives.** (1) Count it (what the first version did); (2) drop the whole
track; (3) keep the visit but mark it censored.

**Chosen.** Option 3. A visit is *complete* only when the vehicle was observed
outside the region first and then left it. Left- and right-censored visits are
counted and displayed but excluded from the averages.

**Failure case.** A clip that starts mid-queue reports fewer usable visits, so
the wait average is computed from fewer samples — the interface states the two
counts side by side rather than hiding it.

**Tested.** `test_visit_that_starts_at_the_first_frame_is_censored`,
`test_repeated_visits_are_separate_episodes`.

---

## D4 — One duration rule for "queued" and "stopped"

**Problem.** Queue length used no duration threshold while the stop detector
required 1.5 s, so a single noisy sample could create a queue entry but never a
stop. Two definitions of the same word is how a number stops meaning anything.

**Alternatives.** (1) Remove the stop threshold; (2) remove the queue threshold
(what it was); (3) give the queue its own threshold and apply it in both places.

**Chosen.** Option 3: `min_queue_seconds` (default 0.5 s) is applied to the queue
series *and* to the wait visits, so the two can never disagree. The cost is
measured, not assumed: the pipeline lags the raw rule by up to 0.5 s while a
queue grows, which is the entire explanation for the residual error in the
validation report.

**Failure case.** A long queue that dissipates in bursts produces shorter
episodes that now fall under the threshold and are not counted as waits; the
threshold is adjustable in the region editor.

**Tested.** `test_short_slow_pass_does_not_create_a_visit` and
`test_queue_series_also_applies_the_duration_threshold` assert the two code paths
agree, plus the ground-truth comparison in `docs/VALIDATION_REPORT.md`.

---

## D5 — Scenario effect against the baseline, model error separately

**Problem.** Showing "observed vs scenario" invites the reader to credit the
model's own error to the intervention.

**Alternatives.** (1) Two series; (2) three series with the error folded in;
(3) three series with the scenario effect measured against the baseline.

**Chosen.** Option 3. Every run computes the baseline anyway, so
`deltas` is C−B and `model_deltas` is B−A. The baseline always replays the
*original* arrival series, so a scenario cannot inflate its own fidelity number.

**Failure case.** If the scenario lengthens the window, throughput is not
comparable; the result adds a note saying so rather than printing a rate.

**Tested.** `test_scenario_effect_is_measured_against_the_baseline` and
`test_fidelity_is_independent_of_the_scenario`.

---

## D6 — Export the evidence, not just the number

**Problem.** A judge asking "where did 13 come from?" had nothing to click.

**Alternatives.** (1) A tooltip per card; (2) a separate evidence page; (3) a
disclosure inside the card that lists the contributing records.

**Chosen.** Option 3, with the evidence built in the page from data already
transmitted, and the vehicle ids that contributed to a bottleneck cell added to
the API so the map can highlight them. Peak queue shows the instant it was
reached, the grid resolution and the region source; throughput shows the crossing
count and the window; wait shows completed versus censored visits.

**Failure case.** With no completed visits the wait evidence shows why: the
censored count explains the empty average instead of showing a dash.

**Tested.** Checked in the browser: the Peak queue panel reports "Peak value 13
vehicles / First reached at 77.90 s", which reconciles with the chart and the
event timeline.

---

## D7 — Counts for line crossings, rate for capacity

**Problem.** The first exit-service-time estimate used the fastest quarter of
the departure gaps. On the demo scene that returned 1.0 s against a true 3.2 s,
because several lanes crossed the measurement line within one sampling instant.

**Alternatives.** (1) Fastest gap (what it was); (2) mean gap over the whole
clip; (3) highest sustained throughput while a queue existed.

**Chosen.** Option 3, because *counting* departures is robust to scatter in
crossing times while the gap is not. The result is explicitly a lower bound and
every fallback is written into the calibration notes.

**Failure case.** With no queue in the clip there is nothing to measure; the
fallback chain runs and the note says which step was used.

**Tested.** `test_calibration_falls_back_and_says_so`, plus the demo calibration
check, where the estimate is 4.29 s against a true 3.2 s.

---

## D8 — Question-first scenario controls

**Problem.** Four sliders do not tell a first-time user which way to turn them,
and moving a control left the previous result on screen looking current.

**Alternatives.** (1) Keep the sliders and label the percentages; (2) add presets
as plain parameter sets; (3) lead with the question, keep the sliders as the
fine control, and mark results stale on any change.

**Chosen.** Option 3. Each preset is a sentence a user would actually ask —
*"What if arrivals were spread over two extra minutes?"* — with the sliders
below it, and `stale` is computed against the *returned* scenario so it stays
correct even if the same scenario is re-run.

**Failure case.** Presets set all four parameters, so a partially adjusted state
is never half-reset.

**Tested.** In the browser: changing a control after a run marks the results
stale; re-running clears the mark.

---

## D9 — Print brief without footage

**Problem.** A competition submission benefits from a one-page document, but
footage of a real site cannot be printed by default.

**Alternatives.** (1) A PDF generator; (2) a print stylesheet on the analysis
page; (3) a dedicated brief route with its own print stylesheet.

**Chosen.** Option 3. The brief renders the region figure as SVG from anonymous
trajectories, runs the baseline scenario for the comparison, and contains no
video or frame. `docs/VALIDATION_REPORT.md` and the export endpoints are the
machine-readable equivalents.

**Failure case.** The brief is printed on a page background; `@media print` hides
the navigation and forces colour retention so the region figure is legible.

**Tested.** Rendered in the browser at 1000 px: all seven sections present, demo
label visible, and `document.querySelectorAll('video, img[blob]')` is empty.

---

## D10 — A tool for the failure I caused

**Problem.** Four source files were corrupted by a PowerShell edit pipeline that
read UTF-8 as ANSI. The interface showed `1280Ã—720` and the diff was clean
ASCII, so nothing caught it.

**Alternatives.** (1) Remember to be careful; (2) stop using the tool;
(3) repair the files and add a check that fails.

**Chosen.** Option 3: the four files were repaired, and
`python -m backend.scripts.check_encoding` now scans 98 files for byte-order
marks and cp1252 mojibake, with the signatures built from code points so the
checker cannot flag itself.

**Failure case.** New files edited through the same pipeline are caught on the
next verification pass.

**Tested.** `scanned 98 files: clean`, and the brief re-renders `1280×720`.

---

## Open questions for the student **[student task]**

1. Is 0.5 s the right `min_queue_seconds` for a school gate, or should it be
   tied to the sampling rate? The validation shows it is the dominant source of
   residual error; justify a different value with a measurement.
2. The exit service time is a lower bound. Would measuring the *median* gap
   during a saturation window be better for a single-lane gate, and what would
   it cost when a second lane is in use?
3. The digital twin has one gate. Before it could be used to compare "where to
   send cars", what would have to be modelled first, and which of it can be
   validated from a single fixed camera?
