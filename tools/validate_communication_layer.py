"""
CLI Communication Layer Validation Tool.

Benchmarks high-throughput non-blocking event publishing across all 5 publishers
(Log File NDJSON, Console, REST Webhook, RabbitMQ, MQTT) with event routing rules,
queue backpressure protection, and metrics monitoring.

Usage::

    python -m camera_analytics.tools.validate_communication_layer --events 500
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from camera_analytics.communication import (
    CommunicationManager,
    ConsolePublisher,
    EventDetailLevel,
    EventSeverity,
    LogPublisher,
    MQTTPublisher,
    RabbitMQPublisher,
    RestPublisher,
    StandardAnalyticsEvent,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("validate_communication_layer")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enterprise CCTV Communication Layer Validator & Benchmark Tool"
    )
    parser.add_argument(
        "--events",
        type=int,
        default=500,
        help="Total number of test events to enqueue (default 500)",
    )
    parser.add_argument(
        "--queue-size",
        type=int,
        default=10000,
        help="Internal bounded queue max size (default 10000)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="camera_analytics/logs",
        help="Log publisher output directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info("================================================================================")
    logger.info("SPRINT 12.2 — ENTERPRISE COMMUNICATION LAYER BENCHMARK & VALIDATION")
    logger.info("================================================================================")

    mgr = CommunicationManager.get_instance(queue_size=args.queue_size)

    # Configure 5 Publishers
    log_pub = LogPublisher(name="file_log", enabled=True, log_dir=args.output_dir, detail_level="summary")
    console_pub = ConsolePublisher(name="console_out", enabled=True, show_payload=False)
    rest_pub = RestPublisher(name="rest_webhook", enabled=True, endpoint_url="http://127.0.0.1:9999/api/v1/events", timeout_sec=0.01, max_retries=0)
    rabbitmq_pub = RabbitMQPublisher(name="rabbitmq", enabled=True)
    mqtt_pub = MQTTPublisher(name="mqtt", enabled=True)

    pub_mgr = mgr.publisher_manager
    pub_mgr.register_publisher(log_pub)
    pub_mgr.register_publisher(console_pub)
    pub_mgr.register_publisher(rest_pub)
    pub_mgr.register_publisher(rabbitmq_pub)
    pub_mgr.register_publisher(mqtt_pub)

    # Configure Routing Rules
    routing_rules = [
        {"event_types": ["CROWD_ALERT", "QUEUE_ALERT"], "publishers": ["file_log", "console_out", "rest_webhook"]},
        {"severities": ["CRITICAL", "ALERT"], "publishers": ["file_log", "rest_webhook"]},
        {"event_types": ["*"], "publishers": ["file_log"]},
    ]
    mgr.router.load_rules(routing_rules)

    mgr.start()

    logger.info("Enqueuing %d StandardAnalyticsEvent objects...", args.events)
    t0 = time.time()

    event_types = ["ZONE_ENTER", "ZONE_EXIT", "CROWD_ALERT", "LOITERING", "QUEUE_ALERT"]

    for i in range(1, args.events + 1):
        evt_type = event_types[i % len(event_types)]
        sev = EventSeverity.CRITICAL.value if "ALERT" in evt_type else EventSeverity.INFO.value

        evt = StandardAnalyticsEvent(
            event_type=evt_type,
            analytics_module="benchmark_module",
            message=f"Validation benchmark event #{i} ({evt_type})",
            camera_id="cam_comm_bench",
            camera_name="Communication Benchmark Cam",
            severity=sev,
            track_id=i % 10,
            zone_id="z_bench",
            frame_index=i,
            payload={"counter": i, "status": "OK"},
        )
        mgr.enqueue(evt)

    elapsed_enqueue = time.time() - t0
    logger.info("Enqueued %d events in %.3f sec (%.1f events/sec enqueue throughput)", args.events, elapsed_enqueue, args.events / max(0.001, elapsed_enqueue))

    # Wait for background queue processing
    time.sleep(1.0)
    mgr.stop()

    metrics = mgr.get_metrics()
    health = mgr.get_health_status()

    logger.info("================================================================================")
    logger.info("COMMUNICATION LAYER BENCHMARK RESULTS")
    logger.info("================================================================================")
    logger.info("Total Events Enqueued:       %d events", metrics.total_events)
    logger.info("Events Published (Deliveries): %d deliveries", metrics.published_events)
    logger.info("Events Failed:               %d failures", metrics.failed_events)
    logger.info("Events Dropped (Queue Full): %d dropped", metrics.dropped_events)
    logger.info("Avg Worker Publish Latency:  %.3f ms / event", metrics.avg_publish_time_ms)
    logger.info("--------------------------------------------------------------------------------")
    logger.info("PUBLISHER HEALTH SNAPSHOT:")
    for pub_name, pub_h in health.get("publishers", {}).items():
        logger.info(
            "  - [%-14s] Enabled: %-5s | Healthy: %-5s | Delivered: %-4d | Retries: %d | Avg Latency: %.2f ms",
            pub_name,
            str(pub_h["enabled"]),
            str(pub_h["healthy"]),
            pub_h["success_count"],
            pub_h["retry_count"],
            pub_h["avg_latency_ms"],
        )
    logger.info("================================================================================")
    logger.info("Sprint 12.2 Communication Layer validation complete.")


if __name__ == "__main__":
    main()
