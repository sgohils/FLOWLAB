"""Developer utility: cut a short, slower test clip out of a long recording.

Not part of the product: it exists so a developer with any long traffic video
can produce a 20 second clip that runs through the pipeline in seconds.

    python -m backend.scripts.make_test_clip input.mp4 output.mp4 \\
        --start 20 --seconds 10 --slowdown 2
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def make_clip(
    source: Path,
    destination: Path,
    start: float,
    seconds: float,
    slowdown: int,
    fps: float,
) -> Path:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise SystemExit(f"Could not open {source}")
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    first = int(start * source_fps)
    last = int((start + seconds) * source_fps)

    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(destination), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise SystemExit("OpenCV could not open an MP4 writer on this machine")

    written = 0
    for index in range(first, last):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            break
        for _ in range(max(1, slowdown)):
            writer.write(frame)
            written += 1
    capture.release()
    writer.release()
    print(f"Wrote {destination} - {written} frames at {fps} fps ({written / fps:.1f}s)")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--start", type=float, default=0.0, help="start time in seconds")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--slowdown", type=int, default=2, help="frames repeated per source frame")
    parser.add_argument("--fps", type=float, default=10.0)
    arguments = parser.parse_args()
    make_clip(
        arguments.source,
        arguments.destination,
        arguments.start,
        arguments.seconds,
        arguments.slowdown,
        arguments.fps,
    )


if __name__ == "__main__":
    main()
