# FLOWLAB — project assessment

**First written 2026-09-28. Re-audited 2026-09-30.**

**Scope (2026-09-28):** the working tree as found (uncommitted work from three
previous sessions plus one initial commit). Nothing was committed or reverted.
**Method:** read the code, ran the checks, drove the interface in a real
browser, traced a displayed value back to its samples, and tried to break the
workflow with bad input.

**Scope (2026-09-30):** the improvement pass that followed, re-audited against
the code as it now stands. Method: read the changed modules, ran the full gate
(ruff, mypy, pytest with coverage, the encoding check, the frontend typecheck,
tests and build), traced one metric again, re-ran the ground-truth validation,
and grepped the documentation for claims the code no longer supports. Findings
F1 to F4 from the first pass are now closed; F5 to F16 are new. Section 7
records what this pass did *not* check.

## Commands run, 2026-09-28 (the original pass)

```text
$ git status --short
 M README.md
?? .gitignore  ?? backend/  ?? docker-compose.yml  ?? docs/  ?? frontend/  ?? run.bat  ?? run.sh
$ git log --oneline -3
24c4132 Initial commit

$ python -m pytest backend/tests -q
142 passed, 1 warning in 16.45s

$ python -m backend.scripts.check_encoding
scanned 99 files: clean

$ python -m pyflakes backend          # no output
$ cd frontend && npx tsc -b --noEmit   # no output
$ cd frontend && npm run build
built in 3.94s

$ GET /api/health  -> {"status":"ok","model_loaded":true,"device":"cpu","model_name":"yolo11n.pt"}
$ GET /api/analyses -> 5 stored analyses, 3 completed real-video, 1 demo, 1 error
```

## Commands run, 2026-09-30 (the re-audit)

```text
$ python -m pytest
277 passed in 16.01s

$ python -m ruff check backend
All checks passed!

$ python -m mypy
Success: no issues found in 38 source files

$ python -m backend.scripts.check_encoding
scanned 120 files: clean

$ cd frontend && npm run typecheck          (no output, exit 0)
$ cd frontend && npm test                   4 files, 50 passed
$ cd frontend && npm run build              689 modules, built in 5.19s

$ python -m pytest --cov=backend --cov-report=term
TOTAL                                    2907    406    738     89    84%

$ python -m backend.scripts.doctor
All runtime dependencies are present.
```

Full verbatim output is in [`VERIFICATION.md`](VERIFICATION.md). The browser was
not re-driven on 2026-09-30; the rows in section 2 that describe the interface
are the 2026-09-28 observations and are marked.

---

## 1. What works, with evidence

| Capability | Evidence |
| --- | --- |
| Upload, validation, job pipeline | 2026-09-28: uploaded a 20 s 1280x720 clip, stages progressed `detecting 23% -> 73% -> results 100%`, annotated video written and playable (HTTP 206 with `content-range`) |
| Zero-vehicle path | 2026-09-28: uploaded a synthetic empty car-park clip, `tracked=0`, `peak_queue=null`, `throughput=null` (not 0), actionable warning returned |
| Persistence across refresh | 2026-09-30: 5 analyses read back from SQLite after restarts (4 real-video, 1 demo); the seeded `stalejob1` failure record from the first audit is gone |
| Measurement correctness | 2026-09-30, re-run: `trace_metric demo peak_queue` rebuilds t=77.90 s from raw samples and finds 13 distinct vehicle ids (14...26); grid 13, API series 13, summary 13, event fires at 77.90 s. Byte-identical to the 2026-09-28 trace |
| Measurement accuracy vs ground truth | 2026-09-30, re-run: arrivals 26/26, exits 26/26, region occupancy 0.028 vehicles mean absolute error (max 1, 97.2 % exact), queued vs slow-rule 0.188 (max 2, 81.8 % exact) |
| Region editing | 2026-09-28: `PUT /regions` re-measures in ~1 s without re-detection; a self-intersecting polygon is rejected |
| Replay | 2026-09-28: seek to 40 s -> clock `00:40 / 02:15`, 10 live dots, chart cursor, event click seeks to `01:17` |
| Three-way comparison | 2026-09-28: observed 13 / baseline 7 / scenario 1 peak queue; model mismatch shown in its own block; window change flagged |
| Delete | 2026-09-28: `{"deleted_files":3,"bytes_freed":3982469}`; files confirmed gone from disk |
| Export | No `.mp4`, filename or local path in any export (asserted by the suite) |
| Narrow layout | 2026-09-28: 1024 px and 1280 px, no horizontal overflow, cards reflow to three columns |
| Unknown analysis id | 2026-09-28: error notice naming the id, no crash |

## 2. What fails, with reproduction

### F1 — The queue chart could contradict the queue metric (correctness) — **RESOLVED 2026-09-29**

`QueueSeries.to_samples()` decimated by taking every *n*-th grid sample. A peak
shorter than the decimation stride disappeared from the chart while the metric
card still reported it.

```text
$ python -c "...synthetic 1-instant peak on an odd index..."
full grid 1350 samples -> transport 675 samples (stride 2)
peak in full grid        : 13
peak in transport series : 13          <- survives here, by luck
synthetic 1-instant peak on an odd index, kept by every-nth: 0
same peak, kept by bucket-max decimation               : 99
```

**Fixed** on 2026-09-29 by aggregating each bucket with `max` and keeping the
ragged tail, recorded as D11 in [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md).
`backend/tests/test_queue.py::test_thinned_series_never_loses_a_brief_peak` puts a
one-instant spike on an odd index and asserts that every-nth would return 0
while the shipped thinning does not. Re-read on 2026-09-30:
`backend/analytics/queue_detection.py:73-95`.

### F2 — Dead controls in degenerate states (trust) — **RESOLVED 2026-09-29**

On the zero-vehicle analysis the **Peak queue** card showed `—` but still
offered a **why?** button that could explain nothing; the trajectory map was an
empty white panel; **Simulate a scenario** was offered and the API then refused
it.

**Fixed** on 2026-09-29 (D12). Re-read on 2026-09-30:
`frontend/src/pages/Analysis.tsx:144` disables the simulate link and explains why
in the `title` when `arrivals` is empty; `MetricCard` hides *why?* when nothing
was measured; the map renders an explicit empty state.

### F3 — The demo dataset shows a file size of `—` in the header — **RESOLVED 2026-09-29**

The size is now omitted entirely rather than rendered as a dash.
Re-read on 2026-09-30: `frontend/src/pages/Analysis.tsx:117` renders it only
when `analysis.video.size_bytes > 0`.

### F4 — Assessment debris in the data folder — **RESOLVED, twice over**

`data/` held `stalejob1`, a failure record created deliberately during the first
audit. On 2026-09-30 the database contains no such record. Separately, the
underlying complaint — "there is no clear-old-analyses affordance, only
per-analysis Delete" — is now answered by `frontend/src/components/RecentAnalyses.tsx`,
which lists stored analyses on the Home page with Reopen and Delete, wired to
`GET /api/analyses` and `DELETE /api/analyses/{id}`.

### F5 — Every failed analysis raised `TypeError` before it could be recorded (correctness, P0) — **FOUND AND FIXED 2026-09-30**

`JobManager._fail()` called `_activate_stage(job.status, "results", 1.0, message,
status="error")`, but the helper's parameter is `status_value` and `status`
collides with its first positional argument:

```text
TypeError: _activate_stage() got multiple values for argument 'status'
```

The `TypeError` was raised on the line *before* the database update, so the row
was never written. `_fail` is reached from every `except` branch of the worker,
so any failed analysis (unsupported codec, a video with no vehicles, a detector
error) stayed at `status="processing"` until the next API restart, when
`reconcile_orphans()` swept it. The user saw a job stuck at *processing* instead
of the error and its hint.

Found by enabling mypy, not by a test: 200 backend tests passed with the bug in
place because nothing exercised the failure path. `backend/tests/test_job_failure.py`
(4 tests) now covers it; three of them fail if `status=` is reintroduced.

### F6 — No SQLite connection was ever closed (resource, P1) — **FOUND AND FIXED 2026-09-30**

`Database._connect()` returned a bare `sqlite3.Connection`. Every caller used it
as `with self._connect() as connection:`, and `sqlite3.Connection.__enter__` is a
*transaction* manager: it commits, it does not close. Every database access
therefore leaked a handle until the cyclic collector ran.

The symptom was loud once warnings were turned into errors: eight
`PytestUnraisableExceptionWarning` failures in `test_data_lifecycle.py`, all
sourced at `backend/storage/database.py:56`, one of the form
`Exception ignored in: <sqlite3.Connection object at 0x...> unclosed database`.

`_connect()` is now a `@contextlib.contextmanager` that keeps the commit/rollback
behaviour inside `with connection:` and closes in a `finally`.
`backend/tests/test_database.py` (6 tests) pins the lifetime, including a test
that counts connections opened against connections closed.

### F7 — `__all__` promised a name that did not exist (packaging) — **FOUND AND FIXED 2026-09-30**

`backend/vision/__init__.py` listed `VehicleDetectionError` in `__all__`; the
class is `DetectorError`. `from backend.vision import *` raised `AttributeError`.
`backend/tests/test_package_layout.py` now walks every `__all__` in the package
and asserts that each name resolves and that every package supports a star
import.

### F8 — `PUT /regions` ignored the map-resolution query parameter (asymmetry) — **FOUND AND FIXED 2026-09-30**

`GET /api/analyses/{id}/result` honoured `?trajectory_points=`; `PUT
/api/analyses/{id}/regions` silently did not, so a re-measure returned a
different map resolution than a reload. Both now take the same parameter with the
same default and the same 4-600 clamp, and both go through the same `_downsample`
helper.

### F9 — The SPA catch-all had no path containment check (security, P1) — **FOUND AND FIXED 2026-09-30**

`spa(full_path)` did `candidate = FRONTEND_DIST / full_path` and served it if it
was a file. The path segment comes straight from the URL and was never checked to
be inside the build directory, so a request path that escaped `frontend/dist`
would have been served — including through a symlink. Ordinary HTTP clients
normalise `..` in the path, which is why this was not obviously exploitable, but
the check was simply absent.

`spa_file()` now resolves the candidate, refuses anything whose resolved parents
do not include the resolved build root, and falls back to `index.html` exactly
like any unknown client-side route.

### F10 — The environment doctor could not fail (tooling) — **FOUND AND FIXED 2026-09-30**

`doctor.py` printed `ok` for `opencv-python` whatever was installed. The declared
bound was `>=4.10,<5` while 5.0.0 was installed and the whole suite passed
against it, so nothing noticed. The check now parses the bounds out of
`backend/requirements.txt` and compares them with
`importlib.metadata.version`; an unparseable clause is a failure, not a pass. The
bound was widened to `>=4.10,<6` to match reality, and
`backend/tests/test_doctor.py` (20 tests) covers the comparison, the
prerelease rule and the requirements/pyproject agreement.

### F11 — The TypeScript mirror of the schema had drifted in both directions — **FOUND AND FIXED 2026-09-30**

- `EvidenceFacts.evidence_is_thin` existed in TypeScript but is a Pydantic
  `@property`, which is never serialised. It was a phantom field the client
  could never actually receive.
- `Analysis.region_occupancy_timeseries` exists in the schema and was missing
  from TypeScript, so the occupancy series added in the previous pass was not
  typed at all.

Both corrected, by reading the Pydantic model against the TypeScript mirror by
hand. **There is still no automated guard for schema-to-TypeScript agreement**,
which is a real gap: `npm run typecheck` proves the frontend is internally
consistent, not that it matches the backend. A test that compares the field
names in `backend/models/schemas.py` with the ones in
`frontend/src/types/index.ts` would close it, and is a good student exercise.

### F12 — Six frontend runtime defects, five of them user-visible — **FOUND AND FIXED 2026-09-30**

| Defect | What it did | Fix |
| --- | --- | --- |
| `hasQueueRegion` | threw on a malformed stored record | `Array.isArray`-guarded; found by a test |
| `queueAt` | disagreed with `backend.analytics.timeline.queue_at` before the first sample, so the replay cursor and the chart disagreed at t=0 | returns `null` before the first sample |
| `VideoViewer.handleClick` | `if (next.length > 12) setDraft(next); else setDraft(next);` — both arms identical, a no-op guard | a real `MAX_QUEUE_CORNERS` cap |
| `CorridorMap` tooltip | rendered the literal text `still queued}s` | fixed |
| `CorridorMap` caption | claimed "every nth vehicle" thinning the code never performed | the code now actually thins to 120 tracks, and the caption matches |
| `ExportMenu` | `role="menuitem"` on elements inside a `<ul>`, breaking ARIA ownership, promising arrow keys that did not exist | correct list semantics, and Escape returns focus to the trigger |

### F13 — Two endpoints existed with no interface, and the presets had drifted — **FOUND AND FIXED 2026-09-30**

`GET /api/analyses` and `GET /api/analyses/{id}/export/measurements` were both
implemented and tested, and neither had a caller in the frontend. The Home page
now has a saved-analyses panel (list, reopen, delete) and the export menu has a
fifth entry.

Worse, the scenario presets were hardcoded in the frontend while
`GET /api/analyses/{id}/simulation/presets` served the real ones; the two lists
had drifted. The panel now loads from the API. The built-in list survives only as
an offline fallback and is visibly labelled as such, so a user can always tell
which one they are looking at.

### F14 — Dead code, in both layers — **REMOVED 2026-09-30**

Backend: `recompute_with_regions`, `is_baseline`, `timeline_sample_count`,
`queue_at` and `position_at` (the last three existed only for tests), and a second
copy of the shoelace area function inside `models/schemas.py`. Frontend: three
exported types that duplicated `TimelinePayload`, plus `RegionKind`,
`RegionToolPicker`, `EvidenceHeader` and `PlaybackBadge`. All three `# type:
ignore` comments are gone and the one un-annotated backend parameter is annotated.

`CorridorMap` was the largest item: a complete component that nothing rendered.
It was wired into the Simulation page rather than deleted, after its two defects
above were fixed.

### F15 — The accessibility help promised a key that did nothing — **FOUND AND FIXED 2026-09-30**

The region editor's help text said "press Enter" and nothing listened for it.
Enter now closes a queue polygon and Escape abandons the draft, both in the
overlay and in the on-screen instructions. Added in the same pass: a global
`:focus-visible` ring, `prefers-reduced-motion` respected, `aria-live` on the
processing status, named icon-only controls, a skip link and real landmarks.

**Not verified:** none of the keyboard paths have been driven in a real browser.
They type-check and the handlers exist; nobody has tabbed through them yet.

### F16 — The replay clock rebuilt every path string on every frame (performance) — **FOUND AND FIXED 2026-09-30**

`TrafficMap` and `QueueChart` rebuilt their path strings on every animation
frame, because the shared replay clock is a context value and both re-derived
their geometry from scratch on each tick. `CorridorMap` and the comparison chart
on the Simulation page rebuilt their series on every render of the surrounding
page. All four are memoised now: the replay clock no longer triggers that work,
and a moved slider no longer rebuilds the corridor paths.

**Not verified:** no before/after frame-time measurement was taken. The change is
structurally obvious; the improvement has not been quantified.

## 3. Where documentation or claims exceed behaviour

| Claim | Reality | Status |
| --- | --- | --- |
| README: "142 tests" (2026-09-28 record) | Accurate then; the suite is now 277 backend + 50 frontend | corrected 2026-09-30 |
| README: "129 tests" in the project-layout tree | Wrong on two counts; now 277 | corrected 2026-09-30 |
| `docs/VERIFICATION.md`: "157 passed" | Stale by 120 tests | corrected 2026-09-30, re-run |
| `docs/PROJECT_ASSESSMENT.md`: "Sensitivity range — **Not implemented**" | **Wrong.** `service_time_sensitivity` in `backend/simulation/simulator.py:451` re-runs the baseline at 0.75x / 1.0x / 1.5x the estimated service time, `run_scenario` attaches it to `SimulationResult.sensitivity` when there are arrivals, and `backend/tests/test_evidence.py` asserts the range, its ordering, its absence without arrivals and its determinism | corrected 2026-09-30 |
| `CONTRIBUTING.md`: "`check` runs the same set of checks CI runs" | **Not quite.** `run.bat check` runs ruff, pytest, encoding, frontend typecheck, tests and build; CI additionally runs mypy, which `check` does not | **open** — file is outside this pass's scope, reported not fixed |
| `CONTRIBUTING.md`: "`backend/tests/ 200 tests`" | Stale; it is 277 | **open** — same |
| `CONTRIBUTING.md`: a blockquote breaks the `check` command table mid-way | The `| install |` row is orphaned below the note, so the table does not render | **open** — same |
| `pyproject.toml`: project URLs point at `github.com/SG-925/FLOWLAB` | The remote is `github.com/sgohils/FLOWLAB` | **open** — outside this pass's scope |
| `doctor.py`: prints `repository <data dir>` | The label names the data directory, not the repository root | **open** — cosmetic, outside this pass's scope |
| Calibration panel: "Arrival rate 0/min" on a zero-vehicle clip | This is a genuine zero, but it sits next to "Exit service time 3 s", which is a fallback default, not a measurement. Both look equally authoritative | **open** — pre-existing, unchanged |
| "Charts and anonymous trajectories only — no footage" in the print brief | Accurate; verified no `<video>` element and no blob image | unchanged |
| Home: "TRAJECTORY REPLAY" badge on the demo | Accurate: no footage is implied, and the section says so | unchanged |

## 4. What remains untested or unverified

- **The detector on real footage.** No human reference annotation exists. Every
  accuracy figure in the repository is either synthetic or qualitative.
- **Docker.** `docker compose build` has never been executed here; Docker is not
  installed. The compose YAML parses, the ignore rules are matched by 47 tests,
  and that is the limit of the evidence.
- **CI.** `.github/workflows/ci.yml` has never run. Its YAML parses and every one
  of its steps was run by hand locally, but the Python 3.11 leg, the Node 20 leg
  and the hosted runners have not.
- **mypy on Python 3.11.** Only 3.13 is installed. `pyproject.toml` sets
  `python_version = "3.12"` deliberately, so a 3.12-only syntax slip would be
  caught by the CI 3.11 leg rather than by the local type check.
- **`run.sh`.** Now syntax-checked, and `--help` and `lint` have run through Git
  Bash. `start`, `install`, `test`, `build` and `check` have not.
- **GPU path.** `device=auto` resolves to CPU on this machine; the CUDA branch
  has not run.
- **Long clips.** Only 20 s clips were processed end to end. A 10-minute clip
  would exercise the 900-sample series cap, the annotated-video writer and the
  SQLite payload at a scale never tested.
- **Two lanes of the same analysis open at once.** Concurrent region edits are
  guarded by a request token, but two browser tabs were not tested.
- **Keyboard-only navigation.** The handlers exist and type-check; nobody has
  tabbed through the region editor, the export menu or the replay.
- **The browser itself.** Not re-driven on 2026-09-30, so the Home page's two
  new panels, the fifth export entry, `CorridorMap` on the Simulation page and
  the accessibility changes have not been seen rendered.
- **The `_busy_window` calibration heuristic** on real footage: the demo's
  service-time estimate is 4.29 s against a true 3.2 s, but on the real clip
  there was no queue at all, so the fallback path was taken.

## 5. The five improvements most likely to help

1. ~~**Fix F1** so the chart can never contradict the card.~~ **Done** 2026-09-29.
2. ~~**Fix F2** so degenerate states never offer an action that cannot work.~~
   **Done** 2026-09-29.
3. ~~**One consolidated "Evidence and assumptions" panel.**~~ **Done** 2026-09-29.
4. **Real-footage reference annotations.** Still the highest-value work for the
   project, and the only one that cannot be done by an assistant.
5. **Long-clip and second-tab checks**, which are cheap to add now and would
   close the two untested reliability gaps.

Added by the 2026-09-30 re-audit, in the same order of value:

6. **Drive the interface again**, specifically the new Home panels, the export
   menu, `CorridorMap` and the keyboard paths. Four of this pass's changes are
   unverified in a browser.
7. **Fix the three documentation defects listed in section 3** that live outside
   `docs/`: the `CONTRIBUTING.md` table, its stale test count, and the project
   URLs in `pyproject.toml`.
8. **Execute the Docker build and one CI run.** Both are one command each on a
   machine that has the tool, and both currently rest on inspection alone.

## 6. Recommended scope, including work that should wait

**Done (2026-09-29 and 2026-09-30):** items 1, 2 and 3 above, plus the F5-F16
defect sweep and the tooling (ruff, mypy, coverage, CI, pre-commit).

**Next, student-owned:** item 4, with `docs/STUDENT_CONTRIBUTIONS.md` exercise 1
as the brief. Item 5 is a good second student exercise. Item 6 above is
student-sized too and is arguably the best way to learn the codebase, because it
means reading the diff.

**Explicitly wait:**

- Perspective calibration. It is the only route to real units and it is a
  project on its own; claiming it now would be dishonest.
- A second gate in the simulator. Useful, but only if the first gate's
  validation is finished, and it is not.
- Anything resembling accounts, deployment, sharing or school integration. None
  is needed to answer the product question, and each one enlarges the privacy
  surface.
- UI polish beyond the items above. The design is already restrained and
  legible; more decoration would not raise judge confidence.
- Further strictness for its own sake. `noUncheckedIndexedAccess` was measured at
  41 diagnostics, nearly all indexing the code already proves safe; the honest
  fix is tighter payload types, not 41 non-null assertions in the replay maths.
