import os
from pathlib import Path
import cv2
import json
import time
import numpy as np
import pytest
import torch

from camera_analytics.plugins.framework.context import PluginContext
from camera_analytics.plugins.framework.states import PluginState
from camera_analytics.context.unified_context import SharedAnalyticsContext
from camera_analytics.communication.models import AnalyticsEventSerializer
from camera_analytics.plugins.vehicle_lpr.plugin import VehicleLPRPlugin

TEST_VIDEO_PATH = os.environ.get("ANPR_TEST_VIDEO", r"E:\ANPR\datasets\VideoProject2.mp4")
DETECTOR_WEIGHTS = os.environ.get("ANPR_DETECTOR_WEIGHTS", r"E:\ANPR\runs\detect\indonesian_plate_yolo26_v1\weights\best.pt")
READER_WEIGHTS = os.environ.get("ANPR_READER_WEIGHTS", r"E:\ANPR\runs\detect\lprd_yolo26n_320\weights\last.pt")

cuda_available = torch.cuda.is_available()
video_exists = Path(TEST_VIDEO_PATH).is_file()
weights_exist = Path(DETECTOR_WEIGHTS).is_file() and Path(READER_WEIGHTS).is_file()

skip_reason = None
if not video_exists:
    skip_reason = f"Integration test video missing at {TEST_VIDEO_PATH}"
elif not cuda_available:
    skip_reason = "CUDA is not available"
elif not weights_exist:
    skip_reason = f"Model weights missing: detector={DETECTOR_WEIGHTS}, reader={READER_WEIGHTS}"


@pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "Prerequisites not met")
def test_vehicle_lpr_cctv_integration():
    """Integration test running detector mode on real CCTV video footage (VideoProject2.mp4)."""
    video_path = TEST_VIDEO_PATH
    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened(), f"Could not open test video: {video_path}"

    plugin = VehicleLPRPlugin(name="Vehicle LPR")
    ctx = PluginContext(pipeline_id="pipeline_integration_test", camera_id="cam_parking_02")
    ctx.config = {
        "mode": "detector",
        "detector_weights": DETECTOR_WEIGHTS,
        "detector_conf": 0.25,
        "detector_iou": 0.45,
        "detector_imgsz": 640,
        "reader_weights": READER_WEIGHTS,
        "reader_conf": 0.02,
        "reader_imgsz": 320,
        "device": 0,
        "frame_stride": 3,
        "min_observations": 2,
        "min_winner_share": 0.50,
        "min_plate_width_px": 50.0,
        "min_sharpness": 10.0,
        "lock_timeout_s": 0.2,
    }

    assert plugin.initialize(ctx), "Plugin initialization failed"
    plugin.warmup()
    plugin.start()

    frame_idx = 0
    emitted_events = []
    latencies_all = []
    latencies_strided = []

    # Stream frames through the plugin
    while True:
        ret, frame = cap.read()
        if not ret or frame_idx > 80:
            break

        f_ctx = SharedAnalyticsContext(
            frame=frame,
            frame_index=frame_idx,
            camera_id="cam_parking_02",
            pipeline_id="pipeline_integration_test",
            timestamp_utc=time.time(),
        )

        t0 = time.perf_counter()
        evts = plugin.process(f_ctx)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        latencies_all.append(dur_ms)
        if frame_idx % 3 == 0:
            latencies_strided.append(dur_ms)

        if evts:
            emitted_events.extend(evts)
            for e in evts:
                ser = AnalyticsEventSerializer.serialize(e)
                print(f"\n[TEST EMITTED EVENT FRAME {frame_idx}]: {ser}")

        frame_idx += 1

    cap.release()
    stats = plugin.get_stats()
    plugin.shutdown()

    # Latency diagnostics
    avg_lat = float(np.mean(latencies_all))
    p95_lat = float(np.percentile(latencies_all, 95))
    avg_stride_lat = float(np.mean(latencies_strided)) if latencies_strided else 0.0
    p95_stride_lat = float(np.percentile(latencies_strided, 95)) if latencies_strided else 0.0

    print("\n================ INTEGRATION TEST PERFORMANCE METRICS ================")
    print(f"Frames Processed      : {frame_idx}")
    print(f"Plates Detected Total : {stats['detections_total']}")
    print(f"Plates Read OK (OCR)  : {stats['reader_ok']}")
    print(f"Events Emitted        : {len(emitted_events)}")
    if stats["detected_widths"]:
        w = stats["detected_widths"]
        print(f"Plate Width Distribution: min={min(w):.1f}px, median={np.median(w):.1f}px, max={max(w):.1f}px")
    print(f"Skip Reasons Breakdown : TooSmall={stats['skipped_too_small']}, TooBlurry={stats['skipped_too_blurry']}, TooDark={stats['skipped_too_dark']}, NoRead={stats['reader_no_read']}, Consensus={stats['skipped_after_consensus']}, Cooldown={stats['skipped_cooldown']}, LockTimeout={stats['skipped_lock_timeout']}")
    print(f"Latency All Calls     : avg={avg_lat:.2f}ms, p95={p95_lat:.2f}ms")
    print(f"Latency Strided Calls : avg={avg_stride_lat:.2f}ms, p95={p95_stride_lat:.2f}ms")
    print("======================================================================")

    assert len(emitted_events) >= 1, "Expected at least 1 verified plate event from CCTV footage"
    first_evt = emitted_events[0]
    assert first_evt.event_type == "VEHICLE_LPR"
    assert first_evt.attributes["status"] == "GRAMMAR_VALID"
    assert len(first_evt.attributes["plate_text"]) >= 3

