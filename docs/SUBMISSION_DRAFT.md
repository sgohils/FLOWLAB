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

**Validation.** The measurement layer is checked against ground truth that is
known by construction (`docs/VALIDATION_REPORT.md`): the arrival and exit counts
match exactly, and the queue length series agrees to a mean absolute error of
**0.211 vehicles** across 1350 instants, with the residual fully explained by the
deliberate 0.5 s stability rule. **The detector is not yet validated against
human annotation of real footage** — that is the next piece of work and is
listed as the student's task.

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
- **Testing:** 129 automated tests (pytest + FastAPI TestClient)
- **Tooling:** Git, headless Chrome for interface verification

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

## 7. What I would do next

1. Complete the hand-annotated validation on a real school-gate clip, and report
   the error honestly whatever it is.
2. Study how the measurements move when the sampling rate changes (5, 10, 15 fps).
3. Add a second exit gate with a routing matrix, so a scenario can test
   *where* to send cars, not only how fast they are processed.
4. Add perspective calibration from four surveyed points so real units become
   defensible.

## 8. AI and external tool disclosure

- **Tool used:** an AI coding assistant (Kilo) inside Visual Studio Code, plus
  Git and headless Chrome.
- **Extent:** the large majority of the code was written with AI assistance and
  then reviewed, tested and corrected. Every defect found in the second pass is
  listed in `docs/AI_ASSISTANCE.md`, including the ones the AI itself introduced.
- **Student-owned work:** the annotated real-footage validation, the design
  decisions, the interpretation and the experiments listed in
  `docs/STUDENT_CONTRIBUTIONS.md`.
- **No fabrication:** no accuracy claim, user interview, testimonial, deployment
  or congestion-reduction figure is made anywhere in this submission. Where
  evidence is missing it is marked as pending.

> **Confirm whether the official rules or your district require this disclosure
> on a separate form, and in what format.**
