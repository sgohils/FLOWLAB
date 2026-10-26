# FLOWLAB application answers

Prepared for Shlok Gohil, GA-07, October 25, 2026. Read the first-person drafts
before pasting so they reflect your actual work and learning. No application
has been submitted. The public demonstration-video URL remains required.

## App name

FLOWLAB

## Programming languages

Select **Python**, **JavaScript**, and **Other**. For Other, enter **TypeScript**.
The frontend is authored in TypeScript/TSX and compiled to JavaScript. HTML,
CSS and SQL are also used for the interface and data storage.

## Platforms

Select **Web**. It runs in a browser; it is not a native iOS or Android app.

## Video demonstration URL

**Pending:** record and upload the narrated demonstration to YouTube or Vimeo,
set it to Public, and paste its actual `https://` URL. The sample traffic MP4
is source footage, not the required demonstration of the app.

## Briefly describe what your app does

FLOWLAB is a web app that turns traffic video into vehicle trajectories,
explainable measurements and interactive traffic experiments. It is intended
for school transportation teams, community planners and students investigating
how traffic moves through an entrance, exit or roadway.

Users can upload a permitted video or explore a bundled example. A pretrained
YOLO model detects vehicles, and ByteTrack connects detections into temporary
track IDs. FLOWLAB calculates queue length, time spent moving slowly in a
selected region, exit-line crossing rates and areas where vehicles slow down.
The annotated video, trajectory map and charts share a playback clock so users
can inspect the evidence behind the numbers.

Users can also compare a simplified baseline model with scenarios such as
fewer arrivals, faster exit processing or an additional exit channel. The app
separates video measurements, model mismatch and hypothetical scenario effects.
It provides measurement exports, experiment notes and a printable brief.

The real example uses credited public-domain footage; a separate synthetic
example demonstrates queue experiments. Results are exploratory and need
independent validation before real traffic decisions.

## What inspired you to create this app?

I was inspired after witnessing an accident one morning before school. That
experience made me think about how schools and communities could better
understand the traffic around them.

I wanted to explore a practical question: could ordinary traffic video help
people see where vehicles slow down and investigate possible changes with
clearer evidence? That question became FLOWLAB.

The app focuses on making traffic measurements understandable. Users can
inspect the video behind a result, see how a number was calculated and compare
a proposed change with a clearly identified model baseline. My goal is to
help people ask better questions about traffic and support further study.
The accident motivated the project; the app has not been shown to prevent
accidents or establish the cause of the accident I witnessed.

## What technical difficulties did you face programming your app?

One major difficulty was moving a computer-vision application from a local
computer to serverless hosting. Python and machine-learning dependencies
exceeded deployment bundle limits. The local design also relied on SQLite,
uploaded files and job state stored on one machine. Hosted processing required
durable database records, video storage, queued jobs and correct routing
between services. I reported deployment failures with logs and screenshots;
AI coding assistance helped implement and debug the changes.

Another challenge was making the simulation comparison trustworthy. The
unchanged baseline was inadvertently stretching arrival timestamps, and some
metrics included vehicles completing after the observation window. Those
problems could make an apparent improvement misleading. The fixes preserve
arrival timing, count completions within the stated window and keep unavailable
measurements separate from zero.

I also found and tested data for the project. The app uses a pretrained
detector, and automated track counts are not an independently verified
accuracy score. The development process included regression tests and browser
checks for playback, calculations and exports.

## What improvements would you make in version 2.0?

My first priority would be independent validation using permitted,
representative traffic footage. I would compare the app's counts and queue
measurements with manual reference annotations across different camera angles,
lighting conditions and levels of occlusion.

I would add sign-in, per-user access controls and configurable automatic
deletion before using a shared hosted version for private school footage. The
current shared demonstration has no account isolation, so it should use only
publicly shareable footage.

I would also improve camera calibration so movement could be interpreted on
a real-world scale, strengthen tracking when vehicles overlap, and expand the
simulator to represent more realistic entrances, turns and signals. Working
with school transportation staff would help evaluate which questions and
reports are actually useful.

I would measure whether those improvements make the results more reliable
and easier to interpret before claiming real-world benefits.

## Did you use AI?

**Yes.**

## How did you use AI, and what did you contribute directly?

I used Kilo in Visual Studio Code and OpenAI Codex for coding assistance.
These tools generated or substantially revised a large majority of the
implementation, including backend and frontend code, tests, deployment fixes,
debugging and documentation. Codex also helped integrate the credited real
traffic example and draft submission materials. This assistance is documented
in the repository's AI assistance record.

The app also uses a pretrained Ultralytics YOLO model for vehicle detection
and ByteTrack for tracking. I am not claiming that I trained a custom model.
The real demonstration footage is an existing public-domain recording, not
AI-generated video. The separate synthetic example is mathematically generated
and labeled synthetic.

My direct contributions included the problem idea, motivated by an accident
I witnessed before school; feature priorities; finding and testing data;
choosing a free hosting approach; and reporting deployment problems using
error logs and screenshots. I distinguish that work from code generated by
the assistants. I am not claiming that I independently wrote the entire
application or that the automated results establish detector accuracy.

## What did you learn or take away?

Draft to review against your own experience:

This project taught me that producing a result is only part of building a
useful application. The result also needs a clear definition, evidence and an
honest explanation of its limits. Finding and testing data matters because
a model's output must be checked against what the footage actually shows.

I learned why traffic measurements and simulated outcomes need to stay
separate. A model can differ from the observed data before any proposed
change is applied. Comparing a scenario with the unchanged model helps avoid
presenting model error as a real improvement.

The deployment problems also showed me how much infrastructure a working web
app needs beyond its interface: persistent storage, background processing,
service routing and useful error messages. I learned to treat AI-generated
code as work that requires testing and disclosure. My biggest takeaway is
that a convincing demonstration should make its evidence and uncertainty easy
to inspect.

## Cover photo

Upload **flowlab-cover-600x800.jpg**, in this directory. It is a 600 by 800 pixel
JPEG cover composed from genuine annotated FLOWLAB video output and recorded
sample measurements. Its editable HTML source is `cover.html`. Source footage
is credited on the cover and in `frontend/public/demos/CREDITS.txt`.

## Optional project link

Website: https://flowlab1.vercel.app/

Source: https://github.com/sgohils/FLOWLAB

Publish the latest source and redeploy before directing judges to new features.
On October 25, the live site served the synthetic demo, but its
`/api/analyses/real-demo/status` returned 404; the real example currently works
in the local tested build.

## Congressional Certification

Suggested optional choice: **Yes, I'd like to learn more about being
Congressional Certified**, if you want information about the program. This
is an opt-in to learn more; it is not a claim of certification.

## Where did you do most of the coding?

**At Home**

## Completion date

**10/25/2026**

## School, club or similar organization project?

**No**, based on your answer that no organization or mentor was involved.

## Organization / teacher / mentor / mentor email

Leave the conditional fields blank after selecting No. Do not enter a fake
email address or name.

## App Challenge Ambassador referral email

Leave blank; you reported no referral.

## Application ready to submit

Do not select Yes yet. The required public video URL is missing. After the
video is public, all required fields are complete, your disclosures and
eligibility are checked, and the links work, the primary applicant can
personally select **Yes** and submit.

The official rules require significant student technical contribution as well
as full AI disclosure. This draft credits the contributions you reported; it
does not certify eligibility or replace the district's determination.
