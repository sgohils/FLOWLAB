"""Annotated video rendering.

Overlays are deliberately restrained: a thin box, an anonymous id, a short
trajectory tail and (optionally) the user drawn regions.  Nothing identifies a
person, a plate or a face - the only label ever written is ``Car #021``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from ..models.schemas import TrajectoryPoint

#: BGR colours per class, chosen to stay legible on asphalt.
CLASS_COLOURS: dict[str, tuple[int, int, int]] = {
    "car": (196, 122, 40),
    "bus": (150, 60, 190),
    "truck": (90, 170, 90),
    "motorcycle": (80, 190, 220),
    "bicycle": (200, 200, 120),
    "vehicle": (196, 122, 40),
}
FALLBACK_COLOUR = (196, 122, 40)
BOX_THICKNESS_RATIO = 0.0016


@dataclass(slots=True)
class FrameAnnotation:
    """Everything drawn for one frame, in pixel coordinates."""

    boxes: list[tuple[tuple[int, int, int, int], str, tuple[int, int, int]]]
    trails: list[list[tuple[int, int]]]


def draw_annotations(frame: np.ndarray, annotation: FrameAnnotation) -> np.ndarray:
    """Return a copy of ``frame`` with the overlays composited on top.

    User drawn regions are *not* baked into the video: they are rendered by the
    browser on top of the player, which keeps the video immutable and lets the
    user redraw a region without re-processing anything.
    """
    canvas = frame.copy()
    height, width = canvas.shape[:2]
    thickness = max(1, round(min(width, height) * BOX_THICKNESS_RATIO))
    font_scale = max(0.35, min(width, height) / 1100.0)

    for trail in annotation.trails:
        if len(trail) < 2:
            continue
        points = np.array(trail, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(canvas, [points], False, (170, 170, 170), thickness, cv2.LINE_AA)

    for (x1, y1, x2, y2), label, colour in annotation.boxes:
        cv2.rectangle(canvas, (x1, y1), (x2, y2), colour, thickness, cv2.LINE_AA)
        _draw_label(canvas, label, (x1, y1), colour, thickness, font_scale)

    return canvas


def _draw_label(
    canvas: np.ndarray,
    label: str,
    origin: tuple[int, int],
    colour: tuple[int, int, int],
    thickness: int,
    font_scale: float,
) -> None:
    (text_width, text_height), baseline = cv2.getTextSize(
        label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
    )
    x, y = origin
    top = max(0, y - text_height - baseline - 4)
    cv2.rectangle(
        canvas,
        (x, top),
        (x + text_width + 8, top + text_height + baseline + 4),
        colour,
        -1,
    )
    cv2.putText(
        canvas,
        label,
        (x + 4, top + text_height),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def build_annotation(
    detections: Sequence[tuple[int, str, tuple[float, float, float, float]]],
    trails: dict[int, list[TrajectoryPoint]],
    width: int,
    height: int,
    trail_length: int,
) -> FrameAnnotation:
    """Convert normalised detections + history into pixel space overlays."""
    boxes: list[tuple[tuple[int, int, int, int], str, tuple[int, int, int]]] = []
    drawn_trails: list[list[tuple[int, int]]] = []
    for vehicle_id, class_name, bbox in detections:
        x1, y1, x2, y2 = bbox
        px1, py1 = int(x1 * width), int(y1 * height)
        px2, py2 = int(x2 * width), int(y2 * height)
        colour = CLASS_COLOURS.get(class_name, FALLBACK_COLOUR)
        label = f"{class_name.capitalize()} #{vehicle_id:03d}"
        boxes.append(((px1, py1, px2, py2), label, colour))
        history = trails.get(vehicle_id)
        if history and len(history) >= 2:
            tail = history[-trail_length:]
            drawn_trails.append([(int(p.x * width), int(p.y * height)) for p in tail])
    return FrameAnnotation(boxes=boxes, trails=drawn_trails)
