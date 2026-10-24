# FLOWLAB — Readiness Audit

**Date:** 2026-09-27
**Scope:** the repository as it stands on `main` (initial commit + uncommitted MVP work).
**Method:** read the code, run the tests and the production build, run the app, exercise the
API and the browser workflow, and reproduce defects rather than assuming them.

Nothing in this document was changed to make it true. Every "reproduced" item lists the
command that was run and what it actually printed.

> **Status of this document.** This is the audit as it was written *before* the fixes.
> The "Resolution" line on each defect records what was done afterwards. Two defects
> (D19, D20) were found by the work that followed, and are listed in the addendum at the
> end.
>
> A second, much larger sweep was run on **2026-09-30** after tooling was enabled
> (ruff, mypy, warnings-as-errors, a frontend test runner). It found 15 further
> defects, including two that had shipped, and added the regression tests for all of
> them. That is **Addendum 2** at the end. Nothing in D1-D22 above has been
> rewritten; the test counts in this document are the counts as they stood at each
> date, and the current figures are in Addendum 2 and in `docs/VERIFICATION.md`.

---

## 0. Baseline reproduction

```text
$ python -m pytest backend/tests -q
87 passed, 1 warning in 11.15s

$ cd frontend && npm run build
✓ built in 7.33s      (react 50.9 kB, index 271.6 kB, charts 404.5 kB)

$ GET /api/health   -> {"status":"ok","model_loaded":true,"device":"cpu","model_name":"yolo11n.pt"}
$ GET http://[::1]:5173/ -> 200
```

Environment: Windows 11, Python 3.13.5, Node 24.18.0, torch 2.14.0+cpu, OpenCV 5.0.0.93.
Both servers are running locally; the browser workflow was exercised through headless Chrome
against the dev server.

---

## 1. Verified working features

These were run, not read.

| Feature | How it was verified |
| --- | --- |
| Video upload + validation | `curl -F file=@clip.mp4 /api/uploads` → 202 with duration/fps/resolution; `.exe` → 415; `text` bytes named `.mp4` → 400; empty file → 400 |
| Detection + tracking | Real 20 s clip: 11 detections, 8 stable tracks, ids like `Car #010` |
| Annotated video | Written and playable; `Range: bytes=0-1023` → `206 Partial Content`, `content-range: bytes 0-1023/2068368` |
| Privacy of detection | Boxes never appear on pedestrians; the `person` class is not in the requested class list |
| Progress stages | Polled `/status` during a real job: `detecting 23% → 41% → 59% → 73% → results 100%` |
| Region redraw | `PUT /regions` recomputed metrics in ~1 s with no re-detection: peak queue 2 → 1, throughput 0 → 3.0/min |
| Scenario simulation | Six scenarios run: volume −25 %, exit ×1.5, second lane, spread +120 s, combined. All moved in the expected direction |
| Determinism | Same scenario twice → identical queue series (asserted in `test_api.py`) |
| Demo dataset | `/api/demo` serves 26 trajectories, labelled `Demo Dataset` in every surface |
| Test suite | 87 tests, 0 failures, no network access required |
| Frontend build | `tsc -b` + `vite build` clean; no console errors on Home / Analysis / Simulation |

---

## 2. Reproduced defects (with evidence)

### D1 — Deleting an analysis leaves the footage on disk (privacy, P0)

```text
$ curl -X DELETE /api/analyses/fdaa59449f0d
HTTP 204

$ ls data/uploads | grep fdaa59449f0d
fdaa59449f0d_clip_b.mp4      1898532 bytes      <-- original footage still present
$ ls data/processed/fdaa59449f0d
annotated.mp4                2068368 bytes      <-- annotated video still present
result.json.gz                 15565 bytes
```

`DELETE` only removes the SQLite row (`backend/api/routes_analysis.py:delete_analysis`).
5.9 MB of footage survives a delete the UI describes as removing the analysis.

### D2 — An interrupted job stays "processing" forever (P0)

```text
# simulate a backend restart with a job record left mid-flight
$ curl /api/analyses/stalejob1/status
{"status":"processing","stage":"detecting","progress":0.42,"stages":[]}
```

`JobManager` keeps jobs in memory only. After a restart the DB still says `processing`,
so the UI polls a job that no longer exists, forever, with no error and no way out.

### D3 — There is no export at all (P0, success criterion 10)

```text
$ grep -rn "csv|CSV|export" backend frontend/src README.md
README.md:680:- Export to CSV / GeoJSON for further analysis      <-- listed as FUTURE work
```

Nothing in the application produces a file the user can keep or hand to a teacher.

### D4 — First queue visit is reported as a completed wait (correctness, P0)

A vehicle that appears **already inside** the queue region at the first tracked frame has
an unknown entry time, but it is counted as a full wait:

```text
# vehicle appears stopped inside the region at t=0, leaves at t=5
episode QueueEpisode(vehicle_id=1, start=0.0, end=5.0, complete=True)
COUNTED AS COMPLETE WAIT: 1  avg 5.0  max 5.0  censored 0
```

This inflates or deflates `average_wait_seconds` and `max_wait_seconds` whenever the clip
starts with traffic already queued — which is the normal case for school dismissal footage.

### D5 — Delete / export are absent from the UI (P0)

`grep -n "delete" frontend/src` → no call to `api.delete` anywhere. A first-time user
cannot remove an analysis at all, and the header offers no download.

### D6 — No comparison against a baseline simulation (P0, criterion 8)

`SimulationResult` has `observed` and `simulated`; the baseline run exists inside
`_fidelity` but is reduced to a single peak-queue number. The user sees "Observed vs
Simulated" where the honest framing is **Observed vs Baseline vs Modified** — otherwise an
observed-vs-model difference can be read as an effect of the intervention.

### D7 — Privacy claims are broader than the behaviour (P0)

```text
frontend/src/pages/Home.tsx
  "Only COCO vehicle classes are requested from the model — people are never detected,
   so no person data exists to store."
  "Everything runs on this machine: local files, local SQLite, no cloud calls."
```

Both are inaccurate:

- The **uploaded and annotated video files are stored on disk** and can contain
  identifiable people and number plates. Anonymous track ids do not anonymise footage.
- Ultralytics **downloads `yolo11n.pt` from GitHub on first run** when the weights are not
  present. There is a network request; "no cloud calls" is false as written.
- There is no retention statement and no stated behaviour when an analysis is removed.

### D8 — "Queued" has no duration threshold, unlike "stopped" (P1)

`queue_detection.track_episodes` opens an episode on a **single** sample below the speed
threshold. `motion.detect_stops` requires `min_stop_seconds` (default 1.5 s). One-sample
detector jitter therefore inflates the queue but not the stop list, and the UI does not say
which definition is in use.

### D9 — Residence time, slow time and traversal time are conflated (P1)

`Trajectory` exposes `duration` (first→last sighting), `stopped_seconds` (slow, whole
scene, min duration) and `queue_seconds` (in region **and** slow). There is no
"inside the queue region" time at all, and the three are surfaced in the UI with the loose
labels *Observed duration*, *Stopped time* and *Queued time*.

### D10 — Line crossings ignore direction (P1)

`geometry.first_crossing_time` counts a crossing whenever the trajectory changes side of the
finite segment, in **either** direction. For an exit line, a vehicle reversing across it is
counted as a departure.

### D11 — Region geometry is not validated for self-intersection (P1)

```text
Regions(queue=[(0.1,0.1),(0.9,0.2),(0.2,0.8),(0.8,0.9)])  ->  ACCEPTED
```

A self-intersecting (bow-tie) polygon with unequal lobes passes the area check and then
produces a meaningless inside/outside test.

### D12 — Concurrent region edits can show a stale result (P1)

`Analysis.tsx:commitRegions` fires a `PUT` per edit with no request sequence guard, so a
slow earlier response can overwrite a newer one, and `setSaving(false)` from the first
response clears the "Recomputing…" indicator while the second request is still in flight.

### D13 — "Top-down map" is presented without the coordinate caveat (P1)

`TrafficMap` is labelled "Top-down view of the camera frame". It is an image-coordinate
plot, not a plan view. The required wording is *image-coordinate trajectory map*.

### D14 — Bottleneck "score" reads like a measured severity (P1)

The card shows `score 0.967`. That number is a fixed-weight ranking of normalised grid
components. It is not a severity measurement and should not be shown as if it were.

### D15 — Unbounded background work and no duplicate-upload guard (P1)

`ThreadPoolExecutor(max_workers=1)` has an unbounded queue: repeated uploads accumulate
futures and uploads on disk with no limit. Nothing stops a user from submitting the same
file repeatedly.

### D16 — No startup script or environment doctor (P1)

The README documents `uvicorn backend.main:app --reload --port 8000` and `npm run dev`, but
there is no single command, no dependency check and no way to confirm the model is
available before a demo.

### D17 — UTF-8 BOM in eight Python modules (P2)

`main.py`, `analytics/metrics.py`, `api/routes_analysis.py`, `api/routes_upload.py`,
`scripts/build_demo_dataset.py`, `simulation/simulator.py`, `tests/test_metrics.py`,
`vision/annotator.py` started with a BOM (an artefact of editing on Windows). Python accepts
it; other tools may not.

### D18 — Model calibration and the queue definition differ between the two queue notions (P2)

The simulator counts a vehicle as queued when it is stopped *anywhere* in the corridor,
while the measured queue requires being *inside the drawn region*. The UI states this in one
sentence; the README does not spell it out as a definitional difference.

---

## 3. Claims that differ from the implementation

| Claim | Where | Reality |
| --- | --- | --- |
| "no cloud calls" | Home page, README | `yolo11n.pt` is downloaded from GitHub on first use |
| "no person data exists to store" | Home page | The uploaded and annotated **video files** are stored and can contain people and plates |
| "Anonymous vehicles only" | Header chip | True for derived data; the footage itself is unchanged and can be identifying |
| "Vehicles appear as anonymous ids" | Home page | True, but an id is not anonymisation of the underlying footage |
| "Keep a deterministic demo available" | spec/README | The demo is bundled; it is **not** available if the backend cannot start, and the UI does not say which parts need the model |
| "87 tests, all offline" | README | True — no test touches the network or the model |

---

## 4. Untested or unavailable capabilities

| Capability | Status |
| --- | --- |
| Detector accuracy against ground truth | **Not established.** No reference annotations exist yet. |
| Real-world congestion reduction | **Not measured and not claimable.** |
| GPU path | Not exercised (no CUDA on this machine); `device=auto` resolves to CPU |
| Docker | `docker compose up` **not executed** on this machine |
| Clean-venv install of `requirements.txt` | Being tested in parallel; result recorded in `docs/VALIDATION_REPORT.md` |
| Multi-gate / multi-lane sites | Not modelled (out of scope by design) |
| Long clips (10 min, 1080p) | Not exercised; only 20 s clips were processed |

---

## 5. Prioritised work

### P0 — demo blockers or incorrect results

1. **Delete must delete.** Remove upload, processed directory and DB row; report bytes freed.
2. **Interrupt recovery.** On startup, mark orphaned `processing` rows as interrupted with a
   clear error and a retry path.
3. **Export.** CSV (trajectories, queue series, stops, events) and a JSON summary, with a
   metadata-only default that contains **no footage**; add Export and Delete to the UI.
4. **Censor left-censored queue visits.** A visit that begins at the first tracked sample is
   not a completed wait.
5. **Three-way comparison.** Observed / baseline / modified, with improvement measured
   against the baseline and model mismatch shown separately.
6. **Privacy claims.** Correct the copy; add a retention and deletion statement to the UI,
   the README and the footer; state the model download explicitly.

### P1 — measurement defensibility and usability

7. Explicit queue definition with `min_queue_seconds`, applied consistently.
8. Region residence time as a distinct metric; consistent naming across code, UI and docs.
9. Crossing direction as an explicit, documented policy.
10. Region validation: self-intersection, repeated vertices, minimum area.
11. Bottleneck evidence (distinct vehicles, slow time) with ranking, not a severity score.
12. Map labelled *image-coordinate trajectory map*.
13. Stale-response guard plus unsaved/stale indicators for region edits.
14. Bounded work queue and duplicate-upload guard.
15. Startup script + `doctor` diagnostics.
16. Validation tooling with manual reference annotations and a report.

### P2 — polish

17. Keyboard-accessible region editing.
18. Shared timeline linking video, map and queue chart.
19. Optional retention/auto-cleanup of old analyses.
20. Strip the UTF-8 BOMs (done during the audit).

---

## 6. Definition-of-done status after this audit

| Requirement | Status |
| --- | --- |
| Backend tests pass | ✅ 87 at audit time → **129** after the fixes |
| Type check + production build pass | ✅ |
| Primary browser workflow exercised | ✅ (headless Chrome, Home → Analysis → Simulation) |
| Demo and real-video modes visibly distinct | ✅ `Demo Dataset` badge + warning |
| Real-video processing verified | ✅ 20 s clip end to end, twice |
| Region edits recompute correctly | ✅ after the D12 race was fixed |
| Simulations repeatable and honest | ✅ three-way comparison added |
| Privacy claims match behaviour | ✅ D7 corrected in the UI, footer and README |
| Setup instructions match tested commands | ✅ `run.bat` added and tested; clean-venv install verified |
| No fabricated evidence in materials | ✅ nothing in the repo claims real-world results |
| Student-owned tasks listed | ✅ `docs/STUDENT_CONTRIBUTIONS.md` |

---

## Addendum — defects found and fixed while doing the work

These were not in the original audit; they were found by the fixes themselves, and
are listed because the record matters more than the ordering.

| # | Defect | Evidence | Resolution |
| --- | --- | --- | --- |
| D19 | The delete implementation introduced during this pass returned the *byte size* where the caller expected a *file count* (`assert files == 3` failed with `5369`) | a new test caught it | `_remove()` now returns `(count, bytes)` |
| D20 | The simulated time window drifted past the clip (135 s observed vs 138.2 s simulated) because the window was taken from the last arrival rather than the observation window | the simulation notes complained about comparing throughput over different durations | `plan_scenario` anchors the arrival series at zero and uses the observation window; the "different windows" note now fires only when arrivals are actually spread |
| D21 | The bundled demo's own entry line sat at x = 0.14 while vehicles in an outer lane start at x ≈ 0.15, so 2 of 26 arrivals were never counted | the validation workflow: arrivals 24 vs 26 | the line moved to x = 0.20; this is a *configuration* fix, and the detection code was correct |
| D22 | The first ground-truth generator double-counted a vehicle across sampling instants, making the reference disagree with the pipeline by a factor of two | validation mean absolute error of 2.85 vehicles | fixed; the same per-vehicle cursor rule as the measurement layer, error dropped to 0.211 vehicles |

*Superseded figure (noted 2026-09-29).* The 0.211 vehicles in D22 was measured
while the stored queue series was decimated by taking every *n*-th grid sample.
D11 in `docs/ENGINEERING_DECISIONS.md` changed that thinning to the bucket
maximum, and the *same* comparison against the *same* reference series now reads
**0.188 vehicles** (max 2, exact on 81.8 % of instants) — re-measured, not
estimated. The D22 row is deliberately left as written: it is a record of what
was true when that defect was found, and rewriting the number would imply the
fix had been verified with code that did not exist at the time. The current
like-for-like figure — region occupancy against the reference's occupancy counts
— is 0.028 vehicles; see `docs/VALIDATION_REPORT.md`.

The full resolution of D1–D18:

| # | Resolution |
| --- | --- |
| D1 | Delete removes the upload, the annotated video, the result and the row, and reports files and bytes freed. Verified: `{"deleted_files":3,"bytes_freed":3982469}` |
| D2 | `reconcile_orphans()` marks interrupted records as failed on startup. Verified: the stale record now reports `Processing was interrupted` |
| D3 | Five export endpoints added; tests assert no export contains `.mp4`, a filename or a local path |
| D4 | The first visit of a track is left-censored when the vehicle was already inside the region. Test: `test_visit_that_starts_at_the_first_frame_is_censored` |
| D5 | Export menu and Delete added to the analysis header |
| D6 | `SimulationResult` now carries `baseline` and `model_deltas`; the interface shows A/B/C with the scenario effect and the model error in separate blocks |
| D7 | Copy corrected on the home page, uploader, footer and README, with a retention statement and the model download named |
| D8 | `min_queue_seconds` (default 0.5 s) applied to both the queue series and the wait visits; two tests |
| D9 | `region_seconds` added per trajectory and `average_region_seconds` in the summary; four distinct quantities named in the UI and README |
| D10 | `entry_direction` / `exit_direction` added with tests for forward-only counting |
| D11 | Self-intersection, repeated vertices and a minimum area (0.2 % of the frame) are rejected; six tests |
| D12 | `useLatestRequest()` gives every edit a token; only the newest response may replace the result, and a "Recomputing" notice shows while one is in flight |
| D13 | Labelled *image-coordinate trajectory map* in the UI and README |
| D14 | Cards now show "Rank N of M" plus distinct vehicles, time below threshold and mean per vehicle; the index is described as a ranking, not a severity |
| D15 | Uploads are refused with HTTP 429 beyond `max_queued_jobs` (default 3); test added |
| D16 | `run.bat` / `run.sh` with `doctor`, `test`, `install`, `build`; `python -m backend.scripts.doctor` checks imports, model weights, storage and the database |
| D17 | BOMs stripped from the eight affected files |
| D18 | Stated in the simulation notes and in the chart caption: one waiting point in the model versus an area in the video |

---

## Addendum 2 — the 2026-09-30 improvement pass

**Date:** 2026-09-30. **Method:** the same loop as the first audit. Read the
code, turned on tooling that had never been enabled, ran the full gate, traced a
metric, re-ran the ground-truth validation, and did **not** fix anything in the
browser. The D1-D20 entries above are left exactly as written, with their
resolutions, because they are a record of what was true when each defect was
found.

**Suite:** 200 -> **277** backend tests, plus a new 50-test frontend suite. Every
one of the bugs below has a regression test that fails on the old code; the ones
found by the type checker and the linter had **no** test at all, which is the
point.

```text
$ python -m pytest                       277 passed in 16.01s
$ python -m ruff check backend           All checks passed!
$ python -m mypy                         Success: no issues found in 38 source files
$ python -m backend.scripts.check_encoding    scanned 120 files: clean
$ python -m pytest --cov=backend --cov-report=term    TOTAL 84 % (2907 stmts, 406 missed)
$ cd frontend && npm test                4 files, 50 passed
```

### Defects found and fixed in this pass

| # | Defect | Severity | How it was found | Resolution |
| --- | --- | --- | --- | --- |
| A1 | Every failed analysis raised `TypeError` before the database update: `_activate_stage(..., status="error")` passed `status` to a parameter named `status_value`, colliding with the first positional argument | correctness, P0 | enabling mypy | `status=` -> `status_value=`. The job-failure path was never exercised, so 200 tests passed with the defect in place. `backend/tests/test_job_failure.py`, 4 tests, 3 of which fail if the old keyword returns |
| A2 | No SQLite connection was ever closed: `Database._connect()` returned a bare connection and `with self._connect()` is sqlite3's *transaction* manager, not a close | resource, P1 | setting `filterwarnings = ["error"]`, which turned the leak into 8 failing tests | `_connect()` is now a `@contextmanager` with `finally: connection.close()`. `backend/tests/test_database.py`, 6 tests |
| A3 | `backend/vision/__init__.py` `__all__` named `VehicleDetectionError`; the class is `DetectorError`, so `from backend.vision import *` raised `AttributeError` | packaging, P2 | reading `__all__` against the module | name corrected; `test_package_layout.py` now walks every `__all__` in the package and star-imports every module |
| A4 | The SPA catch-all served `FRONTEND_DIST / full_path` with no containment check | security, P1 | reading `spa()` | `spa_file()` resolves and verifies containment, falling back to `index.html` |
| A5 | `PUT /analyses/{id}/regions` ignored `?trajectory_points=` while `GET .../result` honoured it, so a re-measure returned a different map resolution than a reload | correctness, P2 | comparing the two routes | both take the parameter, same default, same 4-600 clamp, same `_downsample` helper |
| A6 | `doctor.py` reported `ok` for the dependency pins whatever was installed, which is how an OpenCV 5.0.0 install survived a `>=4.10,<5` bound | tooling, P2 | reading the check | bounds are parsed out of `backend/requirements.txt` and compared with `importlib.metadata`; an unparseable clause is a failure. The bound was widened to `>=4.10,<6`. `test_doctor.py`, 20 tests |
| A7 | `hasQueueRegion` threw on a malformed stored record | frontend, P2 | a new test | `Array.isArray`-guarded |
| A8 | `queueAt` disagreed with `backend.analytics.timeline.queue_at` before the first sample, so the replay cursor and the queue chart disagreed at t=0 | frontend correctness, P1 | reading both implementations | returns `null` before the first sample |
| A9 | `VideoViewer.handleClick` had `if (next.length > 12) setDraft(next); else setDraft(next);` - both arms identical, a no-op guard | frontend, P2 | reading the handler | a real `MAX_QUEUE_CORNERS` cap |
| A10 | `CorridorMap` rendered the literal text `still queued}s` in its tooltip, and its caption claimed a thinning the code never performed | frontend, P3 | reading the component | both fixed; the code now really does thin to 120 tracks |
| A11 | `ExportMenu` put `role="menuitem"` on elements inside a `<ul>`, breaking ARIA ownership, and promised arrow-key navigation that did not exist | accessibility, P2 | reading the component | correct list semantics; Escape returns focus to the trigger |
| A12 | Type drift against `backend/models/schemas.py` in both directions: `EvidenceFacts.evidence_is_thin` is a Pydantic `@property` and is never serialised, while `Analysis.region_occupancy_timeseries` was missing from TypeScript | frontend correctness, P2 | diffing the two models | phantom field removed, missing field added. **There is still no automated guard** for schema-to-TypeScript agreement |
| A13 | `GET /api/analyses` and `GET /api/analyses/{id}/export/measurements` were implemented, tested and unused by the frontend; the scenario presets were hardcoded in the frontend and had drifted from the endpoint that serves them | product, P2 | asking what calls each route | saved-analyses panel, degraded-mode banner, fifth export entry, presets loaded from the API with a visibly labelled offline fallback |
| A14 | `CorridorMap` was a complete component nothing rendered | dead code, P3 | looking for dead exports | wired into the Simulation page after A10 was fixed |
| A15 | The region editor's help text promised "press Enter" and nothing listened for it | accessibility, P2 | reading the help against the handlers | Enter closes a polygon, Escape abandons the draft; plus a global `:focus-visible` ring, `prefers-reduced-motion`, `aria-live` on the processing status, named icon-only controls, a skip link and landmarks |

### Dead code removed

Backend: `recompute_with_regions`, `is_baseline`, `timeline_sample_count`,
`queue_at` and `position_at` (the last three existed only for tests), and the
second copy of the shoelace area function in `models/schemas.py`. Frontend: three
exported types duplicating `TimelinePayload`, plus `RegionKind`,
`RegionToolPicker`, `EvidenceHeader` and `PlaybackBadge`. All three `# type:
ignore` comments are gone and the one un-annotated backend parameter is
annotated.

### Architecture change

`backend/geometry.py` is new and holds the pure geometry primitives; it imports
nothing from the project, which is what lets `models/schemas.py` share them
without a cycle. `backend/analytics/geometry.py` is now a re-export shim. The
layering rule and the reason are in D16 of
`docs/ENGINEERING_DECISIONS.md` and in `CONTRIBUTING.md`.

### Tooling added

| File | What it is |
| --- | --- |
| `pyproject.toml` | the authoritative dependency list, plus ruff, mypy, pytest and coverage configuration |
| `backend/requirements-dev.txt` | pytest, httpx, ruff, mypy, pytest-cov - removed from the runtime requirements |
| `.editorconfig` | line endings, indentation, final newline |
| `.pre-commit-config.yaml` | ruff and the encoding check on changed files |
| `.github/workflows/ci.yml` | backend on Python 3.11 and 3.13, frontend on Node 20 and 24 |
| `.dockerignore` (root) | keeps the build context to what the images actually copy, with a matcher test |
| `CONTRIBUTING.md` | the layering rule, seven house rules, how to write a test that can fail |
| `frontend/vitest.config.ts`, four test files | the frontend suite, which did not exist before |

### What this pass did **not** verify

| Item | Status |
| --- | --- |
| `docker compose build` / `up` | **Never run.** Docker is not installed here. The compose YAML parses, the two services and the one profile are as documented, and 47 tests prove the ignore rules cannot delete a build input. That is the limit of the evidence. |
| CI | **Never run.** `ci.yml` parses and each of its steps was executed by hand locally. The hosted runners, the Python 3.11 leg and the Node 20 leg have not. |
| mypy on Python 3.11 | Only 3.13 is installed. `pyproject.toml` sets `python_version = "3.12"` deliberately because numpy >= 2.3's stubs use PEP 695 `type` statements that mypy cannot parse under 3.11. A 3.12-only syntax slip would be caught by the CI 3.11 leg, not locally. |
| The browser | **Not re-driven.** The Home panels, the fifth export entry, `CorridorMap` on the Simulation page and every keyboard path are implemented and type-check, and none has been seen rendered or tabbed through. |
| `noUncheckedIndexedAccess` | Measured at 41 diagnostics and deliberately left off; the reasoning is recorded in `frontend/tsconfig.json` and D22. This is a real, chosen limitation, not an oversight. |
| Sampling-rate sensitivity | Still unmeasured. Nothing in this pass changes that. |
| Detector accuracy on real footage | **Still not validated, and nothing here changes it.** |
