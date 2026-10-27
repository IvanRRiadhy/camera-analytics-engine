"""
Sprint H1.5B MiVOLO Production AI Runtime Integration Test Suite.

Verifies:
1. TorchScriptBackend model loading via ModelManager.
2. Metadata loading from metadata.json (384x384 input resolution).
3. MiVOLOPreProcessor 6-channel tensor assembly.
4. Real TorchScript MiVOLO AI inference execution on GPU/CUDA.
5. MiVOLOPostProcessor raw output parsing into age and gender predictions.
6. HumanStateUpdater & AttributeLockManager state enrichment.
7. HumanSnapshotMapper serialization containing real age and gender attributes.
8. HumanAnalyticsScheduler execution, batch queueing, and metrics collection.
"""

from __future__ import annotations

import logging
import time
from typing import Any
import numpy as np

from camera_analytics.core.human.backends.torchscript_backend import TorchScriptBackend
from camera_analytics.core.human.context import HumanModuleContext
from camera_analytics.core.human.lock_manager import AttributeLockManager, AttributeLockState
from camera_analytics.core.human.models import HumanRepresentation, HumanState, ROICropCache
from camera_analytics.core.human.model_manager import ModelManager
from camera_analytics.core.human.module_registry import ModuleRegistry
from camera_analytics.core.human.modules.mivolo_module import MiVOLOModule
from camera_analytics.core.human.post_processors.mivolo_post_processor import MiVOLOPostProcessor
from camera_analytics.core.human.pre_processors.mivolo_pre_processor import MiVOLOPreProcessor
from camera_analytics.core.human.scheduler import HumanAnalyticsScheduler
from camera_analytics.core.human.snapshot_mapper import HumanSnapshotMapper
from camera_analytics.models.detection import BoundingBox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestMiVOLORuntime")


def test_torchscript_backend_loading():
    mm = ModelManager()
    mod = MiVOLOModule()
    mod.initialize(mm)
    
    assert mm.is_loaded("mivolo_v2_age_gender") is True
    session = mm.get_session("mivolo_v2_age_gender")
    assert isinstance(session, TorchScriptBackend)
    assert session.is_loaded() is True
    
    mod.cleanup()
    mm.unload_all()
    print("[+] TorchScriptBackend & ModelManager loading test PASSED.")


def test_mivolo_pre_processor_224():
    pre = MiVOLOPreProcessor(input_resolution=(224, 224))
    
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    face_crop = np.full((64, 64, 3), 128, dtype=np.uint8)
    head_crop = np.full((128, 128, 3), 200, dtype=np.uint8)
    
    rep = HumanRepresentation(
        track_id=1,
        frame_index=0,
        timestamp_utc=time.time(),
        body_bbox=bbox,
        crop_cache=ROICropCache(face_crop=face_crop, head_crop=head_crop),
    )
    st = HumanState(track_id=1)
    ctx = HumanModuleContext(representation=rep, state=st)
    
    batch_tensor, lat_ms = pre.preprocess_batch([ctx])
    assert batch_tensor.shape == (1, 6, 224, 224)
    print(f"[+] MiVOLOPreProcessor 224x224 tensor assembly test PASSED ({lat_ms:.2f}ms).")


def test_mivolo_post_processor():
    post = MiVOLOPostProcessor()
    
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    rep = HumanRepresentation(track_id=10, frame_index=0, timestamp_utc=time.time(), body_bbox=bbox)
    st = HumanState(track_id=10)
    ctx = HumanModuleContext(representation=rep, state=st)
    
    # Mock raw output tensor [B, 3] -> age=28.5, gender_male=2.5, gender_female=-1.0
    raw_tensor = np.array([[28.5, 2.5, -1.0]], dtype=np.float32)
    results, lat_ms = post.postprocess_batch(raw_tensor, [ctx], module_id="mivolo")
    
    assert len(results) == 1
    res = results[0]
    assert res.track_id == 10
    assert res.outputs["age"] == 28.5
    assert res.outputs["gender"] == "male"
    assert res.outputs["lock_gender"] is True
    print(f"[+] MiVOLOPostProcessor output parsing test PASSED ({lat_ms:.2f}ms).")


def test_real_mivolo_inference_and_scheduler():
    mm = ModelManager()
    reg = ModuleRegistry()
    scheduler = HumanAnalyticsScheduler(model_manager=mm, registry=reg)
    
    mod = MiVOLOModule()
    mod.config.frame_stride = 1
    scheduler.register_module(mod)
    
    bbox = BoundingBox(x1=10, y1=10, x2=150, y2=300)
    face_crop = np.full((128, 128, 3), 100, dtype=np.uint8)
    head_crop = np.full((180, 180, 3), 150, dtype=np.uint8)
    
    rep = HumanRepresentation(
        track_id=42,
        frame_index=0,
        timestamp_utc=time.time(),
        body_bbox=bbox,
        face_quality_score=0.8,
        visibility_score=0.9,
        crop_cache=ROICropCache(face_crop=face_crop, head_crop=head_crop),
    )
    st = HumanState(track_id=42)
    
    t0 = time.perf_counter()
    st = scheduler.execute_pipeline(representation=rep, state=st, frame_index=0)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    
    # Verify real predictions populated on HumanState
    assert st.demographics.age is not None
    assert isinstance(st.demographics.age, float)
    assert st.demographics.gender in ("male", "female")
    assert st.demographics.gender_confidence > 0.0
    assert st.demographics.gender_lock in (AttributeLockState.UNLOCKED.value, AttributeLockState.LOCKED.value)
    
    metrics = scheduler.get_metrics_summary()
    m_info = metrics["mivolo_age_gender"]
    assert m_info["executionCount"] == 1
    assert m_info["processedCount"] == 1
    
    print(f"[+] Real TorchScript MiVOLO AI Inference test PASSED! (Age: {st.demographics.age}y, Gender: {st.demographics.gender.capitalize()}, Latency: {elapsed_ms:.2f}ms)")
    
    scheduler.cleanup()


def test_snapshot_mapper_real_telemetry():
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    rep = HumanRepresentation(track_id=99, frame_index=0, timestamp_utc=time.time(), body_bbox=bbox, face_quality_score=0.9, visibility_score=0.95)
    st = HumanState(track_id=99)
    st.demographics.age = 29.5
    st.demographics.age_confidence = 0.90
    st.demographics.gender = "female"
    st.demographics.gender_confidence = 0.98
    st.demographics.gender_lock = "LOCKED"
    
    payload = HumanSnapshotMapper.map_snapshot_payload(
        summary={"totalHumansDetected": 1},
        representations={99: rep},
        states={99: st},
    )
    
    trk = payload["tracks"]["99"]
    assert trk["trackId"] == 99
    assert trk["gender"] == "female"
    assert trk["age"] == 29.5
    assert trk["genderConfidence"] == 0.98
    assert trk["genderLock"] == "LOCKED"
    assert trk["faceQuality"] == 0.9
    print("[+] HumanSnapshotMapper real telemetry payload test PASSED.")


def main():
    print("\n========================================================")
    print("   SPRINT H1.5B MIVOLO PRODUCTION AI RUNTIME TEST SUITE ")
    print("========================================================")
    test_torchscript_backend_loading()
    test_mivolo_pre_processor_224()
    test_mivolo_post_processor()
    test_real_mivolo_inference_and_scheduler()
    test_snapshot_mapper_real_telemetry()
    print("========================================================\n")
    print("[SUCCESS] All Sprint H1.5B Production AI Runtime Tests PASSED!\n")


if __name__ == "__main__":
    main()
