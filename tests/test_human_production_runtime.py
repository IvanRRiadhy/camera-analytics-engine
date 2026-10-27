"""
Sprint H1.5A Human Analytics Production Runtime Integration Test Suite.

Verifies:
1. HumanModuleContext & ModuleResult data models.
2. IBatchingStrategy & HumanBatchQueue operation.
3. AttributeLockManager state machine transitions.
4. ResultSplitter & HumanStateUpdater state updates.
5. ModuleRegistry & placeholder MiVOLOModule lifecycle.
6. HumanAnalyticsScheduler DAG batch execution & telemetry metrics.
7. HumanSnapshotMapper payload serialization.
"""

from __future__ import annotations

import logging
import time
from typing import Any
import numpy as np

from camera_analytics.core.human.batch_queue import (
    DynamicBatchStrategy,
    FixedBatchStrategy,
    HumanBatchQueue,
    TimeoutBatchStrategy,
)
from camera_analytics.core.human.context import HumanModuleContext, ModuleResult
from camera_analytics.core.human.lock_manager import AttributeLockManager, AttributeLockState
from camera_analytics.core.human.models import HumanRepresentation, HumanState, ROICropCache
from camera_analytics.models.detection import BoundingBox
from camera_analytics.core.human.model_manager import ModelManager
from camera_analytics.core.human.module_registry import ModuleRegistry
from camera_analytics.core.human.modules.mivolo_module import MiVOLOModule
from camera_analytics.core.human.scheduler import HumanAnalyticsScheduler
from camera_analytics.core.human.snapshot_mapper import HumanSnapshotMapper
from camera_analytics.core.human.state_updater import HumanStateUpdater, ResultSplitter
from camera_analytics.runtime.analytics.snapshot_builder import SnapshotBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestHumanProductionRuntime")


def test_human_module_context_and_result():
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    rep = HumanRepresentation(track_id=1, frame_index=0, timestamp_utc=0.0, body_bbox=bbox, crop_cache=ROICropCache(face_crop=np.zeros((64, 64, 3), dtype=np.uint8)))
    st = HumanState(track_id=1)
    
    ctx = HumanModuleContext(representation=rep, state=st)
    assert ctx.representation.track_id == 1
    assert ctx.state.track_id == 1
    assert ctx.scheduler_context == {}
    
    res = ModuleResult(module_id="test_mod", track_id=1, outputs={"test": 123}, confidence=0.95)
    assert res.module_id == "test_mod"
    assert res.track_id == 1
    assert res.outputs["test"] == 123
    print("[+] HumanModuleContext & ModuleResult test PASSED.")


def test_batching_strategies():
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    queue = HumanBatchQueue(strategy=FixedBatchStrategy(), max_batch_size=4)
    rep = HumanRepresentation(track_id=1, frame_index=0, timestamp_utc=0.0, body_bbox=bbox)
    st = HumanState(track_id=1)
    ctx = HumanModuleContext(representation=rep, state=st)
    
    for i in range(3):
        queue.enqueue(i, ctx)
    assert not queue.should_dispatch()
    
    queue.enqueue(3, ctx)
    assert queue.should_dispatch()
    
    batch = queue.dequeue_batch()
    assert len(batch) == 4
    assert queue.queue_size == 0
    print("[+] IBatchingStrategy & HumanBatchQueue test PASSED.")


def test_lock_manager_and_state_updater():
    st = HumanState(track_id=10)
    assert AttributeLockManager.should_process(st.demographics.gender_lock)
    
    res = ModuleResult(
        module_id="mivolo",
        track_id=10,
        outputs={"age": 30.0, "gender": "female", "lock_gender": True},
        confidence=0.99,
    )
    
    updater = HumanStateUpdater()
    st = updater.update_state(st, [res])
    
    assert st.demographics.age == 30.0
    assert st.demographics.gender == "female"
    assert st.demographics.gender_lock == AttributeLockState.LOCKED.value
    assert AttributeLockManager.is_locked(st.demographics.gender_lock)
    assert not AttributeLockManager.should_process(st.demographics.gender_lock)
    print("[+] AttributeLockManager & HumanStateUpdater test PASSED.")


def test_mivolo_module_placeholder_lifecycle():
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    mm = ModelManager()
    mod = MiVOLOModule()
    mod.initialize(mm)
    
    rep = HumanRepresentation(track_id=7, frame_index=0, timestamp_utc=0.0, body_bbox=bbox, face_quality_score=0.8)
    st = HumanState(track_id=7)
    ctx = HumanModuleContext(representation=rep, state=st)
    
    results = mod.process_batch([ctx])
    assert len(results) == 1
    assert results[0].track_id == 7
    # Verify real outputs in Sprint H1.5B
    assert results[0].outputs["age"] is not None
    assert isinstance(results[0].outputs["age"], float)
    assert results[0].outputs["gender"] in ("male", "female")
    
    mod.cleanup()
    mm.unload_all()
    print("[+] MiVOLOModule placeholder lifecycle test PASSED.")


def test_scheduler_integration_and_metrics():
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    mm = ModelManager()
    reg = ModuleRegistry()
    scheduler = HumanAnalyticsScheduler(model_manager=mm, registry=reg)
    
    mod = MiVOLOModule()
    mod.config.frame_stride = 1
    scheduler.register_module(mod)
    
    rep = HumanRepresentation(track_id=5, frame_index=0, timestamp_utc=0.0, body_bbox=bbox, face_quality_score=0.8, visibility_score=0.9)
    st = HumanState(track_id=5)
    
    # Run 8 frames to trigger batch dispatch
    for f_idx in range(8):
        st = scheduler.execute_pipeline(representation=rep, state=st, frame_index=f_idx)
        
    metrics = scheduler.get_metrics_summary()
    assert "mivolo_age_gender" in metrics
    m_info = metrics["mivolo_age_gender"]
    assert m_info["enqueueCount"] == 8
    assert m_info["processedCount"] == 8
    
    scheduler.cleanup()
    print("[+] HumanAnalyticsScheduler integration & metrics test PASSED.")


def test_snapshot_mapper_serialization():
    bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
    rep = HumanRepresentation(track_id=12, frame_index=0, timestamp_utc=0.0, body_bbox=bbox, face_quality_score=0.75, visibility_score=0.85)
    st = HumanState(track_id=12)
    
    payload = HumanSnapshotMapper.map_snapshot_payload(
        summary={"totalHumansDetected": 1},
        representations={12: rep},
        states={12: st},
    )
    
    assert "summary" in payload
    assert "tracks" in payload
    assert "12" in payload["tracks"]
    
    trk = payload["tracks"]["12"]
    assert trk["trackId"] == 12
    assert trk["gender"] is None
    assert trk["age"] is None
    assert trk["genderLock"] == "UNLOCKED"
    assert trk["ageLock"] == "UNLOCKED"
    assert trk["faceQuality"] == 0.75
    assert trk["visibility"] == 0.85
    print("[+] HumanSnapshotMapper serialization test PASSED.")


def main():
    print("\n========================================================")
    print("   SPRINT H1.5A HUMAN PRODUCTION RUNTIME TEST SUITE     ")
    print("========================================================")
    test_human_module_context_and_result()
    test_batching_strategies()
    test_lock_manager_and_state_updater()
    test_mivolo_module_placeholder_lifecycle()
    test_scheduler_integration_and_metrics()
    test_snapshot_mapper_serialization()
    print("========================================================\n")
    print("[SUCCESS] All Sprint H1.5A Production Runtime Integration Tests PASSED!\n")


if __name__ == "__main__":
    main()
