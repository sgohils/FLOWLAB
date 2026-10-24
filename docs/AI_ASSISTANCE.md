# AI assistance disclosure

This project was built with AI coding assistance. This file records **what the
AI did and what it did not do**, so that nothing in the submission is mistaken
for independent student work.

The 2026 Congressional App Challenge rules allow AI assistance but require
disclosure and significant student contribution. Read
[the 2026 rules](https://www.congressionalappchallenge.us/wp-content/uploads/2026/05/2026-CAC-Rules.pdf)
and your district's requirements before submitting, and check whether they ask
for a separate disclosure form.

---

## Tools used

| Tool | Role |
| --- | --- |
| AI coding assistant (Kilo, running in Visual Studio Code) | wrote and modified code, ran tests, drove a headless browser to verify the interface |
| Git | version control, used by the student to review and keep changes |
| Python, Node, OpenCV, Ultralytics YOLO, Recharts, React | ordinary third-party libraries, not AI products |
| Chrome (headless) | automated screenshots to check that the interface renders |

No generative-image, text-to-video or external API service was used. The only
network access the application makes is the one-time download of the YOLO
checkpoint described in the README.

---

## What the AI produced

The large majority of the code in this repository was written or substantially
rewritten by the AI assistant. Concretely:

### Built from nothing (first session)

- The entire FastAPI backend: upload validation, the background job pipeline
  with nine progress stages, the API routes, error handling and the static file
  serving.
- The vision layer: YOLO detector wrapper, ByteTrack association, adaptive
  trajectory smoothing, the decode → detect → track loop and the annotated video
  renderer.
- The analytics layer: point-in-polygon geometry, the queue length series, queue
  episodes and censoring, stop detection, throughput and capacity estimation,
  the bottleneck grid, the event timeline, and the region-suggestion heuristic.
- The digital twin: the calibration module, the scenario transformations and the
  reduced Intelligent Driver Model corridor simulator.
- The entire frontend: Vite/React/TypeScript/Tailwind setup, three pages and
  fourteen components, the API client, the type definitions and the design
  system.
- The test suite, the demo dataset generator, the doctor script, the validation
  tooling and the documentation.

### Rewritten after a review pass (second session)

- Delete now removes the uploaded video, the annotated video, the result payload
  and the database row, and reports what it removed. The first version deleted
  only the database row.
- Export was added (JSON summary and three CSVs), with the original filename and
  local paths stripped because a filename can identify a school or a person.
- Interrupted jobs are marked failed on startup instead of showing "processing"
  forever.
- The first queue visit of a track is now censored when the vehicle was already
  inside the queue region at the first frame, so an unknown entry time is never
  reported as a measured wait.
- `min_queue_seconds` was added so the queue definition and the stop definition
  use the same duration rule.
- A crossing-direction policy was added, region validation gained
  self-intersection and repeated-vertex checks, and a minimum region area.
- The privacy claims in the interface were corrected: the old text said "no
  cloud calls" while the model weights are downloaded on first use, and said
  "no person data exists to store" while the uploaded footage is stored.
- The simulation result was restructured into a three-way comparison (observed,
  baseline, modified) so that the model's own error is never shown as the effect
  of an intervention.

### Bugs the AI introduced and then had to find and fix

These are listed because a defect that was introduced by AI and never noticed
would be a misrepresentation of the project's quality.

| Bug | How it was found |
| --- | --- |
| Queue length could exceed the number of vehicles (double counting across sampling instants) | validation against known ground truth, and a regression test |
| A second exit processing channel had no effect at all | a test asserting that two channels reduce the queue |
| Vehicles at the same position ignored each other, allowing overtaking | a test asserting no overtaking before the gate |
| Region edits silently changed the "vehicles detected" count | a regression test added after the defect was found by reading the code |
| `device=auto` was rejected by Ultralytics, killing every job | running the app, not a test |
| The frontend kept a stale analysis when navigating to the same route | reading the page during a review pass |
| The demonstration dataset's own entry line was placed behind some vehicles | the validation workflow |
| UTF-8 byte-order marks were written into eight Python files | linting during the review pass |

---

## What the AI produced, part 2 — the third session

The third session turned the application from a set of screens into one
instrument, and fixed defects found while doing it. All of it is disclosed here
because the rules require the extent of AI use to be stated.

### Rewritten or created

- **`backend/analytics/timeline.py`** — a replay payload with uniform-in-time
  samples and explicit tracking-gap segments, plus 9 tests. This exists because
  the audit found the thinned trajectory list made a real dropout
  indistinguishable from thinning, which would have produced invented motion in
  the replay.
- **`frontend/src/state/ReplayContext.tsx`** — one clock shared by the video,
  the trajectory map, the queue chart and the event timeline.
- **`frontend/src/components/AnalysisView.tsx`** — the analysis body, split out
  so it does not re-render once per frame, and carrying the "why?" evidence
  panels.
- **`frontend/src/components/ReplayTransport.tsx`**, **`CorridorComparison.tsx`**,
  **`PrintBrief.tsx`** — the transport bar, the side-by-side corridor animation
  and the printable brief.
- **`backend/scripts/check_encoding.py`** — a guard against a class of damage
  the AI itself caused (see the bug table below).
- `vehicle_ids` on bottleneck cells, so "click a cell, see its vehicles" is
  evidence rather than a claim.
- `vehicles_left_at_window_end` on the simulation metrics, and
  `baseline_tracks` for the animation.

### Defects the AI introduced in this session and then found

| Defect | How it was found |
| --- | --- |
| A replay built on thinned data could not distinguish a tracking dropout from the thinning itself, and would have drawn motion across it | audit, before any code was written |
| `CellStats.vehicles` was cleared before the ids could be reported, so "highlights 0 vehicles" | a browser check that reported `Highlighting 0 vehicles` |
| Four source files were corrupted into cp1252 mojibake (`1280Ã—720`) by a PowerShell edit pipeline; the diff looked clean | a screenshot of the printable brief |
| The delete implementation returned a byte size where a file count was expected (`assert files == 3` failed with `5369`) | a new test |
| The simulated window drifted past the clip (135 s observed vs 138.2 s simulated), which made the throughput comparison invalid | the scenario notes complaining about incomparable windows |
| The demo's own entry line sat behind the vehicles in an outer lane, so 2 of 26 arrivals were never counted | the ground-truth validation |

Each of these has a regression test or a tool that would have caught it. The
mojibake incident is the clearest argument for the `check_encoding` guard: the
damage was invisible in a diff and would have been easy to ship.

---

## What the AI produced, part 3 — the fourth session

The fourth session began with an assessment rather than an edit, and three of
its findings were correctness or trust problems in work the AI had already done.

### Defects the AI introduced earlier, found in this pass

| Defect | How it was found | Status |
| --- | --- | --- |
| The queue chart could show a **smaller** peak than the metric card, because every-nth decimation silently drops a brief peak | wrote `trace_metric.py` to re-derive a value from raw samples, then probed the thinning directly with a synthetic one-instant spike | fixed: buckets keep the **max**, plus the ragged tail (3 tests) |
| A fragmentation metric computed inside the AI's own new code compared a running total against a per-track count, reporting **913 % missing samples** | the number was impossible; traced to the loop | fixed, now 0 % on clean data |
| The analyses list showed **33 vehicles for the demo** while the detail page showed 26, because the list reads the stored summary and the demo file had been regenerated | listing stored analyses after regenerating the demo | fixed: `register_demo()` refreshes the row from the bundled file (2 tests) |
| On a clip with no vehicles, `why?`, the map and "Simulate a scenario" were all dead ends | uploaded a synthetic empty car park and looked at the page | fixed: reasons on unavailable cards, map empty state, simulate disabled |
| Two earlier false "bugs" in this pass were the **test harness**, not the app: case-sensitive searches against CSS-uppercased text, and a same-hash navigation that never reloaded the page | read the rendered DOM instead of trusting a failed matcher | harness corrected; no product change |

### Created or changed in this pass

- `backend/scripts/trace_metric.py` — re-derives a displayed metric from the raw
  samples and checks it against the grid, the API and the event list.
- `Evidence` — a block of counts (crossings, completed versus censored visits,
  tracking gaps, missing-sample share, window) surfaced as an "Evidence and
  assumptions" panel, with a *thin evidence* warning.
- `service_time_sensitivity` — a **sensitivity range** over the one estimated
  parameter, explicitly not a confidence interval.
- `MetricCard.unavailableReason`, a map empty state, a disabled simulate link,
  and a demo-header fix that omits a meaningless file size.
- `docs/PROJECT_ASSESSMENT.md`, `docs/VERIFICATION.md`, and decisions D11–D14 in
  `docs/ENGINEERING_DECISIONS.md`.

### What this pass did not do

- It did not re-tune the demo scene. The sensitivity range makes the model's
  dependence on the estimated service time visible rather than hiding it.
- It did not add a confidence score, because none has been computed.
- It did not annotate real footage.

---

## What the AI produced, part 4 — the fifth session (2026-09-29)

### The design decision is the AI's

The user set out the problem — the annotator instructions describe a pure
region count, the application reports slow-and-held vehicles, and the validation
report could not say which of a missed detection, a duplicate id or a definition
gap produced a difference — and instructed the AI to resolve it. The AI chose
**option (b)** of D15 in [`docs/ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md):
compare the human counts against a new region-occupancy series and report the
queued count alongside it. The choice between the options, the reasoning and the
stated failure case are the AI's, not the student's.

### Written in this session

- `build_region_occupancy_series` in `backend/analytics/queue_detection.py`, a
  purely geometric count on the same grid as the queue series.
- `Analysis.region_occupancy_timeseries` in `backend/models/schemas.py` and its
  wiring in `backend/analytics/metrics.py`.
- `backend/scripts/validate_against_reference.py`: the two comparison blocks,
  their `compares_against` labels, and the fallback for results stored before
  this change.
- Five tests: four in `backend/tests/test_queue.py` and one in
  `backend/tests/test_evidence.py`.
- The D15 entry in `docs/ENGINEERING_DECISIONS.md`, and the rewrite of the
  `queue_counts` and `queue_visits` instructions in
  `backend/validation/README.md` so the annotator's rule matches what the
  application measures.

### What this session did not do

- **The student has not annotated any footage.** No real clip has been compared
  against a human count, before this change or after it. Part B of
  `docs/VALIDATION_REPORT.md` remains PENDING and still contains no accuracy
  number. Nothing above should be read as student work or as evidence of
  detector accuracy.
- It did not change the wait estimate, the summary, the calibration or the
  evidence block; the application still defines "queued" exactly as it did.
- That first change did not regenerate the demo dataset or the stored
  validation report. A later change in the same session did; see below.

### Later the same session

The change above was followed by a second one, on the same day, once the
comparison had actually been run.

- The AI found that `backend/analytics/simulation_truth.py` — the generator
  that produces the synthetic ground truth — emitted only `queue_counts`, the
  SLOW rule, while `backend/scripts/validate_against_reference.py` had been
  changed to compare the application against the new REGION OCCUPANCY series.
  The two are different quantities, so the comparison was measuring the
  difference between the speed-and-hold rule and a hand-taken count rather
  than the detector. The defect was **masked at the time**: the stored demo
  analysis predated the occupancy field, so the script fell back to the queued
  series and the fallback was enough to make the run look consistent.
- The fix was to give the ground truth an `occupancy_counts` series under the
  same purely geometric rule, and to make the validation script prefer
  `occupancy_counts` when the reference file carries one, labelling in
  `compares_against` which reference series was used either way.
- The AI then found that the figures quoted across the documentation
  (**0.211 vehicles, max 3, 79.8 %**) were **stale**: they had been generated
  before D11 changed the series thinning to a bucket maximum. A fresh run of
  the same comparison read **0.188 vehicles, max 2, 81.8 % exact** for the
  slow-rule block. The cause was established empirically, by re-running with
  the reference held fixed and only the decimation varied, and is recorded as
  D11 in `docs/ENGINEERING_DECISIONS.md`.
- `backend/demo/sample_analysis.json`, `backend/demo/sample_reference.json`,
  `docs/validation-measurement.md` and `docs/validation-measurement.json` were
  regenerated, and the quoted figure was corrected in `README.md`,
  `docs/VERIFICATION.md`, `docs/VALIDATION_REPORT.md`,
  `docs/PROJECT_ASSESSMENT.md`, `docs/JUDGE_QA.md`, `docs/SUBMISSION_DRAFT.md`,
  `docs/DEMO_SCRIPT.md` and `docs/ENGINEERING_DECISIONS.md`. The like-for-like
  occupancy result — **0.028 vehicles, max 1, 97.2 % exact** — was added
  alongside the slow-rule result wherever the figure is quoted. In
  `docs/READINESS_AUDIT.md`, entry D22 was **deliberately not rewritten**: it
  is a record of what was true when that defect was found, so a dated note
  recording the superseded figure was appended instead.
- `backend/tests/test_truth.py` was added, with six tests covering the new
  reference series, the relationship between the two rules, the script's
  preference for `occupancy_counts`, the labelled fallback, and a reference
  carrying no count series at all.

None of this was student work, and none of it is a real-world accuracy result:
the ground truth is still produced by this project's own simulator, and no real
clip has been compared against a human count. Part B of
`docs/VALIDATION_REPORT.md` remains PENDING.

---

## What the AI produced, part 5 — the sixth session (2026-09-30)

This session was an engineering pass, not a feature session, and it was
AI-driven from end to end: the plan, the code, the test names, the commits'
worthiness and this disclosure. Nothing in it is student work.

### The two defects that had shipped

These are the headline of this pass, and they are listed first because they are
the argument for everything else in it.

| Defect | How the AI found it | Status |
| --- | --- | --- |
| `backend/api/jobs.py` passed `status="error"` to a parameter named `status_value`, which collides with the helper's first positional argument, so `TypeError` was raised on the line *before* the database write in the job-failure path. Every failed analysis stayed at `processing` in SQLite until the next restart, and the user saw a job that would never finish. | enabling mypy, **not** a test: the previous suite had 200 tests and none of them exercised a failing analysis | fixed; `backend/tests/test_job_failure.py`, 4 tests, 3 of which fail if the old keyword returns |
| `Database._connect()` returned a bare `sqlite3.Connection` and every caller used `with self._connect()`, which in sqlite3 ends a transaction and does not close the connection. Every read and every write leaked a handle. | setting `filterwarnings = ["error"]`, which turned the leak into 8 failing tests pointing at the line | fixed; `_connect()` is now a `@contextmanager` that closes in a `finally`; `backend/tests/test_database.py`, 6 tests |

Both were in code the AI had written in an earlier session. Both had survived a
review pass, a green suite, and repeated use of the application by hand. The
honest conclusion is not "the AI made mistakes" - it is that the project had no
mechanism that could have found them, and that is a process failure.

### Further defects found and fixed in this session

Backend: `backend/vision/__init__.py` exported `VehicleDetectionError`, a name
that does not exist, so `from backend.vision import *` raised `AttributeError`;
the single page app route served any path under its own name with no containment
check; `PUT /analyses/{id}/regions` ignored the map-resolution query parameter
that `GET .../result` honoured; `doctor.py` reported "ok" for dependency
versions whatever was installed, which is how an OpenCV 5.0.0 install survived a
declared `<5` bound.

Frontend: a helper that threw on a malformed stored record; a replay cursor that
disagreed with the backend before the first sample; a guard whose two branches
were identical; a tooltip rendering the literal text `still queued}s`; a caption
claiming a simplification the code did not perform; a menu with the wrong ARIA
roles; two places where the TypeScript mirror of the API contract had drifted
from the Pydantic model, once in each direction.

Product and accessibility: two endpoints that existed, were tested and had no
interface; scenario presets hardcoded in the frontend that had drifted from the
endpoint serving them; a dead `CorridorMap` component; and on-screen help that
promised a keyboard action nothing implemented.

### What was created

- `backend/geometry.py`, a dependency-free geometry module, with
  `analytics/geometry.py` reduced to a re-export shim, so the schema layer and
  the analytics layer can share one shoelace implementation without a cycle.
- `pyproject.toml` (ruff, mypy, pytest with warnings-as-errors, coverage),
  `backend/requirements-dev.txt`, `.editorconfig`, `.pre-commit-config.yaml`,
  `.github/workflows/ci.yml`, a root `.dockerignore` and `CONTRIBUTING.md`.
- A frontend test runner that did not exist: vitest, `@testing-library/react` and
  jsdom, four test files, 50 tests.
- Ten new backend test files' worth of coverage: 200 -> **277** tests, plus the
  dead-code removal (including three `# type: ignore` comments and one
  un-annotated parameter, all gone).

### Were the verification commands actually run?

Yes, and the output is pasted verbatim in [`VERIFICATION.md`](VERIFICATION.md)
rather than summarised: the pytest run, ruff, mypy, the encoding check, the
coverage table, the frontend typecheck, tests and build, the environment doctor,
a traced metric and the ground-truth validation. Where a command could not run,
it says so in that document rather than being quietly omitted: Docker is not
installed, so `docker compose build` has never executed; CI has never executed;
only Python 3.13 is present, so the 3.11 leg of the matrix has not run; and the
browser was not re-driven, so this pass's interface changes are type-checked but
unseen.

### What this session did not do

- It did not validate the detector on real footage. Part B of
  `docs/VALIDATION_REPORT.md` is still PENDING and still contains no accuracy
  number.
- It did not soften a single limitation. The 0.54 model-mismatch factor, the
  missing camera calibration, the unmeasured sampling sensitivity, the ambiguous
  single-vehicle queue and the unverified container path are all still stated
  plainly, in the same words.
- It did not change any measurement definition. The ground-truth figures
  (0.028 and 0.188 vehicles) were re-run and are unchanged.
- It did not touch the Dockerfile, the CI workflow, `run.bat`/`run.sh` or any
  frontend source file after the engineering waves finished; the documentation
  pass that followed edited `README.md` and `docs/` and nothing else.

---

## What the AI did not do

- It did not invent a story about the project. The motivation, the school
  context, the problem the student wanted to solve and the decisions about scope
  are either the student's own words in `docs/STUDENT_CONTRIBUTIONS.md` or are
  left blank for the student to complete.
- It did not create any accuracy claim, user interview, testimonial, deployment
  or congestion-reduction figure. Where such evidence is missing, the
  validation report says the evidence is pending.
- It did not run the real-world validation, because that needs a clip the student
  is permitted to use and annotations the student writes.
- It did not submit anything, publish anything, or contact anyone.

---

## How AI-written code was reviewed

Every change made in the second session followed the same loop:

1. **Reproduce first.** The defect was demonstrated with a command and its
   output was written into `docs/READINESS_AUDIT.md` before anything changed.
   No defect was "fixed" on suspicion.
2. **Write the test that would have caught it.** The regression test was added
   alongside the fix, using hand-calculated expectations on small synthetic
   trajectories rather than snapshots of current behaviour.
3. **Run the whole suite.** The full suite, then the production build, then the
   browser.
4. **Drive the interface, don't assume it.** The replay, the stale marker, the
   evidence panel and the print brief were each exercised through a headless
   browser script that reads the rendered DOM, because "it compiles" is not
   evidence that a button does anything.
5. **Update the documentation in the same change.** The metric definition, the
   README and the interface text were changed together, so the code and the
   claims could not drift apart again.

The student is expected to be able to explain the code that ships. The questions
in `docs/JUDGE_QA.md` were written to test exactly that, and the exercises in
`docs/STUDENT_CONTRIBUTIONS.md` are the parts of the system the student should
implement, change and defend personally. `docs/ENGINEERING_DECISIONS.md` records
25 design decisions with their alternatives, the failure case each is exposed to
and how it was tested, so the student can challenge any of them.

---

## What the student still has to do

See `docs/STUDENT_CONTRIBUTIONS.md`. In summary:

- Complete the annotated validation on a real clip (the AI cannot annotate
  footage the student has permission to use on the student's behalf).
- Own at least one implemented change, with the design decision written down.
- Write the motivation, the story and the reflection in their own words.
- Verify the district and national requirements, including whether a separate
  AI-use disclosure form is required.
