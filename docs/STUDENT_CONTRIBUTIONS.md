# Student contributions

**This file is a template, not a record.** The sections marked *to be completed*
are for you alone to fill in. Nothing in this file should be written by an AI
assistant, and nothing in it should claim work you did not do.

The purpose is twofold: the competition requires significant student
contribution, and — more usefully — a submission you can defend in a live
judging round comes from work you can explain without notes.

---

## 1. What is already true, and what is not

| Area | Status |
| --- | --- |
| Backend pipeline, analytics, simulator | Written with AI assistance, reviewed, tested (129 automated tests) |
| Frontend interface | Written with AI assistance, reviewed in a browser |
| Test suite and validation tooling | Written with AI assistance, executed and extended |
| Real-footage validation with your own annotations | **Not done. This is yours.** |
| Design decisions, scope choices, story | **Yours. Not recorded anywhere yet.** |

If you cannot explain a piece of the code in the judging round, that piece is
not yet a contribution. The exercises in section 4 are chosen to cover the parts
of the system that are most worth understanding.

---

## 2. Your motivation — to be completed in your own words

*What made you build this? What did you notice? Who did you talk to? What
frustrated you?*

<!-- Write 3-6 sentences. Do not invent interviews, quotes or numbers. If you
     have not spoken to anyone at a school, say that. -->

> **To be completed by the student.**

**A prompt to start from, if useful:** school dismissal happens every day and
everyone complains about it, but nobody has ever measured it. What would you
have liked to know before deciding what to do about it?

---

## 3. Decisions you made — to be completed

Record at least three decisions where you chose between real alternatives, and
say why. Good candidates:

| Decision | Options you weighed | What you chose and why |
| --- | --- | --- |
| *e.g. how the queue should be defined* | *slow vs stopped vs both* | **to be completed** |
| *e.g. which regions to ship with the demo* | | **to be completed** |
| *e.g. what the simulator should be allowed to change* | | **to be completed** |
| *e.g. what to leave out* | | **to be completed** |

The queue definition is a genuinely interesting decision and the one most worth
owning. The system currently says:

```text
queued = inside the queue region AND below the speed threshold
         continuously for at least min_queue_seconds (default 0.5 s)
```

Before this rule existed, a single noisy detection could create a phantom queue.
Adding a duration threshold made the queue definition agree with the separate
"stopped" definition. If you disagree with that choice — or think 0.5 s is the
wrong number — say so, change it, and write down what moved.

---

## 4. Exercises: implement these yourself

Each one is small enough to finish in an evening and is real work, not busywork.
Acceptance criteria are specific so you know when it is done.

### Exercise 1 — Complete the real-footage validation (highest priority)

**Why it is yours:** the AI cannot annotate footage you have permission to use.

1. Find or record a 10–60 second fixed-camera clip of a gate, car park or road
   where **you** have permission to use the footage. Write down where it came
   from and who permits its use.
2. Make a short segment:
   `python -m backend.scripts.make_test_clip long.mp4 sample.mp4 --start 30 --seconds 12 --slowdown 2 --fps 10`
3. Watch it and annotate, in `backend/validation/template.json`:
   - 10–20 queue counts at instants you choose (pause and count);
   - every arrival and departure time you can see;
   - 3–5 complete queue visits with entry and exit times.
4. Run:
   `python -m backend.scripts.validate_against_reference backend/validation/mine.json --clip sample.mp4 --markdown docs/validation-detector.md`
5. Write down honestly: which numbers were close, which were not, and what you
   think caused the differences (small vehicles, shadow, occlusion, a lost id,
   a badly placed line).

**Acceptance criteria**

- [ ] A reference JSON exists with at least 10 annotated queue counts.
- [ ] A validation report exists with the clip, its source and its permission.
- [ ] You can explain every number in the report, including why it differs from
      the reference where it does.
- [ ] The report states the failure modes you saw.

### Exercise 2 — Study sampling frequency

**Why:** the app samples video at 10 fps and nobody has measured what that costs
in accuracy. This is a real open question in the project.

1. Take your clip and run the analysis three times with
   `FLOWLAB_SAMPLE_FPS=5`, `10`, `15`.
2. Record, for each run: vehicles tracked, peak queue, average wait, throughput,
   and the processing time.
3. Write one paragraph: which metric moves most, and what that implies about
   whether 5 fps is enough for a school gate.

**Acceptance criteria**

- [ ] A table with three rows and the five numbers.
- [ ] A written conclusion, including a case where a metric moves in the
      *opposite* direction to what you expected.
- [ ] Your conclusion is quoted in the README or the submission.

### Exercise 3 — Change a definition and defend it

Pick one and change it, with the test updated:

- the default `min_queue_seconds` (0.5 s),
- the minimum region area (`MIN_POLYGON_AREA`),
- the bottleneck reporting threshold (`min_passes`),
- the grid size (8×6).

**Acceptance criteria**

- [ ] The change is made, and the existing tests still pass — or you can explain
      which test correctly failed.
- [ ] One new test covers the behaviour you added.
- [ ] You can say what the change does to the demo numbers and why.

### Exercise 4 — Explain the code you did not write

Pick one module and be ready to defend it in the judging round. A good starting
point for a "why is it like this?" question is `backend/analytics/queue_detection.py`.

Be ready to answer, without notes:

- Why is the queue sampled on a fixed time grid instead of per frame?
- Why is the contact point the bottom-centre of the box?
- What is the "cursor" in `build_queue_series` and what bug does it prevent?
- What happens to a vehicle that is already in the queue when the clip starts?

**Acceptance criteria**

- [ ] You can describe the module's job in three sentences.
- [ ] You can name one bug the current design prevents, with a concrete example.

### Exercise 5 — Something you think is wrong

Find something the application gets wrong or handles badly — a misleading label,
an edge case, a metric that does not mean quite what it says. Write it down, and
either fix it or file it as a known limitation.

**Acceptance criteria**

- [ ] The observation is written up in your own words.
- [ ] Either the fix is implemented with a test, or the limitation is documented
      where a user will see it.

---

## 5. Reflection — to be completed

- What did you find hardest, and what did you do about it?
- What would you want to know before trusting these numbers at your own school?
- If you had one more week, what would you build next, and why that?
- What would you show someone who does not care about computer vision?

> **To be completed by the student.**

---

## 6. Evidence checklist

Judges and your own teacher may ask to see that the work is yours. Collect these
before submission:

- [ ] Git history showing your commits, if you are using Git.
- [ ] The annotated reference JSON and the validation report from exercise 1.
- [ ] The measurement table from exercise 2.
- [ ] Screenshots of the app running with **your** clip, not the demo dataset.
- [ ] A short note (half a page) naming the AI tool used and which parts of the
      work were yours, in your own words.

Do not claim a real-world effect you have not measured. "This is what the
numbers looked like on one clip I recorded" is a strong, honest statement.
"Flowlab reduces congestion" is not, and FLOWLAB does not claim it anywhere.
