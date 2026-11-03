"""
Tests for live RTSP frame backlog removal (Slice A).

Verifies:
1. FrameQueue policy:
   - drop_oldest keeps the newest N items and never blocks producer.
   - drop_newest keeps oldest items and drops newest on timeout.
2. ReaderWorker policy resolution:
   - RTSP sources resolve to drop_oldest by default under 'auto'.
   - File and webcam sources resolve to drop_newest by default under 'auto'.
   - Explicit config overrides are respected.
3. Slow consumer frame age bound on live RTSP:
   - With drop_oldest, consumer receives recent frames even when slow.
4. Config schema & loader:
   - IngestionConfig parses and validates overflow_policy ('auto', 'drop_oldest', 'drop_newest').
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
import pytest

import camera_analytics.models
from camera_analytics.config.loader import ConfigLoader, ConfigValidationError
from camera_analytics.config.schema import IngestionConfig
from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.ingestion.queue import FrameQueue
from camera_analytics.ingestion.reader import VideoReader
from camera_analytics.ingestion.sources.base import StreamPacket, VideoSource
from camera_analytics.ingestion.sources.file_source import VideoFileSource
from camera_analytics.ingestion.sources.webcam_source import WebcamSource
from camera_analytics.ingestion.worker import ReaderWorker


def _make_frame(frame_num: int, timestamp: Optional[float] = None) -> IngestedFrame:
    return IngestedFrame(
        pipeline_id="pipe_test",
        camera_id="cam_test",
        frame_number=frame_num,
        timestamp=timestamp if timestamp is not None else time.time(),
        read_latency_ms=1.0,
        image=np.zeros((32, 32, 3), dtype=np.uint8),
        width=32,
        height=32,
        channels=3,
    )


class FakeRTSPSource(VideoSource):
    """Fake RTSP video source for unit tests without network/GPU."""

    def __init__(self, uri: str = "rtsp://127.0.0.1:8554/live") -> None:
        super().__init__(uri=uri)
        self._count = 0

    def open(self) -> bool:
        self._is_open = True
        return True

    def read_packet(self) -> Optional[StreamPacket]:
        if not self._is_open:
            return None
        self._count += 1
        dummy_img = np.zeros((32, 32, 3), dtype=np.uint8)
        return StreamPacket(payload=dummy_img, timestamp=time.time(), packet_index=self._count)

    def close(self) -> None:
        self._is_open = False


class FakeFileSource(VideoSource):
    """Fake file video source for unit tests."""

    def __init__(self, uri: str = "sample_video.mp4") -> None:
        super().__init__(uri=uri)
        self._count = 0

    def open(self) -> bool:
        self._is_open = True
        return True

    def read_packet(self) -> Optional[StreamPacket]:
        if not self._is_open:
            return None
        self._count += 1
        dummy_img = np.zeros((32, 32, 3), dtype=np.uint8)
        return StreamPacket(payload=dummy_img, timestamp=time.time(), packet_index=self._count)

    def close(self) -> None:
        self._is_open = False


# ---------------------------------------------------------------------------
# 1. FrameQueue Policy Tests
# ---------------------------------------------------------------------------

def test_frame_queue_drop_oldest_keeps_newest_and_never_blocks():
    """drop_oldest must never block when full, discard oldest item, keep newest N, count drops."""
    capacity = 3
    q = FrameQueue(capacity=capacity, overflow="drop_oldest")
    assert q.capacity == capacity
    assert q.overflow == "drop_oldest"
    assert q.drop_count == 0

    # Put 5 items into capacity-3 queue
    for i in range(1, 6):
        res = q.put(_make_frame(i), timeout=0.0)
        assert res is True

    # 2 oldest items (1 and 2) must have been discarded
    assert q.drop_count == 2
    assert q.size() == 3

    # Dequeued items must be the 3 newest (3, 4, 5)
    out1 = q.get(timeout=0.01)
    out2 = q.get(timeout=0.01)
    out3 = q.get(timeout=0.01)
    assert out1 is not None and out1.frame_number == 3
    assert out2 is not None and out2.frame_number == 4
    assert out3 is not None and out3.frame_number == 5
    assert q.get(timeout=0.01) is None


def test_frame_queue_drop_newest_behaves_as_before():
    """drop_newest must block until timeout when full, drop incoming item, keep oldest N."""
    capacity = 3
    q = FrameQueue(capacity=capacity, overflow="drop_newest")
    assert q.capacity == capacity
    assert q.overflow == "drop_newest"
    assert q.drop_count == 0

    for i in range(1, 4):
        assert q.put(_make_frame(i), timeout=0.01) is True

    # 4th item cannot be enqueued; timeout drops it
    res = q.put(_make_frame(4), timeout=0.02)
    assert res is False
    assert q.drop_count == 1
    assert q.size() == 3

    # Dequeued items must be the original 3 oldest (1, 2, 3)
    out1 = q.get(timeout=0.01)
    out2 = q.get(timeout=0.01)
    out3 = q.get(timeout=0.01)
    assert out1 is not None and out1.frame_number == 1
    assert out2 is not None and out2.frame_number == 2
    assert out3 is not None and out3.frame_number == 3


def test_frame_queue_invalid_policy_raises():
    with pytest.raises(ValueError, match="Invalid overflow policy"):
        FrameQueue(capacity=5, overflow="invalid_policy")


# ---------------------------------------------------------------------------
# 2. ReaderWorker Policy Resolution
# ---------------------------------------------------------------------------

def test_reader_worker_auto_policy_resolution():
    """RTSP sources resolve to drop_oldest, file/webcam sources resolve to drop_newest under auto."""
    # Fake RTSP source
    rtsp_src = FakeRTSPSource()
    r_rtsp = VideoReader(source=rtsp_src)
    worker_rtsp = ReaderWorker(pipeline_id="pipe_1", camera_id="cam_1", reader=r_rtsp)
    assert worker_rtsp.overflow_policy == "drop_oldest"
    assert worker_rtsp.queue.overflow == "drop_oldest"

    # Fake File source
    file_src = FakeFileSource()
    r_file = VideoReader(source=file_src)
    worker_file = ReaderWorker(pipeline_id="pipe_2", camera_id="cam_2", reader=r_file)
    assert worker_file.overflow_policy == "drop_newest"
    assert worker_file.queue.overflow == "drop_newest"

    # Webcam source
    webcam_src = WebcamSource(uri="0")
    r_webcam = VideoReader(source=webcam_src)
    worker_webcam = ReaderWorker(pipeline_id="pipe_3", camera_id="cam_3", reader=r_webcam)
    assert worker_webcam.overflow_policy == "drop_newest"
    assert worker_webcam.queue.overflow == "drop_newest"

    # Real VideoFileSource class
    fs = VideoFileSource(uri="fake.mp4")
    r_fs = VideoReader(source=fs)
    worker_fs = ReaderWorker(pipeline_id="pipe_4", camera_id="cam_4", reader=r_fs)
    assert worker_fs.overflow_policy == "drop_newest"
    assert worker_fs.queue.overflow == "drop_newest"


def test_reader_worker_explicit_policy_override():
    """Explicit overflow_policy overrides auto-detection."""
    # RTSP source forced to drop_newest
    rtsp_src = FakeRTSPSource()
    r_rtsp = VideoReader(source=rtsp_src)
    worker1 = ReaderWorker(pipeline_id="p1", camera_id="c1", reader=r_rtsp, overflow_policy="drop_newest")
    assert worker1.overflow_policy == "drop_newest"

    # File source forced to drop_oldest
    file_src = FakeFileSource()
    r_file = VideoReader(source=file_src)
    worker2 = ReaderWorker(pipeline_id="p2", camera_id="c2", reader=r_file, overflow_policy="drop_oldest")
    assert worker2.overflow_policy == "drop_oldest"


# ---------------------------------------------------------------------------
# 3. Slow Consumer Frame Age Bound on RTSP
# ---------------------------------------------------------------------------

def test_rtsp_slow_consumer_frame_age_bounded():
    """With drop_oldest on RTSP, a slow consumer sees fresh frames rather than stale head."""
    source = FakeRTSPSource()
    reader = VideoReader(source=source)
    queue_cap = 5
    worker = ReaderWorker(
        pipeline_id="pipe_rtsp_test",
        camera_id="cam_rtsp_test",
        reader=reader,
        queue_capacity=queue_cap,
    )
    assert worker.overflow_policy == "drop_oldest"

    worker.start()
    try:
        # Producer runs fast for a short time (e.g. 100ms generates many frames)
        time.sleep(0.15)

        # Slow consumer wakes up and reads one frame
        consumed = worker.queue.get(timeout=1.0)
        assert consumed is not None

        # Frame age must be tightly bounded (e.g. < 0.25s) even though producer produced many frames
        age_sec = time.time() - consumed.timestamp
        assert age_sec < 0.5, f"Frame age too high: {age_sec:.3f}s"

        # Frame number must NOT be frame #1 (early frames were dropped to keep queue fresh)
        assert consumed.frame_number > 1
        assert worker.queue.drop_count > 0
        assert worker.metrics.frame_drop_count == worker.queue.drop_count
    finally:
        worker.stop()


def test_file_source_keeps_old_policy_and_drops_newest():
    """File source keeps drop_newest policy under default auto configuration."""
    source = FakeFileSource()
    reader = VideoReader(source=source)
    queue_cap = 3
    worker = ReaderWorker(
        pipeline_id="pipe_file_test",
        camera_id="cam_file_test",
        reader=reader,
        queue_capacity=queue_cap,
    )
    assert worker.overflow_policy == "drop_newest"

    worker.start()
    try:
        time.sleep(0.1)
        # Slow consumer reads oldest frame first
        consumed = worker.queue.get(timeout=1.0)
        assert consumed is not None
        # With drop_newest, the first frame consumed is frame #1
        assert consumed.frame_number == 1
    finally:
        worker.stop()


# ---------------------------------------------------------------------------
# 4. Config Schema & Loader Tests
# ---------------------------------------------------------------------------

def test_config_loader_ingestion_overflow_policy():
    """ConfigLoader parses ingestion.overflow_policy correctly."""
    # Default is auto
    cfg_default = ConfigLoader.from_dict({
        "camera": {"camera_id": "c1", "name": "Cam 1"},
        "source": {"source_type": "rtsp", "uri": "rtsp://10.0.0.1/live"},
        "detector": {},
        "tracker": {},
        "runner": {},
        "analytics": {},
    })
    assert cfg_default.ingestion.overflow_policy == "auto"
    assert cfg_default.ingestion.queue_capacity == 30

    # Explicit drop_oldest
    cfg_drop_oldest = ConfigLoader.from_dict({
        "camera": {"camera_id": "c1", "name": "Cam 1"},
        "source": {"source_type": "rtsp", "uri": "rtsp://10.0.0.1/live"},
        "detector": {},
        "tracker": {},
        "runner": {},
        "analytics": {},
        "ingestion": {"overflow_policy": "drop_oldest", "queue_capacity": 15},
    })
    assert cfg_drop_oldest.ingestion.overflow_policy == "drop_oldest"
    assert cfg_drop_oldest.ingestion.queue_capacity == 15

    # Invalid overflow policy raises ConfigValidationError
    with pytest.raises(ConfigValidationError, match="Invalid 'ingestion.overflow_policy'"):
        ConfigLoader.from_dict({
            "camera": {"camera_id": "c1", "name": "Cam 1"},
            "source": {"source_type": "rtsp", "uri": "rtsp://10.0.0.1/live"},
            "detector": {},
            "tracker": {},
            "runner": {},
            "analytics": {},
            "ingestion": {"overflow_policy": "bogus_policy"},
        })
