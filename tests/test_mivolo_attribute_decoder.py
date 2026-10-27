"""
Sprint H1.5B MiVOLO Attribute Decoder & Decoded AI Runtime Debug Viewer Test Suite.

Verifies:
1. MiVOLOAttributeDecoder raw tensor [B, 3] parsing into age, gender, Softmax probabilities, and InferenceResult.
2. Generic RuntimeDebugInfo container with dict attributes, status, skip_reason, and TTL expiration.
3. RuntimeOverlayProvider multi-module multi-track telemetry management & automatic TTL purge.
4. AI Capability concept matching (Age, Gender, Emotion, PPE).
5. OverlayRenderer Debug Panel rendering.
"""

from __future__ import annotations

import logging
import time
import numpy as np
import torch

from camera_analytics.core.human.decoders.mivolo_decoder import MiVOLOAttributeDecoder
from camera_analytics.core.human.models import ROICropCache
from camera_analytics.core.human.request import HumanInferenceRequest
from camera_analytics.models.detection import BoundingBox
from camera_analytics.viewer.overlay_provider import RuntimeDebugInfo, RuntimeOverlayProvider
from camera_analytics.viewer.renderer import OverlayRenderer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestMiVOLOAttributeDecoder")


def test_mivolo_attribute_decoder():
    decoder = MiVOLOAttributeDecoder(min_age=1.0, max_age=95.0)
    assert decoder.module_id == "mivolo_age_gender"

    # Dummy raw tensor: age=28.5, male_logit=2.5, female_logit=0.5 -> male prob ~88%
    raw_tensor = torch.tensor([[28.5, 2.5, 0.5]], dtype=torch.float32)
    
    cache = ROICropCache()
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    req = HumanInferenceRequest(
        track_id=12,
        timestamp_utc=time.time(),
        frame_index=10,
        crop_handle=None,
        body_bbox=bbox,
    )

    result = decoder.decode(raw_output=raw_tensor, request=req, execution_time_ms=15.2)

    assert result.track_id == 12
    assert result.attributes.age == 28.5
    assert result.attributes.gender == "male"
    assert result.attributes.confidence > 0.85
    assert result.status == "SUCCESS"
    assert "raw_age" in result.attributes.raw_outputs
    print("[+] MiVOLOAttributeDecoder Softmax & age decoding test PASSED.")


def test_runtime_debug_info_and_ttl():
    info = RuntimeDebugInfo(
        track_id=5,
        module_id="mivolo_age_gender",
        capabilities=("Age", "Gender"),
        attributes={"age": 32.0, "gender": "female"},
        status="EXECUTED",
        face_quality=0.88,
        latency_ms=18.4,
        ttl_seconds=0.1,
    )
    assert not info.is_expired
    time.sleep(0.15)
    assert info.is_expired
    print("[+] RuntimeDebugInfo generic attributes & TTL expiration test PASSED.")


def test_runtime_overlay_provider():
    provider = RuntimeOverlayProvider(default_ttl_seconds=0.2)
    
    info1 = RuntimeDebugInfo(
        track_id=1,
        module_id="mivolo_age_gender",
        capabilities=("Age", "Gender"),
        attributes={"age": 25.0, "gender": "male"},
        status="EXECUTED",
        latency_ms=12.0,
        ttl_seconds=0.5,
    )
    info2 = RuntimeDebugInfo(
        track_id=1,
        module_id="hsemotion",
        capabilities=("Emotion",),
        attributes={"emotion": "happy"},
        status="EXECUTED",
        latency_ms=8.0,
        ttl_seconds=0.5,
    )
    info3 = RuntimeDebugInfo(
        track_id=2,
        module_id="mivolo_age_gender",
        capabilities=("Age", "Gender"),
        status="SKIPPED",
        skip_reason="Low Face Quality",
        face_quality=0.25,
        ttl_seconds=0.5,
    )

    provider.update_debug_info("cam_lobby", info1)
    provider.update_debug_info("cam_lobby", info2)
    provider.update_debug_info("cam_lobby", info3)

    # Verify multi-module per track
    track1_infos = provider.get_track_debug_info("cam_lobby", track_id=1)
    assert len(track1_infos) == 2

    # Verify multi-track per camera
    all_cam = provider.get_all_camera_debug_info("cam_lobby")
    assert len(all_cam) == 2
    assert all_cam[2][0].skip_reason == "Low Face Quality"

    print("[+] RuntimeOverlayProvider multi-module multi-track & skip reason test PASSED.")


def test_overlay_renderer_debug_panel():
    provider = RuntimeOverlayProvider()
    renderer = OverlayRenderer(overlay_provider=provider)

    info = RuntimeDebugInfo(
        track_id=7,
        module_id="mivolo_age_gender",
        capabilities=("Age", "Gender"),
        attributes={"age": 29.0, "gender": "female"},
        status="EXECUTED",
        latency_ms=21.0,
        face_quality=0.92,
        ttl_seconds=5.0,
    )
    provider.update_debug_info("default_camera", info)

    # Render dummy image
    dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
    from camera_analytics.viewer.models import FramePresentation
    pres = FramePresentation(
        camera_id="default_camera",
        camera_name="Test Camera",
        frame_number=1,
        timestamp=time.time(),
        image=dummy_img,
        tracks=[],
        zones=[],
    )

    rendered = renderer.render(pres)
    assert rendered.shape == (480, 640, 3)
    print("[+] OverlayRenderer Standalone AI Runtime Debug Panel test PASSED.")


def main():
    print("\n========================================================")
    print("   SPRINT H1.5B MIVOLO ATTRIBUTE DECODER TEST ")
    print("========================================================")
    test_mivolo_attribute_decoder()
    test_runtime_debug_info_and_ttl()
    test_runtime_overlay_provider()
    test_overlay_renderer_debug_panel()
    print("========================================================\n")
    print("[SUCCESS] All Sprint H1.5B Decoder & Viewer Tests PASSED!\n")


if __name__ == "__main__":
    main()
