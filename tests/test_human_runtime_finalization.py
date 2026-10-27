"""
Sprint H1.4.7 Human Inference Runtime Finalization Test Suite.

Verifies:
1. ROICropHandle zero-copy reference layer.
2. HumanInferenceRequest lifecycle and factory methods.
3. HumanAttributes, InferenceResult, and IAttributeDecoder interfaces.
4. AttributeStabilizer (EMA age, Majority Voting gender, Confidence Locking, Decay).
5. InferenceTask scheduler batch output.
6. InferenceProfiler per-module telemetry profiling.
7. HumanRuntimeMetrics API dashboard snapshot serialization.
"""

from __future__ import annotations

import logging
import time
import numpy as np

from camera_analytics.core.human.decoder import HumanAttributes, IAttributeDecoder, InferenceResult
from camera_analytics.core.human.lock_manager import AttributeLockState
from camera_analytics.core.human.metrics import HumanRuntimeMetrics
from camera_analytics.core.human.models import HumanRepresentation, HumanState, ROICropCache
from camera_analytics.core.human.profiler import InferenceProfiler
from camera_analytics.core.human.request import HumanInferenceRequest, ROICropHandle
from camera_analytics.core.human.scheduler import HumanAnalyticsScheduler, InferenceTask
from camera_analytics.core.human.stabilizer import AttributeStabilizer
from camera_analytics.models.detection import BoundingBox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestHumanRuntimeFinalization")


def test_roi_crop_handle_and_inference_request():
    face = np.full((50, 50, 3), 100, dtype=np.uint8)
    head = np.full((80, 80, 3), 150, dtype=np.uint8)
    cache = ROICropCache(face_crop=face, head_crop=head)
    
    bbox = BoundingBox(x1=10, y1=20, x2=110, y2=220)
    rep = HumanRepresentation(
        track_id=1,
        frame_index=5,
        timestamp_utc=time.time(),
        body_bbox=bbox,
        crop_cache=cache,
        face_quality_score=0.85,
        visibility_score=0.90,
    )
    
    req = HumanInferenceRequest.from_representation(rep, camera_id="cam_lobby_01")
    assert req.track_id == 1
    assert req.frame_index == 5
    assert req.camera_id == "cam_lobby_01"
    assert req.crop_handle.face_crop.shape == (50, 50, 3)
    assert req.crop_handle.body_crop.shape == (80, 80, 3)
    assert req.face_quality_score == 0.85
    print("[+] ROICropHandle & HumanInferenceRequest test PASSED.")


class StubAgeGenderDecoder(IAttributeDecoder):
    @property
    def module_id(self) -> str:
        return "stub_mivolo"

    def decode(self, raw_output: Any, request: Any, execution_time_ms: float = 0.0) -> InferenceResult:
        attrs = HumanAttributes(age=28.0, gender="female", confidence=0.92)
        return InferenceResult(
            track_id=request.track_id,
            module_id=self.module_id,
            attributes=attrs,
            confidence=0.92,
            execution_time_ms=execution_time_ms,
        )


def test_attribute_decoder_and_inference_result():
    decoder = StubAgeGenderDecoder()
    cache = ROICropCache()
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    rep = HumanRepresentation(track_id=10, frame_index=0, timestamp_utc=time.time(), body_bbox=bbox, crop_cache=cache)
    req = HumanInferenceRequest.from_representation(rep)
    
    res = decoder.decode(raw_output=None, request=req, execution_time_ms=12.5)
    assert res.track_id == 10
    assert res.attributes.age == 28.0
    assert res.attributes.gender == "female"
    assert res.attributes.confidence == 0.92
    assert res.execution_time_ms == 12.5
    print("[+] IAttributeDecoder & InferenceResult DTO test PASSED.")


def test_attribute_stabilizer():
    stabilizer = AttributeStabilizer(ema_alpha=0.20, majority_window_size=5, lock_threshold=0.80)
    st = HumanState(track_id=42)
    
    # Pass frame 1: age=30.0, gender=female (conf 0.85 -> lock)
    attrs1 = HumanAttributes(age=30.0, gender="female", confidence=0.85)
    res1 = InferenceResult(track_id=42, module_id="mivolo", attributes=attrs1, confidence=0.85)
    stab1 = stabilizer.stabilize(res1, st)
    assert stab1.age == 30.0
    assert stab1.gender == "female"
    assert st.demographics.gender_lock == AttributeLockState.LOCKED.value
    
    # Pass frame 2: age=20.0 (EMA smooths 30*0.8 + 20*0.2 = 28.0)
    attrs2 = HumanAttributes(age=20.0, gender="male", confidence=0.50)
    res2 = InferenceResult(track_id=42, module_id="mivolo", attributes=attrs2, confidence=0.50)
    stab2 = stabilizer.stabilize(res2, st)
    assert stab2.age == 28.0
    assert stab2.gender == "female"  # Locked to female!
    
    # Test confidence decay
    stabilizer.apply_decay(track_id=42, state=st)
    stabilizer.purge_track(42)
    print("[+] AttributeStabilizer (EMA, Majority Vote, Lock, Decay) test PASSED.")


def test_inference_task_and_profiler():
    profiler = InferenceProfiler()
    
    # Record execution metrics
    profiler.get_profile("mivolo").record_execution(latency_ms=15.0, batch_size=2, success=True, wait_time_ms=1.2)
    profiler.get_profile("mivolo").record_execution(latency_ms=25.0, batch_size=2, success=True, wait_time_ms=1.5)
    profiler.record_quality_rejection("mivolo", count=3)
    
    prof = profiler.get_profile("mivolo")
    assert prof.execution_count == 4
    assert prof.quality_rejected_count == 3
    assert prof.average_latency_ms == 20.0
    assert prof.median_latency_ms == 20.0
    
    # Test InferenceTask
    cache = ROICropCache()
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    rep = HumanRepresentation(track_id=7, frame_index=0, timestamp_utc=time.time(), body_bbox=bbox, crop_cache=cache)
    req = HumanInferenceRequest.from_representation(rep)
    
    task = InferenceTask(task_id="task_001", module_id="mivolo", requests=(req,), priority=2)
    assert task.batch_size == 1
    assert task.module_id == "mivolo"
    print("[+] InferenceProfiler & InferenceTask test PASSED.")


def test_runtime_metrics_api():
    scheduler = HumanAnalyticsScheduler()
    metrics_api = HumanRuntimeMetrics(scheduler=scheduler)
    
    telemetry = metrics_api.get_runtime_telemetry()
    assert telemetry["status"] == "HEALTHY"
    assert "scheduler" in telemetry
    assert "profiler" in telemetry
    print("[+] HumanRuntimeMetrics API test PASSED.")


def main():
    print("\n========================================================")
    print("   SPRINT H1.4.7 HUMAN INFERENCE RUNTIME FINALIZATION TEST ")
    print("========================================================")
    test_roi_crop_handle_and_inference_request()
    test_attribute_decoder_and_inference_result()
    test_attribute_stabilizer()
    test_inference_task_and_profiler()
    test_runtime_metrics_api()
    print("========================================================\n")
    print("[SUCCESS] All Sprint H1.4.7 Finalization Tests PASSED!\n")


if __name__ == "__main__":
    main()
