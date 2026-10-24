"""Vehicle detection with a pretrained Ultralytics YOLO model.

Only COCO vehicle classes are requested, so people are never even detected -
FLOWLAB stores nothing that could identify a person.  No model is trained here:
the interesting engineering is the pipeline that runs *after* detection.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..config import Settings
from ..config import settings as default_settings

logger = logging.getLogger(__name__)


class DetectorError(RuntimeError):
    """Raised when the model cannot be loaded (missing weights, no torch, ...)."""


@dataclass(frozen=True, slots=True)
class RawDetection:
    """One detection box, already converted to normalised coordinates."""

    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    track_id: int | None = None

    @property
    def contact(self) -> tuple[float, float]:
        """Bottom-centre of the box: the closest point to the road surface.

        The bounding-box *centre* floats above the ground for tall vehicles and
        moves differently when the camera is tilted, which distorts speed
        proxies.  The bottom-centre is the standard traffic-analysis choice.
        """
        return ((self.x1 + self.x2) / 2.0, self.y2)


class VehicleDetector:
    """Lazily loaded YOLO detector + ByteTrack association.

    The model is loaded once per process and shared between jobs (loading takes
    a few seconds).  All work happens in a worker thread, and the model object
    is only ever touched by one job at a time.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or default_settings
        self._model: Any = None
        self._names: dict[int, str] = {}
        self._lock = threading.Lock()
        self._loaded = False
        self._error: str | None = None
        self._device: str | None = None

    # -- lifecycle ---------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def device(self) -> str:
        """The device actually in use (``cpu`` or ``cuda:0``)."""
        if self._device:
            return self._device
        configured = self._settings.device
        return "cpu" if configured.lower() in {"auto", ""} else configured

    def _device_argument(self) -> str | None:
        """Translate the configured device into what Ultralytics expects.

        Ultralytics uses ``None`` for "pick the best available device" and
        rejects the literal string ``auto``.
        """
        configured = self._settings.device
        if configured.strip().lower() in {"auto", ""}:
            return None
        return configured

    def load(self) -> None:
        """Load weights once.  Raises :class:`DetectorError` with a clear message."""
        with self._lock:
            if self._loaded:
                return
            if self._error:
                raise DetectorError(self._error)
            try:
                from ultralytics import YOLO
            except Exception as exc:  # pragma: no cover - depends on the env
                self._error = (
                    "The Ultralytics package is not installed. Run "
                    "`pip install -r backend/requirements.txt`."
                )
                raise DetectorError(self._error) from exc
            try:
                model = YOLO(self._settings.model_name)
            except Exception as exc:
                self._error = (
                    f"Model '{self._settings.model_name}' could not be loaded "
                    f"({type(exc).__name__}). It downloads on first use; check the "
                    "network connection or set FLOWLAB_MODEL to a local .pt file."
                )
                raise DetectorError(self._error) from exc
            self._model = model
            self._names = dict(getattr(model, "names", {}) or {})
            self._loaded = True
            self._device = _device_of(model) or self.device
            logger.info("Loaded YOLO model %s on %s", self._settings.model_name, self._device)

    def class_name(self, class_id: int) -> str:
        """Name of a COCO class id, or ``"vehicle"`` if the model does not know it.

        ``_names`` is filled from the loaded model's own ``names`` mapping in
        :meth:`load`, so it is the single source: a second lookup into the model
        object could only ever return the same value.
        """
        name = self._names.get(class_id)
        return str(name) if name is not None else "vehicle"

    # -- inference ---------------------------------------------------------

    def detect(self, frame: np.ndarray, track: bool = True) -> list[RawDetection]:
        """Run detection (+ tracking) on a BGR frame.

        ``track=True`` uses Ultralytics' ByteTrack association, which keeps a
        stable id per vehicle across frames.  When an ROI is configured, the
        frame is cropped before inference and the boxes are mapped back to full
        frame coordinates so every downstream module stays resolution agnostic.
        """
        self.load()
        assert self._model is not None  # guaranteed by load()
        settings = self._settings
        roi = settings.roi
        if roi is None:
            crop = frame
            crop_width, crop_height = frame.shape[1], frame.shape[0]
        else:
            x0, y0, x1, y1 = roi
            crop_width = max(1, round((x1 - x0) * frame.shape[1]))
            crop_height = max(1, round((y1 - y0) * frame.shape[0]))
            crop = frame[
                round(y0 * frame.shape[0]) : round(y1 * frame.shape[0]),
                round(x0 * frame.shape[1]) : round(x1 * frame.shape[1]),
            ]
        with self._lock:
            results = self._model.track(
                crop,
                persist=track,
                tracker=settings.tracker_config if track else None,
                conf=settings.confidence,
                iou=settings.iou,
                imgsz=settings.imgsz,
                device=self._device_argument(),
                classes=settings.class_ids,
                verbose=False,
            )
        detections = self._parse(results[0] if results else None, crop_width, crop_height)
        if roi is not None:
            x0, y0, x1, y1 = roi
            width = x1 - x0
            height = y1 - y0
            detections = [
                RawDetection(
                    class_name=item.class_name,
                    confidence=item.confidence,
                    x1=_clamp(x0 + item.x1 * width),
                    y1=_clamp(y0 + item.y1 * height),
                    x2=_clamp(x0 + item.x2 * width),
                    y2=_clamp(y0 + item.y2 * height),
                    track_id=item.track_id,
                )
                for item in detections
            ]
        return detections

    def _parse(self, result, width: int, height: int) -> list[RawDetection]:
        if result is None or getattr(result, "boxes", None) is None:
            return []
        boxes = result.boxes
        xyxy = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()
        class_ids = boxes.cls.cpu().numpy().astype(int)
        track_ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else None

        detections: list[RawDetection] = []
        for index in range(len(xyxy)):
            name = self.class_name(int(class_ids[index]))
            if name not in self._settings.classes:
                continue  # privacy guard: never keep a class we did not ask for
            x1, y1, x2, y2 = xyxy[index]
            detections.append(
                RawDetection(
                    class_name=name,
                    confidence=float(confidences[index]),
                    x1=_clamp(x1 / width),
                    y1=_clamp(y1 / height),
                    x2=_clamp(x2 / width),
                    y2=_clamp(y2 / height),
                    track_id=int(track_ids[index]) if track_ids is not None else None,
                )
            )
        return detections


def _device_of(model) -> str | None:
    """Read the device the loaded weights ended up on."""
    try:
        parameters = model.model.parameters()
        return str(next(iter(parameters)).device)
    except (AttributeError, StopIteration, TypeError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if not np.isfinite(value):
        return low
    return float(min(high, max(low, value)))


#: One shared detector for the whole process.
detector = VehicleDetector()
