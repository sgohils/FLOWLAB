# Verification record

**Re-run 2026-09-30.** Every command in section 1 was executed on this machine
on that date and its output is pasted verbatim. Sections 4 and 5 record checks
from the earlier 2026-09-28 session; they were **not** repeated on 2026-09-30 and
are marked as such. Where a check could not run, that is stated rather than
glossed.

**Machine:** Microsoft Windows 11 Pro, Windows NT 10.0.26200, AMD64
(`Intel64 Family 6 Model 154 Stepping 4`).
**Interpreters:** CPython 3.13.5 at
`C:\Users\gohil\AppData\Local\Programs\Python\Python313\python.exe`, Node
v24.18.0 with npm 11.16.0, CPU only (torch 2.14.0+cpu).
Tooling under test: ruff 0.16.9, mypy 2.3.1, pytest 9.1.1, coverage 7.16.2,
vitest 3.2.7, Vite 6.4.3, TypeScript 5.x.

> The repository's own `.venv\Scripts\python.exe` exists but is **empty** (no
> `site-packages`, no pip). Every command below was run with the base
> interpreter named above. `run.bat` detects this: a candidate must answer both
> `import sys` and `-m pip --version` before it is accepted, so an unpopulated
> `.venv` produces a named error and an `install` hint rather than an
> `ImportError` three commands later.

---

## 1. Automated checks, run 2026-09-30

### Backend suite

```text
$ python -m pytest
........................................................................ [ 51%]
........................................................................ [ 77%]
.............................................................            [100%]
277 passed in 16.01s
```

Zero warnings: `filterwarnings = ["error"]` is active in `pyproject.toml`.

### Lint

```text
$ python -m ruff check backend
All checks passed!

$ python -m ruff --version
ruff 0.16.9
```

### Types

```text
$ python -m mypy
Success: no issues found in 38 source files

$ python -m mypy --version
mypy 2.3.1 (compiled: yes)
```

### Coverage

```text
$ python -m pytest --cov=backend --cov-report=term
...
Name                                    Stmts   Miss Branch BrPart  Cover   Missing
-----------------------------------------------------------------------------------
backend\__init__.py                         1      0      0      0   100%
backend\analytics\__init__.py               9      0      0      0   100%
backend\analytics\bottlenecks.py           80      5     24      0    93%   181-185
backend\analytics\events.py                54      8     30      6    81%   64->73, 77, 87, 98-99, 134, 138-140
backend\analytics\geometry.py               3      0      0      0   100%
backend\analytics\metrics.py              166      6     62      6    95%   225->227, 286->292, 298, 309-310, 312, 341-342
backend\analytics\motion.py                59      2     18      1    96%   75-78
backend\analytics\queue_detection.py      151      3     54      2    98%   84, 94-95
backend\analytics\simulation_truth.py      58      1     20      2    96%   66, 89->91
backend\analytics\suggestions.py           86      4     26      4    93%   49, 70, 102, 138
backend\analytics\throughput.py            66      1     18      1    98%   114
backend\analytics\timeline.py              92      4     36      6    92%   48, 62->64, 77, 87, 147, 152->143
backend\analytics\wait_time.py             23      1      2      0    96%   40
backend\api\__init__.py                     4      0      0      0   100%
backend\api\errors.py                       8      0      0      0   100%
backend\api\exports.py                     66      0     14      0   100%
backend\api\jobs.py                       146     32     26      5    75%   122, 146-179, 197, 210->exit, 215-226, 230->238, 278, 291-294
backend\api\routes_analysis.py            169     24     34      6    82%   103-107, 113->115, 127-129, 183, 194, 240->242, 274-275, 286-292, 297-300, 336-342
backend\api\routes_simulation.py           34      6      8      4    76%   30, 32, 38, 45-46, 55
backend\api\routes_upload.py               54      4      8      1    92%   68-71
backend\api\state.py                      112     33     34      5    68%   40-41, 44-46, 67-72, 75, 87, 109-110, 114-118, 123-129, 155-158, 174-175
backend\config.py                          85     13      8      2    82%   25-26, 32-33, 40, 55-61, 162
backend\geometry.py                       105     10     48      7    89%   60, 62, 74, 111, 148, 178, 189, 204-206
backend\main.py                            83     12      8      2    85%   49, 120-122, 131, 136, 145, 150-151, 178-179, 185->exit, 190
backend\models\__init__.py                 0      0      0      0   100%
backend\models\schemas.py                331      2     32      2    99%   56, 110
backend\simulation\__init__.py             4      0      0      0   100%
backend\simulation\scenarios.py           78      4     30      4    93%   37, 66, 132, 170, 171->173
backend\simulation\simulator.py           250     12     84     12    93%   127->261, 226->235, 233-234, 263-264, 275, 341, 423->425, 426, 431, 547-548, 564, 574
backend\simulation\traffic_model.py        36      0     10      0   100%
backend\storage\__init__.py                 3      0      0      0   100%
backend\storage\database.py                58      1      8      1    97%   98
backend\storage\files.py                  86     10     20      7    84%   68-69, 90-91, 108, 110, 117, 120, 122, 127
backend\vision\__init__.py                 5      0      0      0   100%
backend\vision\annotator.py                48     32     10      0    28%   46-61, 72-84, 104-117
backend\vision\detector.py                117     53     20      3    49%   47, 75, 82-83, 91-94, 100, 102, 113-119, 146-190, 193-218, 226-227, 231-233
backend\vision\trajectories.py             69     44     20      0    28%   40-42, 49-50, 53-69, 87-100, 104, 108-128
backend\vision\video_processor.py         108     79     26      0    22%   60-169, 182, 190-201, 205-213
-----------------------------------------------------------------------------------
TOTAL                                    2907    406    738     89    84%

277 passed in 31.98s
```

Read the number honestly: **84 %** overall, and the gap is concentrated in the
vision layer (`video_processor.py` 22 %, `trajectories.py` 28 %, `annotator.py`
28 %, `detector.py` 49 %), because exercising those means running inference,
which the suite deliberately does not do. The analytics, the API and the storage
layer sit between 75 % and 100 %.

### Source encoding

```text
$ python -m backend.scripts.check_encoding
scanned 120 files: clean
```

### Frontend

```text
$ cd frontend
$ npm run typecheck
> flowlab-frontend@1.0.0 typecheck
> tsc -b --noEmit
                                     (no output, exit 0)

$ npm test
> flowlab-frontend@1.0.0 test
> vitest run

 RUN  v3.2.7 C:/Users/gohil/Documents/GitHub/FLOWLAB/frontend

 ✓ src/types/index.test.ts (4 tests) 6ms
 ✓ src/utils/format.test.ts (20 tests) 18ms
 ✓ src/state/ReplayContext.test.tsx (14 tests) 268ms
 ✓ src/components/Primitives.test.tsx (12 tests) 347ms

 Test Files  4 passed (4)
      Tests  50 passed (50)
   Start at  17:31:37
   Duration  3.83s
                                     (exit 0)

$ npm run build
> flowlab-frontend@1.0.0 build
> tsc -b && vite build

vite v6.4.3 building for production...
✓ 689 modules transformed.
dist/index.html                 0.77 kB │ gzip:   0.43 kB
dist/assets/index-*.css        28.45 kB │ gzip:   6.45 kB
dist/assets/react-*.js         50.89 kB │ gzip:  17.94 kB
dist/assets/index-*.js        330.43 kB │ gzip:  99.76 kB
dist/assets/charts-*.js       404.53 kB │ gzip: 109.96 kB
✓ built in 5.19s
                                     (exit 0)
```

There was no frontend test runner before 2026-09-30. The build sizes above differ
from the 2026-09-28 record because the two new components and the memoisation
changed the bundle; nothing else about the build changed.

### The launcher scripts

```text
$ "C:\Users\gohil\AppData\Local\Programs\Git\bin\bash.exe" -n run.sh
                                     (exit 0)

$ bash run.sh --help
  ./run.sh             start the API and the frontend dev server (default)
  ./run.sh install     install backend and frontend dependencies
  ./run.sh lint        ruff over backend/ plus the source encoding check
  ./run.sh test        run the backend test suite
  ./run.sh build       production build of the frontend
  ./run.sh check       everything: ruff, backend tests, source encoding,
                      frontend typecheck, frontend tests, frontend build
  ./run.sh doctor      check the environment only
  ./run.sh --help      this list
                                     (exit 0)

$ bash run.sh lint
Using Python 3.13.5  (python)

==== lint - ruff ==========================================================
All checks passed!

==== lint - source encoding ==============================================
scanned 120 files: clean

Lint passed.
                                     (exit 0)
```

This is a change from the 2026-09-28 record, which listed `run.sh` as
never-executed: a Git Bash is present on this machine, so `run.sh` has now been
syntax-checked and `lint` and `--help` have actually run through it. `run.sh
start`, `install`, `test`, `build` and `check` have not been run through bash.

### Environment doctor

```text
$ python -m backend.scripts.doctor
FLOWLAB doctor
  python     3.13.5 on Windows AMD64
  repository C:\Users\gohil\Documents\GitHub\FLOWLAB\data

  [ok  ] fastapi          0.141.1 — HTTP API
  [ok  ] uvicorn          0.54.0 — server
  [ok  ] pydantic         2.12.5 — data validation
  [ok  ] numpy            2.5.1 — arrays
  [ok  ] cv2              5.0.0 — video decode and annotation
  [ok  ] ultralytics      8.4.163 — detector
  [ok  ] torch            2.14.0+cpu — detector runtime
  [ok  ] pytest           9.1.1 — test suite (optional at runtime)  (dev only)
  [ok  ] opencv           version 5.0.0, encode/decode ok
  [ok  ] dependency pins  7 packages match requirements.txt
  [ok  ] model weights    yolo11n.pt present (5.6 MB)
  [ok  ] data folder      C:\Users\gohil\Documents\GitHub\FLOWLAB\data writable, 180447 MB free
  [ok  ] database         readable

All runtime dependencies are present.
                                     (exit 0)
```

The `dependency pins` line is a real check as of this pass: it parses the bounds
out of `backend/requirements.txt` and compares them with
`importlib.metadata.version`. Before this pass it printed `ok` unconditionally,
which is how an OpenCV 5.0.0 install survived a `>=4.10,<5` bound for months.
(The `repository` label prints the *data* directory, not the repository root; a
cosmetic mislabel in a script, noted rather than fixed.)

### Docker configuration, by inspection only

```text
$ python -c "import yaml; d=yaml.safe_load(open('docker-compose.yml')); ..."
services ['backend', 'frontend']
profiles {'backend': None, 'frontend': ['dev']}
ports {'backend': ['127.0.0.1:8000:8000'], 'frontend': ['127.0.0.1:5173:5173']}

$ python -m pytest backend/tests/test_dockerignore.py
47 passed in 0.13s
```

The compose file and the CI workflow both parse, and the 47 ignore tests pass.
**`docker compose build` and `docker compose up` have never been executed here**,
because Docker is not installed on this machine.

---

## 2. A displayed number traced to its samples

Re-run 2026-09-30, verbatim:

```text
$ python -m backend.scripts.trace_metric demo peak_queue
==========================================================================
metric: peak_queue   analysis: demo (demo dataset)
==========================================================================

1. INPUT - measurement rules in force
   queue polygon      : 4 points
   speed threshold    : 0.012 frame widths / s
   minimum queue stay : 0.5 s
   grid step          : 0.100 s (sample_fps 10.0)
   gap threshold      : 0.250 s
   trajectories       : 26

2. GRID - how many vehicles are inside the region and slow, per instant
   grid instants      : 1350
   reported peak      : 13
   time-average       : 4.3756
   occupied           : 98.2 s
   peak reached at    : 77.90 s (grid index 779)

3. HAND CHECK - rebuild that instant from the raw samples
   distinct vehicles inside the polygon and slow at t=77.90: [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]
   hand count = 13   grid count = 13
   agreement: YES

4. SUMMARY - what the API returns
   summary.peak_queue        : 13
   summary.average_queue     : 4.38
   queue_timeseries samples  : 675
   max over the API series   : 13
   summary matches series    : YES

5. EVENTS - the peak is a first-class event
   t=77.90  Peak queue reached: 13 vehicles
                                     (exit 0)
```

Identical to the 2026-09-28 trace, which is the point: the metric definitions
have not moved. The trace exists as a script so it can be re-run after any
change to the queue definition.

---

## 3. Accuracy against known ground truth

Re-run 2026-09-30, offline, verbatim (JSON output in full):

```text
$ python -m backend.scripts.validate_against_reference backend/demo/sample_reference.json
{
  "generated_at": "2026-09-30T17:31:23",
  "clip": {
    "path": "demo_school_dismissal.mp4",
    "source": "synthetic - generated by backend/scripts/build_demo_dataset.py",
    "permission": "generated by this project; no third-party footage involved",
    "duration_s": 135.0,
    "width": 1280,
    "height": 720,
    "source_fps": 10.0,
    "sampling_fps": 10.0,
    "model": "yolo11n.pt",
    "confidence": 0.25,
    "speed_threshold": 0.012,
    "min_queue_seconds": 0.5
  },
  "environment": {
    "python": "3.13.5",
    "platform": "Windows AMD64",
    "processing_seconds": 0.0
  },
  "computed": {
    "vehicles_tracked": 26,
    "vehicles_crossed_exit": 26,
    "peak_queue": 13,
    "average_wait_s": 14.72,
    "max_wait_s": 43.9,
    "throughput_per_min": 11.56
  },
  "queue_series": {
    "compares_against": "region occupancy (vehicles inside the polygon, any speed)",
    "reference_points": 1350,
    "matched_points": 1350,
    "mean_absolute_error": 0.028,
    "max_absolute_error": 1,
    "exact_match_rate": 0.9719
  },
  "queue_length_app_definition": {
    "compares_against": "queued (inside polygon AND below speed threshold for >= min_queue_seconds)",
    "reference_points": 1350,
    "matched_points": 1350,
    "mean_absolute_error": 0.188,
    "max_absolute_error": 2,
    "exact_match_rate": 0.8185
  },
  "exit_crossings": {
    "window_s": 135.0,
    "computed": 26,
    "reference": 26,
    "absolute_error": 0,
    "relative_error": 0.0
  },
  "arrivals": {
    "window_s": 135.0,
    "computed": 26,
    "reference": 26,
    "absolute_error": 0,
    "relative_error": 0.0
  },
  "reference_notes": "Ground truth rebuilt from the simulator's own per-vehicle positions. ..."
}
                                     (exit 0)
```

The figures are unchanged from the 2026-09-28 record: arrivals 26/26, exit
crossings 26/26, region occupancy **0.028** vehicles mean absolute error (max 1,
97.2 % exact), queued series against the slow-rule counts **0.188** vehicles
(max 2, 81.8 % exact). The first block is like for like: both sides count every
vehicle geometrically inside the polygon at any speed, and the small residual is
the chart thinning. The second block compares two different quantities on
purpose, and is reported separately for exactly that reason.

The sensitivity range, also re-derived on 2026-09-30 from the bundled demo
analysis: exit service time 3.214 / 4.286 / 6.429 s gives peak queue
**12 / 14 / 17** and mean wait **27.07 / 37.39 / 56.54** s. It remains a
sensitivity range and not a confidence interval, because no probability has been
computed.

---

## 4. Real video, end to end *(2026-09-28; not repeated on 2026-09-30)*

```text
$ curl -F "file=@clip_b.mp4" /api/uploads            -> 202, analysis fff1b16e8881
$ GET /api/analyses/fff1b16e8881/status              -> detecting 23% -> 73% -> 100%
$ GET .../video/annotated  (Range: bytes=0-1023)     -> 206, content-range 0-1023/2068368
```

Clip: 1280x720, 20 s, 15 fps source, sampled at 10 fps, 150 frames processed in
59.8 s on CPU. 19 tracks created, 13 survived the noise filter, median track
length 8 samples, 2 vehicles crossed the exit line.

**This clip is a public-domain 24x time-lapse and is a poor case for the
detector.** Vehicles are a few pixels wide and move several car lengths between
sampled frames, so the queue metrics are near zero. That is reported honestly in
`docs/VALIDATION_REPORT.md` rather than hidden.

---

## 5. Browser workflow *(2026-09-28; not repeated on 2026-09-30)*

Driven through headless Chrome over CDP, reading the rendered DOM. This pass
changed the Home page (saved analyses panel, degraded-mode banner), the export
menu, `CorridorMap` and the accessibility layer, so these rows are evidence for
the 2026-09-28 build, not for the current one. They have not been re-driven.

| Check | Result |
| --- | --- |
| Demo loads and replays | transport, map dots, chart cursor all present |
| Seek to 40 s | clock reads `00:40 / 02:15` |
| Click the peak event | clock moves to `01:17`, matching the event time |
| `why?` on Peak queue | "Peak value 13 vehicles / First reached at 77.90 s" |
| Click bottleneck Rank 1 | "Highlighting 26 vehicles measured as slowed in bottleneck cell 1" |
| Zero-vehicle analysis | every card shows a reason, map says "Nothing to plot", simulate link disabled, zero `why?` buttons |
| Evidence panel | 7/7 expected rows on the demo |
| Scenario: Spread +120 s | A 13 / B 7 / C 1 peak queue; stale marker appears on control change and clears on re-run |
| Sensitivity range | 3.2 s -> 12, 4.3 s -> 14, 6.4 s -> 17 peak queue, labelled "not a statistical confidence interval" |
| Print brief | 7 sections, demo label present, `document.querySelectorAll('video, img[blob]')` empty |
| Narrow 1024 px and 1280 px | no horizontal overflow; cards reflow to three columns |
| Unknown analysis id | error notice naming the id, no crash |

The keyboard paths added in this pass (Enter/Escape on the video draw tools,
focus return from the export menu, the skip link) are implemented and type-check,
but **have not been driven in a browser**. Treat that as untested until someone
tabs through it.

---

## 6. Error and edge cases *(2026-09-28; the API cases are additionally covered by the suite)*

| Input | Result |
| --- | --- |
| `.exe` upload | 415 with the accepted formats listed |
| Text bytes named `.mp4` | 400 "could not be opened as a video" |
| Empty file | 400 |
| Clip with no vehicles (synthetic empty car park) | completes with `tracked=0`, all measurements `null` (not 0), actionable warning, no dead controls |
| Self-intersecting region | 422 "crosses over itself" |
| Region below the minimum area | 422 "too small to measure" |
| Simulation with no arrivals | 400 explaining that there is nothing to simulate; the UI disables the link beforehand |
| Delete while processing | 409 "still being processed" |
| Delete an unknown id | 404 |
| Interrupted job (record left `processing`) | marked failed on startup with a retry hint |
| A failing analysis | now reaches the database as `error`; before this pass the failure path raised `TypeError` and left the row at `processing` until a restart. Covered by `backend/tests/test_job_failure.py` |

---

## 7. Checks that could not run here

- **`docker compose build` / `up`** — Docker is not installed on this machine.
  The compose file, the ignore rules and a matcher test are verified; the build
  itself is not.
- **CI** — `.github/workflows/ci.yml` has never executed. Its YAML parses and its
  steps were each run by hand locally, but the hosted runners, the Python 3.11
  leg and the Node 20 leg have not run.
- **mypy on Python 3.11** — only 3.13 is installed here. `pyproject.toml` sets
  `python_version = "3.12"` on purpose (numpy >= 2.3 ships PEP 695 `type`
  statements in its stubs that mypy cannot parse under 3.11 semantics), so a 3.12
  only syntax slip would be caught by the CI 3.11 leg, not by the type checker
  run locally.
- **`run.sh start`, `install`, `test`, `build`, `check`** — only `--help` and
  `lint` were run through Git Bash. The full `check` was run as its individual
  commands.
- **GPU path** — `device=auto` resolves to CPU; the CUDA branch has not run.
- **Long clips** — only 20 s clips were processed end to end. A 10-minute clip
  would exercise the 900-sample cap, the video writer and the SQLite payload at
  a scale never tested.
- **Two browser tabs on one analysis** — concurrent region edits are guarded by
  a request token, but the two-tab case was not exercised.
- **Keyboard-only navigation** of the region editor and the replay, in a real
  browser.
- **Real-footage reference annotations** — requires a clip the student may use.
  The tooling is complete; the evidence does not exist yet.

---

## 8. What this record does not claim

- No accuracy figure for the detector on real footage. Every number above is
  either synthetic ground truth or a count on a deliberately unsuitable clip.
- No deployment, user, school, testimonial or congestion-reduction result.
- No proof that the container image builds or that CI is green.
- "Runs locally" is accurate; "fully offline" is not, and the README says the
  model weights are downloaded once.
