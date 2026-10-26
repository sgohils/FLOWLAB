"""Build a real-video example with the ordinary detector and analytics pipeline.

The input must be the licensed, stabilized excerpt documented in
``backend/demo/real_video_provenance.json``. No synthetic tracks are introduced.
Run from the repository root with --source and --ffmpeg paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import replace
from pathlib import Path

from ..analytics.metrics import build_analysis
from ..config import BACKEND_DIR, PROJECT_DIR, settings
from ..models.schemas import Regions, SampleProvenance
from ..vision.detector import VehicleDetector
from ..vision.video_processor import process_video

ASSETS = PROJECT_DIR / "frontend" / "public" / "demos"
PROVENANCE = BACKEND_DIR / "demo" / "real_video_provenance.json"
OUTPUT = BACKEND_DIR / "demo" / "real_analysis.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--poster", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    ASSETS.mkdir(parents=True, exist_ok=True)
    source = ASSETS / "traffic-source.mp4"
    if args.source.resolve() != source.resolve():
        shutil.copyfile(args.source, source)
    poster = ASSETS / "traffic-poster.jpg"
    if args.poster.resolve() != poster.resolve():
        shutil.copyfile(args.poster, poster)
    scratch = PROJECT_DIR / "data" / "demo-candidates" / "pipeline-annotated.mp4"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    config = replace(settings, hosted=False, model_name=str(PROJECT_DIR / "yolo11n.pt"))
    previous = -1

    def progress(stage: str, fraction: float, message: str) -> None:
        nonlocal previous
        percent = int(fraction * 100)
        if stage != "detecting" or percent // 10 != previous:
            print(f"{stage}: {percent}% {message}", flush=True)
            previous = percent // 10

    started = time.monotonic()
    result = process_video(
        source, output_path=scratch, progress=progress,
        detector=VehicleDetector(config), settings=config, sample_fps=10.0,
    )
    # The near carriageway moves from bottom-left to top-right. The lines
    # cover that carriageway only; the total tracked count covers the scene.
    regions = Regions(
        queue=[(0.56, 0.93), (0.75, 0.48), (0.98, 0.48), (0.98, 0.96)],
        entry=[(0.53, 0.88), (0.94, 0.88)],
        exit=[(0.76, 0.42), (0.99, 0.42)],
        entry_direction="any", exit_direction="any",
        speed_threshold=0.006, min_stop_seconds=1.5,
        min_queue_seconds=0.5, sample_fps=10.0,
    )
    analysis = build_analysis(
        "real-demo", result.video.model_copy(update={"annotated_path": None}),
        result.tracks, regions, source="video",
    )
    if not analysis.trajectories or not analysis.arrivals:
        raise RuntimeError("The real video produced no usable tracks/arrivals; do not publish it.")
    analysis.sample = SampleProvenance(
        title="Real traffic · Lysaker, Norway",
        description="A public-road, free-flow traffic example processed with FLOWLAB's "
        "ordinary detector and tracker. It is not a Georgia school dismissal study.",
        author=metadata["author"], source_url=metadata["source_url"],
        license=metadata["license"], license_url=metadata["source_url"],
        processing_notes=[
            "Source excerpt: 5-30 seconds, original timing retained. Background stabilization, "
            "edge cropping, resizing and audio removal; "
            "no generated vehicles or interpolated frames.",
            "YOLO11n + ByteTrack; sampled at 10 fps. Precomputed results use the same "
            "pipeline as uploads. No manual detector-accuracy benchmark has been performed.",
            "This is free-flow highway traffic with opposing directions. Entry/exit lines "
            "measure the near carriageway; the tracked-vehicle count covers the full scene.",
            "Tracked counts are retained tracker IDs, not a manually verified count of "
            "unique physical vehicles; ID switches can split a vehicle into several tracks.",
            "Perspective, residual camera drift, occlusions and fragmented tracks affect "
            "measurements. Image motion is not a calibrated physical speed.",
        ],
        video_url="/demos/traffic-source.mp4",
        annotated_video_url="/demos/traffic-annotated.mp4",
        poster_url="/demos/traffic-poster.jpg",
    )
    analysis.warnings.insert(
        0, "Real public-road footage; automated measurements, not a validated school study."
    )
    OUTPUT.write_text(analysis.model_dump_json(), encoding="utf-8")
    subprocess.run([
        str(args.ffmpeg), "-y", "-i", str(scratch), "-an", "-c:v", "libx264",
        "-preset", "fast", "-crf", "25", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(ASSETS / "traffic-annotated.mp4"),
    ], check=True, capture_output=True)
    metadata["sample_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    metadata["model_file_sha256"] = hashlib.sha256(Path(config.model_name).read_bytes()).hexdigest()
    metadata["processing_seconds"] = round(time.monotonic() - started, 2)
    metadata["vehicles_tracked"] = analysis.summary.vehicles_tracked
    metadata["vehicles_crossed_exit"] = analysis.evidence.vehicles_crossed_exit
    metadata["sampled_frames"] = result.processed_frames
    PROVENANCE.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": analysis.summary.model_dump(), "arrivals": len(analysis.arrivals),
                      "provenance": str(PROVENANCE), "output": str(OUTPUT)}, indent=2))


if __name__ == "__main__":
    main()
