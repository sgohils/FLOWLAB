# FLOWLAB demonstration outline: target 2 minutes 45 seconds

**Created by Shlok Gohil · GA-07**

For the personalized 2:50 narration, exact recording steps and YouTube upload
instructions, use [RECORDING_PLAN.md](submission/RECORDING_PLAN.md). The
[application answers](submission/APPLICATION_ANSWERS.md) include the motivation
and process details supplied by Shlok.

Revised October 25, 2026. Read [CAC_SUBMISSION.md](CAC_SUBMISSION.md) before
recording, especially the conflicting official deadline times and student/AI
requirements. Replace bracketed text and speak in your own words. Do not read
unverified first-person claims.

## Before recording

- **Participants:** Shlok Gohil `[TODO: introduce any actual teammates too]`
- **School/eligibility:** `[TODO: confirm privately; do not infer from GA-07]`
- **App version:** `[TODO: commit/release shown in the recording]`
- **Student technical contribution:** `[TODO: specific code, decision, and test
  the student actually implemented]`
- Rehearse on the deployed site. A completed bundled analysis avoids waiting
  for an upload in the recording. Keep a local backup; identify the environment
  accurately if using it.
- Open `/analysis/real-demo` for the real video and `/simulation/demo` for the
  synthetic queue experiment after this release is deployed. Both examples work
  without cloud database, Blob, or Queues setup; upload must be tested separately.
- Public-road footage is not footage of your school or proof of accuracy.
- Use only numbers visible in this release. Run current checks; old documents'
  test totals are historical. Time the finished video rather than assuming the
  time blocks below will match a spoken take.

## 0:00–0:20 — Name, purpose, audience, actual motivation

**Show:** home page.

> “I'm Shlok Gohil, and this is FLOWLAB. It turns traffic video into explainable
> vehicle measurements and lets schools compare simplified traffic scenarios.
> It's intended for school administrators looking at pickup traffic and
> students learning how measurement and models work. [One sentence about your
> actual motivation.]”

## 0:20–0:50 — Real footage and working tracking

**Action:** choose **Watch real traffic analysis** (`/analysis/real-demo`). Play
the clip and trajectory replay; point out the source/credit. Pause once.

> “This is Kjetil_r's public-domain road footage from Lysaker, Norway, processed
> beforehand. It's a 25-second excerpt with original timing. Pretrained YOLO
> finds vehicles; ByteTrack links tracks. Video and positions share one clock.
> Track IDs don't identify a person or plate.”

> “This shared demo has no sign-in: anyone with access can open analyses and
> videos. Upload only footage permitted for public sharing; run locally for
> private school footage.”

Do not imply that this road is the student's school, that Shlok recorded it, or
that replay is live inference. If real footage is unavailable in the version
being recorded, use **Try Sample Analysis**, explicitly call it synthetic, and
describe trajectory replay without claiming there is source video.

Full source and transformation notes are in
[CREDITS.txt](../frontend/public/demos/CREDITS.txt). Stabilization, crop, resize,
and audio removal are disclosed; no vehicles or frames were generated.

## 0:50–1:20 — One number and the evidence behind it

**Action:** open throughput's **why?** panel and the evidence/assumptions panel.
Point to the near-carriageway measurement lines and the source-credit panel.

> “Ten tracks cross this exit line in 25 seconds: 24 crossings per minute over
> this short window. The 75 retained track IDs cover both traffic directions;
> they aren't a hand-verified unique vehicle count. These measurement lines
> cover the near carriageway.”

> “This is evidence to investigate, not a verified real-world speed measurement
> or a claim that every vehicle was detected.”

The actual real example has **peak queue 0** and **wait unavailable** because no
completed queue waits were measured. Its 91 initial fragments and 75 retained
IDs are automated output, not an accuracy score. If a later release changes
these values, use its actual displayed numbers and update this outline.

## 1:20–1:55 — Change one variable and compare fairly

**Action:** switch explicitly to `/simulation/demo`, the **synthetic queue
sandbox**. Choose one preset and run it. Show the observed/baseline/scenario
table and paired corridor replay. Use the synthetic sandbox's actual numbers.

> “The real clip is free-flow traffic, so I'm switching to the labelled synthetic
> queue example. What if [the preset's question]? Compare the unmodified model
> with the dataset, then the change with that model baseline. [Read the actual
> baseline and scenario values.] That separates model mismatch from the change.”

> “This is a simplified corridor model. The sensitivity range shows how results
> depend on estimated service time. It's an experiment, not a promise of the
> same improvement on a real road.”

If the model fits poorly or a metric is unavailable, show the caveat. Do not
claim a benefit if the screen shows no change, or compare throughput across
different time windows without the app's qualification.

## 1:55–2:20 — A useful output and an honest limitation

**Action:** open the print brief, or show the export controls and evidence.

> “The brief takes the definitions and comparison into a conversation.
> Measurement exports omit source video and the original filename. Before
> using this for a school decision, I'd need permission for representative
> footage and independent hand counts. This real clip demonstrates
> functionality; it isn't an accuracy study or proof of reduced congestion.”

If independent annotation has actually been completed, replace the last sentence
with its measured comparison, scope, and limitations. Do not quote synthetic
validation as real detector accuracy.

## 2:20–2:45 — Student contribution, tools, disclosure

**Show:** the relevant module/test briefly, then return to the app.

> “[Describe a technical problem you personally worked on, your change, and how
> you checked it.] The stack uses Python, FastAPI, OpenCV, pretrained Ultralytics
> YOLO and ByteTrack, TypeScript, React and Vite, and automated tests. Hosted
> storage uses PostgreSQL and Vercel Blob, with queued processing. AI
> coding assistance and third-party sources are disclosed in the submission.
> [State your actual contribution and next step in your own words.]”

Only name hosted services if that is the build shown; a local fallback uses
SQLite and local processing. Do not say “I built” about an assistant's work.
Review [AI_ASSISTANCE.md](AI_ASSISTANCE.md) and
[STUDENT_CONTRIBUTIONS.md](STUDENT_CONTRIBUTIONS.md).

## Final recording checks

- [ ] All participant names, app name, one clear purpose sentence, target users,
      languages/tools, and a working demonstration appear.
- [ ] The final video is 1–3 minutes; speech is clear and text is legible.
- [ ] Source credit remains visible; real and synthetic examples are distinct.
- [ ] The 75 real-road IDs are not described as verified unique vehicles; the
      synthetic queue is never presented as a queue from the free-flow video.
- [ ] Cuts/precomputation are identified; no unsupported accuracy, school
      adoption, safety, or congestion-reduction claims are spoken.
- [ ] No secrets/profile details are shown. Review footage permission and
      identifiable details before public publication. Hosted demo uploads must
      be permitted for public sharing; private school footage belongs locally.
- [ ] Student work and AI/tool assistance are accurately represented.
- [ ] After publishing, check the public YouTube/Vimeo link while signed out.

Video publication and application submission remain the student's actions.
