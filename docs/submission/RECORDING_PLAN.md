# Record FLOWLAB: a 2:50 walkthrough

Use your own voice. This is a screen recording of working software, with the
personal motivation supplied by Shlok Gohil. Adjust any sentence that does not
reflect your experience. A webcam, paid editor and background music are not
needed. Keep the final recording between 1 and 3 minutes.

## 1. Prepare the working version

The tested local preview is currently at http://127.0.0.1:3180/ . The production
site needs the latest release: its real-demo status endpoint returned 404 on
October 25. Record the local build and identify it accurately, or redeploy and
verify the same paths before using the production site.

Open four browser tabs:

1. http://127.0.0.1:3180/
2. http://127.0.0.1:3180/analysis/real-demo
3. http://127.0.0.1:3180/simulation/demo
4. http://127.0.0.1:3180/brief/real-demo

If the local preview has stopped, run the existing local app launcher from the
repository and use its displayed address instead. The usual Vite development
address is `http://localhost:5173/`; the same route suffixes apply. Keep the
backend running. Do not launch another service on an occupied port.

On the real analysis tab, find Play, the annotated video, the trajectory map
and throughput's explanation. On the simulation tab, choose **Volume -25%**,
click **Run simulated scenario**, and verify baseline peak 14 and scenario peak
8. Reset for the recording. The real road example has no measured queue; use
the explicitly synthetic example for the queue experiment.

Maximize Chrome. Use a 1920 by 1080 screen if available and browser zoom around
100–125% so labels remain legible. Open only these tabs, enable Do Not Disturb,
and hide credentials, email, personal files and unrelated browser content.

## 2. Set up free screen recording

Download OBS Studio from https://obsproject.com/ . Run its Auto-Configuration
Wizard for recording. Add a **Window Capture** source for Chrome and fit it to
the canvas. Use **Display Capture** only if Window Capture shows a black frame;
review everything visible on that display.

Under Settings > Video, use 1920 by 1080 output at 30 fps if supported by your
screen and hardware. Use high-quality recording. Enable your actual microphone,
mute desktop audio, and check that speech stays clear without reaching the red
end of the meter. The sample traffic video is muted.

Record a 15-second test: speak your introduction, play the road video and move
the page once. Watch the saved file to check sound, legibility and smooth video
before doing a full take. If recording to MKV, use OBS's **File > Remux
Recordings** to create an MP4 afterward.

Official setup guidance: https://obsproject.com/kb/quick-start-guide

## 3. Rehearse these exact actions and narration

Aim for about 125 words per minute with short pauses. The script is
321 words; timing depends on your speaking pace. Use a phone stopwatch for
rehearsal. The timestamps are targets, not a guarantee. Do two full takes and
choose the clearest one.

### 0:00–0:22: home, name and motivation

Show the home page. Keep the cursor still while introducing the problem.

> I'm Shlok Gohil from Georgia's Seventh Congressional District. I was inspired
> to create FLOWLAB after witnessing an accident one morning before school.
> FLOWLAB turns traffic video into explainable vehicle measurements and helps
> school teams and community planners explore simplified traffic changes.

### 0:22–0:36: tools

Point to the pipeline. If using the local build, identify it here.

> This is the local web app, built with Python, FastAPI, React and TypeScript.
> Pretrained YOLO detects vehicles, ByteTrack links their paths, and the app
> calculates measurements from those paths.

Replace "local" only if you are actually showing the deployed release.

### 0:36–1:00: real video and synchronized replay

Switch to the real analysis. Scroll to the video, click Play, show several
seconds of tracked cars, then show the moving trajectory map and pause.

> This is Kjetil_r's public-domain footage from Lysaker, Norway. I'm opening a
> precomputed analysis of 25 seconds of real traffic. Watch the video and map
> move together. The IDs are temporary tracker labels. The clip is not footage
> from my school.

### 1:00–1:20: evidence behind one measurement

Scroll to Throughput and open its **why?** explanation. Point to the exit-line
crossing count. Do not spend time reading every metric.

> Ten tracks cross this exit line in 25 seconds: 24 crossings per minute over
> this short window. I can inspect how that number was calculated. Tracking can
> miss or split vehicles, and image motion is not calibrated physical speed.

### 1:20–1:55: one controlled experiment

Switch to `/simulation/demo`. Keep the synthetic label visible. Choose
**Volume -25%**, click **Run simulated scenario**, and scroll to the comparison
and experiment takeaway. Pause on the 14 to 8 result. If the screen differs,
use the current result rather than reciting old numbers.

> This road clip does not show a queue, so I'm switching to the labeled
> synthetic queue sandbox. What if a quarter fewer vehicles arrived? I'll run
> that scenario against the unchanged model. The baseline peak queue is 14;
> the scenario peak is 8. That is a model outcome, not an observed improvement
> on a real road.

### 1:55–2:13: show why the comparison matters

Point to A, B and C and the sensitivity explanation. If useful, briefly play
the paired corridor replay. Do not introduce a second intervention.

> The app separates the source measurements from the baseline model. The
> model can be wrong before I change anything. Sensitivity checks show how
> results depend on assumptions such as exit service time. They are not
> confidence intervals.

### 2:13–2:28: a useful output

Click **Download experiment note**. Then switch to the brief tab and show its
definitions and source credits. Avoid opening a print dialog during the take.

> I can download an experiment note and open a printable brief with
> definitions, source credits and limitations. That gives users evidence and
> questions to take into a field study.

### 2:28–2:50: personal work and disclosure

Switch to About or home. End on the app's name.

> My contributions included the problem idea, feature direction, finding and
> testing data, and reporting deployment failures. Kilo and OpenAI Codex
> provided substantial coding assistance, disclosed in my submission. Next I
> would add independent validation and stronger access controls. My goal is to
> make traffic decisions easier to examine with evidence.

Do not claim independently authored modules, training or accuracy experiments
that you did not perform. Current test counts are software checks, not a
detector-accuracy percentage. Source footage can identify people or plates,
and the shared deployment has no per-user access controls.

## 4. Save and upload

Trim only dead time at the beginning and end if needed. Keep the actual
workflow visible and identify precomputation. Keep the final video below
3:00. Listen all the way through at normal volume.

In YouTube Studio, select **Create > Upload videos**, select the MP4, and use:

**Title:** FLOWLAB — Shlok Gohil | Congressional App Challenge 2026 | GA-07

**Description:**

```text
FLOWLAB turns traffic video into explainable vehicle measurements and
simplified traffic experiments.
Creator: Shlok Gohil, Georgia's 7th Congressional District.
This walkthrough shows the local working build. Real analysis is precomputed.
The queue intervention uses a separately labeled synthetic dataset.

Real footage: E18-Lysaker (02).ogv, Kjetil_r, public domain author release.
Source: https://commons.wikimedia.org/wiki/File:E18-Lysaker_(02).ogv
Edits: source seconds 5-30; stabilization, cropping, resizing, audio removal;
FLOWLAB adds detection boxes and track trails. No generated traffic footage.

AI disclosure: Kilo and OpenAI Codex assisted substantial implementation,
debugging, testing and documentation. My reported contributions include the
problem idea, feature direction, finding/testing data and reporting deployment
issues. The app uses pretrained YOLO and ByteTrack; no custom model-training
or independent accuracy benchmark is claimed.
Source and assistance record: https://github.com/sgohils/FLOWLAB
```

Change the local-build sentence if you actually record the deployed release.
Answer YouTube's audience questions truthfully for your intended audience.
Under **Visibility**, choose **Public**, then publish. Wait for HD processing.
Do not rely on the default visibility; accounts aged 13–17 default to Private.

Open the video in a signed-out/private browser window. Confirm it plays,
speech is audible, labels are readable, it is 1–3 minutes, and no access
request appears. Copy its actual `https://www.youtube.com/watch?v=...` URL into
the required application field. Do not paste a placeholder or the source MP4.

Official upload help: https://support.google.com/youtube/answer/57407?hl=en
Official visibility help: https://support.google.com/youtube/answer/157177?hl=en
Official CAC rules: https://www.congressionalappchallenge.us/wp-content/uploads/2026/05/2026-CAC-Rules.pdf

Use the portrait JPEG in this directory for the application cover photo.
The app walkthrough itself should stay landscape so the interface is legible.
