"""
Adapters package.

Concrete implementations of ports (DetectorPort, TrackerPort, PipelineWorker).
"""

from camera_analytics.adapters.bridge.inference_pipeline import (
    FrameProcessingSummary,
    InferencePipeline,
)
from camera_analytics.adapters.bridge.pipeline_worker import PipelineExecutionWorker
from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
from camera_analytics.adapters.tracking.botsort_adapter import BoTSORTAdapter

__all__ = [
    "YOLOPoseAdapter",
    "BoTSORTAdapter",
    "InferencePipeline",
    "PipelineExecutionWorker",
    "FrameProcessingSummary",
]
