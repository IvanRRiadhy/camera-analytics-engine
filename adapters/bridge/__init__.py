"""
Adapters Bridge package exports.
"""

from camera_analytics.adapters.bridge.frame_adapter import FrameIngestionAdapter
from camera_analytics.adapters.bridge.inference_pipeline import FrameProcessingSummary, InferencePipeline
from camera_analytics.adapters.bridge.pipeline_worker import PipelineExecutionWorker

__all__ = [
    "FrameIngestionAdapter",
    "InferencePipeline",
    "FrameProcessingSummary",
    "PipelineExecutionWorker",
]
