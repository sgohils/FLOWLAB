# Contributing to FLOWLAB

FLOWLAB is a local-only traffic-video analysis tool: a FastAPI backend and a
React single page app, with no server component and no account. Everything runs
on your machine.

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.11+ (CI runs 3.11 and 3.13) | `requires-python` in `pyproject.toml` |
| Node.js | 20+ (CI runs 20 and 24) | Vite 6 is the build tool; there is no `engines` field to satisfy |
| ffmpeg | any recent | only needed to read exotic video containers; OpenCV usually copes without it |
| ~2 GB disk | | measured on this checkout: torch 1.05 GB, opencv-python 289 MB, numpy 64 MB |

Nothing else. There is no database server, no Docker requirement and no API key.

## Install

```bat
run.bat install          REM Windows
./run.sh install         # macOS / Linux
```

That installs three things: the runtime Python packages
(`backend/requirements.txt`), the development tools
(`backend/requirements-dev.txt` - pytest, httpx, ruff, mypy, pytest-cov and
pre-commit) and the frontend packages. `pyproject.toml` is the source of truth
for the dependency versions; the two requirements files mirror it so a plain
`pip install -r` works without a build step, and two tests in
`backend/tests/test_doctor.py` fail if either copy drifts.

## Is it healthy? One command

```bat
run.bat check            REM Windows
./run.sh check           # macOS / Linux
```

`check` runs, in order: `ruff check backend` → `mypy` → the pytest suite → the
source encoding check → `npm run typecheck` → `npm test` → `npm run build`.

That is the same set of checks the two CI jobs run, so if `check` passes
locally the pull request will. (CI differs in breadth, not in kind: it runs the
backend job on Python 3.11 and 3.13 and the frontend job on Node 20 and 24, and
it uploads coverage XML. `check` does *not* run the pre-commit hooks; those are
three extra local-only steps, listed at the end.) Individual pieces are
available too:

| Command | What it does |
| --- | --- |
| `install` | installs everything listed above |
| `lint` | ruff over `backend/` plus the source encoding check |
| `test` | the backend pytest suite plus the encoding check |
| `build` | the production frontend bundle into `frontend/dist` |
| `doctor` | reports the environment; changes nothing |

> **One surprise on a fresh clone:** the first `test` (or `check`) downloads the
> YOLO checkpoint, about 6 MB. Nothing in the pipeline needs it - the demo
> dataset is synthetic and no test runs inference - but
> `test_health_reports_the_model_state` calls `/api/health`, and that endpoint
> loads the detector, so Ultralytics fetches `yolo11n.pt` the first time it is
> missing. It happens once and is cached afterwards. Point `FLOWLAB_MODEL` at a
> path that does not exist to skip the download entirely: the health endpoint
> then reports `degraded` and the test still passes. That is what CI does
> (`FLOWLAB_MODEL: ci-no-such-model.pt`).

## Layout, on one screen

```text
flowlab/
├── pyproject.toml        ruff, mypy, pytest, coverage, dependencies
├── run.bat / run.sh      install, lint, test, build, check, doctor, start
├── docker-compose.yml    one app on :8000; `--profile dev` adds Vite on :5173
├── backend/
│   ├── main.py           FastAPI app, error handling, SPA hosting
│   ├── config.py         every tunable, environment overrides
│   ├── geometry.py       dependency-free primitives (area, centroid, ray cast)
│   ├── api/              routes, job manager, exports, shared state
│   ├── analytics/        the metrics: motion, queue, wait, throughput,
│   │                     bottlenecks, events, timeline, suggestions
│   ├── simulation/       calibration, scenarios, corridor simulator
│   ├── vision/           detector, trajectories, annotator, video processor
│   ├── models/schemas.py the Pydantic contract for the whole API
│   ├── storage/          SQLite and file helpers
│   ├── validation/       how to write reference annotations
│   ├── scripts/          doctor, demo dataset, validation, dev tools
│   ├── demo/             the bundled synthetic dataset and its ground truth
│   └── tests/            357 tests
└── frontend/src/
    ├── api/client.ts     typed client, one error shape
    ├── types/index.ts    TypeScript mirror of the schemas
    ├── state/            analysis context, shared replay clock
    ├── test/             vitest setup, and the U+FFFD sweep over src/
    ├── components/       uploader, viewer, region editor, replay transport,
    │                     maps, charts, evidence panels, print brief
    ├── pages/            Home, Analysis, Simulation
    └── utils/format.ts   shared formatting
```

## Architecture: the layering rule

Dependencies run in **one direction only**. Nothing below ever imports from
above. This is the actual import graph, not an idealised one:

```text
geometry.py, config.py   import nothing from the project at all

models/      -> geometry              simulation/ -> models
storage/     -> config                vision/      -> models, config
analytics/   -> geometry, config, models, simulation
api/         -> analytics, simulation, vision, storage, models, config
main.py      -> api, storage, vision, config
scripts/     -> anything (see below)
```

- `analytics/metrics.py` imports `simulation/traffic_model.calibrate`, so
  `analytics/` sits *below* `simulation/` rather than beside it. That is the one
  edge in the graph that is not a straight line down.
- `scripts/` is outside the graph entirely. Those are operator CLIs (`doctor`,
  the demo builder, the validation runner) and they may import anything; they
  are also excluded from mypy and from coverage, because they are run by hand
  and judged by their output.
- `backend/geometry.py` is the **bottom layer**: polygon area, centroid,
  point-in-polygon, line crossings. It imports nothing from the project at all,
  which is why `models/schemas.py` can validate a region without pulling in the
  analytics layer that imports the schemas.
- `models/schemas.py` is the single contract. The frontend mirrors it in
  `frontend/src/types/index.ts`; if you change one, change the other in the
  same commit or `npm run typecheck` will tell you what drifted.
- `api/` may reach into analytics, simulation, vision and storage. Those layers
  may not reach back into `api/`.
- If you find yourself wanting an import from a lower layer into a higher one,
  the thing you want usually belongs in a shared module, not in a back-edge.

## House rules

These are the invariants that are easy to break by accident. Most of the test
suite exists to defend them.

**1. Geometry is normalised 0-1 image coordinates.** `x` is a fraction of the
frame width, `y` a fraction of the height, both in `[0, 1]`. Never store or
compute in pixels. This is what lets the user redraw a region on a resized
player without invalidating the analysis, and it is why the frontend never needs
to know the video resolution.

**2. Every metric is a count or a difference of timestamps.** There is no
congestion score, no weighted composite, no "confidence" attached to a queue
length. If a number cannot be written as `N / dt` or `t_end - t_start` over
the tracked vehicles, it does not belong in the result. A measurement that
could not be made is `null` with a reason, never `0` - `mean_or_none()` in
`backend/analytics/motion.py` is the helper that exists for this.

**3. No `random` in the simulator or the analytics.** The digital twin has to
be reproducible: the demo dataset, the ground truth and the validation report
all assume the same seeded scenario every time. If you need variation, take it
from the observed data.

**4. No face, plate or identity processing, anywhere.** Not for a debug view,
not behind a flag. The detector requests only the five COCO *vehicle* class ids
in `COCO_CLASS_IDS` in `backend/config.py` - bicycle, car, motorcycle, bus,
truck - and `person` is deliberately absent. Trajectories carry anonymous
integer ids that mean nothing outside one analysis.

**5. `api_error()` is the only way to return a 4xx.** The UI expects exactly one
error shape - `{"message": ..., "hint": ...}` - from every failing endpoint, and
never a traceback. Raising a bare `HTTPException` with a dict detail, or letting
a `ValueError` become a 500, breaks that contract for the client.
`backend/api/errors.py` is the only module that imports `HTTPException`.

**6. One clock.** The replay is one instrument, not five screens: the video, the
map, the chart, the timeline and the inspector all read the same
`ReplayContext` clock. If you add a sixth view, drive it from that clock.

**7. Unknown is not zero.** A tracking gap means the position is *unknown*.
The replay payload encodes that as separate `segments` precisely so the client
cannot draw a straight line across the gap. Preserve that.

## Adding a test

Tests live in `backend/tests/` and are plain pytest - no test classes, no
fixture magic beyond `conftest.py`.

```python
# backend/tests/test_metrics.py
from backend.analytics.motion import detect_stops
from backend.tests.conftest import drive_through, make_track


def test_a_short_pause_is_not_a_stop():
    track = make_track(1, drive_through(0.3, y=0.6, stop_at=0.6, stop_seconds=0.5))
    assert detect_stops(track, 0.012, 1.5, 1.25) == []
```

- One behaviour per test, and the name says what it asserts, not what it calls.
- Build tracks with the `conftest.py` helpers - `make_track`, `make_points`,
  `drive_through`, `make_regions` - rather than hand-rolling
  `TrajectoryPoint`s.
- A test that cannot fail is worse than no test: make sure you have seen it
  fail for the right reason before you make it pass.
- If it needs the real YOLO model or a real video, it does not belong in the
  default suite - mark it `@pytest.mark.slow`. CI passes `-m "not slow"`, so a
  marked test is skipped there. Nothing is marked slow today.

Frontend tests are vitest + Testing Library, colocated next to the component
(`Primitives.test.tsx`), and assert on what a user can see:

```tsx
render(<Primitives.Row label="Peak queue" value="7" />)
expect(screen.getByText("7")).toBeInTheDocument()
```

## Running it

```bat
run.bat                  REM Windows: API on :8000, Vite on :5173
./run.sh                 # macOS / Linux
```

The API is on <http://127.0.0.1:8000> and its OpenAPI docs on `/docs`. The
frontend dev server is on <http://127.0.0.1:5173> and proxies `/api` to the
backend, so the browser stays on one origin and CORS is not involved in
development. Both bind to loopback on purpose: **the API has no
authentication**, so the browser origin list in `backend/config.py` and the
loopback binding are the only access boundary there is. `backend/config.py`
refuses to start on any `FLOWLAB_CORS_ORIGINS` entry that is not an http(s)
loopback origin, so a routable host needs the documented
`FLOWLAB_ALLOW_UNSAFE_CORS=1` escape hatch and a log line naming what it let
through. Do not put the published Docker port on `0.0.0.0` either, without
putting authentication in front of it first.

Alternatively, one container serving both halves on <http://localhost:8000>:

```bash
docker compose up --build              # production bundle, one app
docker compose --profile dev up        # + the Vite dev server for hot reload
```

Both containers are gated on `GET /api/ready`, which returns 503 until the
detector has loaded. `GET /api/health` stays 200 either way, because the
browser banner in `ApiHealthBanner.tsx` needs to read *why* the backend is
degraded - which is why the container probe uses `/api/ready` and the banner
uses `/api/health`.

## Before you push

```bat
run.bat check
```

If you installed the pre-commit hooks (`pre-commit install`), they check more
than that: YAML parseability, trailing whitespace, a final newline on every
text file, ruff, and the source encoding. All of them are also CI steps, except
the first three, which are cheap enough to be worth having locally.
