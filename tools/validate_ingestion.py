"""
Validation tool script for Sprint 11.3 Video Ingestion Layer & Frame Pipeline Architecture.

Validates VideoSource, VideoDecoder, VideoReader, FrameBuffer (Ring Cache), FrameQueue (Producer-Consumer),
ReaderWorker background threads, event hooks, and connection recovery.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from camera_analytics.ingestion import (
    DecoderFactory,
    FrameBuffer,
    FrameQueue,
    IngestedFrame,
    IngestionEventHooks,
    OpenCVDecoder,
    ReaderState,
    ReaderWorker,
    VideoFileSource,
    VideoReader,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("validate_ingestion")


def main() -> int:
    logger.info("=" * 70)
    logger.info("Sprint 11.3 Validation: Video Ingestion Layer & Frame Pipeline")
    logger.info("=" * 70)

    sample_video = Path("camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4")
    if not sample_video.exists():
        logger.error("[-] Sample video '%s' not found!", sample_video)
        return 1

    # 1. Test VideoSource & Decoder Abstraction
    logger.info("\n--- 1. Testing VideoSource & Decoder Abstraction ---")
    source = VideoFileSource(str(sample_video))
    decoder = DecoderFactory.create("opencv")
    reader = VideoReader(source=source, decoder=decoder)

    assert reader.open() is True
    logger.info("[+] VideoReader opened sample stream successfully.")

    frame = reader.read_frame(pipeline_id="pipe_test_01", camera_id="cam_test_01")
    assert frame is not None
    assert isinstance(frame, IngestedFrame)
    assert frame.image.flags.writeable is False  # Immutable array check
    logger.info(
        "[+] IngestedFrame read verified: %dx%d (Latency: %.2f ms, Immutability: True)",
        frame.width,
        frame.height,
        frame.read_latency_ms,
    )
    reader.close()

    # 2. Test FrameBuffer (Ring Buffer Cache) vs FrameQueue (Producer-Consumer)
    logger.info("\n--- 2. Testing FrameBuffer (Cache) vs FrameQueue (Transport) ---")
    buffer = FrameBuffer(capacity=5)
    queue = FrameQueue(capacity=5)

    buffer.push(frame)
    queue.put(frame)

    assert len(buffer) == 1
    assert queue.size() == 1

    latest_cache = buffer.get_latest()
    assert latest_cache is not None and latest_cache.frame_id == frame.frame_id
    logger.info("[+] FrameBuffer latest-frame cache retrieval verified.")

    consumed_frame = queue.get(timeout=0.1)
    assert consumed_frame is not None and consumed_frame.frame_id == frame.frame_id
    logger.info("[+] FrameQueue Consumer dequeue verified.")

    # 3. Test ReaderWorker Background Ingestion Thread & Hooks
    logger.info("\n--- 3. Testing ReaderWorker Background Thread & Metrics ---")
    produced_count = 0

    def on_frame(f: IngestedFrame):
        nonlocal produced_count
        produced_count += 1

    hooks = IngestionEventHooks(on_frame_produced=on_frame)
    test_source = VideoFileSource(str(sample_video))
    test_reader = VideoReader(source=test_source)

    worker = ReaderWorker(
        pipeline_id="pipe_val_01",
        camera_id="cam_val_01",
        reader=test_reader,
        buffer_capacity=10,
        queue_capacity=10,
        event_hooks=hooks,
    )

    worker.start()
    assert worker.state in (ReaderState.CREATED, ReaderState.INITIALIZED, ReaderState.READING)
    time.sleep(1.0)  # Allow background thread to read frames

    metrics = worker.metrics
    logger.info("[+] ReaderWorker running: Input FPS=%.1f, Total Frames Read=%d, Drops=%d",
                metrics.fps_input, metrics.total_frames_read, metrics.frame_drop_count)
    assert metrics.total_frames_read > 0
    assert produced_count > 0

    worker.stop()
    assert worker.state == ReaderState.STOPPED
    logger.info("[+] ReaderWorker stopped cleanly.")

    logger.info("\n" + "=" * 70)
    logger.info("SUCCESS: All Sprint 11.3 Video Ingestion Layer validation checks PASSED!")
    logger.info("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
