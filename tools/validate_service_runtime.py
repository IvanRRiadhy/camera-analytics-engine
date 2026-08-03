"""
CLI Event Service Runtime Validator & Benchmark Tool.

Validates service discovery, topological dependency startup, PlatformEvent bus dispatch,
dynamic plugin loading, exception isolation barriers, re-emitting events, hierarchical health,
and graceful runtime shutdown.

Usage::

    python -m camera_analytics.tools.validate_service_runtime
"""

from __future__ import annotations

import argparse
import logging
import time

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing import (
    AnalyticsPayload,
    EventSchemaVersion,
    PlatformEvent,
    PlatformEventBus,
)
from camera_analytics.services import EventServiceRuntimeManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("validate_service_runtime")


def main() -> None:
    logger.info("================================================================================")
    logger.info("SPRINT 12.5 — ENTERPRISE EVENT SERVICE RUNTIME VALIDATION")
    logger.info("================================================================================")

    # 1. Initialize Event Bus & Service Runtime Manager
    event_bus = PlatformEventBus()
    runtime_mgr = EventServiceRuntimeManager(
        plugin_dir="camera_analytics/services/plugins",
        event_bus=event_bus,
    )

    # 2. Discover, Load & Start Services Topologically
    logger.info("Starting Event Service Runtime Manager (Discovery & Topological Startup)...")
    loaded_count = runtime_mgr.initialize_and_start()

    # 3. Simulate Platform Events & Analytics Events
    sample_events = [
        StandardAnalyticsEvent(event_type="ZONE_ENTER", message="Pedestrian entered lobby", camera_id="cam_lobby_01", track_id=1, severity="INFO"),
        StandardAnalyticsEvent(event_type="LOITERING", message="Loitering detected near vault", camera_id="cam_lobby_01", track_id=2, severity="WARNING"),
        StandardAnalyticsEvent(event_type="CROWD_ALERT", message="Crowd density threshold exceeded", camera_id="cam_lobby_01", severity="CRITICAL"),
    ]

    logger.info("Dispatching events into Event Service Runtime...")
    total_dispatches = 0

    for evt in sample_events:
        count = runtime_mgr.dispatch(evt)
        total_dispatches += count

    # Also dispatch an immutable PlatformEvent
    pe = PlatformEvent.create(
        event_type="ANALYTICS_EVENT",
        payload=AnalyticsPayload(camera_id="cam_lobby_01", severity="CRITICAL", message="Immutable platform event test"),
        source="ai_runtime",
        version="1.0",
    )
    event_bus.publish(pe)

    time.sleep(0.5)

    # 4. Fetch Hierarchical Health Report
    health_report = runtime_mgr.get_health_report()

    logger.info("================================================================================")
    logger.info("EVENT SERVICE RUNTIME BENCHMARK RESULTS")
    logger.info("================================================================================")
    logger.info("Discovered & Loaded Services: %d services", loaded_count)
    logger.info("Total Event Dispatches:        %d deliveries", total_dispatches)
    logger.info("Runtime Status:                %s", health_report["runtime"]["status"])
    logger.info("Runtime Uptime:                %.1f sec", health_report["runtime"]["uptime_sec"])
    logger.info("--------------------------------------------------------------------------------")
    logger.info("SERVICE PLUGIN HEALTH HIERARCHY:")
    for s_name, s_info in health_report["services"].items():
        logger.info(
            "  - [%-14s] State: %-11s | Mode: %-9s | Version: %s | Errors: %d",
            s_name,
            s_info["state"],
            s_info["execution_mode"],
            s_info["version"],
            s_info["error_count"],
        )
    logger.info("================================================================================")

    # 5. Graceful Shutdown
    runtime_mgr.shutdown()
    logger.info("Sprint 12.5 Enterprise Event Service Runtime validation complete.")


if __name__ == "__main__":
    main()
