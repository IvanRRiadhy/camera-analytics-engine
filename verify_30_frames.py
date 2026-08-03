"""
30-Frame Runtime Execution & Presentation Audit Script.
"""

from __future__ import annotations

import logging
import sys
import time
import threading

# Configure root logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
logger = logging.getLogger("verification")

# Import system dependencies
import camera_analytics.adapters.bridge.inference_pipeline  # Pre-import to break circular import cycle
from camera_analytics.bootstrap.engine_bootstrap import EngineBootstrap
from camera_analytics.bootstrap.providers.backend_provider import BackendConfigurationProvider
from camera_analytics.orchestration.pipeline_coordinator import PipelineCoordinator
from camera_analytics.telemetry.snapshot_publisher import RuntimeSnapshotPublisher
from camera_analytics.adapters.bridge.pipeline_worker import PipelineExecutionWorker
from camera_analytics.ingestion.worker import ReaderWorker
from camera_analytics.ingestion.reader import VideoReader
from camera_analytics.ingestion.sources.factory import create_video_source
from camera_analytics.adapters.bridge.inference_pipeline import InferencePipeline
from camera_analytics.viewer.builder import FramePresentationBuilder
from camera_analytics.viewer.models import FramePresentation

# Global verification state counters
verification_stats = {
    "frames_processed": 0,
    "detections_count": 0,
    "tracks_count": 0,
    "boxes_rendered": 0,
    "skeletons_rendered": 0,
    "snapshots_published": 0,
    "builder_executed": False,
    "buffer_updated": False,
}

_lock = threading.Lock()

# Monkey-patch FramePresentationBuilder.build to record verification metrics cleanly
_orig_build = FramePresentationBuilder.build

def _verification_build(*args, **kwargs) -> FramePresentation:
    pres = _orig_build.__func__(FramePresentationBuilder, *args, **kwargs) if hasattr(_orig_build, "__func__") else _orig_build(*args, **kwargs)
    with _lock:
        verification_stats["builder_executed"] = True
        if pres.boxes:
            verification_stats["boxes_rendered"] += len(pres.boxes)
        if pres.skeletons:
            verification_stats["skeletons_rendered"] += len(pres.skeletons)
    return pres

FramePresentationBuilder.build = _verification_build

# Monkey-patch RuntimeSnapshotPublisher.publish_snapshots to record snapshot metrics
_orig_pub = RuntimeSnapshotPublisher.publish_snapshots

def _verification_publish(self, *args, **kwargs):
    count = _orig_pub(self, *args, **kwargs)
    with _lock:
        if count > 0:
            verification_stats["snapshots_published"] += count
    return count

RuntimeSnapshotPublisher.publish_snapshots = _verification_publish


def run_verification():
    logger.info("================================================================================")
    logger.info("Starting 30-Frame Runtime Execution & Visual Verification")
    logger.info("================================================================================")

    # 1. Bootstrap Engine
    provider = BackendConfigurationProvider("http://localhost:5100")
    bootstrap = EngineBootstrap(provider=provider)
    res = bootstrap.bootstrap()
    context = res.context
    coordinator: PipelineCoordinator = context.services.get_required("pipeline_coordinator", PipelineCoordinator)
    comm_mgr = context.services.get("communication_manager")

    # 2. Instantiate Workers
    snapshot_publisher = None
    reader_workers: list[ReaderWorker] = []
    execution_workers: list[PipelineExecutionWorker] = []

    for pipe_inst in coordinator.pipeline_manager.list_pipelines():
        camera = pipe_inst.camera
        video_source = create_video_source(camera.source)
        video_reader = VideoReader(source=video_source)

        r_worker = ReaderWorker(
            pipeline_id=pipe_inst.pipeline_id,
            camera_id=pipe_inst.camera_id,
            reader=video_reader,
            queue_capacity=30,
        )

        inf_pipeline = InferencePipeline(
            camera=camera,
            gpu_id=pipe_inst.gpu_id,
        )

        e_worker = PipelineExecutionWorker(
            pipeline_id=pipe_inst.pipeline_id,
            camera_id=camera.camera_id,
            frame_queue=r_worker.queue,
            inference_pipeline=inf_pipeline,
            camera=camera,
        )
        reader_workers.append(r_worker)
        execution_workers.append(e_worker)

    snapshot_publisher = RuntimeSnapshotPublisher(
        coordinator=coordinator,
        execution_workers=execution_workers,
        comm_manager=comm_mgr,
        publish_interval_ms=1000,
        deduplicate_streams=True,
        engine_id=context.engine_id,
    )

    # 3. Start Workers
    for rw in reader_workers:
        rw.start()
    for ew in execution_workers:
        ew.start()
    if snapshot_publisher:
        snapshot_publisher.start()

    logger.info("[+] All workers started. Waiting for 30 frames to process...")

    start_t = time.time()
    max_wait_s = 35.0

    while time.time() - start_t < max_wait_s:
        time.sleep(0.2)

        # Check total frames processed across workers
        total_frames = sum(ew.total_processed_frames for ew in execution_workers)
        
        # Check last summary metrics
        total_dets = 0
        total_trks = 0
        for ew in execution_workers:
            if ew.last_summary:
                total_dets += ew.last_summary.detected_persons_count
                total_trks += ew.last_summary.active_tracks_count

        with _lock:
            verification_stats["frames_processed"] = total_frames
            verification_stats["detections_count"] = total_dets
            verification_stats["tracks_count"] = total_trks
            if any(ew.presentation_buffer.get_latest() is not None for ew in execution_workers):
                verification_stats["buffer_updated"] = True

        if total_frames >= 30:
            logger.info("[✓] Target frame count reached: %d frames processed!", total_frames)
            break

    # 4. Stop Workers
    if snapshot_publisher:
        snapshot_publisher.stop()
    for ew in execution_workers:
        ew.stop()
    for rw in reader_workers:
        rw.stop()

    print("\n================================================================================")
    print("VERIFICATION METRICS RESULTS")
    print("================================================================================")
    print(f"Frame count processed:       {verification_stats['frames_processed']}")
    print(f"Detection count:             {verification_stats['detections_count']}")
    print(f"Track count:                 {verification_stats['tracks_count']}")
    print(f"Boxes rendered:              {verification_stats['boxes_rendered']}")
    print(f"Skeletons rendered:          {verification_stats['skeletons_rendered']}")
    print(f"Snapshots published:         {verification_stats['snapshots_published']}")
    print(f"FramePresentationBuilder:    {'EXECUTED' if verification_stats['builder_executed'] else 'FAILED'}")
    print(f"PresentationBuffer update:   {'EXECUTED' if verification_stats['buffer_updated'] else 'FAILED'}")
    print("================================================================广\n")

if __name__ == "__main__":
    run_verification()
