# Submission draft

**Status: draft for the student to complete.** Sections marked *to be completed*
contain no invented content on purpose — a submission that describes a story you
did not live is both wrong and a rule violation.

Before submitting, verify against
[the 2026 rules](https://www.congressionalappchallenge.us/wp-content/uploads/2026/05/2026-CAC-Rules.pdf)
and your district's own requirements. Confirm: the submission format, whether a
video is required and its length limit, whether a separate AI-use disclosure form
is required, and the exact deadline and timezone. **The deadline stated in the
project brief is 26 October 2026 at 12:00 EDT — confirm it, and check your
district's deadline, which may be earlier.**

---

## 1. What is FLOWLAB

FLOWLAB is a local-first web application that turns ordinary traffic video into
anonymous vehicle trajectories, a set of explainable traffic measurements, and a
simplified traffic simulation. It is built for the arrival and dismissal traffic
that happens at a school gate, where the visible problem — a line of cars — is
easy to see and hard to quantify.

The application runs entirely on one machine: a Python/FastAPI backend with an
open-source detector, a React interface, local files and a local SQLite database.

**Intended audience:** a school administrator who already suspects the junction
is the problem and wants evidence; and a student who wants to see a computer
vision pipeline end to end, from a video file to a number they can check by hand.

## 2. Inspiration

*To be completed by the student.* Use these prompts — do not copy an answer that
is not true for you.

- What did you notice first, and where?
- Who did you speak to about it, and what did they say?
- What did you already know about traffic or queues before starting?
- What is the smallest question you wanted to answer, that you could check
  yourself?

> **To be completed by the student.**

## 3. Technical challenges, and what was done about them

These are real problems that came up while building it, with the fixes in the
repository. Each is verifiable by reading the code or running the tests.

| Challenge | What it caused | What was done |
| --- | --- | --- |
| A vehicle can only be in one place at one instant, but its motion is sampled | The reported peak queue could exceed the number of vehicles in the clip | A per-vehicle cursor makes the sampling cursor move forward, so a vehicle is never counted twice for the same instant. Regression test: `test_peak_queue_can_never_exceed_the_vehicle_count` |
| A vehicle already queueing when the clip starts has an unknown entry time | Its wait was being reported as a full, completed wait, biasing the average | The first visit of a track is now **censored** and excluded from the wait averages, with the censored count shown |
| Two definitions of "queued" disagreed | Queue length used no duration threshold while "stopped" used 1.5 s, so jitter could create a queue but never a stop | `min_queue_seconds` (default 0.5 s) is applied to both the queue series and the wait visits |
| A second processing lane had no effect at all | Vehicles being served blocked the lane, so the scenario control silently did nothing | Vehicles at the gate are treated as out of the lane, so a second lane genuinely doubles capacity. Test: `test_second_channel_reduces_the_queue` |
| Vehicles at the same position ignored each other | Later arrivals could overtake earlier ones in the model | The leader lookup was rebuilt as a proper chain, front to back, with a no-overtaking invariant test |
| Deleting an analysis left the footage on disk | 5.9 MB of uploaded video survived a delete the interface described as removing the analysis | Delete now removes the upload, the annotated video, the result and the database row, and reports how much space it freed |
| A restart left jobs "processing" forever | The interface polled a job that no longer existed, with no error and no way out | Orphaned records are marked as interrupted on startup with a message and a way to retry |
| An observed-vs-model difference could be read as the effect of an intervention | The comparison was dishonest about where the number came from | The result is now a three-way comparison: observed, unmodified model, modified model, with model error and scenario effect reported separately |
| The detector is blind at a distance | A telephoto clip produced a handful of tiny tracks | An optional region-of-interest crop is applied before inference, which roughly tripled the detections on the test clip |
| Thinning the queue series for the chart dropped short peaks | The chart could show a **smaller** peak than the metric card beside it | Each bucket keeps its maximum, so the displayed series can never under-report a queue. Test: `test_thinned_series_never_loses_a_brief_peak` |
| **Every failed analysis raised `TypeError` before it could be recorded** | The failure path passed `status=` to a parameter named `status_value`, so the database row stayed at `processing` until the next restart and the user saw a job that would never finish | One keyword, found by enabling the type checker, plus `backend/tests/test_job_failure.py` |
| **No database connection was ever closed** | `with connection:` in sqlite3 ends a transaction, it does not close; every read and write leaked a handle | `_connect()` is now a context manager that closes in a `finally`. Found by turning warnings into errors; 6 tests pin the lifetime |
| **A "runs on my machine" API could serve files outside its own directory** | The single page app route took the request path and served it unchecked | The path is resolved and checked for containment, falling back to `index.html` |
| **The environment checker could not fail** | It reported "ok" for installed versions whatever they were, so an OpenCV 5 install survived a declared `<5` bound for months | The bounds are read from `requirements.txt` and compared with what is actually installed; 20 tests |
| **The interface's help promised a key that did nothing** | "Press Enter" was in the on-screen instructions and no handler existed | Enter closes a region polygon and Escape abandons the draft; plus a focus ring, reduced-motion support, live status and a skip link |

**Testing.** 277 backend tests and 50 frontend tests, none of which touch the
network or run the detector, plus ruff, mypy with warnings-as-errors, coverage
measurement, and a CI matrix that runs on Python 3.11 and 3.13 and Node 20 and
24. Twelve of the defects above were found *by that tooling*, not by using the
application, and each now has a regression test.

**Validation.** The measurement layer is checked against ground truth that is
known by construction (`docs/VALIDATION_REPORT.md`): the arrival and exit counts
match exactly, and the region occupancy series - every vehicle inside the region
at any speed - agrees with the reference's own occupancy counts to a mean
absolute error of **0.028 vehicles** across 1350 instants, never more than 1 and
exact on 97.2 % of them, with the small remainder explained by the chart thinning
rather than by a rule difference. The application's queued series (inside the
region and below the speed threshold for at least 0.5 s) is a different quantity
and is reported against the reference's slow-rule counts as its own block, where
the residual of 0.188 vehicles is the deliberate 0.5 s stability rule. Re-run
2026-09-30, unchanged.
**The detector is not yet validated against human annotation of real footage** —
that is the next piece of work and is listed as the student's task.

## 4. What I learned and what I contributed

*Learning section to be completed by the student, in your own words.* Useful
anchors, all of which are true of this project:

- Sampling the video at 10 frames a second instead of every frame is a
  three-times speed-up, and the trade-off is one you can reason about from the
  distance a car covers in a tenth of a second.
- Most traffic metrics are not vision problems at all. Once you have positions,
  queue length is a count, throughput is a count divided by a duration, and a
  wait is a difference of timestamps.
- The hard part of an honest tool is not the maths, it is deciding what you are
  allowed to claim. Censored visits, approximate units and a model-fidelity
  readout exist because the first version of each was quietly wrong.
- Determinism matters: the simulator uses no random numbers, so running the same
  scenario twice gives the same answer, which is what makes an A/B comparison
  mean anything.

> **To be completed by the student.**

**Contributed by the student — to be completed.** List the work that is yours:
the annotated validation on a real clip, any definition you changed, any bug you
found, and the experiments you ran. See `docs/STUDENT_CONTRIBUTIONS.md`.

> **To be completed by the student.**

## 5. Built with

- **Languages:** Python 3.13, TypeScript
- **Backend:** FastAPI, Uvicorn, Pydantic, OpenCV, Ultralytics YOLO11n with
  ByteTrack, NumPy, SQLite
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS 4, Recharts
- **Modelling:** a reduced Intelligent Driver Model (car following) with a
  service gate, written for this project
- **Testing:** 277 backend tests (pytest + FastAPI TestClient) and 50 frontend tests (vitest + React Testing Library on jsdom); ruff, mypy and coverage as enforced gates
- **Tooling:** Git, ruff, mypy, pre-commit, GitHub Actions (Python 3.11 and 3.13, Node 20 and 24), headless Chrome for interface verification

## 6. Honest limitations

- No camera calibration, so positions and speeds are in image coordinates; the
  interface never reports km/h or metres.
- The digital twin is a single lane with one gate. Merges, signals, multiple
  approaches and pedestrians are not modelled.
- The unmodified model reproduces the observed peak queue of the demo clip with a
  factor of 0.54, so scenario results are meaningful as a *change from the
  baseline*, not as absolute predictions.
- The detector has not been validated against human annotation of a real clip.
- One queue region, one corridor: FLOWLAB is a teaching and exploration tool, not
  a traffic engineering study.
- The sampling rate is not validated: it is not known how much any metric moves
  between 5 and 15 frames a second.
- The container path is unverified. Docker was not available on the machine
  this was built on, so the image has been reviewed and its build inputs
  tested, but it has never been built or run.
- The exit service time is a lower bound, and a queue of one vehicle is
  ambiguous: a car pausing at a kerb looks like a car joining a queue.

## 7. What I would do next

1. Complete the hand-annotated validation on a real school-gate clip, and report
   the error honestly whatever it is.
2. Drive the interface end to end in a browser, including with the keyboard alone.
   The most recent changes have been type-checked but not seen rendered.
3. Study how the measurements move when the sampling rate changes (5, 10, 15 fps).
4. Add a second exit gate with a routing matrix, so a scenario can test
   *where* to send cars, not only how fast they are processed.
5. Add perspective calibration from four surveyed points so real units become
   defensible.
6. Build the container image and get one green CI run, so both stop being
   statements of intent.

## 8. AI and external tool disclosure

- **Tool used:** an AI coding assistant (Kilo) inside Visual Studio Code, plus
  Git and headless Chrome.
- **Extent:** the large majority of the code was written with AI assistance and
  then reviewed, tested and corrected. Every defect found in the second pass is
  listed in `docs/AI_ASSISTANCE.md`, including the ones the AI itself introduced.
- **This was true of the most recent pass too.** The engineering pass of
  2026-09-30 was AI-driven: it enabled the linter and type checker, found and
  fixed two defects that had shipped, removed dead code, added the frontend
  test suite and the continuous-integration workflow, and ran every
  verification command it claims. The full disclosure is in
  `docs/AI_ASSISTANCE.md`.
- **Student-owned work:** the annotated real-footage validation, the design
  decisions, the interpretation and the experiments listed in
  `docs/STUDENT_CONTRIBUTIONS.md`.
- **No fabrication:** no accuracy claim, user interview, testimonial, deployment
  or congestion-reduction figure is made anywhere in this submission. Where
  evidence is missing it is marked as pending.

> **Confirm whether the official rules or your district require this disclosure
> on a separate form, and in what format.**
