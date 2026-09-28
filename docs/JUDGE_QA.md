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
is the entire explanation for the residual error in the validation report.

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
vehicle at every instant is known. I rebuilt the queue series from those
positions with the same rule the analytics use and compared: arrival and exit
counts match exactly, and the queue series agrees to a mean absolute error of
0.211 vehicles over 1350 instants. Full numbers in `docs/VALIDATION_REPORT.md`.

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
authentication, and must not be published to a network. Anything that serves
video without authentication should stay on the machine it runs on.

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
