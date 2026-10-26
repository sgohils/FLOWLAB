# Real video example

The home-page **Watch real traffic analysis** link opens `/analysis/real-demo`.
Its video, trajectories, replay, evidence and exports are bundled with the app.
They work without PostgreSQL, Blob credentials or queue workers. Scenario
execution still uses the backend's ordinary simulator, using the bundled data.

## Footage and rights

- Original: [E18-Lysaker (02).ogv](https://commons.wikimedia.org/wiki/File:E18-Lysaker_(02).ogv).
- Author: [Kjetil_r](https://commons.wikimedia.org/wiki/User:Kjetil_r).
- Recorded April 23, 2010, on the E18 at Lysaker, Norway.
- Public domain through the author's own-work release; this is not a CC0 claim.
- Source excerpt: seconds 5–30, preserving all 750 frames at 30 fps.
- Preparation: background-feature stabilization, a fixed 64-pixel edge crop,
  resizing to 960×494, audio removal, and H.264 MP4 encoding. The annotated
  version adds detector boxes and trails. No generated vehicles, frame
  interpolation or changed timing.

Credits are included with the files in
[CREDITS.txt](../frontend/public/demos/CREDITS.txt). Source/model/excerpt hashes
and the full preparation record are in
[real_video_provenance.json](../backend/demo/real_video_provenance.json).

## What the run actually produced

| Item | Value |
| --- | --- |
| Source duration | 25.0 seconds |
| Input frames | 750 |
| Detector samples | 250, at 10 fps |
| Initial tracker fragments | 91 |
| Retained tracker IDs | 75 |
| Entry-line crossings | 12 |
| Exit-line crossings | 10 |
| Selected-line throughput | 24 vehicles/minute, extrapolated from 25 seconds |
| Peak measured queue | 0 |
| Completed queue visits | 0 |
| Estimated wait | Unavailable; no completed queue visits |

These are **automated pipeline outputs**, not independent accuracy evidence.
Tracker IDs are not a manually verified count of unique physical vehicles.
The scene contains opposing traffic. Total retained IDs cover the full scene;
entry/exit lines cover only the near carriageway.

The clip shows free-flow highway traffic, not a school gate. Use it to explain
real detection, tracking and line measurement. Use the separately labeled
`/simulation/demo` synthetic queue sandbox to explain a gate intervention.
Do not claim that a zero queue was reduced or that this is Georgia school data.

No complete queued-discharge window was observed. The simulator uses the
fastest-departure-gap capacity proxy and its explicit minimum service-time
floor. Those are model assumptions, not an observed gate-processing capacity.
The interface and experiment note show this distinction.

## Rebuild

Install the backend dependencies and provide the same licensed, prepared
excerpt, poster and an FFmpeg executable. Keep `yolo11n.pt` in the repository
root, or adjust the builder's documented model path.

```powershell
python -m backend.scripts.build_real_demo --source frontend/public/demos/traffic-source.mp4 --poster frontend/public/demos/traffic-poster.jpg --ffmpeg PATH_TO_FFMPEG
```

The command runs the real detector and analytics; it does not invent tracks.
It writes `backend/demo/real_analysis.json`, media under `frontend/public/demos`,
and hashes/processing metadata. Model/dependency changes can alter detections.

The source video can also be downloaded from the home page and uploaded as an
ordinary analysis. That path uses the deployment's configured storage and
processing worker and permits the user to edit measurement regions.
