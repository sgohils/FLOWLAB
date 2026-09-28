"""Vision layer: detection, tracking, trajectories and video rendering."""

from .annotator import FrameAnnotation, build_annotation, draw_annotations
from .detector import DetectorError, RawDetection, VehicleDetector, detector
from .trajectories import TrackAccumulator
from .video_processor import ProcessingResult, VideoProcessingError, process_video

__all__ = [
    "DetectorError",
    "FrameAnnotation",
    "ProcessingResult",
    "RawDetection",
    "TrackAccumulator",
    "VehicleDetectionError",
    "VehicleDetector",
    "VideoProcessingError",
    "build_annotation",
    "detector",
    "draw_annotations",
    "process_video",
]
