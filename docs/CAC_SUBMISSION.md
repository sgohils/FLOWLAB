# FLOWLAB Congressional App Challenge preparation

**Created by Shlok Gohil · GA-07**

Checked **October 25, 2026**, America/New_York. This is preparation material,
not a completed application or a promise of eligibility or an award. Replace
every `TODO`, verify the running app, and submit personally.

The [local release check](CAC_READINESS_CHECK.md) records the current tests,
browser walkthrough and remaining production checks.

## Deadline: conflicting official times

The [2026 rulebook, section 5](https://www.congressionalappchallenge.us/wp-content/uploads/2026/05/2026-CAC-Rules.pdf)
says **Monday, October 26, 2026 at noon EDT**. The current
[national registration page](https://www.congressionalappchallenge.us/students/student-registration/)
says **9:00 pm ET that day**. Treat **noon EDT as the safe cutoff** unless your
district and application portal explicitly confirm otherwise. Verify them now;
do not rely on an assumed extension.

The [national 2026 participating-district list](https://www.congressionalappchallenge.us/students/participating-districts/)
marks **GA07 (Richard McCormick)** as participating. The
[district office services page](https://mccormick.house.gov/services)
also identifies the GA-07 competition. A district-specific 2026 cutoff was not
independently verified; participation alone does not resolve the time conflict.

## Student and eligibility checks

The [rulebook, sections 1 and 3](https://www.congressionalappchallenge.us/wp-content/uploads/2026/05/2026-CAC-Rules.pdf)
requires eligible students, a participating district, at most four teammates,
one entry per person, and qualifying project dates. AI must be disclosed;
substantial personal technical work and understanding are required. Libraries
and external tools must be attributed.

- [ ] `TODO: school, grade/enrollment, residence/school district connection, and
      any teammates; verify eligibility and project dates against the rules`.
- [ ] `TODO: complete registration and eligibility questions in the portal`.
- [ ] `TODO: record actual student contributions and explain the relevant code`.
- [ ] `TODO: guardian/contact/profile details entered privately in the portal`.

**Material gap:** [AI_ASSISTANCE.md](AI_ASSISTANCE.md) records extensive
AI-written development; [STUDENT_CONTRIBUTIONS.md](STUDENT_CONTRIBUTIONS.md)
contains unfinished student tasks. More AI-generated features do not establish
student authorship. Update the disclosure to include this Codex session and
real-demo work, and write a truthful contribution record. Do not claim the
student independently implemented generated code. Explaining generated code
does not by itself establish an individual technical contribution.

## Demonstration video

Prepare a **1–3 minute** video, public on YouTube or Vimeo. Include participant
names, app name, one-sentence purpose, intended users, languages/tools, and a
working demonstration. See the
[2026 rulebook, section 4](https://www.congressionalappchallenge.us/wp-content/uploads/2026/05/2026-CAC-Rules.pdf)
and [official district submission guidance](https://larsen.house.gov/helping-you/2026-congressional-app-challenge.htm).
Use [DEMO_SCRIPT.md](DEMO_SCRIPT.md) to rehearse, then speak in your own words.
You do not need to purchase music, editing software, or footage.

- [ ] Record the version judges will receive, with real and synthetic examples
      identified separately. Show the real clip's source credit.
- [ ] If processing time is cut, say the clip was processed beforehand.
- [ ] Include AI and third-party disclosure in submission materials; check for
      any separate disclosure form required by the district.
- [ ] Play the published video while signed out: check sound, legibility,
      public visibility, URL, and runtime.
- [ ] Enter actual app/source access requested by the portal. Keep credentials
      and personal profile details out of public links.

## Show evidence that makes the app compelling

The [national judging criteria, section 7](https://www.congressionalappchallenge.us/wp-content/uploads/2026/05/2026-CAC-Rules.pdf)
cover idea quality, implementation/design, and coding skill; district judging
can vary. This table is our presentation advice, not an official scoring rubric.

| What a judge should see | Working evidence to show |
| --- | --- |
| A clear problem and audience | One traffic question a school administrator might investigate; the student's actual motivation |
| A functioning app | Real public traffic footage with tracked replay, a scenario comparison, and a printable brief |
| Explainable implementation | A metric's **why?** panel; regions, crossing lines, tracking gaps, and unfinished waits |
| Careful reasoning | Observed versus unmodified model versus scenario; acknowledge model mismatch |
| Student skill | A student-made change, its code/test, alternatives considered, and limitations |
| Responsible use | Media credits, accurate cloud/privacy wording, and explicit AI disclosure |

### The two bundled examples

| Example | Route after deploying this release | What it demonstrates |
| --- | --- | --- |
| Real traffic: Lysaker, Norway | `/analysis/real-demo` | Source/annotated footage and actual detector/tracker output on free-flow road traffic |
| Synthetic queue sandbox | `/analysis/demo`, then `/simulation/demo` | A queue-producing example for comparing a gate intervention with the unmodified model |

The real example is a **25-second excerpt (source seconds 5–30)** of
[E18-Lysaker (02).ogv by Kjetil_r](https://commons.wikimedia.org/wiki/File:E18-Lysaker_(02).ogv),
released by its author into the public domain. It is a PD-self author release,
not a CC0 declaration. See the bundled
[CREDITS.txt](../frontend/public/demos/CREDITS.txt) for source details, changes,
and hashes. The excerpt was stabilized using background features, cropped by a
fixed 64-pixel edge, resized to 960×494, muted, and encoded as MP4. The annotated
copy adds boxes and trails. Original timing is retained; no vehicles or frames
were generated or interpolated.

The real example is precomputed with the ordinary upload analysis pipeline and
bundled with source, annotated video, and poster. It can be opened without
PostgreSQL, Blob credentials, or Queues. This does not verify a separate cloud
upload path.

| Current real-example output | Correct interpretation |
| --- | --- |
| 250 frames sampled at 10 fps across 25 seconds | A finite short observation, not continuous monitoring |
| 91 initial detection/tracking fragments; 75 retained IDs | Automated track IDs across both directions; **not 75 manually verified unique vehicles** |
| 12 entry crossings and 10 exit crossings | Selected lines on the near carriageway, not counts across the whole scene |
| Throughput 24/min | `10 crossings ÷ (25/60 minutes)` over this short window, not a long-term road-capacity estimate |
| Peak queue 0; estimated wait unavailable | Free-flow traffic; no completed queue waits measured by these regions/rules |

Do not claim that the real road has a queue to reduce. Switch explicitly to
the **synthetic queue sandbox** for the gate-intervention demonstration. The
synthetic example is useful because its generating positions are known; keep
its label visible. Neither example establishes performance at Shlok's school.

A detector's output is not independent ground truth. Before claiming accuracy,
independently count/annotate a permitted clip and compare it using
[the validation tooling](../backend/validation/README.md). Automated test counts
are not detection-accuracy percentages. Do not claim measured reductions in
congestion, emissions, crashes, or school pickup time from simulated outcomes.

## Submission answer worksheet

These are prompts, not answers about the student's life. The
[rulebook's example questions, section 4](https://www.congressionalappchallenge.us/wp-content/uploads/2026/05/2026-CAC-Rules.pdf)
ask about purpose, inspiration, technical difficulty, learning, and future
changes. Follow the live form's wording and character limits.

| Field | Draft or student task |
| --- | --- |
| Title / creator | FLOWLAB / Shlok Gohil |
| One-sentence purpose | Draft: FLOWLAB turns traffic video into explainable vehicle measurements and lets schools compare simplified traffic scenarios. |
| Intended users | Draft: school administrators investigating pickup traffic, and students learning about measurement and models. This is an intended audience, not a claim of existing customers. |
| Inspiration | `TODO: a real experience or observation in your own words. Do not invent interviews or partnerships.` |
| Technical difficulty | `TODO: a problem you personally worked on; original failure, your change, why you chose it, and evidence it works.` Topics to study: tracking gaps, incomplete waits, baseline fidelity, upload authorization. |
| What you learned | `TODO: a specific changed understanding, including something the app still gets wrong.` |
| Future version | `TODO: a realistic next step, such as independent annotations or representative school-gate footage. Describe future work as future work.` |
| Individual contributions | `TODO: actual student design, coding, testing, and analysis with commit/file references. Identify assistance separately.` |
| AI assistance | `TODO: tool names and scope, including generated code, tests, documentation, deployment fixes, and this real-demo work. Link the updated disclosure if the form accepts links.` |
| External components/media | Include pretrained Ultralytics YOLO/ByteTrack and frameworks; real clip: **E18-Lysaker (02).ogv, Kjetil_r, public domain author release**, with the source link and bundled modifications/credits above. `TODO: verify the full dependency and attribution list for the submitted release.` |
| App/source links | Intended production: `https://flowlab1.vercel.app/analysis/real-demo` and `/simulation/demo` after redeployment. `TODO: test those production links, source URL, commit/release, and any access instructions.` |

Do not copy historical test totals, timings, or validation numbers without
checking the submitted release. Hosted uploads leave the laptop. Although Blob
objects are private at the storage layer, **this shared demo has no sign-in or
per-user access controls**: anyone with access to the deployment can list/open
saved analyses and videos through its API. Upload only footage permitted for
public sharing; run locally for private school footage. Source footage can
contain identifiable details even though FLOWLAB does not recognize identities.

## Final rehearsal and handoff

1. Open the deployed site in a fresh signed-out browser. Verify both examples,
   replay, **why?**, scenario execution, and print brief. Reload direct
   analysis/simulation links to catch routing failures.
2. If showing upload, test a permitted short clip through completion, results,
   and deletion. Bundled-demo success does not prove cloud upload readiness.
   Use only footage permitted for public sharing on the shared deployment.
   If uploads fail, identify that limitation and show the bundled example.
3. Check every spoken number against the screen. Keep a local recording and
   screenshots of the actual submitted version as a fallback.
4. Complete [STUDENT_CONTRIBUTIONS.md](STUDENT_CONTRIBUTIONS.md), review
   [JUDGE_QA.md](JUDGE_QA.md), and correct outdated disclosure claims.
5. Finish required portal fields, submit before the applicable deadline, save
   the confirmation, and follow the exit-questionnaire instructions.

This preparation work has not registered, submitted, published a video, or
contacted anyone on the student's behalf.
