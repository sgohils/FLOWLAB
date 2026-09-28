# Validation reference files

A **reference file** is the list of measurements a human (or the scene generator)
knows to be true. `backend/scripts/validate_against_reference.py` runs the
pipeline, then compares it against that file and prints the errors.

Two different jobs use the same format:

| Job | Reference comes from | Proves |
| --- | --- | --- |
| **Measurement validation** | `backend/demo/sample_reference.json`, written by the demo generator, which knows the exact positions of every vehicle | the queue / wait / count code is correct |
| **Detector validation** | a person watching a real clip and writing down what they see | the detector and tracker find the right vehicles |

The first is already automated. The second needs your clip.

---

## 1. Getting a clip you may use

Use footage you created, or footage whose licence permits your use. A clip is
good when:

- the camera is fixed (no pan, no zoom, no shake),
- vehicles are bigger than roughly 15 pixels across,
- the scene is evenly lit (no heavy shadow or glare across the road),
- the codec decodes (MP4/H.264 is the safest),
- it is 10–60 seconds long, so a run takes seconds rather than minutes.

If a distant camera makes the vehicles too small, the detector will find few of
them. The app can crop to a region of interest before inference:

```bash
# Windows
set FLOWLAB_ROI=0.40,0.0,0.72,1.0
# macOS / Linux
export FLOWLAB_ROI=0.40,0.0,0.72,1.0
```

Those four numbers are `x0,y0,x1,y1` in normalised image coordinates, i.e. the
part of the frame that contains the road.

## 2. Producing a short test segment

```bash
python -m backend.scripts.make_test_clip long_recording.mp4 sample.mp4 \
    --start 30 --seconds 12 --slowdown 2 --fps 10
```

`--slowdown` repeats frames, which makes fast (for example time-lapse) footage
easier to analyse.

## 3. Writing the reference file

Copy `backend/validation/template.json` and fill it in. Every field is optional
except `regions` — delete the parts you did not annotate, and the script skips
them.

```json
{
  "clip": "sample.mp4",
  "clip_source": "recorded on my own phone at the school gate",
  "permission": "my own footage",
  "annotated_by": "your name",
  "annotated_at": "2026-10-05",
  "notes": "Heavy shadow under the tree from 00:18 onwards.",

  "regions": {
    "queue": [[0.52, 0.05], [0.66, 0.05], [0.66, 0.45], [0.52, 0.45]],
    "entry": [[0.0, 0.10], [1.0, 0.10]],
    "exit":  [[0.0, 0.90], [1.0, 0.90]],
    "exit_direction": "any"
  },

  "arrivals_s":   [2.4, 6.1, 9.8, 14.2],
  "departures_s": [7.9, 11.0, 15.6, 19.3],

  "queue_counts": [
    {"time_s": 10.0, "count": 2},
    {"time_s": 15.0, "count": 3},
    {"time_s": 20.0, "count": 1}
  ],

  "queue_visits": [
    {"label": "silver car", "entry_s": 8.2, "exit_s": 15.4, "censored": false},
    {"label": "white van",  "entry_s": 12.0, "exit_s": null, "censored": true}
  ]
}
```

### How to annotate each field

**`regions`** — the same geometry the app draws on the video. The line
coordinates are what matter: a vehicle counts as crossing when its track goes
from one side of the segment to the other and the intersection is inside the
segment. Place entry and exit lines where every vehicle clearly passes.

> A line that some vehicles start *past* will never be crossed by them. If a
> vehicle is already on the far side of the entry line when it first appears,
> it is not counted as an arrival. This is not a bug in the crossing code; it
> showed up during validation of the bundled demo and the line was moved.

**`arrivals_s` / `departures_s`** — the times, in seconds from the start of the
clip, at which you see a vehicle cross the line. Write down the time to about a
tenth of a second. The comparison is a count inside the window, so what matters
most is getting the *count* right, not the exact timestamp.

**`queue_counts`** — a handful of instants where you pause the video and count
how many vehicles are inside the queue region. 10 to 20 instants spread across
the clip is plenty. This is the most valuable field: it checks the central
number of the whole application.

**`queue_visits`** — for 3 to 5 vehicles, the moment it joins the queue and the
moment it leaves. If a vehicle is still in the queue when the clip ends, set
`"censored": true` and leave `exit_s` as `null`; censored visits are excluded
from the comparison because their true duration is unknown by construction.

## 4. Running the comparison

```bash
# measurement layer against the bundled ground truth (no clip needed)
python -m backend.scripts.validate_against_reference backend/demo/sample_reference.json

# your clip against your annotations
python -m backend.scripts.validate_against_reference backend/validation/mine.json \
    --clip sample.mp4 \
    --markdown docs/VALIDATION_REPORT.md \
    --json docs/validation.json
```

The report records the clip, the configuration, the computed results, and the
error against each annotated quantity.

## 5. What the numbers mean

- **Counts** (arrivals, departures): an absolute error of 0 means every vehicle
  was counted once. Error of 1 means one vehicle was missed or counted twice.
- **Queue counts**: `mean_absolute_error` is the average number of vehicles by
  which the pipeline disagreed with you, across the instants you annotated.
  A value under 1 means it was usually right or off by one.
- **Visit durations**: the error is in seconds and is signed, so a systematic
  offset points at the definition rather than at noise.

## 6. What you should not conclude

- A small error on the synthetic dataset says **nothing** about detector accuracy
  on real footage.
- Agreement on 15 annotated instants is a smoke test, not a statistical claim.
  If you want to quote a number in a submission, say how many instants and how
  many vehicles were annotated.
- FLOWLAB measures vehicles, not safety, compliance or capacity. Nothing here
  supports a claim about congestion reduction at a real school.
