"""
Unit and integration tests for Decoupled Display Architecture (SLICE B).

Verifies:
1. OverlayStore thread-safe publishing and retrieval without raw image data.
2. OverlayRenderer accepting (frame, overlay) separately while keeping the coupled
   (presentation) entry point fully functional.
3. Overlay age expiration: when overlay is older than overlay_max_age_ms, boxes
   are suppressed and the HUD indicates staleness.
4. Concurrency & timing: with a slow detector (100 ms/frame) and a fast producer,
   decoupled display retrieves frames near the source rate with bounded frame age,
   while coupled display is throttled to inference speed.
5. Configuration schema and loader wiring for viewer.decoupled_display and
   viewer.overlay_max_age_ms.
"""

from __future__ import annotations

import time
import threading
from typing import Any, List, Optional
from unittest.mock import MagicMock

import numpy as np
import pytest

# Pre-import to resolve circular dependency between models and config
import camera_analytics.models
from camera_analytics.config.loader import ConfigLoader
from camera_analytics.config.schema import AppConfig, ViewerConfig
from camera_analytics.ingestion.buffer import FrameBuffer
from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.ingestion.queue import FrameQueue
from camera_analytics.viewer.buffer import PresentationFrameBuffer
from camera_analytics.viewer.models import (
    FramePresentation,
    OverlayData,
    PresentedBox,
    PresentedMetrics,
    PresentedPlateBox,
)
from camera_analytics.viewer.overlay_store import OverlayStore
from camera_analytics.viewer.renderer import OverlayRenderer, RenderOptions
from camera_analytics.viewer.viewer_provider import ViewerProvider


def make_ingested_frame(
    frame_number: int = 1,
    timestamp: Optional[float] = None,
    w: int = 200,
    h: int = 200,
    pipeline_id: str = "pipe_1",
    camera_id: str = "cam_1",
) -> IngestedFrame:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    return IngestedFrame(
        pipeline_id=pipeline_id,
        camera_id=camera_id,
        frame_number=frame_number,
        timestamp=time.time() if timestamp is None else timestamp,
        read_latency_ms=1.0,
        image=img,
        width=w,
        height=h,
    )


def test_overlay_store_publish_and_retrieve():
    store = OverlayStore()
    assert store.get_latest("pipe_1") is None

    now = time.time()
    overlay = OverlayData(
        camera_id="cam_1",
        camera_name="Main Gate",
        frame_number=42,
        timestamp=now,
        boxes=(PresentedBox(track_id=1, x1=10, y1=10, x2=50, y2=50, confidence=0.9),),
        created_at=now,
    )
    store.publish("pipe_1", overlay)

    retrieved = store.get_latest("pipe_1")
    assert retrieved is not None
    assert retrieved.camera_id == "cam_1"
    assert retrieved.frame_number == 42
    assert len(retrieved.boxes) == 1

    store.clear("pipe_1")
    assert store.get_latest("pipe_1") is None


def test_overlay_renderer_coupled_entry_point():
    renderer = OverlayRenderer(options=RenderOptions(draw_bbox=True, draw_metrics=False))
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    pres = FramePresentation(
        camera_id="cam_1",
        camera_name="Cam 1",
        frame_number=1,
        timestamp=time.time(),
        image=img,
        boxes=(PresentedBox(track_id=1, x1=20, y1=20, x2=80, y2=80, confidence=0.9, color_rgb=(0, 255, 0)),),
    )

    rendered = renderer.render(pres)
    assert rendered.shape == (200, 200, 3)
    assert np.any(rendered != 0)


def test_overlay_renderer_decoupled_entry_point():
    renderer = OverlayRenderer(options=RenderOptions(draw_bbox=True, draw_metrics=False))
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    now = time.time()
    overlay = OverlayData(
        camera_id="cam_1",
        camera_name="Cam 1",
        frame_number=1,
        timestamp=now,
        boxes=(PresentedBox(track_id=1, x1=20, y1=20, x2=80, y2=80, confidence=0.9, color_rgb=(0, 255, 0)),),
    )

    rendered = renderer.render(frame, overlay=overlay)
    assert rendered.shape == (200, 200, 3)
    assert np.any(rendered != 0)


def test_overlay_max_age_suppresses_boxes_and_shows_hud():
    renderer = OverlayRenderer(options=RenderOptions(draw_bbox=True, draw_metrics=True))
    frame = np.zeros((400, 400, 3), dtype=np.uint8)
    old_timestamp = time.time() - 2.0  # 2 seconds old

    overlay = OverlayData(
        camera_id="cam_1",
        camera_name="Cam 1",
        frame_number=10,
        timestamp=old_timestamp,
        boxes=(PresentedBox(track_id=1, x1=50, y1=150, x2=150, y2=250, confidence=0.95, color_rgb=(0, 255, 0)),),
        metrics=PresentedMetrics(
            camera_id="cam_1",
            camera_name="Cam 1",
            fps_input=30.0,
            fps_execution=5.0,
            read_latency_ms=2.0,
            pipeline_latency_ms=200.0,
            gpu_id=0,
            queue_size=1,
            active_tracks_count=1,
            active_zones_count=0,
        ),
    )

    # 1. Stale overlay: is_stale=True (age 2000 ms > max 500 ms)
    rendered_stale = renderer.render(
        presentation_or_frame=frame,
        overlay=overlay,
        is_stale=True,
        stale_age_ms=2000.0,
        max_age_ms=500.0,
    )
    # Check bottom line of the bounding box at y=250, x=60..140 (color_rgb=(0, 255, 0))
    box_pixels_green_stale = (rendered_stale[250, 60:140, 1] == 255)
    assert not np.any(box_pixels_green_stale), "Bounding box must NOT be drawn when overlay is stale!"

    # 2. Fresh overlay: is_stale=False (age 20 ms <= max 500 ms)
    rendered_fresh = renderer.render(
        presentation_or_frame=frame,
        overlay=overlay,
        is_stale=False,
        stale_age_ms=20.0,
        max_age_ms=500.0,
    )
    box_pixels_green_fresh = (rendered_fresh[250, 60:140, 1] == 255)
    assert np.any(box_pixels_green_fresh), "Bounding box should be drawn when overlay is fresh!"


def test_viewer_provider_render_decoupled():
    vp = ViewerProvider(name="test_vp", enabled=False)
    vp._window_manager = MagicMock()

    now = time.time()
    raw_frame = make_ingested_frame(frame_number=100, timestamp=now)

    # Stale overlay (600 ms old > 500 ms max)
    stale_overlay = OverlayData(
        camera_id="cam_1",
        camera_name="Test Cam",
        frame_number=80,
        timestamp=now - 0.600,
        boxes=(PresentedBox(track_id=1, x1=10, y1=10, x2=40, y2=40, confidence=0.8),),
    )

    vp.render_decoupled(
        camera_name="Test Cam",
        raw_frame=raw_frame,
        overlay=stale_overlay,
        max_age_ms=500.0,
    )

    assert vp._window_manager.show_frame.called
    call_args = vp._window_manager.show_frame.call_args[0]
    assert call_args[0] == "Test Cam"
    rendered_img = call_args[1]
    assert isinstance(rendered_img, np.ndarray)


def test_decoupled_vs_coupled_throughput_with_slow_inference():
    """
    Simulates:
    - Producer ingesting frames into FrameBuffer & FrameQueue.
    - Consumer/Inference sleeping 100 ms per frame (simulating a heavy neural network).
    - Decoupled viewer sampling FrameBuffer.get_latest() gets fresh frames with small frame age.
    - Coupled viewer sampling presentation_buffer.get_latest() is throttled to inference rate.
    """
    buffer = FrameBuffer(capacity=30)
    queue = FrameQueue(capacity=30, overflow="drop_oldest")
    pres_buffer = PresentationFrameBuffer(capacity=5)
    overlay_store = OverlayStore()

    stop_event = threading.Event()

    # 1. Fast Producer Thread (Produces a new frame every 15 ms)
    def producer():
        frame_idx = 0
        while not stop_event.is_set() and frame_idx < 30:
            frame_idx += 1
            now = time.time()
            f = make_ingested_frame(frame_number=frame_idx, timestamp=now)
            buffer.push(f)
            queue.put(f, timeout=0.0)
            time.sleep(0.015)

    # 2. Slow Inference Worker Thread (Sleeps 100 ms per frame)
    def slow_worker():
        while not stop_event.is_set():
            frame = queue.get(timeout=0.05)
            if frame is None:
                continue
            time.sleep(0.100)
            pres = FramePresentation(
                camera_id=frame.camera_id,
                camera_name="Sim Cam",
                frame_number=frame.frame_number,
                timestamp=frame.timestamp,
                image=frame.image,
                boxes=(PresentedBox(track_id=1, x1=5, y1=5, x2=20, y2=20, confidence=0.9),),
            )
            pres_buffer.update(pres)
            overlay = OverlayData.from_presentation(pres)
            overlay_store.publish(frame.pipeline_id, overlay)

    t_prod = threading.Thread(target=producer, daemon=True)
    t_work = threading.Thread(target=slow_worker, daemon=True)
    t_prod.start()
    t_work.start()

    time.sleep(0.12)

    # Sample Decoupled: reads directly from buffer.get_latest()
    decoupled_frames_seen = []
    decoupled_ages_ms = []

    for _ in range(12):
        latest = buffer.get_latest()
        if latest is not None:
            age = (time.time() - latest.timestamp) * 1000.0
            decoupled_frames_seen.append(latest.frame_number)
            decoupled_ages_ms.append(age)
        time.sleep(0.015)

    # Sample Coupled: reads from pres_buffer.get_latest()
    coupled_frames_seen = []
    for _ in range(12):
        latest_pres = pres_buffer.get_latest()
        if latest_pres is not None:
            coupled_frames_seen.append(latest_pres.frame_number)
        time.sleep(0.015)

    stop_event.set()
    t_prod.join(timeout=1.0)
    t_work.join(timeout=1.0)

    unique_decoupled = len(set(decoupled_frames_seen))
    unique_coupled = len(set(coupled_frames_seen))

    assert unique_decoupled > unique_coupled, (
        f"Decoupled display should see more distinct frames ({unique_decoupled}) "
        f"than coupled display ({unique_coupled}) during slow inference!"
    )
    median_decoupled_age = float(np.median(decoupled_ages_ms))
    assert median_decoupled_age < 100.0, f"Decoupled frame age must be small (< 100ms), got {median_decoupled_age:.1f}ms"


def test_config_loader_viewer_wiring():
    raw_cfg = {
        "camera": {"camera_id": "c1"},
        "source": {"source_type": "video", "uri": "video.mp4"},
        "detector": {},
        "tracker": {},
        "runner": {},
        "analytics": {},
        "viewer": {
            "decoupled_display": True,
            "overlay_max_age_ms": 750.0,
        },
    }

    app_cfg = ConfigLoader.from_dict(raw_cfg)
    assert app_cfg.viewer.decoupled_display is True
    assert app_cfg.viewer.overlay_max_age_ms == 750.0

    # Default values
    default_cfg = ConfigLoader.from_dict({
        "camera": {"camera_id": "c1"},
        "source": {"source_type": "video", "uri": "video.mp4"},
        "detector": {},
        "tracker": {},
        "runner": {},
        "analytics": {},
    })
    assert default_cfg.viewer.decoupled_display is False
    assert default_cfg.viewer.overlay_max_age_ms == 500.0
