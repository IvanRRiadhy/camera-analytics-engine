"""
Unit & Integration Test Suite for AI Model Runtime Infrastructure (Sprint H1.4).

Tests:
1. InferenceModelRegistry metadata registration and capability discovery.
2. IInferenceBackend, StubInferenceBackend, and ModelManager lifecycle.
3. ModuleDependencyGraph topological sorting, priority ordering, and cycle detection.
4. BaseHumanAnalyticsModule & multi-condition trigger evaluation (stride, quality, lock).
5. HumanAnalyticsScheduler DAG pipeline execution and ModuleExecutionMetrics collection.
6. Backward compatibility with existing HumanRuntime facade.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional
import numpy as np
import pytest

from camera_analytics.models.detection import BoundingBox
from camera_analytics.core.human.base_module import BaseHumanAnalyticsModule, ModuleConfig
from camera_analytics.core.human.dependency_graph import ModuleDependencyGraph
from camera_analytics.core.human.model_manager import IInferenceBackend, ModelManager, StubInferenceBackend
from camera_analytics.core.human.models import HumanRepresentation, HumanState
from camera_analytics.core.human.registry import InferenceModelRegistry, ModelMetadata
from camera_analytics.core.human.runtime import HumanRuntime
from camera_analytics.core.human.scheduler import HumanAnalyticsScheduler, ModuleExecutionMetrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestAIRuntimeInfrastructure")


# Concrete Dummy Module for testing
class DummyAIModule(BaseHumanAnalyticsModule):

    def __init__(self, m_id: str = "dummy_module", priority: int = 3, capabilities: tuple[str, ...] = ("test",), config: Optional[ModuleConfig] = None) -> None:
        cfg = config or ModuleConfig(priority=priority)
        super().__init__(config=cfg)
        self._m_id = m_id
        self._meta = ModelMetadata(
            model_id=f"model_{m_id}",
            name=f"Dummy Model {m_id}",
            version="1.0.0",
            capabilities=capabilities,
        )

    @property
    def module_id(self) -> str:
        return self._m_id

    @property
    def metadata(self) -> ModelMetadata:
        return self._meta

    def initialize(self, model_manager: ModelManager) -> None:
        model_manager.registry.register_model(self._meta)
        model_manager.load_model(self._meta.model_id)
        self._is_initialized = True

    def process(
        self,
        representation: HumanRepresentation,
        state: HumanState,
        frame: Optional[np.ndarray] = None,
        runtime_context: Optional[Any] = None,
    ) -> HumanState:
        return self.update_state(state, {"processed_by": self._m_id})

    def update_state(self, state: HumanState, inference_output: Any) -> HumanState:
        state.custom_attributes[self._m_id] = inference_output
        return state

    def cleanup(self) -> None:
        self._is_initialized = False


def test_registry_and_capability_discovery():
    """Test InferenceModelRegistry registration and capability query."""
    registry = InferenceModelRegistry()
    m1 = ModelMetadata(model_id="mivolo_v1", name="MiVOLO", version="1.0.0", capabilities=("age", "gender"))
    m2 = ModelMetadata(model_id="hsemotion_v1", name="HSEmotion", version="1.0.0", capabilities=("emotion",))
    m3 = ModelMetadata(model_id="arcface_v1", name="ArcFace", version="2.0.0", capabilities=("face_embedding", "age"))

    registry.register_model(m1)
    registry.register_model(m2)
    registry.register_model(m3)

    assert len(registry.list_models()) == 3
    assert len(registry.find_models_by_capability("age")) == 2
    assert len(registry.find_models_by_capability("emotion")) == 1
    assert len(registry.find_models_by_capability("unknown")) == 0
    print("[+] InferenceModelRegistry capability discovery test PASSED.")


def test_model_manager_and_backend():
    """Test IInferenceBackend and ModelManager session lifecycle."""
    registry = InferenceModelRegistry()
    meta = ModelMetadata(model_id="test_model", name="Test Model", version="1.0.0")
    registry.register_model(meta)

    mgr = ModelManager(registry=registry)
    backend = StubInferenceBackend(backend_type="TensorRT")
    session = mgr.load_model("test_model", backend=backend)

    assert session.is_loaded() is True
    assert mgr.is_loaded("test_model") is True
    assert session.infer({})["output"] == "stub_inference_result"

    mgr.unload_model("test_model")
    assert mgr.is_loaded("test_model") is False
    print("[+] ModelManager & IInferenceBackend lifecycle test PASSED.")


def test_dependency_graph():
    """Test ModuleDependencyGraph topological sorting and cycle detection."""
    graph = ModuleDependencyGraph()
    graph.add_module(module_id="recognition", priority=4, dependencies=["embedding"])
    graph.add_module(module_id="embedding", priority=3, dependencies=["alignment"])
    graph.add_module(module_id="alignment", priority=2, dependencies=["quality"])
    graph.add_module(module_id="quality", priority=1, dependencies=[])

    order = graph.resolve_execution_order()
    assert order == ["quality", "alignment", "embedding", "recognition"]

    # Test cycle detection
    graph_cycle = ModuleDependencyGraph()
    graph_cycle.add_module("mod_a", dependencies=["mod_b"])
    graph_cycle.add_module("mod_b", dependencies=["mod_a"])

    with pytest.raises(ValueError, match="Circular dependency"):
        graph_cycle.resolve_execution_order()

    print("[+] ModuleDependencyGraph topological sort & cycle detection test PASSED.")


def test_scheduler_and_multi_condition_triggers():
    """Test HumanAnalyticsScheduler multi-condition triggers (stride, quality gate, lock)."""
    mgr = ModelManager()
    scheduler = HumanAnalyticsScheduler(model_manager=mgr)

    # Config with frame_stride=2 and min_face_quality=0.5
    cfg = ModuleConfig(frame_stride=2, minimum_face_quality=0.5)
    mod = DummyAIModule(m_id="mod_strided", config=cfg)
    scheduler.register_module(mod)

    state = HumanState(track_id=1)
    rep_high_q = HumanRepresentation(
        track_id=1,
        frame_index=0,
        timestamp_utc=time.time(),
        body_bbox=BoundingBox(x1=10, y1=10, x2=100, y2=200),
        face_quality_score=0.8,
        visibility_score=0.9,
    )
    rep_low_q = HumanRepresentation(
        track_id=1,
        frame_index=0,
        timestamp_utc=time.time(),
        body_bbox=BoundingBox(x1=10, y1=10, x2=100, y2=200),
        face_quality_score=0.2,
        visibility_score=0.9,
    )

    # Frame 0 (Stride pass, High Quality pass) -> Execute
    st0 = scheduler.execute_pipeline(rep_high_q, state, frame_index=0)
    assert "mod_strided" in st0.custom_attributes

    # Frame 1 (Stride fail) -> Skipped
    state.custom_attributes.clear()
    st1 = scheduler.execute_pipeline(rep_high_q, state, frame_index=1)
    assert "mod_strided" not in st1.custom_attributes

    # Frame 2 (Stride pass, Low Quality fail) -> Skipped
    state.custom_attributes.clear()
    st2 = scheduler.execute_pipeline(rep_low_q, state, frame_index=2)
    assert "mod_strided" not in st2.custom_attributes

    # Metrics verification
    summary = scheduler.get_metrics_summary()
    assert summary["mod_strided"]["executionCount"] == 1
    assert summary["mod_strided"]["skippedCount"] == 2
    print("[+] HumanAnalyticsScheduler multi-condition trigger test PASSED.")


def test_human_runtime_backwards_compatibility():
    """Verify HumanRuntime operates seamlessly with scheduler integration."""
    runtime = HumanRuntime()
    dummy_mod = DummyAIModule(m_id="test_runtime_mod")
    runtime.scheduler.register_module(dummy_mod)

    tracks = [{"track_id": 99, "bbox": [10.0, 10.0, 100.0, 200.0], "confidence": 0.9}]
    res = runtime.process_frame(tracks, frame_index=0)

    assert 99 in res.states
    assert "moduleMetrics" in res.summary
    assert "test_runtime_mod" in res.summary["moduleMetrics"]
    runtime.cleanup()
    print("[+] HumanRuntime backwards compatibility test PASSED.")


if __name__ == "__main__":
    test_registry_and_capability_discovery()
    test_model_manager_and_backend()
    test_dependency_graph()
    test_scheduler_and_multi_condition_triggers()
    test_human_runtime_backwards_compatibility()
    print("\n[SUCCESS] All Sprint H1.4 AI Model Runtime Infrastructure Unit Tests PASSED!\n")
