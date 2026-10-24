# Judge Q&A — expected questions and honest answers

Every answer below describes what the code actually does. Where the honest answer
is "it is not validated" or "that is a known limitation", say so — a judge will
respect a known limitation far more than a confident claim.

**Participant name:** ______ **Date:** ______

---

### 1. Why YOLO, and why ByteTrack?

**Q: Why use a pretrained YOLO model instead of training your own?**

A: Because the interesting problem is not the detector — it is everything
after it. YOLO11n is a small open-source checkpoint that already recognises
cars, buses, trucks, motorcycles and bicycles. Training a detector would have
consumed the whole project and told us nothing about traffic measurement. I did
not train anything; `yolo11n.pt` is downloaded on first use.

**Q: Why ByteTrack for tracking?**

A: Because I need a *stable id* per vehicle across frames, and the measurements
are all built on those ids. ByteTrack associates low-confidence detections too,
which matters here: a vehicle half hidden behind another still produces a
detection, and dropping it would break the track. Each id is internal to one
clip and is shown as `Car #014`.

---

### 2. What happens when a track is lost?

**Q: A vehicle disappears for two seconds. What does FLOWLAB do with it?**

A: Three separate things, deliberately:

1. **The trajectory keeps a gap.** Samples more than 2.5 sampling intervals
   apart are not connected.
2. **Nothing is invented across the gap.** No distance is accumulated for a stop
   or a crossing, because we do not know where the vehicle was. A crossing that
   would have to be interpolated across the gap is discarded rather than guessed
   (`test_crossing_is_not_bridged_across_a_tracking_gap`).
3. **A queue visit that is open when the track ends is censored**, and censored
   visits are excluded from the wait averages and reported separately.

**Q: And a vehicle that is already queueing in the first frame?**

A: Its first visit has no known start, so it is left-censored too. This was a
real bug: the first version counted it as a completed wait, which is wrong
because the vehicle may have been waiting before the clip started.

---

### 3. How are queue and wait calculated?

**Q: Define "queued" exactly.**

A: A vehicle is queued at time *t* when it is **inside the queue polygon the
user drew** *and* its motion is **below the speed threshold** (default 0.012
frame-widths per second) *and* it has been below that threshold continuously for
at least `min_queue_seconds` (default 0.5 s). The position between two samples
is interpolated, and the queue length is sampled on a fixed time grid.

**Q: Why a 0.5 second rule?**

A: Because a single noisy detection should not create a queue. Before this
rule, the queue definition and the separate "stopped" definition disagreed: a
one-sample flicker could produce a queue entry but never a stop. Adding a
duration rule to both made them consistent. It also means the pipeline is
slightly behind the raw rule while a queue is growing — and I measured that: it
is the entire explanation for the 0.188-vehicle gap in the validation block that
compares the queued series against a slow-rule reference with no hold. The
like-for-like occupancy comparison is unaffected and comes out at 0.028
vehicles.

**Q: What is "estimated wait"?**

A: The time a vehicle spent inside the queue region while slow, for at least
0.5 s at a time, counting only visits that both started and ended inside the
clip. It is labelled *estimated* everywhere because there is no camera
calibration: positions are image coordinates, so the number is "seconds of
clip time inside this polygon", not a verified measure of real-world queueing.

**Q: How is throughput defined?**

A: Vehicles whose trajectory crosses the exit line, divided by the clip
duration in minutes. Each vehicle is counted at most once per line. The crossing
must happen on the finite segment, not on the infinite line, and the crossing
time is interpolated between the two samples that straddle it. The observation
window is the whole clip, and the interface says so — a clip that starts and
ends with a queue reports a lower rate than the instantaneous rate in the
middle.

---

### 4. Why call it a simplified digital twin?

**Q: What is actually being simulated?**

A: One lane, normalised to length 1, with a processing gate at the far end.
Vehicles move with a reduced Intelligent Driver Model — a standard car-following
equation — and the gate is a virtual stopped obstacle whenever all processing
lanes are busy. A queue forms for exactly the reason it forms in reality: if
arrivals outrun the service rate, the vehicles behind the gate stop.

**Q: What is calibrated from the footage, and what is not?**

A: Calibrated: the arrival sequence (from entry-line crossings), the exit service
time, the free-flow travel time, the observation window. Not calibrated and not
claimed: merging, opposing traffic, signals, multiple approaches, pedestrians,
and any real-world speed or distance.

**Q: How do you know the model is any good?**

A: By replaying the observed arrivals through the *unmodified* model and
comparing with the footage. That number is shown in the interface as "how well
the model reproduces the clip". On the demo dataset it is a factor of 0.54 on
peak queue — which is why the scenario results are presented as the change from
the baseline, never as an absolute prediction.

**Q: Is the baseline forced to match?**

A: No, and the code makes that hard: the baseline always replays the *original*
arrival series, so a scenario that changes the volume or the timing cannot
inflate its own fidelity number. There is a test for it
(`test_fidelity_is_independent_of_the_scenario`).

---

### 5. How is the model calibrated, and how was it validated?

**Q: Where does the exit service time come from?**

A: From the highest throughput the exit actually achieved while a queue was
present — a queue keeps an exit at full capacity, so that window measures the
capacity rather than the arrival rate. It is a **lower bound**, and every
fallback (fastest quartile of departure gaps, then a documented 3.0 s default) is
written into the calibration notes and shown in the interface.

**Q: How do you know the measurements are right?**

A: The demo scene is generated by a simulation, so the true position of every
vehicle at every instant is known. I rebuilt the counted series from those
positions with the same rules the analytics use and compared. Arrival and exit
counts match exactly. For the region occupancy - every vehicle inside the
polygon, at any speed - the like-for-like comparison over 1350 instants gives a
mean absolute error of 0.028 vehicles, never more than 1, and 97.2 % of instants
exact; the near-zero residual is the chart thinning, not a rule difference. The
application's own queued series (inside the polygon and slow for at least 0.5 s)
is a different quantity and is reported against the reference's slow-rule counts
separately, where it agrees to 0.188 vehicles. Full numbers in
`docs/VALIDATION_REPORT.md`.

**Q: That validates the maths, not the detector. What about the detector?**

A: Correct, and I have not validated it. That needs a clip I am permitted to use
plus my own hand annotations, and it is the first task in my contribution list.
What I can say is what the tool *does* on hard footage: on a distant 24×
time-lapse clip it produced 19 tracks of which 13 survived the noise filter, with
a median length of 8 samples — which is why the app has a region-of-interest
crop and why the demo script tells me to use my own footage.

**Q: How accurate is it, then?**

A: I do not know yet, and I am not going to quote a number I have not measured.
The first step is the annotated validation; the honest answer after that will be
whatever it is.

---

### 6. What does local-first privacy actually protect?

**Q: Is it private if the video is stored on the machine?**

A: The *processing* is private: there is no cloud call, no account, no
telemetry, and the model only ever receives vehicle classes. But the uploaded
and annotated videos are stored on disk and can contain identifiable people and
plates. An anonymous track id does not anonymise the footage underneath it. That
is stated in the interface, in the footer and in the README, and it is why
delete removes the actual files.

**Q: Is it fully offline?**

A: Not on the very first run: Ultralytics downloads `yolo11n.pt` once. After the
weights are on disk, processing is entirely local. I would not describe the
application as fully offline without that first download.

**Q: Do you detect people?**

A: No — `person` is not in the class list the detector is asked for, and the
detector module re-checks the class name of every box. There is no face, plate
or identity code anywhere in the project. But again: that is about the derived
data, not about the footage.

**Q: Is the API safe to expose?**

A: It is a local tool and is documented as such: it binds to 127.0.0.1, has no
authentication, and must not be published to a network. The list of browser
origins allowed to call it is a setting, `FLOWLAB_CORS_ORIGINS`, and it defaults
to the four loopback development origins - which means the origin list is the
only access boundary the application has. A test asserts that the list is
read from configuration rather than written into the application module, and that
a blank value falls back to the loopback defaults rather than to "allow
everything". Anything that serves video without authentication should stay on
the machine it runs on.

---

### 7. What did the student personally contribute?

> **Answer from `docs/STUDENT_CONTRIBUTIONS.md`.** Be specific and do not claim
> more than is listed there. A judge will ask a follow-up on whatever you name,
> which is the point of naming it.

---

### 8. What would be needed before a school relied on this?

In rough order of importance:

1. **Hand-annotated validation on that school's own footage**, so the error is
   known for *their* camera, *their* weather and *their* traffic.
2. **Perspective calibration**, from a few surveyed points, so the outputs can be
   stated in metres and km/h rather than in image coordinates.
3. **A sampling-rate sensitivity study**, so we know what 10 frames a second
   costs in accuracy.
4. **A model that handles more than one gate**, including a second entrance, so
   the scenarios can test *where* to send cars, not only how fast they are
   processed.
5. **An operational rule for this tool**: a measurement is a starting point for
   a conversation, not a compliance number, and never a safety judgement about
   people near the gate. Nothing in this project evaluates pedestrian safety,
   and it should not be used to.
6. **Licence review** before any distribution: the YOLO weights are AGPL-3.0 and
   that has consequences beyond a school project.

---

### 9. How do you know it only works on your machine?

**Q: What stops a wrong number from being a one-off that happens to work here?**

A: Three independent things, and none of them is me pressing the button once.

1. **Automated tests, run by a machine, not by me.** 277 backend tests (pytest)
   and 50 frontend tests (vitest with Testing Library), all re-run on 2026-09-30
   with the output pasted verbatim in `docs/VERIFICATION.md`. None of them touch
   the network and none of them run the detector: the demo dataset is synthetic
   and already in the repository, so the suite is fast and deterministic.
2. **A CI matrix that I cannot skip.** `.github/workflows/ci.yml` runs on every
   push and every pull request, on two Python versions (3.11 and 3.13) and two
   Node versions (20 and 24). It runs the linter, the type checker, the tests
   with coverage, the encoding check, the frontend typecheck, the frontend tests
   and the production build. It sets `FLOWLAB_MODEL` to a path that cannot
   resolve, so the job cannot quietly download a model to prove that imports
   work.
3. **Checks for the things a test would normally miss.** Warnings are errors in
   the test run, so a leaked file handle fails the suite instead of accumulating.
   `mypy` runs over the analytics, simulation, storage and API layers with
   `check_untyped_defs`. `ruff` runs with bugbear and pyupgrade enabled. And
   there is a test that asserts `backend/requirements.txt` and `pyproject.toml`
   declare the same bounds, so the installed version and the declared version
   cannot quietly disagree.

I would rather tell you what CI has *not* done than what it has: it has never
actually run. The workflow file parses and every one of its steps was run by
hand on this machine, but the hosted runners, the Python 3.11 leg and the Node 20
leg have not executed. That is stated in `docs/VERIFICATION.md` section 7.

---

### 10. What bugs did you find in your own code?

**Q: Be honest. What was broken?**

A: Here is the list, and it is longer than I would like, which is why I am
giving it to you rather than waiting for you to find it. Every one of these now
has a regression test that fails on the old code.

**The two that had actually shipped:**

1. **Every failed analysis crashed before it could be recorded.** The
   job-failure path passed a keyword argument called `status` to a helper whose
   parameter is `status_value`, which collided with the helper's first positional
   argument and raised `TypeError` - on the line *before* the database update.
   So a video that failed to process stayed at "processing" in the database
   until the next restart, when the startup sweep noticed it. The user saw a job
   that would never finish instead of the error and the fix. I found this by
   turning on the type checker, not by testing: the previous suite had 200 tests
   and none of them exercised a failing analysis.
2. **No database connection was ever closed.** `Database._connect()` returned a
   plain `sqlite3.Connection` and every caller used `with self._connect()`, which
   in sqlite3 means "commit or roll back", not "close". Every read and write
   leaked a file handle. On a single-user local tool the practical damage is
   small, but it is a real bug and it is why I was able to turn warnings into
   errors: with that setting on, the suite went red with eight unclosed-database
   warnings pointing straight at the line.

**Correctness and consistency:**

3. `backend/vision/__init__.py` exported a name, `VehicleDetectionError`, that
   does not exist - the class is `DetectorError` - so `from backend.vision
   import *` raised `AttributeError`.
4. `PUT /analyses/{id}/regions` ignored the map-resolution parameter that
   `GET .../result` honoured, so re-measuring your regions silently redrew the
   map at a different resolution than reloading the page.
5. The single page app's catch-all route served any file under its name without
   checking that the path stayed inside the build directory.
6. `doctor.py` - the script whose entire job is to tell you whether your
   environment works - reported "ok" for the dependency versions whatever was
   installed. That is how an OpenCV 5.0.0 install survived a declared `<5` bound
   for months. The check now reads the bounds out of `requirements.txt` and
   compares them with what is actually installed.

**Frontend, six of them:** a helper that threw on a malformed stored record; a
replay cursor that disagreed with the backend about the instant before the first
sample; a guard whose two branches did the same thing; a tooltip that rendered
the literal text `still queued}s`; a caption claiming a code simplification the
code did not perform; and a menu that used the wrong ARIA roles. Plus two places
where the TypeScript mirror of the API contract had drifted from the Pydantic
model, once in each direction.

**Q: Why did it take this long to find them?**

A: Because until this pass nothing in the repository would have told me. There
was no linter configured, no type checker, no coverage number, no frontend test
runner at all, and "142 tests pass" was as much verification as existed. Adding
the tooling is what found the two shipped bugs; both of those had survived a
review pass, a green test suite and a session of using the application by hand.
The uncomfortable conclusion is that the tests I had were not the tests that
would have caught those, and that is a process problem rather than a coding one.

---

### 11. What can't you prove?

**Q: What are you not able to demonstrate?**

A: Four things, none of which I am going to paper over.

1. **That the detector finds the right vehicles in real footage.** This is the
   big one, and I have not done it. It needs a clip I am permitted to use and
   annotations I write myself. Every accuracy number in this repository is
   either synthetic ground truth generated by this project's own simulator, or a
   description of what happened on one deliberately unsuitable time-lapse clip.
   No detector accuracy figure is claimed anywhere.
2. **That the Docker image builds and runs.** Docker is not installed on the
   machine I developed this on. I have verified that the compose file parses,
   that it declares the two services and the one profile I describe, and that the
   ignore rules cannot delete a file the build needs (47 tests). I have never run
   `docker compose build`.
3. **That continuous integration is green.** The workflow exists, it is
   configured the way I describe, and I ran each of its steps by hand. The
   hosted runners, Python 3.11 and Node 20 have not executed it. The Python 3.11
   leg in particular matters, because the type checker deliberately assumes
   Python 3.12 syntax so it can read NumPy's type stubs, so a version slip would
   be caught there and not locally.
4. **How much the sampling rate costs.** I sample at 10 frames a second and I
   cannot tell you how much the metrics move between 5 and 15 fps, because
   nobody has measured it. It is the first thing in my list of things to do next,
   and it is a real open question rather than a formality.

**Q: And things you have not measured at all?**

A: Perspective calibration, obviously, so no number here is in metres or km/h.
Merges, signals and multiple approaches, so the twin is one corridor and one
gate. Long clips: I have only ever processed 20-second clips end to end, and a
ten-minute clip would exercise the series cap, the video writer and the database
payload at a scale I have not seen. Keyboard-only operation: the handlers exist
and the code type-checks, but nobody has tabbed through the application yet.
And GPU inference: `device=auto` resolves to CPU on my machine, so the CUDA
branch has never run.
