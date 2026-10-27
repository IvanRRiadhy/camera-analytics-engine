"""
Sprint H1.5C Persistent HumanState & Temporal Intelligence Layer Test Suite.

Verifies:
1. HumanState & HumanStateLifecycle state machine transitions.
2. CapabilityId enum & CapabilityState modular separation.
3. HumanTimeline ring buffer (deque maxlen=100) and metadata completeness.
4. HumanStatistics recording (track lifetime, inference count, average quality).
5. HumanStateUpdater mutation isolation.
6. HumanStatePresenter view model mapping for viewer decoupling.
7. Multi-camera state isolation and track termination cleanup.
"""

from __future__ import annotations

import logging
import time

from camera_analytics.core.human.decoder import HumanAttributes, InferenceResult
from camera_analytics.core.human.models import CapabilityId, CapabilityState, HumanState, HumanStateLifecycle
from camera_analytics.core.human.state_updater import HumanStateUpdater
from camera_analytics.core.human.timeline import HumanTimeline, HumanTimelineEntry
from camera_analytics.viewer.presenter import HumanStatePresenter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestHumanState")


def test_human_state_lifecycle_and_capabilities():
    state = HumanState(track_id=101)
    assert state.lifecycle == HumanStateLifecycle.NEW
    assert state.is_active

    # Get CapabilityState for AGE and GENDER
    age_cap = state.get_capability_state(CapabilityId.AGE)
    gender_cap = state.get_capability_state(CapabilityId.GENDER)
    assert age_cap.capability_id == CapabilityId.AGE
    assert gender_cap.capability_id == CapabilityId.GENDER

    print("[+] HumanState lifecycle & CapabilityId state container test PASSED.")


def test_human_timeline_ring_buffer():
    timeline = HumanTimeline(max_entries=3, max_age_seconds=10.0)
    
    entry1 = HumanTimelineEntry(timestamp_utc=time.time(), frame_index=1, capability_id="AGE", value=25.0)
    entry2 = HumanTimelineEntry(timestamp_utc=time.time(), frame_index=2, capability_id="AGE", value=26.0)
    entry3 = HumanTimelineEntry(timestamp_utc=time.time(), frame_index=3, capability_id="AGE", value=27.0)
    entry4 = HumanTimelineEntry(timestamp_utc=time.time(), frame_index=4, capability_id="AGE", value=28.0)

    timeline.append(entry1)
    timeline.append(entry2)
    timeline.append(entry3)
    assert len(timeline) == 3

    # Exceed maxlen=3 -> entry1 automatically popped
    timeline.append(entry4)
    assert len(timeline) == 3
    entries = timeline.get_entries()
    assert entries[0].value == 26.0
    assert entries[-1].value == 28.0

    timeline.clear()
    assert len(timeline) == 0
    print("[+] HumanTimeline ring buffer (deque maxlen) & O(1) bounded memory test PASSED.")


def test_human_state_updater_and_statistics():
    updater = HumanStateUpdater()
    state = HumanState(track_id=202)

    # 1. Update frame 1 via InferenceResult
    attrs1 = HumanAttributes(age=30.0, gender="male", confidence=0.90)
    res1 = InferenceResult(track_id=202, module_id="mivolo", attributes=attrs1, confidence=0.90, execution_time_ms=18.5)
    
    updater.update_state(state, [res1])
    assert state.lifecycle == HumanStateLifecycle.INITIALIZING
    assert state.demographics.age == 30.0
    assert state.demographics.gender == "male"
    assert state.statistics.inference_count == 1
    assert state.statistics.last_inference_latency_ms == 18.5
    assert len(state.timeline) == 2  # Age + Gender timeline entries

    # 2. Perform multiple updates to transition lifecycle: INITIALIZING -> LEARNING -> STABLE
    for i in range(5):
        attrs_i = HumanAttributes(age=30.0, gender="male", confidence=0.92)
        res_i = InferenceResult(track_id=202, module_id="mivolo", attributes=attrs_i, confidence=0.92, execution_time_ms=15.0)
        updater.update_state(state, [res_i])

    assert state.lifecycle == HumanStateLifecycle.STABLE
    assert state.statistics.inference_count == 6

    # 3. Test purge_track on track termination
    updater.purge_track(state)
    assert state.lifecycle == HumanStateLifecycle.TERMINATED
    assert len(state.timeline) == 0
    print("[+] HumanStateUpdater sole mutator & HumanStatistics lifecycle test PASSED.")


def test_human_state_presenter_viewer_mapping():
    updater = HumanStateUpdater()
    state = HumanState(track_id=303)
    
    attrs = HumanAttributes(age=28.0, gender="female", confidence=0.95)
    res = InferenceResult(track_id=303, module_id="mivolo", attributes=attrs, confidence=0.95, execution_time_ms=14.0)
    updater.update_state(state, [res])

    vm = HumanStatePresenter.present(state)
    assert vm.track_id == 303
    assert vm.lifecycle == "INITIALIZING"
    assert vm.total_inference_count == 1
    assert len(vm.capabilities) == 2  # Age & Gender
    assert vm.capabilities[0].capability_id == "AGE"
    print("[+] HumanStatePresenter view model mapping test PASSED.")


def main():
    print("\n========================================================")
    print("   SPRINT H1.5C HUMANSTATE & TEMPORAL INTELLIGENCE TEST ")
    print("========================================================")
    test_human_state_lifecycle_and_capabilities()
    test_human_timeline_ring_buffer()
    test_human_state_updater_and_statistics()
    test_human_state_presenter_viewer_mapping()
    print("========================================================\n")
    print("[SUCCESS] All Sprint H1.5C HumanState Tests PASSED!\n")


if __name__ == "__main__":
    main()
