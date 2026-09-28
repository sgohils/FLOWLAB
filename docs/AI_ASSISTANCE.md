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
3. **Run the whole suite.** 142 tests, then the production build, then the
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
implement, change and defend personally. `docs/DECISIONS.md` records ten design
decisions with their alternatives, so the student can challenge any of them.

---

## What the student still has to do

See `docs/STUDENT_CONTRIBUTIONS.md`. In summary:

- Complete the annotated validation on a real clip (the AI cannot annotate
  footage the student has permission to use on the student's behalf).
- Own at least one implemented change, with the design decision written down.
- Write the motivation, the story and the reflection in their own words.
- Verify the district and national requirements, including whether a separate
  AI-use disclosure form is required.
