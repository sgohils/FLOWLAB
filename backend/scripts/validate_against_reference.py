"""Validate a FLOWLAB analysis against human (or generator) reference data.

    python -m backend.scripts.validate_against_reference <reference.json>
    python -m backend.scripts.validate_against_reference <reference.json> --clip my.mp4

Without ``--clip`` the stored demo analysis is used, which is how the *measurement
layer* is validated against known values.  With a clip, the full pipeline runs
first, which is how *detector* output is validated against human annotations.

What this script can and cannot tell you
-----------------------------------------
* It measures agreement between the pipeline and the reference.  A small error on
  synthetic data says nothing about real-world detector accuracy.
* A real clip needs a reference file written by a person.  The format is
  documented in ``backend/validation/README.md``.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from ..analytics.metrics import build_analysis
from ..config import settings
from ..models.schemas import Analysis, Regions


def _load_analysis(reference: dict, clip: Path | None) -> tuple[Analysis, float]:
    """Return the analysis to validate and how long it took to produce (seconds)."""
    if clip is not None:
        from ..vision.detector import detector
        from ..vision.video_processor import process_video

        started = time.time()
        result = process_video(
            clip,
            output_path=settings.processed_dir / "validation" / "annotated.mp4",
            progress=lambda *_: None,
            detector=detector,
            settings=settings,
        )
        analysis = build_analysis(
            analysis_id="validation",
            video=result.video,
            tracks=result.tracks,
            regions=Regions.model_validate(reference["regions"]),
        )
        return analysis, time.time() - started

    # The bundled demo analysis is the same file the app serves at /api/demo.
    from ..api.state import DEMO_FILE, demo_analysis

    if DEMO_FILE.exists():
        analysis = demo_analysis()
        if analysis is not None:
            return analysis, 0.0
    raise SystemExit(
        "No bundled demo analysis found. Run:\n"
        "  python -m backend.scripts.build_demo_dataset"
    )


def compare_queue_series(
    computed: list[dict], reference: list[dict], tolerance_s: float = 0.5
) -> dict[str, Any]:
    """Compare the queue length at matching instants.

    Reference files written by a person use ``time_s``/``count``; the generator
    writes ``time_s``/``count`` too.  ``time``/``queue`` is accepted as well so
    a computed series can be fed back in.
    """
    by_time = {
        round(item.get("time_s", item.get("time", 0.0)), 2): item.get(
            "count", item.get("queue", 0)
        )
        for item in computed
    }
    errors: list[int] = []
    exact = 0
    matched = 0
    for item in reference:
        moment = round(item.get("time_s", item.get("time", 0.0)), 2)
        expected = item.get("count", item.get("queue", 0))
        # Find the computed sample closest in time.
        candidates = [key for key in by_time if abs(key - moment) <= tolerance_s]
        if not candidates:
            continue
        matched += 1
        nearest = min(candidates, key=lambda key: abs(key - moment))
        difference = by_time[nearest] - expected
        errors.append(abs(difference))
        if difference == 0:
            exact += 1
    return {
        "reference_points": len(reference),
        "matched_points": matched,
        "mean_absolute_error": round(statistics.fmean(errors), 3) if errors else None,
        "max_absolute_error": max(errors) if errors else None,
        "exact_match_rate": round(exact / matched, 4) if matched else None,
    }


def compare_counts(computed: list[float], reference: list[float], window: float) -> dict:
    """Count events inside a time window (the counting policy is compared too)."""
    computed_count = sum(1 for value in computed if 0.0 <= value <= window)
    reference_count = sum(1 for value in reference if 0.0 <= value <= window)
    error = computed_count - reference_count
    return {
        "window_s": round(window, 2),
        "computed": computed_count,
        "reference": reference_count,
        "absolute_error": error,
        "relative_error": (
            round(error / reference_count * 100, 1) if reference_count else None
        ),
    }


def compare_visits(computed: list[dict], reference: list[dict]) -> dict[str, Any]:
    """Match visits by start time and compare durations.

    Only visits that the reference marks as complete are comparable: a censored
    visit has no known true duration by construction.
    """
    rows: list[dict] = []
    used: set[int] = set()
    for entry in reference:
        if entry.get("censored"):
            continue
        best_index = None
        best_delta = float("inf")
        for index, candidate in enumerate(computed):
            if index in used:
                continue
            delta = abs(candidate["start"] - entry["entry_s"])
            if delta < best_delta and delta <= 2.0:
                best_delta = delta
                best_index = index
        if best_index is None:
            rows.append({"entry_s": entry["entry_s"], "matched": False})
            continue
        used.add(best_index)
        got = computed[best_index]
        true_duration = entry["exit_s"] - entry["entry_s"]
        got_duration = (got["end"] or got["start"]) - got["start"]
        rows.append(
            {
                "entry_s": entry["entry_s"],
                "matched": True,
                "start_delta_s": round(got["start"] - entry["entry_s"], 2),
                "reference_duration_s": round(true_duration, 2),
                "computed_duration_s": round(got_duration, 2),
                "duration_error_s": round(got_duration - true_duration, 2),
                "complete": got["complete"],
            }
        )
    errors = [abs(row["duration_error_s"]) for row in rows if row["matched"]]
    return {
        "reference_visits": len(reference),
        "matched": sum(1 for row in rows if row["matched"]),
        "mean_absolute_duration_error_s": round(statistics.fmean(errors), 2) if errors else None,
        "max_absolute_duration_error_s": max(errors) if errors else None,
        "rows": rows,
    }


def build_report(reference: dict, analysis: Analysis, seconds: float, clip: Path | None) -> dict:
    window = analysis.video.duration
    result: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "clip": {
            "path": str(clip) if clip else reference.get("clip"),
            "source": reference.get("clip_source"),
            "permission": reference.get("permission"),
            "duration_s": window,
            "width": analysis.video.width,
            "height": analysis.video.height,
            "source_fps": analysis.video.fps,
            "sampling_fps": analysis.regions.sample_fps,
            "model": settings.model_name,
            "confidence": settings.confidence,
            "speed_threshold": analysis.regions.speed_threshold,
            "min_queue_seconds": analysis.regions.min_queue_seconds,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": f"{platform.system()} {platform.machine()}",
            "processing_seconds": round(seconds, 1),
        },
        "computed": {
            "vehicles_tracked": analysis.summary.vehicles_tracked,
            "vehicles_crossed_exit": analysis.summary.vehicles_processed,
            "peak_queue": analysis.summary.peak_queue,
            "average_wait_s": analysis.summary.average_wait_seconds,
            "max_wait_s": analysis.summary.max_wait_seconds,
            "throughput_per_min": analysis.summary.throughput_per_minute,
        },
    }

    truth = reference.get("queue_counts")
    if truth:
        result["queue_series"] = compare_queue_series(
            [{"time": s.time, "queue": s.queue} for s in analysis.queue_timeseries], truth
        )
    if reference.get("departures_s") is not None:
        result["exit_crossings"] = compare_counts(analysis.departures, reference["departures_s"], window)
    if reference.get("arrivals_s") is not None:
        result["arrivals"] = compare_counts(analysis.arrivals, reference["arrivals_s"], window)
    if reference.get("queue_visits"):
        result["queue_visits"] = compare_visits(
            [v.model_dump() for v in analysis.queue_visits], reference["queue_visits"]
        )
    result["reference_notes"] = reference.get("notes", "")
    return result


def render_markdown(report: dict) -> str:
    clip = report["clip"]
    lines = [
        "# Validation report",
        "",
        f"Generated {report['generated_at']} by `backend.scripts.validate_against_reference`.",
        "",
        "## Clip",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| File | `{clip['path']}` |",
        f"| Source | {clip['source']} |",
        f"| Permission | {clip['permission']} |",
        f"| Resolution | {clip['width']}x{clip['height']} |",
        f"| Duration | {clip['duration_s']} s |",
        f"| Source FPS / sampling | {clip['source_fps']} / {clip['sampling_fps']} |",
        f"| Model | {clip['model']} (conf {clip['confidence']}) |",
        f"| Speed threshold | {clip['speed_threshold']} frame widths/s |",
        f"| Minimum queue time | {clip['min_queue_seconds']} s |",
        f"| Processing time | {report['environment']['processing_seconds']} s |",
        f"| Platform | {report['environment']['platform']}, Python {report['environment']['python']} |",
        "",
        "## Computed results",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for key, value in report["computed"].items():
        lines.append(f"| {key.replace('_', ' ')} | {value} |")

    series = report.get("queue_series")
    if series:
        lines += [
            "",
            "## Queue length agreement",
            "",
            f"- reference points: **{series['reference_points']}**, matched: **{series['matched_points']}**",
            f"- mean absolute error: **{series['mean_absolute_error']} vehicles**",
            f"- maximum absolute error: **{series['max_absolute_error']} vehicles**",
            f"- exact agreement: **{series['exact_match_rate'] * 100:.1f}%** of matched instants",
        ]
    for key, title in (
        ("exit_crossings", "Exit crossings"),
        ("arrivals", "Arrivals"),
    ):
        block = report.get(key)
        if block:
            lines += [
                "",
                f"## {title}",
                "",
                f"- computed **{block['computed']}**, reference **{block['reference']}** "
                f"in a {block['window_s']} s window",
                f"- absolute error **{block['absolute_error']}**, relative error "
                f"**{block['relative_error']}%**" if block["relative_error"] is not None
                else f"- absolute error **{block['absolute_error']}**",
            ]
    visits = report.get("queue_visits")
    if visits:
        lines += [
            "",
            "## Queue visits",
            "",
            f"- matched **{visits['matched']}** of **{visits['reference_visits']}** reference visits",
            f"- mean absolute duration error **{visits['mean_absolute_duration_error_s']} s**",
            f"- maximum absolute duration error **{visits['max_absolute_duration_error_s']} s**",
        ]
    if report.get("reference_notes"):
        lines += ["", "## Reference notes", "", report["reference_notes"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="reference annotation JSON")
    parser.add_argument("--clip", type=Path, default=None, help="run the full pipeline first")
    parser.add_argument("--json", type=Path, default=None, help="also write the raw JSON report")
    parser.add_argument("--markdown", type=Path, default=None, help="write a markdown report")
    arguments = parser.parse_args()

    reference = json.loads(arguments.reference.read_text(encoding="utf-8"))
    analysis, seconds = _load_analysis(reference, arguments.clip)
    report = build_report(reference, analysis, seconds, arguments.clip)

    if arguments.json:
        arguments.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if arguments.markdown:
        arguments.markdown.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
