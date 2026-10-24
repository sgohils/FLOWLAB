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

**Tested.** `backend/tests/test_timeline.py` (11 tests as of 2026-09-30), including
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
queue grows, which is the entire explanation for the 0.188-vehicle gap in the
`queue_length_app_definition` block of the validation report. The
like-for-like region-occupancy comparison applies no hold and is unaffected.

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

**Tested.** `scanned 98 files: clean` at the time. The count has grown
with the repository: on 2026-09-30 the same command reports `scanned 120 files: clean`,
and the brief still renders the resolution correctly.

---

## D11 — Decimate the queue series by bucket maximum, not every n-th sample

**Problem.** The queue series is a step function sampled at 10 fps, and the
transport caps it at 900 samples. Taking every *n*-th sample drops any peak
shorter than the stride, so the chart could show a smaller number than the
metric card beside it.

**Alternatives.** (1) Keep every-nth (what it was); (2) send the full-resolution
series (a 10-minute clip becomes ~3 MB); (3) aggregate each bucket with `max`.

**Chosen.** Option 3. The displayed series becomes coarser but *faithful*: it can
never under-report a queue, and the ragged tail is kept rather than dropped,
because a remainder is exactly where a short peak hides.

**Failure case.** `max` per bucket makes the displayed average slightly higher
than the true time-average. That direction is deliberate — over-reporting is
recoverable, under-reporting is not — and the card shows the exact value.

**Tested.** `test_thinned_series_never_loses_a_brief_peak` puts a one-instant
spike on an odd index and asserts every-nth would return 0 while the new
thinning returns 7; two more tests cover the ragged tail and monotonicity.

---

## D12 — Say "unavailable", and remove controls that cannot work

**Problem.** On a clip with no detected vehicles the interface showed `—` for
every measurement but still offered a *why?* button that could explain nothing,
an empty map with no explanation, and a "Simulate a scenario" link the API then
refused.

**Alternatives.** (1) Leave it — the numbers were already honest; (2) hide the
page; (3) state the reason inline and remove the dead affordance.

**Chosen.** Option 3. A dash with no reason reads as a bug, and a control that
leads to a refusal reads as an unreliable product. `MetricCard` takes
`unavailableReason` and hides *why?* when nothing was measured, the map renders
an explicit empty state, and the simulate link is disabled with a `title`
explaining why.

**Failure case.** An unavailable reason can itself be stale; it is derived from
the same summary the cards show, so they cannot disagree.

**Tested.** Uploaded a synthetic empty car park: `tracked=0`, every card carries
a reason, the map says "Nothing to plot", the link is disabled, and zero `why?`
buttons remain.

---

## D13 — Publish the evidence, and a sensitivity range for the one estimate

**Problem.** A judge could not see what the measurements were made *from*, and
the exit service time — the only parameter the application estimates rather than
counts — had no visible influence.

**Alternatives.** (1) More prose; (2) an overall confidence score; (3) counts
plus a re-run under stated alternative values.

**Chosen.** Option 3. `Evidence` is a block of counts (crossings in and out,
completed versus censored visits, tracking gaps, missing-sample share,
observation window) and the panel flags the evidence as thin below five tracks or
above 15 % missing samples. The sensitivity re-runs the baseline at 0.75x, 1.0x
and 1.5x the estimated service time and reports the spread, explicitly labelled
*not a statistical confidence interval*.

**Failure case.** `Evidence` defaults every field, so a result stored by an older
build still loads and the panel says so instead of showing zeros as measurements.

**Tested.** `test_an_analysis_stored_by_an_older_build_still_loads`,
`test_fragmentation_reports_gaps_and_missing_samples`,
`test_sensitivity_range_spans_the_stated_alternative_values`; in the browser the
panel shows 7/7 expected rows and the sensitivity table shows 12 → 14 → 17 peak
queue for 3.2 / 4.3 / 6.4 s.

---

## D14 — The bundled demo file is the source of truth for its own summary

**Problem.** The analyses list reads a stored summary, so regenerating the demo
dataset left the list showing 33 vehicles while the detail page showed 26.

**Alternatives.** (1) Accept the drift; (2) remove the demo from the list;
(3) refresh the stored row from the bundled file on every start.

**Chosen.** Option 3: `register_demo()` rewrites the stored video metadata and
summary each time, so the file can never be contradicted by the database.

**Failure case.** None observed; it is two small rows on startup.

**Tested.** `test_demo_record_is_refreshed_from_the_bundled_file` seeds a wrong
summary, calls `register_demo()`, and asserts the row matches the file.

---

## D15 — Compare like with like: region occupancy beside the queued series

**Problem.** The annotator instructions tell a person to pause the frame and
count the vehicles inside the queue region, which is a purely geometric
observation. The application's queue series additionally requires the vehicle to
be below `speed_threshold` and to stay there for `min_queue_seconds`. The
validation script compared the two directly, so a difference could mean a missed
detection, a duplicate id, or a definition gap, and the report could not say
which of the three it was.

**Alternatives.**
1. Annotate the application's slow-and-held rule by eye.
2. Compare against a new region-occupancy series and report the queued count
   alongside it.
3. Make region occupancy the headline metric and demote the slow rule.

**Chosen.** Option 2. `build_region_occupancy_series` counts every vehicle
geometrically inside `regions.queue` on the same time grid, with no speed
threshold and no hold, and is stored as `Analysis.region_occupancy_timeseries`.
The report's `queue_series` block now compares the hand-taken counts against it
and carries a `compares_against` label saying so; a second block,
`queue_length_app_definition`, compares the same instants against the queued
series. Option 2 keeps both the human observation and the application's
definition visible and separately attributable, so a disagreement can be read.
Option 1 was rejected because a paused frame cannot show whether a vehicle is
slow, so a hand-annotated "queued" count would be a guess presented as a
measurement. Option 3 was rejected because it would make the headline metric
disagree with the definition the wait estimate and the interface use.

**Failure case.** A badly placed polygon makes the occupancy count wrong in the
same way on both sides, so a matching total can still mean two different
mistakes. A matching aggregate never proves the individual vehicles were
detected and tracked either, because a missed vehicle and a duplicate id cancel
out in a total; the report says so where the number is printed. A result stored
before this change has no occupancy series, so the script falls back to the
queued series and records that in `compares_against` rather than reporting a
like-for-like comparison it cannot make.

**Tested.** `test_region_occupancy_counts_a_vehicle_that_is_moving`,
`test_region_occupancy_never_exceeds_the_vehicle_count`,
`test_region_occupancy_ignores_the_minimum_queue_seconds` and
`test_region_occupancy_requires_a_region` in `backend/tests/test_queue.py`, plus
`test_a_result_stored_before_the_occupancy_series_still_loads` in
`backend/tests/test_evidence.py`. The double-count test is the same shape as
`test_peak_queue_can_never_exceed_the_vehicle_count`: deleting the forward-only
cursor makes the peak 10 for 5 vehicles, so the test fails on the defect it
exists to prevent rather than passing vacuously.

---

## D16 — Pure geometry lives in its own dependency-free module

**Problem.** `polygon_area` was implemented twice: once in
`backend/analytics/geometry.py` and once, identically, inside
`backend/models/schemas.py`, because `schemas.py` needs an area to reject a
too-small measurement region at validation time and could not import the
analytics one. `analytics/__init__` imports `analytics.metrics`, which imports
`models.schemas`, so `models.schemas` importing from `analytics` is a cycle.
Two copies of a shoelace loop is two definitions of "how big is this region",
which is exactly the kind of drift the rest of this log exists to prevent.

**Alternatives.**
1. Leave the duplicate and add a comment.
2. Move the primitives into `models/`, since that is where the second copy
   already lived.
3. Extract them into a module that imports nothing from the project.

**Chosen.** Option 3: `backend/geometry.py` holds `polygon_area`,
`polygon_centroid`, `point_in_polygon`, `first_crossing_time`,
`line_intersection`, `simplify_polyline` and `point_segment_side`. It imports
only `collections.abc` and `typing`, so it can never be part of a cycle.
`backend/analytics/geometry.py` is now a re-export shim, so every existing
import keeps working and there is exactly one implementation.
`schemas.polygon_area` is that same function object, not a copy.

Option 2 was rejected for the reason the module docstring gives: putting the
primitives in `models/` means every geometry computation imports the pydantic
API contract, and the dependency arrow points the wrong way.

**Failure case.** The rule that keeps this module safe is that anything added
here must depend on nothing but the standard library. The moment a helper needs
a pydantic model or an analytics result, the module becomes the place a cycle
can start.

**Tested.** `backend/tests/test_package_layout.py`:
`test_backend_geometry_imports_nothing_from_the_project` reads the source and
asserts the ban, `test_schemas_import_without_loading_analytics` proves the
reverse edge stays absent, `test_region_validation_uses_the_shared_area_function`
asserts `schemas.polygon_area is geometry.polygon_area`, and
`test_the_analytics_geometry_shim_reexports_the_shared_objects` asserts the two
import paths are the same functions. `backend/tests/test_geometry.py` covers the
primitives themselves.

---

## D17 — `api_error()` is the only way a route raises a 4xx

**Problem.** The client contract is one error shape,
`{"message": ..., "hint": ...}`, and the frontend parses exactly that. The
helper existed in `backend/api/errors.py` and was used in one place; the rest
of the routes raised `HTTPException` with a dict detail, or let a `ValueError`
become a 500. Two shapes in flight is one more thing the client has to guess
about, and it is exactly the shape that produced the "the API failed" reports
this project cannot debug from a screenshot.

**Alternatives.** (1) Leave it and normalise in the client; (2) a middleware
that rewrites every error; (3) one helper every route calls.

**Chosen.** Option 3, and `CONTRIBUTING.md` house rule 5 states it as an
invariant rather than a suggestion. `hint` is the sentence that tells the user
what to *do*, which is a different job from explaining what went wrong.

**Failure case.** A route that raises a bare `HTTPException` still produces a
valid response; the enforcement is by convention plus review, not by a test
that walks every route. That is a known weakness, and the middleware rewrite
was rejected because normalising after the fact means the route's own code can
still contradict what the client receives.

**Tested.** `backend/tests/test_api.py` asserts the shape on the upload,
region and delete failures. A route-by-route lint for bare `HTTPException`
outside `errors.py` would be the next step and has not been written.

---

## D18 — ruff, mypy and coverage are CI gates; mypy assumes Python 3.12

**Problem.** `python -m pyflakes backend` was the only static check, it ran
locally by hand, and nothing failed if it was skipped. A gate nobody runs is a
comment.

**Alternatives.** (1) Keep pyflakes and add it to `run.bat check`; (2) add ruff
and mypy to the local scripts only; (3) make them CI gates that block a merge.

**Chosen.** Option 3, with the configuration in `pyproject.toml` so the rules
live next to the code they judge. The ruff rule set is deliberately small and
chosen for defect shapes rather than taste (`E,F,I,UP,B,C4,SIM,RET,PTH,ARG,N,RUF`);
bandit is not enabled because its findings on a local-only analysis tool are
noise. Coverage is measured with `branch = true`; `backend/scripts` is omitted
because it is operator tooling measured by its own assertions.

`python_version = "3.12"` in `[tool.mypy]` is a deliberate deviation from
`requires-python = ">=3.11"`, and the config says why in full: numpy >= 2.3
ships PEP 695 `type` statements in its stubs, which mypy cannot parse under 3.11
semantics, so with 3.11 it stops dead before reading a line of this codebase.
Per-module `python_version` is not an escape hatch; mypy removed it. The fix is
to pin `numpy<2.3`, not to change the number. The package still supports 3.11
and CI runs the whole suite there, so a stray 3.12-only syntax slip is caught by
the 3.11 job rather than shipped.

**Failure case.** The type checker assumes a *language version*, not a
runtime. A construct that is valid in 3.12 and invalid in 3.11 passes locally
and fails in the 3.11 CI leg. That is the accepted cost of being able to read
the numpy stubs at all.

**Tested.** `python -m mypy` reports "Success: no issues found in 38 source
files"; `python -m ruff check backend` reports "All checks passed!". Both run in
`.github/workflows/ci.yml` on every push and pull request. The 3.11 leg has
never executed, because only 3.13 is installed on the development machine.

---

## D19 — Warnings are errors, with exactly one ignore

**Problem.** `pytest` reported "1 warning" and the suite passed. Turning
`-W default` up by hand showed roughly 107 warnings, of which essentially all
were `PytestUnraisableExceptionWarning` from unclosed sqlite3 handles, plus one
third-party deprecation from inside starlette. A warning nobody reads is not a
gate.

**Alternatives.** (1) Leave warnings visible; (2) filter the known-noisy ones;
(3) `filterwarnings = ["error"]` plus narrowly justified exceptions.

**Chosen.** Option 3. It is what turned the SQLite leak (D20) from an invisible
problem into eight failing tests. Exactly one filter sits below `error`, and it
is not discretionary: `fastapi.testclient` imports starlette's TestClient shim,
which warns at import time from inside `site-packages/starlette/testclient.py`
that it wants `httpx2` instead of `httpx`. There is no line in this repository
to fix, so it is suppressed by exact category plus message and will start
failing the day starlette is bumped past the upstream fix. The comment in
`pyproject.toml` says all of this.

**Failure case.** A new third-party warning turns into a red suite that looks
like a product defect. That is the intended trade: a noisy gate gets widened
deliberately and in writing, never quietly.

**Tested.** `python -m pytest` passes with 277 tests and prints no warning
summary at all.

---

## D20 — One SQLite connection per operation, owned by a context manager

**Problem.** `Database._connect()` returned a bare `sqlite3.Connection` and
every caller wrote `with self._connect() as connection:`. In the sqlite3 API
that context manager ends the *transaction*; it does not close the connection.
Every read and every write therefore leaked a file handle until the cyclic
collector happened to run.

**Alternatives.**
1. A connection pool (the textbook answer).
2. One long-lived connection guarded by the existing lock.
3. Keep one connection per operation but make `_connect()` actually close it.

**Chosen.** Option 3. `_connect()` is now a `@contextlib.contextmanager` that
keeps `with connection:` inside it, so commit-on-success and rollback-on-error
are unchanged, and closes in a `finally`. Option 1 was rejected as overbuilt: a
single-user local tool with one worker thread gains nothing from a pool, and a
pool introduces a second lifetime question ("when is it safe to return this
connection?") on top of the one being fixed. Option 2 was rejected because a
connection shared across threads needs `check_same_thread=False` and moves the
concurrency question rather than answering it; the existing `threading.Lock`
already serialises writers.

**Failure case.** `PRAGMA journal_mode=WAL` is re-issued per connection. It is
persistent, so this is a redundant statement rather than a bug, but it is the
line most likely to matter if the file is ever moved to a network filesystem.

**Tested.** `backend/tests/test_database.py`, six tests: connections opened
equal connections closed, a double-close raises `ProgrammingError`, the WAL mode
and the lock behaviour still hold, and the suite passes with
`filterwarnings = ["error"]`, which is what fails outright on the old code with
eight unclosed-database warnings.

---

## D21 — vitest and Testing Library, and not snapshot tests

**Problem.** The frontend had no test runner at all. `tsc -b` proved the
components type-checked; nothing proved that pressing a button did anything.

**Alternatives.** (1) Playwright end-to-end tests; (2) vitest with snapshots;
(3) vitest with React Testing Library and jsdom.

**Chosen.** Option 3. The tests reuse the application's own Vite config, so the
`@` alias and the React plugin are identical to the build and a test can never
resolve a module the bundler would not. `globals: false`, so every test names
what it uses and a deleted import is an error rather than a mystery
`ReferenceError`.

Snapshots were rejected over assertions deliberately. A snapshot of a rendered
tree is a picture of the component as it was; it passes when the component
regresses as long as someone updates the snapshot, and it says nothing about
what the user can see. `screen.getByText("7")` is a claim about behaviour that
has to be re-derived every time the wording changes.

**Failure case.** jsdom is not a browser. It cannot measure a frame rate, it
does not lay anything out, and it cannot tell you a control is off screen. Any
claim that depends on layout or paint is outside what this suite can support and
has to be checked by driving a real browser.

**Tested.** `cd frontend && npm test`: 4 files, 50 tests, all passing. The
files are `utils/format.test.ts`, `types/index.test.ts`,
`state/ReplayContext.test.tsx` and `components/Primitives.test.tsx`, colocated
with the code they cover.

---

## D22 — `noUncheckedIndexedAccess` is deliberately off

**Problem.** TypeScript's `noUncheckedIndexedAccess` makes every
`array[i]` a `T | undefined`, which is the correct model for data arriving from
outside the program and the wrong model for a `[x, y]` coordinate pair that the
same function just built.

**Alternatives.** (1) Turn it on and fix all 41 diagnostics; (2) turn it on with
`!` where it is inconvenient; (3) leave it off and record the decision.

**Chosen.** Option 3, recorded as a comment in `frontend/tsconfig.json` next to
the setting. Enabling it was measured at 41 diagnostics across the source, and
nearly all of them are indexing the code already proves safe by construction: a
pair of `[x, y]` coordinates, a bracketing pair from a binary search in the
replay. Turning it on would mean sprinkling non-null assertions through the
replay maths and the region editor, which are the two places where an assertion
is least likely to be re-checked by whoever reads it next.

The honest fix is tighter payload types, not more assertions. That is the
condition under which the comment says to revisit this.

**Failure case.** A payload that arrives malformed from the API is not caught by
the compiler. `hasQueueRegion` is the place where that already bit, and it is
now guarded by a runtime check instead, which is the trade this setting makes.

**Tested.** `npm run typecheck` is clean with `noImplicitOverride` enabled and
`noUncheckedIndexedAccess` off. `ReplayContext.test.tsx` exercises the replay
clock's edge cases, which is the code the setting would have made noisier.

---

## D23 — Presets come from the backend, with a labelled offline fallback

**Problem.** The scenario presets were hardcoded in the frontend while
`GET /api/analyses/{id}/simulation/presets` served the real ones. Nothing
compared the two, and they had drifted: the panel was offering scenarios the API
would not recognise.

**Alternatives.** (1) Keep the hardcoded list and delete the endpoint;
(2) fetch from the API with no fallback; (3) fetch from the API, keep the
built-in list only for when the request fails, and say so on screen.

**Chosen.** Option 3. Option 1 would have been simpler and honest, but a
simulator with no scenarios at all is a worse outcome than one with slightly
stale ones. Option 2 makes the whole panel depend on a round trip that can fail
for reasons the user cannot see.

**Failure case.** The fallback list is stale, which is precisely why it is
visibly marked: a caution pill reading "built-in presets" and a caution
paragraph in the panel, so a user is never left guessing which list they are
looking at. A preset the backend does not recognise gets a label generated from
its own numbers rather than being silently dropped.

**Tested.** No automated frontend test covers the panel's fetch and fallback
path; it is verified by reading `SimulationPanel.tsx` and by type-checking. This
is a gap, and the honest thing is to say so rather than to imply coverage.

---

## D24 — `docker compose` ships one app, with the dev server behind a profile

**Problem.** Two services by default meant two origins to configure, a CORS
question to answer, and a Vite dev server that started whether or not anyone was
editing React.

**Alternatives.** (1) Two services, always; (2) one service, no dev server in
compose at all; (3) one service by default, dev server behind a profile.

**Chosen.** Option 3. `docker compose up --build` builds the production frontend
bundle in a first stage of `backend/Dockerfile` and serves it from the same
origin, so there is no second process to keep in sync. The Vite server is what
you want while editing React, and `docker compose --profile dev up` is the only
way to get it. Only that second service needs `FLOWLAB_CORS_ORIGINS` to include
the Vite origin, because only it is a different origin. Both published ports
bind to `127.0.0.1`.

**Failure case.** Someone editing React expects a dev server, gets a stale
bundle, and concludes the change did not work. The README states both commands
and says which is which.

**Tested.** `docker-compose.yml` parses as YAML and declares exactly those two
services, that one profile and those two loopback port mappings;
`backend/tests/test_dockerignore.py` (47 tests) proves the root `.dockerignore`
cannot delete a file either Dockerfile copies. **`docker compose build` has never
been run**, because Docker is not installed on the development machine. The
container path is unverified and the documentation says so.

---

## D25 — Turning on the type checker found a bug that shipped

**Problem.** `backend/api/jobs.py` called
`_activate_stage(job.status, "results", 1.0, message, status="error")`, but the
helper's parameter is `status_value` and `status` is its first positional
argument. The call raised `TypeError: got multiple values for argument
'status'`, on the line *before* the database update, inside the failure path
reached by every `except` branch of the worker.

**Alternatives.** (1) Ignore it, it is in a rarely-taken branch; (2) add a
`try/except` around it; (3) fix the keyword and pin it with a test.

**Chosen.** Option 3. The consequence was not a rare error message: a failed
analysis was never written to the database, so its row stayed at
`status="processing"` until the next API restart, when `reconcile_orphans()`
swept it. The user saw a job spinning forever instead of the error and its hint.

**Failure case.** The equivalent shape is easy to write again: a helper with a
parameter called `status` and a keyword called something else. mypy is the only
thing in this toolchain that notices, which is the argument for D18.

**Tested.** `backend/tests/test_job_failure.py`, four tests; three of them fail
if `status=` is put back, because the stage stays `active` and the row stays
`processing`. This is the strongest argument in the repository for the tooling
in D18, because 200 backend tests passed with the defect in place.

---

## Open questions for the student **[student task]**

1. Is 0.5 s the right `min_queue_seconds` for a school gate, or should it be
   tied to the sampling rate? The validation shows it is the whole of the
   0.188-vehicle gap between the queued series and a slow-rule reference;
   justify a different value with a measurement.
2. The exit service time is a lower bound. Would measuring the *median* gap
   during a saturation window be better for a single-lane gate, and what would
   it cost when a second lane is in use?
3. The digital twin has one gate. Before it could be used to compare "where to
   send cars", what would have to be modelled first, and which of it can be
   validated from a single fixed camera?
