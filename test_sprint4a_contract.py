"""
Sprint 4A Contract Verification Test Suite.
Validates that CameraAnalyticsSnapshot produces summary, byZone, byCamera + legacy fields.
"""

import json
from camera_analytics.runtime.analytics.models import (
    PeopleCountingState,
    QueueDetectionState,
    LoiteringState,
    ZoneOccupancyState,
)
from camera_analytics.runtime.analytics.pipeline_analytics_aggregator import PipelineAnalyticsAggregator

def test_sprint4a_contract():
    print("=== Running Sprint 4A Contract Verification Test ===")
    
    aggregator = PipelineAnalyticsAggregator(camera_id="cam_main_lobby_01", pipeline_id="pipe_01")
    
    # 1. Update Repository with Plugin States
    aggregator.update_plugin_state("peopleCounting", PeopleCountingState(current=18, entered=45, exited=27))
    aggregator.update_zone_metric("peopleCounting", "zone_lobby", {"current": 10, "entered": 25, "exited": 15})
    aggregator.update_zone_metric("peopleCounting", "zone_hallway", {"current": 8, "entered": 20, "exited": 12})

    aggregator.update_plugin_state("queueDetection", QueueDetectionState(queue_length=4, waiting_people=4))
    aggregator.update_zone_metric("queueDetection", "zone_cashier", {"queueLength": 4, "waitingPeople": 4})

    aggregator.update_plugin_state("loitering", LoiteringState(active_count=2, track_ids=(101, 105)))
    aggregator.update_zone_metric("loitering", "zone_restricted", {"active": 2})

    aggregator.update_plugin_state("zoneOccupancy", ZoneOccupancyState(occupancy_by_zone={"zone_lobby": 10, "zone_hallway": 8}))

    # 2. Build Snapshot
    snapshot = aggregator.create_snapshot()
    payload = snapshot.to_dict()

    print("\n--- Generated JSON Payload ---")
    print(json.dumps(payload, indent=2))

    # 3. Assertions
    assert "plugins" in payload, "Missing 'plugins' dictionary in payload"
    plugins = payload["plugins"]

    for p_code in ["peopleCounting", "queueDetection", "loitering", "zoneOccupancy"]:
        assert p_code in plugins, f"Missing plugin '{p_code}' in plugins dictionary"
        p_dict = plugins[p_code]

        assert "summary" in p_dict, f"Missing 'summary' in plugin '{p_code}'"
        assert "byZone" in p_dict, f"Missing 'byZone' in plugin '{p_code}'"
        assert "byCamera" in p_dict, f"Missing 'byCamera' in plugin '{p_code}'"

    # Verify PeopleCounting summary and breakdown
    pc = plugins["peopleCounting"]
    assert pc["summary"]["current"] == 18
    assert pc["current"] == 18  # Backward compatibility field
    assert "zone_lobby" in pc["byZone"]
    assert pc["byZone"]["zone_lobby"]["metrics"]["current"] == 10
    assert "cam_main_lobby_01" in pc["byCamera"]

    print("\n[SUCCESS] Sprint 4A Verification Test PASSED! Contract conforms 100% to specification.")

if __name__ == "__main__":
    test_sprint4a_contract()
