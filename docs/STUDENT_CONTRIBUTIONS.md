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
| Backend pipeline, analytics, simulator | Written with AI assistance, reviewed, tested (277 automated tests) |
| Frontend interface | Written with AI assistance, reviewed in a browser (50 automated tests) |
| Linting, type checking, coverage, CI | Configured and running in CI (`.github/workflows/ci.yml`); the configuration is a decision you should be able to defend |
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

Two more decisions the code already makes for you, both of which are defensible
and neither of which you will be asked about unless you raise them:

- **`backend/geometry.py` exists as its own module** (D16). It is the only way
  the schema layer can share the shoelace formula with the analytics layer
  without a circular import. Explain why the duplication it replaced was worse.
- **`noUncheckedIndexedAccess` is deliberately switched off in the frontend**
  (D22). Enabling it was measured at 41 diagnostics, nearly all indexing the
  code already proves safe. Argue for or against that call.

---

## 4. Exercises: implement these yourself

Each one is small enough to finish in an evening and is real work, not busywork.
Acceptance criteria are specific so you know when it is done.

### Exercise 1 — Complete the real-footage validation (highest priority)

**Why it is yours:** the AI cannot annotate footage you have permission to use.
The tooling is finished and tested (`backend/validation/`, and the gap this pass
found is closed — the replay no longer hides tracking gaps, so your manual queue
counts and the application's can be compared fairly).

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
   think caused the differences (small vehicles, shadow, occlusion, a lost id, a
   badly placed line).

**Acceptance criteria**

- [ ] A reference JSON with at least 10 annotated queue counts.
- [ ] A validation report with the clip, its source and its permission.
- [ ] You can explain every number in the report, including why it differs from
      the reference where it does.
- [ ] The report states the failure modes you saw, including the
      `evidence.tracking gaps` and `missing sample share` counts the new panel
      reports for the same clip.

### Exercise 1b — Exercise the "thin evidence" rule **[new this session]**

The new evidence panel refuses to look authoritative below five tracks or above
15 % missing samples. Find a clip (or a region) that trips it and check the claim
is fair.

**Acceptance criteria**

- [ ] A screenshot or note showing the *Thin evidence* warning.
- [ ] Your judgement: is one threshold right for both conditions, or should
      they be separate? Change it if you disagree, with a test.

### Exercise 2 — Study sampling frequency

**Why:** the app samples video at 10 fps and nobody has measured what that costs
in accuracy. This is a real open question in the project.

1. Take your clip and run the analysis three times with
   `FLOWLAB_SAMPLE_FPS=5`, `10`, `15`.
2. Record, for each run: vehicles tracked, peak queue, average wait, throughput,
   the `evidence.missing sample share`, and the processing time.
3. Write one paragraph: which metric moves most, and what that implies about
   whether 5 fps is enough for a school gate.
4. Cross-check with the sensitivity range on the simulation page: if service
   time is estimated at 4.3 s and the plausible range is 3.2–6.4 s, which
   measurement error matters more?

**Acceptance criteria**

- [ ] A table with three rows and the numbers above.
- [ ] A written conclusion, including a case where a metric moves in the
      *opposite* direction to what you expected.
- [ ] Your conclusion is quoted in the README or the submission.

### Exercise 3 — Challenge a design decision

`docs/ENGINEERING_DECISIONS.md` records **25** decisions with their
alternatives, the failure case each one is exposed to, and how it was tested.
Pick one you think is **wrong**, and either change it or argue it in writing.

Good candidates: D11 (bucket-max decimation biases the displayed average
upward), D4 (0.5 s queue threshold), D3 (censoring first-frame visits), D13
(0.75x/1.5x sensitivity factors), D20 (one SQLite connection per operation
rather than a pool), D22 (`noUncheckedIndexedAccess` left off).

**Acceptance criteria**

- [ ] The decision entry gains a paragraph in your own voice, with your reasoning
      and what evidence would change it.
- [ ] If you change behaviour: the existing tests pass, or you can explain which
      test correctly failed, and you add one that covers the new behaviour.

### Exercise 4 — Explain the code you did not write

Pick one module and be ready to defend it in the judging round. A good starting
point for a "why is it like this?" question is `backend/analytics/queue_detection.py`.

Be ready to answer, without notes:

- Why is the queue sampled on a fixed time grid instead of per frame?
- Why is the contact point the bottom-centre of the box?
- What is the "cursor" in `build_queue_series` and what bug does it prevent?
- What happens to a vehicle that is already in the queue when the clip starts?
- Why does the chart decimate by bucket maximum rather than taking every n-th
  sample? (Hint: `docs/ENGINEERING_DECISIONS.md` D11, and a test that names the
  failure case.)

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

### Exercise 6 — Close an automated gap **[added 2026-09-30]**

The most recent pass added a linter, a type checker, coverage and a frontend test
runner, and immediately found two bugs that had shipped: a keyword-argument
mismatch that made every failed analysis raise `TypeError` before it could be
recorded, and a database layer that never closed a connection. 200 backend tests
had passed with both in place.

There is still no automated guard against the **TypeScript mirror of the API
contract** drifting from `backend/models/schemas.py`. It drifted once already, in
both directions at once, and a judge would not have found it either.

1. Write a test that reads the Pydantic model and the TypeScript mirror and
   compares the field names that both are supposed to carry.
2. Decide what to do when a field exists in only one of them: fail, or warn and
   list it. Argue for your choice.

**Acceptance criteria**

- [ ] A test that fails when a field is added to one side only.
- [ ] You can say in one sentence why `npm run typecheck` does not catch this
      already (it proves the frontend is internally consistent, not that it
      matches the backend).

### Exercise 7 — Prove something in a browser **[added 2026-09-30]**

The last pass changed the Home page (a saved-analyses panel, a degraded-mode
banner), the export menu, and the accessibility layer, and **none of it has been
driven in a browser**. The code type-checks; nobody has seen it render.

1. Run the application and walk the whole workflow: upload or demo, draw
   regions, replay, simulate, export, delete.
2. Complete the same walk using only the keyboard. The region drawing tools
   claim Enter closes a polygon and Escape abandons it; check that they do.
3. Check the degraded-mode banner by stopping the backend and by pointing
   `FLOWLAB_MODEL` at a path that does not exist.
4. Write down every place where the interface contradicts what the documentation
   says, with the file and line where the documentation is wrong.

**Acceptance criteria**

- [ ] A list of every contradiction found, each with the file to fix.
- [ ] At least one of them fixed, with a test if it is testable.
- [ ] Screenshot or note showing the keyboard-only region drawing working.

### Exercise 8 — Explain the twin, as a piece of engineering

The digital twin is not a picture: it is a one-lane corridor with a processing
gate, driven by a reduced Intelligent Driver Model. The frontend has a small
component library around it (`frontend/src/components/Primitives.tsx` for the
shared primitives, `CorridorMap.tsx` for the corridor picture, `CorridorComparison.tsx`
for the two side by side, `SimulationPanel.tsx` for the controls).

1. Read `backend/simulation/simulator.py` and `backend/simulation/scenarios.py`.
2. Explain without notes: what a "scenario" is, which parameters it may change,
   which it must not, and why the baseline replays the *original* arrival series
   rather than the modified one.
3. Explain what the three-way comparison (observed / baseline / modified) would
   look like with only two lines, and what error that would let a reader make.
4. Explain the sensitivity range and why it is explicitly not a confidence
   interval.

**Acceptance criteria**

- [ ] You can draw the corridor model on paper and explain where a queue comes
      from in it.
- [ ] You can state, from memory, the model-mismatch factor on the demo dataset
      and why it is reported separately from the scenario effect.

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
- [ ] A green CI run for the commit you are submitting (the workflow exists; it
      has never executed on GitHub yet, so pushing it is part of the evidence).
- [ ] A short note (half a page) naming the AI tool used and which parts of the
      work were yours, in your own words.

Do not claim a real-world effect you have not measured. "This is what the
numbers looked like on one clip I recorded" is a strong, honest statement.
"Flowlab reduces congestion" is not, and FLOWLAB does not claim it anywhere.
