"""
Inference Pipeline Component.

Encapsulates and orchestrates the production AI runtime pipeline:
    Frame Source -> ContextBuilder (YOLO Pose -> BoT-SORT -> Zone Engine) -> SharedAnalyticsContext -> PluginManager -> CommunicationManager.

Enforces Fail-Fast policy (no synthetic/fake fallbacks permitted in production runtime).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
from camera_analytics.adapters.tracking.botsort_adapter import BoTSORTAdapter
from camera_analytics.communication.manager import CommunicationManager
from camera_analytics.context.services import ContextBuilder
from camera_analytics.context.unified_context import SharedAnalyticsContext
from camera_analytics.core.ports import DetectorPort, TrackerPort
from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.models.camera import Camera
from camera_analytics.plugins.framework.context import PluginContext
from camera_analytics.plugins.framework.manager import PluginManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FrameProcessingSummary:
    """Summary payload resulting from processing a single frame through InferencePipeline."""

    frame_number: int
    timestamp: float
    detected_persons_count: int
    active_tracks_count: int
    events_emitted_count: int
    total_pipeline_latency_ms: float


class InferencePipeline:
    """Production orchestrator encapsulating single-pass AI inference and dynamic plugin execution."""

    def __init__(
        self,
        camera: Camera,
        detector: Optional[DetectorPort] = None,
        tracker: Optional[TrackerPort] = None,
        runtime_kernel: Any = None,
        comm_manager: Optional[CommunicationManager] = None,
        gpu_id: int = 0,
        enabled_modules: Optional[list[str]] = None,
        zone_manager: Any = None,
        zone_engine: Any = None,
        aggregator: Any = None,
    ) -> None:
        self._camera = camera
        self._gpu_id = gpu_id
        self._zone_manager = zone_manager
        self._zone_engine = zone_engine
        self._aggregator = aggregator
        self._detector = detector or self._create_default_detector()
        self._tracker = tracker or self._create_default_tracker()
        self._comm_manager = comm_manager or CommunicationManager.get_instance()
        self._enabled_modules = enabled_modules or ["people_counting", "queue_detection", "loitering_detection"]

        # Centralized ContextBuilder executing shared services ONCE per frame
        self._context_builder = ContextBuilder(
            detector=self._detector,
            tracker=self._tracker,
            zone_manager=self._zone_manager,
            zone_engine=self._zone_engine,
        )

        # Framework PluginManager setup
        pipeline_id = f"pipeline_{camera.camera_id}"
        self._plugin_manager = PluginManager(pipeline_id=pipeline_id)
        self._is_initialized = False

        # Provenance audit logging timer
        self._last_provenance_log_time = 0.0

    def _create_default_detector(self) -> DetectorPort:
        """Instantiate production YOLOPoseAdapter. Fails fast if model or CUDA cannot be initialized."""
        try:
            import torch
            has_cuda = torch.cuda.is_available()
            adapter = YOLOPoseAdapter(confidence_threshold=0.5, iou_threshold=0.45)
            weights = "yolo26m-pose.pt" if (has_cuda and Path("yolo26m-pose.pt").exists()) else "yolov8n-pose.pt"
            device = "cuda" if has_cuda else "cpu"
            adapter.load(weights, device=device)
            return adapter
        except Exception as exc:
            msg = (
                f"\n========================================================\n"
                f"[CRITICAL] Pipeline Aborted: '{self._camera.camera_id}'\n"
                f"Unable to initialize YOLO Pose Detector\n"
                f"Reason: {exc}\n"
                f"========================================================"
            )
            logger.critical(msg)
            raise RuntimeError(f"Pipeline '{self._camera.camera_id}' ABORTED: Unable to initialize YOLO Pose Detector ({exc})") from exc

    def _create_default_tracker(self) -> TrackerPort:
        """Instantiate production BoTSORTAdapter. Fails fast if tracker cannot be initialized."""
        try:
            adapter = BoTSORTAdapter(track_high_thresh=0.5, match_thresh=0.8)
            adapter.initialize()
            return adapter
        except Exception as exc:
            msg = (
                f"\n========================================================\n"
                f"[CRITICAL] Pipeline Aborted: '{self._camera.camera_id}'\n"
                f"Unable to initialize BoT-SORT Tracker\n"
                f"Reason: {exc}\n"
                f"========================================================"
            )
            logger.critical(msg)
            raise RuntimeError(f"Pipeline '{self._camera.camera_id}' ABORTED: Unable to initialize BoT-SORT Tracker ({exc})") from exc

    def initialize(self) -> None:
        """Initialize pipeline, log diagnostic banner, and dynamically load vision plugins."""
        if self._is_initialized:
            return

        # Dynamic Plugin Loading via PluginManager & PluginLoader
        pipeline_id = f"pipeline_{self._camera.camera_id}"
        plugin_context = PluginContext(
            pipeline_id=pipeline_id,
            camera_id=self._camera.camera_id,
            camera_name=self._camera.name,
            rtsp_url=self._camera.source
        )

        for mod_code in self._enabled_modules:
            entry_point = f"camera_analytics.plugins.{mod_code}.plugin"
            self._plugin_manager.load_plugin(
                entry_point=entry_point,
                name=mod_code.replace('_', ' ').title(),
                context=plugin_context
            )

        self._is_initialized = True

        # TAHAP 6: Startup Diagnostics Display
        det_name = getattr(self._detector, "__class__", type(self._detector)).__name__
        trk_name = getattr(self._tracker, "__class__", type(self._tracker)).__name__
        weights = getattr(self._detector, "_model_path", "N/A")
        device_str = getattr(self._detector, "device", "N/A")

        startup_banner = (
            f"\n========================================================\n"
            f"Pipeline : {pipeline_id}\n"
            f"Camera   : {self._camera.camera_id} ({self._camera.name})\n"
            f"Detector : {det_name}\n"
            f"Tracker  : {trk_name}\n"
            f"Weights  : {weights}\n"
            f"Device   : {device_str} (GPU{self._gpu_id})\n"
            f"Plugins  : {', '.join(self._enabled_modules)}\n"
            f"Status   : READY\n"
            f"========================================================"
        )
        logger.info(startup_banner)

    def process_frame(self, frame: IngestedFrame) -> FrameProcessingSummary:
        """Process a single IngestedFrame through the production Shared Context AI pipeline."""
        if not self._is_initialized:
            self.initialize()

        start_time = time.time()
        img_bgr = frame.image

        # 1. Build unified SharedAnalyticsContext via ContextBuilder
        context = self._context_builder.build_context(
            frame=img_bgr,
            frame_index=frame.frame_number,
            camera_id=self._camera.camera_id,
            camera_name=self._camera.name,
            pipeline_id=f"pipeline_{self._camera.camera_id}"
        )
        self.latest_frame_context = context
        self.last_context = context

        if self._aggregator is not None:
            context.plugin_repository = self._aggregator.repository

        # 2. Execute Dynamic Plugin Framework with SharedAnalyticsContext
        plugin_events = self._plugin_manager.process(context)

        # 3. Publish events to CommunicationManager if generated
        events_emitted = len(plugin_events)
        for evt in plugin_events:
            if hasattr(self._comm_manager, "enqueue"):
                self._comm_manager.enqueue(evt)

        pipeline_latency_ms = (time.time() - start_time) * 1000.0

        # TAHAP 7: Detector & Tracker Provenance Audit (Every 5 seconds)
        now = time.time()
        if now - self._last_provenance_log_time >= 5.0:
            self._last_provenance_log_time = now
            prov_msg = (
                f"[PROVENANCE AUDIT]\n"
                f"Camera            : {self._camera.camera_id}\n"
                f"Detector          : {self._detector.__class__.__name__}\n"
                f"Tracker           : {self._tracker.__class__.__name__}\n"
                f"Inference         : SUCCESS\n"
                f"Raw Detections    : {len(context.detections)}\n"
                f"Active Tracks     : {len(context.tracks)}"
            )
            logger.info(prov_msg)

        return FrameProcessingSummary(
            frame_number=frame.frame_number,
            timestamp=frame.timestamp,
            detected_persons_count=len(context.detections),
            active_tracks_count=len(context.tracks),
            events_emitted_count=events_emitted,
            total_pipeline_latency_ms=pipeline_latency_ms,
        )

    def stop(self) -> None:
        """Stop and release AI pipeline resources."""
        if not self._is_initialized:
            return

        self._detector.release()
        self._tracker.reset()
        self._is_initialized = False
        logger.info("InferencePipeline[%s]: Stopped and released AI pipeline resources.", self._camera.camera_id)
