warning: in the working copy of 'adapters/detection/fake_detector.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'communication/__init__.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'communication/manager.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'communication/models.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'communication/publisher_base.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'communication/publisher_manager.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'communication/publishers/log_publisher.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'communication/publishers/mqtt_publisher.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'communication/publishers/rabbitmq_publisher.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'communication/registry.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'config/schema.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/frame_context.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/pipeline.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/runtime.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'diagnostics/__init__.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'diagnostics/collector.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'entities/factory.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'entities/serializer.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'models/detection.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'plugins/dwell_time/manifest.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'plugins/dwell_time/module.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'sdk/__init__.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_communication.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runtime_diagnostics.py', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/adapters/detection/fake_detector.py b/adapters/detection/fake_detector.py[m
[1mindex 35ff0e4..464b28c 100644[m
[1m--- a/adapters/detection/fake_detector.py[m
[1m+++ b/adapters/detection/fake_detector.py[m
[36m@@ -34,6 +34,7 @@[m [mfrom camera_analytics.models.detection import ([m
     Detection,[m
     DetectionClass,[m
     Keypoint,[m
[32m+[m[32m    PoseKeypoints,[m
 )[m
 [m
 if TYPE_CHECKING:[m
[36m@@ -210,9 +211,9 @@[m [mclass FakeDetector(DetectorPort):[m
         confidence = self._rng.uniform(*self._confidence_range)[m
 [m
         # Optional pose keypoints[m
[31m-        keypoints: list[Keypoint] = [][m
[32m+[m[32m        keypoints: PoseKeypoints | None = None[m
         if self._generate_pose:[m
[31m-            keypoints = self._generate_keypoints(bbox)[m
[32m+[m[32m            keypoints = PoseKeypoints(keypoints=tuple(self._generate_keypoints(bbox)))[m
 [m
         return Detection([m
             bbox=bbox,[m
[1mdiff --git a/communication/__init__.py b/communication/__init__.py[m
[1mindex de46241..011f241 100644[m
[1m--- a/communication/__init__.py[m
[1m+++ b/communication/__init__.py[m
[36m@@ -2,7 +2,7 @@[m
 Event Communication Layer Package.[m
 [m
 Provides high-throughput, non-blocking, transport-agnostic, plugin-based event communication[m
[31m-and publishing infrastructure for external integrations (Log, MQTT, WebSocket, Kafka, RabbitMQ).[m
[32m+[m[32mand publishing infrastructure for external integrations (Log, MQTT, REST Webhook, Console, RabbitMQ).[m
 """[m
 [m
 from camera_analytics.communication.manager import ([m
[36m@@ -11,21 +11,27 @@[m [mfrom camera_analytics.communication.manager import ([m
 )[m
 from camera_analytics.communication.models import ([m
     AnalyticsEventSerializer,[m
[32m+[m[32m    EventDetailLevel,[m
     EventSeverity,[m
     StandardAnalyticsEvent,[m
 )[m
 from camera_analytics.communication.publisher_base import EventPublisher[m
 from camera_analytics.communication.publisher_manager import PublisherManager[m
[32m+[m[32mfrom camera_analytics.communication.publishers.console_publisher import ConsolePublisher[m
 from camera_analytics.communication.publishers.log_publisher import LogPublisher[m
 from camera_analytics.communication.publishers.mqtt_publisher import MQTTPublisher[m
[32m+[m[32mfrom camera_analytics.communication.publishers.rabbitmq_publisher import RabbitMQPublisher[m
[32m+[m[32mfrom camera_analytics.communication.publishers.rest_publisher import RestPublisher[m
 from camera_analytics.communication.registry import ([m
     PublisherRegistry,[m
     register_publisher,[m
 )[m
[32m+[m[32mfrom camera_analytics.communication.router import EventRouter, EventRoutingRule[m
 [m
 __all__ = [[m
     "StandardAnalyticsEvent",[m
     "EventSeverity",[m
[32m+[m[32m    "EventDetailLevel",[m
     "AnalyticsEventSerializer",[m
     "EventPublisher",[m
     "PublisherRegistry",[m
[36m@@ -33,6 +39,11 @@[m [m__all__ = [[m
     "PublisherManager",[m
     "CommunicationManager",[m
     "CommunicationMetrics",[m
[32m+[m[32m    "EventRouter",[m
[32m+[m[32m    "EventRoutingRule",[m
     "LogPublisher",[m
     "MQTTPublisher",[m
[32m+[m[32m    "RabbitMQPublisher",[m
[32m+[m[32m    "RestPublisher",[m
[32m+[m[32m    "ConsolePublisher",[m
 ][m
[1mdiff --git a/communication/manager.py b/communication/manager.py[m
[1mindex 5fa866d..3fac314 100644[m
[1m--- a/communication/manager.py[m
[1m+++ b/communication/manager.py[m
[36m@@ -2,8 +2,8 @@[m
 Communication Manager and Event Queue Coordinator.[m
 [m
 Central singleton controller managing the thread-safe `PublishQueue`, background worker thread,[m
[31m-and `PublisherManager`. Guarantees non-blocking event emission for AI Pipeline processing loops,[m
[31m-tracks communication runtime metrics, and handles graceful shutdown.[m
[32m+[m[32m`EventRouter`, and `PublisherManager`. Guarantees non-blocking event emission for AI Pipeline[m
[32m+[m[32mprocessing loops, tracks communication runtime metrics, and handles graceful shutdown.[m
 """[m
 [m
 from __future__ import annotations[m
[36m@@ -21,6 +21,7 @@[m [mfrom camera_analytics.communication.models import ([m
 )[m
 from camera_analytics.communication.publisher_base import EventPublisher[m
 from camera_analytics.communication.publisher_manager import PublisherManager[m
[32m+[m[32mfrom camera_analytics.communication.router import EventRouter[m
 [m
 logger = logging.getLogger(__name__)[m
 [m
[36m@@ -45,8 +46,9 @@[m [mclass CommunicationManager:[m
     Features:[m
         - Non-blocking event enqueueing (`enqueue`).[m
         - Thread-safe bounded Queue (`queue_size`).[m
[32m+[m[32m        - Integrated `EventRouter` for rule-based destination filtering.[m
         - Background worker thread processing events asynchronously.[m
[31m-        - Runtime performance metrics calculation.[m
[32m+[m[32m        - Runtime performance metrics & health status calculation.[m
         - Graceful flush and shutdown.[m
     """[m
 [m
[36m@@ -59,6 +61,7 @@[m [mclass CommunicationManager:[m
         self._queue: queue.Queue[StandardAnalyticsEvent] = queue.Queue(maxsize=queue_size)[m
 [m
         self._publisher_manager = PublisherManager()[m
[32m+[m[32m        self._router = EventRouter()[m
         self._serializer = AnalyticsEventSerializer()[m
 [m
         self._is_initialized = False[m
[36m@@ -96,13 +99,18 @@[m [mclass CommunicationManager:[m
         """Reference to internal PublisherManager."""[m
         return self._publisher_manager[m
 [m
[32m+[m[32m    @property[m
[32m+[m[32m    def router(self) -> EventRouter:[m
[32m+[m[32m        """Reference to internal EventRouter."""[m
[32m+[m[32m        return self._router[m
[32m+[m
     @property[m
     def is_running(self) -> bool:[m
         """Whether the communication manager and worker thread are running."""[m
         return self._is_running[m
 [m
     def initialize(self, config: dict[str, Any]) -> None:[m
[31m-        """Initialize communication manager and publisher manager from configuration.[m
[32m+[m[32m        """Initialize communication manager, event router, and publisher manager from configuration.[m
 [m
         Args:[m
             config: Communication configuration dictionary.[m
[36m@@ -115,8 +123,13 @@[m [mclass CommunicationManager:[m
         if self._queue.maxsize != self._queue_size:[m
             self._queue = queue.Queue(maxsize=self._queue_size)[m
 [m
[32m+[m[32m        # Load routing rules[m
[32m+[m[32m        routing_rules = comm_cfg.get("routing_rules", [])[m
[32m+[m[32m        if routing_rules:[m
[32m+[m[32m            self._router.load_rules(routing_rules)[m
[32m+[m
         # Load publishers from config[m
[31m-        pub_configs = config.get("publishers", [])[m
[32m+[m[32m        pub_configs = config.get("publishers", comm_cfg.get("publishers", []))[m
         if pub_configs:[m
             self._publisher_manager.load_from_config(pub_configs)[m
 [m
[36m@@ -173,6 +186,7 @@[m [mclass CommunicationManager:[m
         """Retrieve current runtime metrics snapshot."""[m
         with self._metrics_lock:[m
             avg_time = (sum(self._publish_times) / max(len(self._publish_times), 1)) if self._publish_times else 0.0[m
[32m+[m[32m            total_retries = sum(p.get_health().get("retry_count", 0) for p in self._publisher_manager.publishers.values())[m
             return CommunicationMetrics([m
                 total_events=self._total_events,[m
                 published_events=self._published_events,[m
[36m@@ -180,10 +194,19 @@[m [mclass CommunicationManager:[m
                 queue_size=self._queue.qsize(),[m
                 dropped_events=self._dropped_events,[m
                 publisher_errors=self._publisher_errors,[m
[31m-                retry_count=0,[m
[32m+[m[32m                retry_count=total_retries,[m
                 avg_publish_time_ms=avg_time,[m
             )[m
 [m
[32m+[m[32m    def get_health_status(self) -> dict[str, Any]:[m
[32m+[m[32m        """Retrieve health status snapshot across all publishers."""[m
[32m+[m[32m        return {[m
[32m+[m[32m            "is_running": self._is_running,[m
[32m+[m[32m            "queue_size": self._queue.qsize(),[m
[32m+[m[32m            "max_queue_size": self._queue_size,[m
[32m+[m[32m            "publishers": self._publisher_manager.get_health_status(),[m
[32m+[m[32m        }[m
[32m+[m
     def stop(self) -> None:[m
         """Flush pending queue items and stop worker thread cleanly."""[m
         if not self._is_running:[m
[36m@@ -214,7 +237,7 @@[m [mclass CommunicationManager:[m
     # --- Internal Background Worker Loop ---[m
 [m
     def _worker_loop(self) -> None:[m
[31m-        """Background thread loop that dequeues events, serializes, and broadcasts to publishers."""[m
[32m+[m[32m        """Background thread loop that dequeues events, routes, serializes, and broadcasts."""[m
         while not self._stop_event.is_set() or not self._queue.empty():[m
             try:[m
                 event = self._queue.get(timeout=0.1)[m
[36m@@ -223,11 +246,15 @@[m [mclass CommunicationManager:[m
 [m
             t0 = time.monotonic()[m
             try:[m
[32m+[m[32m                # Route event to target publisher names[m
[32m+[m[32m                active_names = list(self._publisher_manager.publishers.keys())[m
[32m+[m[32m                target_names = self._router.route(event, active_names)[m
[32m+[m
                 # Step 1: Standardized Serialization[m
                 json_payload = self._serializer.serialize(event)[m
 [m
[31m-                # Step 2: Broadcast to all active publishers[m
[31m-                succ, fail = self._publisher_manager.broadcast(event, json_payload)[m
[32m+[m[32m                # Step 2: Broadcast to target publishers[m
[32m+[m[32m                succ, fail = self._publisher_manager.broadcast(event, json_payload, target_publishers=target_names)[m
 [m
                 t1 = time.monotonic()[m
                 duration_ms = (t1 - t0) * 1000.0[m
[36m@@ -252,8 +279,10 @@[m [mclass CommunicationManager:[m
         while not self._queue.empty():[m
             try:[m
                 event = self._queue.get_nowait()[m
[32m+[m[32m                active_names = list(self._publisher_manager.publishers.keys())[m
[32m+[m[32m                target_names = self._router.route(event, active_names)[m
                 json_payload = self._serializer.serialize(event)[m
[31m-                succ, fail = self._publisher_manager.broadcast(event, json_payload)[m
[32m+[m[32m                succ, fail = self._publisher_manager.broadcast(event, json_payload, target_publishers=target_names)[m
                 with self._metrics_lock:[m
                     self._published_events += succ[m
                     self._failed_events += fail[m
[1mdiff --git a/communication/models.py b/communication/models.py[m
[1mindex 18a76b7..75071c9 100644[m
[1m--- a/communication/models.py[m
[1m+++ b/communication/models.py[m
[36m@@ -1,8 +1,8 @@[m
 """[m
 Communication Layer Data Models & Event Serializer.[m
 [m
[31m-Defines the enterprise standard `StandardAnalyticsEvent` data structure and `AnalyticsEventSerializer`[m
[31m-for consistent JSON serialization across all network transport publishers (Log, MQTT, Kafka, etc.).[m
[32m+[m[32mDefines the enterprise standard `StandardAnalyticsEvent` data structure, `EventDetailLevel` enum,[m
[32m+[m[32mand `AnalyticsEventSerializer` for consistent JSON serialization across all network transport publishers.[m
 """[m
 [m
 from __future__ import annotations[m
[36m@@ -10,11 +10,12 @@[m [mfrom __future__ import annotations[m
 import datetime[m
 import json[m
 import uuid[m
[31m-from dataclasses import asdict, dataclass, field[m
[32m+[m[32mfrom dataclasses import dataclass, field[m
 from enum import Enum[m
 from typing import Any, Optional[m
 [m
 FRAMEWORK_VERSION = "v1.0.0"[m
[32m+[m[32mSCHEMA_VERSION = "1.0"[m
 [m
 [m
 class EventSeverity(Enum):[m
[36m@@ -26,6 +27,14 @@[m [mclass EventSeverity(Enum):[m
     CRITICAL = "CRITICAL"[m
 [m
 [m
[32m+[m[32mclass EventDetailLevel(Enum):[m
[32m+[m[32m    """Logging detail level classification for event payload serialization."""[m
[32m+[m
[32m+[m[32m    SUMMARY = "summary"      # Production default: 300-700 bytes (Business Event)[m
[32m+[m[32m    STANDARD = "standard"    # Production debugging: 700-1200 bytes[m
[32m+[m[32m    FULL = "full"            # Dev & AI diagnostics: 2000-3500 bytes (Telemetry)[m
[32m+[m
[32m+[m
 @dataclass(slots=True)[m
 class StandardAnalyticsEvent:[m
     """Enterprise Standard Analytics Event Payload.[m
[36m@@ -33,15 +42,17 @@[m [mclass StandardAnalyticsEvent:[m
     Transport-agnostic schema emitted by Analytics Modules to external communication publishers.[m
 [m
     Attributes:[m
[31m-        event_id: Unique UUID string identifier.[m
[31m-        timestamp: UTC ISO8601 formatted timestamp string.[m
[31m-        camera_id: Unique string camera identifier.[m
[31m-        camera_name: Human-readable camera name.[m
[31m-        analytics_module: Originating Analytics Module name.[m
[32m+[m[32m        event_id: Unique UUID v4 string identifier.[m
[32m+[m[32m        schema_version: Event schema version string (default "1.0").[m
         event_type: String identifier of event classification (e.g. 'ZONE_ENTER').[m
[32m+[m[32m        analytics_module: Originating Analytics Module name.[m
[32m+[m[32m        source_module: Alias for analytics_module for backwards compatibility.[m
         severity: Event severity level ('INFO', 'WARNING', 'ALERT', 'CRITICAL').[m
         message: Human-readable event description.[m
[31m-        correlation_id: Optional tracking correlation ID.[m
[32m+[m[32m        timestamp: UTC ISO8601 formatted timestamp string.[m
[32m+[m[32m        correlation_id: Unique string UUID for distributed tracing.[m
[32m+[m[32m        camera_id: Unique string camera identifier.[m
[32m+[m[32m        camera_name: Human-readable camera name.[m
         track_id: Optional associated Track ID.[m
         zone_id: Optional associated Zone ID.[m
         zone_name: Optional associated Zone name.[m
[36m@@ -51,17 +62,19 @@[m [mclass StandardAnalyticsEvent:[m
         framework_version: Platform framework version string.[m
     """[m
 [m
[31m-    event_type: str[m
[31m-    message: str[m
[32m+[m[32m    event_type: str = "GENERIC_EVENT"[m
[32m+[m[32m    message: str = ""[m
     analytics_module: str = "UnknownModule"[m
[32m+[m[32m    source_module: Optional[str] = None[m
     camera_id: str = "default_cam"[m
     camera_name: str = "Default Camera"[m
     event_id: str = field(default_factory=lambda: str(uuid.uuid4()))[m
[32m+[m[32m    schema_version: str = SCHEMA_VERSION[m
     timestamp: str = field([m
         default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()[m
     )[m
     severity: str = EventSeverity.INFO.value[m
[31m-    correlation_id: Optional[str] = None[m
[32m+[m[32m    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))[m
     track_id: Optional[int] = None[m
     zone_id: Optional[str] = None[m
     zone_name: Optional[str] = None[m
[36m@@ -70,49 +83,195 @@[m [mclass StandardAnalyticsEvent:[m
     metadata: dict[str, Any] = field(default_factory=dict)[m
     framework_version: str = FRAMEWORK_VERSION[m
 [m
[31m-    def to_dict(self) -> dict[str, Any]:[m
[31m-        """Convert event payload to a clean dictionary."""[m
[31m-        return {[m
[31m-            "event_id": self.event_id,[m
[31m-            "timestamp": self.timestamp,[m
[31m-            "camera_id": self.camera_id,[m
[31m-            "camera_name": self.camera_name,[m
[31m-            "analytics_module": self.analytics_module,[m
[31m-            "event_type": self.event_type,[m
[31m-            "severity": self.severity,[m
[31m-            "message": self.message,[m
[31m-            "correlation_id": self.correlation_id,[m
[31m-            "track_id": self.track_id,[m
[31m-            "zone_id": self.zone_id,[m
[31m-            "zone_name": self.zone_name,[m
[31m-            "frame_index": self.frame_index,[m
[31m-            "payload": self.payload,[m
[31m-            "metadata": self.metadata,[m
[31m-            "framework_version": self.framework_version,[m
[31m-        }[m
[32m+[m[32m    def __post_init__(self) -> None:[m
[32m+[m[32m        """Synchronize analytics_module and source_module fields."""[m
[32m+[m[32m        if hasattr(self.severity, "value"):[m
[32m+[m[32m            object.__setattr__(self, "severity", self.severity.value)[m
[32m+[m[32m        if self.source_module and (not self.analytics_module or self.analytics_module == "UnknownModule"):[m
[32m+[m[32m            object.__setattr__(self, "analytics_module", self.source_module)[m
[32m+[m[32m        elif self.analytics_module and not self.source_module:[m
[32m+[m[32m            object.__setattr__(self, "source_module", self.analytics_module)[m
[32m+[m
[32m+[m[32m    def _build_optimized_payload(self, detail_level: EventDetailLevel) -> dict[str, Any]:[m
[32m+[m[32m        """Compact payload dictionary based on requested detail level."""[m
[32m+[m[32m        if not isinstance(self.payload, dict):[m
[32m+[m[32m            return self.payload[m
[32m+[m
[32m+[m[32m        p = dict(self.payload)[m
[32m+[m
[32m+[m[32m        # Strip redundant duplicated fields inside payload[m
[32m+[m[32m        p.pop("camera_id", None)[m
[32m+[m[32m        p.pop("timestamp", None)[m
[32m+[m
[32m+[m[32m        # Handle track dict optimization if present inside payload[m
[32m+[m[32m        if "track" in p and isinstance(p["track"], dict):[m
[32m+[m[32m            tr = dict(p["track"])[m
[32m+[m
[32m+[m[32m            # Strip pose in SUMMARY and STANDARD modes[m
[32m+[m[32m            if detail_level != EventDetailLevel.FULL:[m
[32m+[m[32m                tr.pop("pose", None)[m
[32m+[m
[32m+[m[32m            # Compact bbox dictionary to [x1, y1, x2, y2] list[m
[32m+[m[32m            if "bbox" in tr and isinstance(tr["bbox"], dict):[m
[32m+[m[32m                b = tr["bbox"][m
[32m+[m[32m                if "x1" in b and "y1" in b and "x2" in b and "y2" in b:[m
[32m+[m[32m                    tr["bbox"] = [b["x1"], b["y1"], b["x2"], b["y2"]][m
[32m+[m
[32m+[m[32m            # Compact ground point to [x, y] list[m
[32m+[m[32m            if "ground_point" in tr and isinstance(tr["ground_point"], dict):[m
[32m+[m[32m                gp = tr["ground_point"][m
[32m+[m[32m                if "x" in gp and "y" in gp:[m
[32m+[m[32m                    tr["ground_point"] = [gp["x"], gp["y"]][m
[32m+[m
[32m+[m[32m            # In SUMMARY mode, retain only essential track fields[m
[32m+[m[32m            if detail_level == EventDetailLevel.SUMMARY:[m
[32m+[m[32m                tr.pop("feature_store", None)[m
[32m+[m[32m                tr.pop("velocity", None)[m
[32m+[m[32m                tr.pop("direction", None)[m
[32m+[m
[32m+[m[32m            p["track"] = tr[m
[32m+[m
[32m+[m[32m        # Compact top-level bbox in payload if present as dict[m
[32m+[m[32m        if "bbox" in p and isinstance(p["bbox"], dict):[m
[32m+[m[32m            b = p["bbox"][m
[32m+[m[32m            if "x1" in b and "y1" in b and "x2" in b and "y2" in b:[m
[32m+[m[32m                p["bbox"] = [b["x1"], b["y1"], b["x2"], b["y2"]][m
[32m+[m
[32m+[m[32m        # Compact ground point in payload if present as dict[m
[32m+[m[32m        if "ground_point" in p and isinstance(p["ground_point"], dict):[m
[32m+[m[32m            gp = p["ground_point"][m
[32m+[m[32m            if "x" in gp and "y" in gp:[m
[32m+[m[32m                p["ground_point"] = [gp["x"], gp["y"]][m
[32m+[m
[32m+[m[32m        return p[m
[32m+[m
[32m+[m[32m    def to_dict(self, detail_level: Optional[EventDetailLevel | str] = None) -> dict[str, Any]:[m
[32m+[m[32m        """Convert event payload to clean dictionary optimized for the requested detail level."""[m
[32m+[m[32m        mod_name = self.analytics_module or self.source_module or "UnknownModule"[m
[32m+[m
[32m+[m[32m        if detail_level is None:[m
[32m+[m[32m            # Default to full canonical representation for backward compatibility[m
[32m+[m[32m            return {[m
[32m+[m[32m                "event_id": self.event_id,[m
[32m+[m[32m                "schema_version": self.schema_version,[m
[32m+[m[32m                "event_type": self.event_type,[m
[32m+[m[32m                "analytics_module": mod_name,[m
[32m+[m[32m                "source_module": mod_name,[m
[32m+[m[32m                "severity": self.severity,[m
[32m+[m[32m                "message": self.message,[m
[32m+[m[32m                "timestamp": self.timestamp,[m
[32m+[m[32m                "correlation_id": self.correlation_id,[m
[32m+[m[32m                "camera_id": self.camera_id,[m
[32m+[m[32m                "camera_name": self.camera_name,[m
[32m+[m[32m                "track_id": self.track_id,[m
[32m+[m[32m                "zone_id": self.zone_id,[m
[32m+[m[32m                "zone_name": self.zone_name,[m
[32m+[m[32m                "frame_index": self.frame_index,[m
[32m+[m[32m                "payload": self.payload,[m
[32m+[m[32m                "metadata": self.metadata,[m
[32m+[m[32m                "framework_version": self.framework_version,[m
[32m+[m[32m            }[m
[32m+[m
[32m+[m[32m        if isinstance(detail_level, str):[m
[32m+[m[32m            try:[m
[32m+[m[32m                detail_level = EventDetailLevel(detail_level.lower())[m
[32m+[m[32m            except ValueError:[m
[32m+[m[32m                detail_level = EventDetailLevel.SUMMARY[m
[32m+[m
[32m+[m[32m        clean_payload = self._build_optimized_payload(detail_level)[m
[32m+[m
[32m+[m[32m        if detail_level == EventDetailLevel.SUMMARY:[m
[32m+[m[32m            # Compact Business Event: Exclude nested heavy camera/frame/pose objects[m
[32m+[m[32m            res = {[m
[32m+[m[32m                "event_id": self.event_id,[m
[32m+[m[32m                "schema_version": self.schema_version,[m
[32m+[m[32m                "event_type": self.event_type,[m
[32m+[m[32m                "analytics_module": mod_name,[m
[32m+[m[32m                "severity": self.severity,[m
[32m+[m[32m                "timestamp": self.timestamp,[m
[32m+[m[32m                "correlation_id": self.correlation_id,[m
[32m+[m[32m                "camera_id": self.camera_id,[m
[32m+[m[32m                "frame_index": self.frame_index,[m
[32m+[m[32m                "payload": clean_payload,[m
[32m+[m[32m            }[m
[32m+[m[32m            if self.track_id is not None:[m
[32m+[m[32m                res["track_id"] = self.track_id[m
[32m+[m[32m            if self.zone_id is not None:[m
[32m+[m[32m                res["zone_id"] = self.zone_id[m
[32m+[m[32m            if self.zone_name is not None:[m
[32m+[m[32m                res["zone_name"] = self.zone_name[m
[32m+[m[32m            return res[m
[32m+[m
[32m+[m[32m        elif detail_level == EventDetailLevel.STANDARD:[m
[32m+[m[32m            # Production Debugging Mode[m
[32m+[m[32m            res = {[m
[32m+[m[32m                "event_id": self.event_id,[m
[32m+[m[32m                "schema_version": self.schema_version,[m
[32m+[m[32m                "event_type": self.event_type,[m
[32m+[m[32m                "analytics_module": mod_name,[m
[32m+[m[32m                "severity": self.severity,[m
[32m+[m[32m                "message": self.message,[m
[32m+[m[32m                "timestamp": self.timestamp,[m
[32m+[m[32m                "correlation_id": self.correlation_id,[m
[32m+[m[32m                "camera_id": self.camera_id,[m
[32m+[m[32m                "camera_name": self.camera_name,[m
[32m+[m[32m                "track_id": self.track_id,[m
[32m+[m[32m                "zone_id": self.zone_id,[m
[32m+[m[32m                "zone_name": self.zone_name,[m
[32m+[m[32m                "frame_index": self.frame_index,[m
[32m+[m[32m                "payload": clean_payload,[m
[32m+[m[32m            }[m
[32m+[m[32m            return res[m
[32m+[m
[32m+[m[32m        else:[m
[32m+[m[32m            # FULL mode (Development / Diagnostics)[m
[32m+[m[32m            return {[m
[32m+[m[32m                "event_id": self.event_id,[m
[32m+[m[32m                "schema_version": self.schema_version,[m
[32m+[m[32m                "event_type": self.event_type,[m
[32m+[m[32m                "analytics_module": mod_name,[m
[32m+[m[32m                "source_module": mod_name,[m
[32m+[m[32m                "severity": self.severity,[m
[32m+[m[32m                "message": self.message,[m
[32m+[m[32m                "timestamp": self.timestamp,[m
[32m+[m[32m                "correlation_id": self.correlation_id,[m
[32m+[m[32m                "camera_id": self.camera_id,[m
[32m+[m[32m                "camera_name": self.camera_name,[m
[32m+[m[32m                "track_id": self.track_id,[m
[32m+[m[32m                "zone_id": self.zone_id,[m
[32m+[m[32m                "zone_name": self.zone_name,[m
[32m+[m[32m                "frame_index": self.frame_index,[m
[32m+[m[32m                "payload": clean_payload,[m
[32m+[m[32m                "metadata": self.metadata,[m
[32m+[m[32m                "framework_version": self.framework_version,[m
[32m+[m[32m            }[m
 [m
 [m
 class AnalyticsEventSerializer:[m
     """Thread-safe JSON Serializer for StandardAnalyticsEvent instances.[m
 [m
[31m-    Guarantees consistent JSON structure for all publishers.[m
[32m+[m[32m    Guarantees strict single-line NDJSON format with UTF-8 encoding.[m
     """[m
 [m
     @staticmethod[m
[31m-    def serialize(event: StandardAnalyticsEvent) -> str:[m
[31m-        """Serialize a StandardAnalyticsEvent into a JSON string formatted payload.[m
[32m+[m[32m    def serialize([m
[32m+[m[32m        event: StandardAnalyticsEvent,[m
[32m+[m[32m        detail_level: EventDetailLevel | str = EventDetailLevel.SUMMARY,[m
[32m+[m[32m    ) -> str:[m
[32m+[m[32m        """Serialize a StandardAnalyticsEvent into a single-line compact JSON string payload.[m
 [m
         Args:[m
             event: StandardAnalyticsEvent dataclass instance.[m
[32m+[m[32m            detail_level: Desired detail level ('summary', 'standard', 'full').[m
 [m
         Returns:[m
[31m-            JSON string.[m
[32m+[m[32m            Single-line JSON string without raw newlines.[m
         """[m
[31m-        return json.dumps(event.to_dict(), ensure_ascii=False)[m
[32m+[m[32m        return json.dumps(event.to_dict(detail_level=detail_level), ensure_ascii=False, separators=(",", ":"))[m
 [m
     @staticmethod[m
     def deserialize(json_str: str) -> dict[str, Any]:[m
[31m-        """Deserialize a JSON payload back into a dictionary.[m
[32m+[m[32m        """Deserialize a JSON payload string back into a dictionary.[m
 [m
         Args:[m
             json_str: Valid JSON formatted string.[m
[1mdiff --git a/communication/publisher_base.py b/communication/publisher_base.py[m
[1mindex 4a71f9a..8dd6eb4 100644[m
[1m--- a/communication/publisher_base.py[m
[1m+++ b/communication/publisher_base.py[m
[36m@@ -2,12 +2,13 @@[m
 Event Publisher Base Contract.[m
 [m
 Defines the abstract base class `EventPublisher` with full lifecycle contracts[m
[31m-for external communication publishers (Log, MQTT, WebSocket, Kafka, RabbitMQ, etc.).[m
[32m+[m[32mfor external communication publishers (Log, MQTT, REST HTTP, Console, RabbitMQ, etc.).[m
 """[m
 [m
 from __future__ import annotations[m
 [m
 import logging[m
[32m+[m[32mimport time[m
 from abc import ABC, abstractmethod[m
 from typing import TYPE_CHECKING, Any, Optional[m
 [m
[36m@@ -19,8 +20,8 @@[m [mlogger = logging.getLogger(__name__)[m
 class EventPublisher(ABC):[m
     """Abstract Base Class for all external communication publishers in the platform.[m
 [m
[31m-    Provides standard lifecycle management (initialize, start, publish, flush, stop, dispose)[m
[31m-    and health status monitoring.[m
[32m+[m[32m    Provides standard lifecycle management (initialize, start, publish, flush, stop, dispose),[m
[32m+[m[32m    exponential retry mechanisms, and health status monitoring.[m
 [m
     Attributes:[m
         name: String identifier of the publisher instance.[m
[36m@@ -33,6 +34,10 @@[m [mclass EventPublisher(ABC):[m
         self._is_initialized = False[m
         self._is_running = False[m
         self._is_healthy = True[m
[32m+[m[32m        self._success_count = 0[m
[32m+[m[32m        self._failure_count = 0[m
[32m+[m[32m        self._retry_count = 0[m
[32m+[m[32m        self._total_latency_ms = 0.0[m
 [m
     @property[m
     def name(self) -> str:[m
[36m@@ -59,6 +64,20 @@[m [mclass EventPublisher(ABC):[m
         """Whether the publisher connection is healthy."""[m
         return self._is_healthy[m
 [m
[32m+[m[32m    def get_health(self) -> dict[str, Any]:[m
[32m+[m[32m        """Get publisher health status and operational metrics."""[m
[32m+[m[32m        avg_lat = self._total_latency_ms / max(1, self._success_count) if self._success_count > 0 else 0.0[m
[32m+[m[32m        return {[m
[32m+[m[32m            "name": self._name,[m
[32m+[m[32m            "enabled": self._enabled,[m
[32m+[m[32m            "running": self._is_running,[m
[32m+[m[32m            "healthy": self._is_healthy,[m
[32m+[m[32m            "success_count": self._success_count,[m
[32m+[m[32m            "failure_count": self._failure_count,[m
[32m+[m[32m            "retry_count": self._retry_count,[m
[32m+[m[32m            "avg_latency_ms": round(avg_lat, 2),[m
[32m+[m[32m        }[m
[32m+[m
     # --- Lifecycle Contracts ---[m
 [m
     def initialize(self, config: dict[str, Any]) -> None:[m
[36m@@ -93,6 +112,18 @@[m [mclass EventPublisher(ABC):[m
         """[m
         pass[m
 [m
[32m+[m[32m    def record_publish_metrics(self, success: bool, latency_ms: float, retries: int = 0) -> None:[m
[32m+[m[32m        """Record telemetry metrics for a publish attempt."""[m
[32m+[m[32m        self._retry_count += retries[m
[32m+[m[32m        if success:[m
[32m+[m[32m            self._success_count += 1[m
[32m+[m[32m            self._total_latency_ms += latency_ms[m
[32m+[m[32m            self._is_healthy = True[m
[32m+[m[32m        else:[m
[32m+[m[32m            self._failure_count += 1[m
[32m+[m[32m            if self._failure_count > 5:[m
[32m+[m[32m                self._is_healthy = False[m
[32m+[m
     def flush(self) -> None:[m
         """Flush pending buffered messages or file buffers to disk/network."""[m
         if self._is_running:[m
[1mdiff --git a/communication/publisher_manager.py b/communication/publisher_manager.py[m
[1mindex cbafd5d..4afcb82 100644[m
[1m--- a/communication/publisher_manager.py[m
[1m+++ b/communication/publisher_manager.py[m
[36m@@ -8,7 +8,7 @@[m [mmonitors publisher health, and enforces Exception Isolation across all publisher[m
 from __future__ import annotations[m
 [m
 import logging[m
[31m-from typing import TYPE_CHECKING, Any, Sequence[m
[32m+[m[32mfrom typing import TYPE_CHECKING, Any, Optional, Sequence[m
 [m
 from camera_analytics.communication.models import StandardAnalyticsEvent[m
 from camera_analytics.communication.publisher_base import EventPublisher[m
[36m@@ -71,6 +71,10 @@[m [mclass PublisherManager:[m
                 logger.error("PublisherManager: Failed to load publisher '%s' of type '%s' (%s)",[m
                              pub_name, pub_type, exc)[m
 [m
[32m+[m[32m    def get_health_status(self) -> dict[str, dict[str, Any]]:[m
[32m+[m[32m        """Get health status snapshot for all registered publishers."""[m
[32m+[m[32m        return {name: pub.get_health() for name, pub in self._publishers.items()}[m
[32m+[m
     # --- Lifecycle Contracts ---[m
 [m
     def initialize(self, global_config: Optional[dict[str, Any]] = None) -> None:[m
[36m@@ -103,12 +107,18 @@[m [mclass PublisherManager:[m
         self._is_running = True[m
         logger.info("PublisherManager: Started %d publisher(s)", len(self._publishers))[m
 [m
[31m-    def broadcast(self, event: StandardAnalyticsEvent, serialized_payload: str) -> tuple[int, int]:[m
[31m-        """Broadcast serialized event payload to all active publishers with Exception Isolation.[m
[32m+[m[32m    def broadcast([m
[32m+[m[32m        self,[m
[32m+[m[32m        event: StandardAnalyticsEvent,[m
[32m+[m[32m        serialized_payload: str,[m
[32m+[m[32m        target_publishers: Optional[list[str]] = None,[m
[32m+[m[32m    ) -> tuple[int, int]:[m
[32m+[m[32m        """Broadcast serialized event payload to active target publishers with Exception Isolation.[m
 [m
         Args:[m
             event: StandardAnalyticsEvent instance.[m
             serialized_payload: Pre-serialized JSON string.[m
[32m+[m[32m            target_publishers: Optional list of target publisher names to publish to.[m
 [m
         Returns:[m
             Tuple of (successful_publishes_count, failed_publishes_count).[m
[36m@@ -117,6 +127,9 @@[m [mclass PublisherManager:[m
         failure_count = 0[m
 [m
         for name, pub in self._publishers.items():[m
[32m+[m[32m            if target_publishers is not None and name not in target_publishers:[m
[32m+[m[32m                continue[m
[32m+[m
             if not pub.is_running or not pub.is_enabled:[m
                 continue[m
 [m
[1mdiff --git a/communication/publishers/log_publisher.py b/communication/publishers/log_publisher.py[m
[1mindex 9630171..b1d2d37 100644[m
[1m--- a/communication/publishers/log_publisher.py[m
[1m+++ b/communication/publishers/log_publisher.py[m
[36m@@ -11,10 +11,15 @@[m [mimport datetime[m
 import logging[m
 import os[m
 import threading[m
[32m+[m[32mimport time[m
 from pathlib import Path[m
 from typing import Any, Optional, TextIO[m
 [m
[31m-from camera_analytics.communication.models import StandardAnalyticsEvent[m
[32m+[m[32mfrom camera_analytics.communication.models import ([m
[32m+[m[32m    AnalyticsEventSerializer,[m
[32m+[m[32m    EventDetailLevel,[m
[32m+[m[32m    StandardAnalyticsEvent,[m
[32m+[m[32m)[m
 from camera_analytics.communication.publisher_base import EventPublisher[m
 from camera_analytics.communication.registry import PublisherRegistry[m
 [m
[36m@@ -27,6 +32,7 @@[m [mclass LogPublisher(EventPublisher):[m
 [m
     Features:[m
         - Auto-creation of output directory.[m
[32m+[m[32m        - Configurable detail level ('summary', 'standard', 'full').[m
         - Dynamic date-based filename rotation (e.g. `events_20260723.jsonl`).[m
         - UTF-8 encoding with append mode.[m
         - Thread-safe file flush.[m
[36m@@ -37,6 +43,7 @@[m [mclass LogPublisher(EventPublisher):[m
         log_dir: Output log directory path.[m
         filename_pattern: Log file name pattern (supports `{date}`).[m
         rotate_daily: Whether to auto-rotate log files daily.[m
[32m+[m[32m        detail_level: Configurable detail level ('summary', 'standard', 'full').[m
     """[m
 [m
     def __init__([m
[36m@@ -46,11 +53,13 @@[m [mclass LogPublisher(EventPublisher):[m
         log_dir: str = "logs",[m
         filename_pattern: str = "events_{date}.jsonl",[m
         rotate_daily: bool = True,[m
[32m+[m[32m        detail_level: str = "summary",[m
     ) -> None:[m
         super().__init__(name=name, enabled=enabled)[m
         self._log_dir = Path(log_dir)[m
         self._filename_pattern = filename_pattern[m
         self._rotate_daily = rotate_daily[m
[32m+[m[32m        self._detail_level = detail_level[m
 [m
         self._file_handle: Optional[TextIO] = None[m
         self._current_file_path: Optional[Path] = None[m
[36m@@ -67,6 +76,7 @@[m [mclass LogPublisher(EventPublisher):[m
             self._log_dir = Path(config["log_dir"])[m
 [m
         self._rotate_daily = config.get("rotate_daily", self._rotate_daily)[m
[32m+[m[32m        self._detail_level = config.get("detail_level", self._detail_level)[m
 [m
     def on_start(self) -> None:[m
         """Create log directory and open initial log file stream."""[m
[36m@@ -74,11 +84,11 @@[m [mclass LogPublisher(EventPublisher):[m
         self._open_log_file()[m
 [m
     def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:[m
[31m-        """Write single JSON line payload to log file.[m
[32m+[m[32m        """Write single JSON line payload to log file formatted according to detail_level.[m
 [m
         Args:[m
             event: StandardAnalyticsEvent instance.[m
[31m-            serialized_payload: Pre-serialized JSON string.[m
[32m+[m[32m            serialized_payload: Pre-serialized JSON string (fallback).[m
 [m
         Returns:[m
             True if written successfully, False otherwise.[m
[36m@@ -86,6 +96,10 @@[m [mclass LogPublisher(EventPublisher):[m
         if not self._is_running or not self._enabled:[m
             return False[m
 [m
[32m+[m[32m        # Format payload according to configured detail level[m
[32m+[m[32m        formatted_line = AnalyticsEventSerializer.serialize(event, detail_level=self._detail_level)[m
[32m+[m
[32m+[m[32m        t_start = time.time()[m
         with self._lock:[m
             try:[m
                 # Check for daily rotation[m
[36m@@ -98,11 +112,14 @@[m [mclass LogPublisher(EventPublisher):[m
                     self._open_log_file()[m
 [m
                 if self._file_handle is not None:[m
[31m-                    self._file_handle.write(serialized_payload + "\n")[m
[32m+[m[32m                    self._file_handle.write(formatted_line + "\n")[m
[32m+[m[32m                    latency_ms = (time.time() - t_start) * 1000.0[m
[32m+[m[32m                    self.record_publish_metrics(success=True, latency_ms=latency_ms)[m
                     return True[m
             except Exception as exc:[m
                 self._is_healthy = False[m
                 logger.error("LogPublisher '%s' write error: %s", self.name, exc)[m
[32m+[m[32m                self.record_publish_metrics(success=False, latency_ms=0.0)[m
                 return False[m
 [m
         return False[m
[36m@@ -153,4 +170,4 @@[m [mclass LogPublisher(EventPublisher):[m
         self._file_handle = open(file_path, mode="a", encoding="utf-8")[m
         self._current_file_path = file_path[m
         self._is_healthy = True[m
[31m-        logger.info("LogPublisher '%s' opened log file: %s", self.name, file_path)[m
[32m+[m[32m        logger.info("LogPublisher '%s' opened log file: %s (Detail Level: %s)", self.name, file_path, self._detail_level)[m
[1mdiff --git a/communication/publishers/mqtt_publisher.py b/communication/publishers/mqtt_publisher.py[m
[1mindex 2be9726..51dd734 100644[m
[1m--- a/communication/publishers/mqtt_publisher.py[m
[1m+++ b/communication/publishers/mqtt_publisher.py[m
[36m@@ -10,6 +10,7 @@[m [mfrom __future__ import annotations[m
 [m
 import logging[m
 import threading[m
[32m+[m[32mimport time[m
 from typing import Any, Optional[m
 from urllib.parse import urlparse[m
 [m
[36m@@ -128,12 +129,15 @@[m [mclass MQTTPublisher(EventPublisher):[m
         if not self._is_running or not self._enabled:[m
             return False[m
 [m
[32m+[m[32m        t_start = time.time()[m
         # Format topic with camera_id[m
         target_topic = self._topic_template.format(camera_id=event.camera_id)[m
 [m
         if self._client is None or self._paho is None:[m
             # Fallback mock log when paho-mqtt unavailable[m
             logger.debug("MQTTPublisher [Fallback Mock] Topic '%s': %s", target_topic, serialized_payload[:80])[m
[32m+[m[32m            latency_ms = (time.time() - t_start) * 1000.0[m
[32m+[m[32m            self.record_publish_metrics(success=True, latency_ms=latency_ms)[m
             return True[m
 [m
         try:[m
[36m@@ -143,10 +147,14 @@[m [mclass MQTTPublisher(EventPublisher):[m
                 qos=self._qos,[m
                 retain=self._retain,[m
             )[m
[31m-            return info.rc == self._paho.MQTT_ERR_SUCCESS[m
[32m+[m[32m            success = info.rc == self._paho.MQTT_ERR_SUCCESS[m
[32m+[m[32m            latency_ms = (time.time() - t_start) * 1000.0[m
[32m+[m[32m            self.record_publish_metrics(success=success, latency_ms=latency_ms)[m
[32m+[m[32m            return success[m
         except Exception as exc:[m
             self._is_healthy = False[m
             logger.error("MQTTPublisher '%s' publish error on topic '%s': %s", self.name, target_topic, exc)[m
[32m+[m[32m            self.record_publish_metrics(success=False, latency_ms=0.0)[m
             return False[m
 [m
     def on_stop(self) -> None:[m
[1mdiff --git a/communication/publishers/rabbitmq_publisher.py b/communication/publishers/rabbitmq_publisher.py[m
[1mindex 3e89edc..a52f9b3 100644[m
[1m--- a/communication/publishers/rabbitmq_publisher.py[m
[1m+++ b/communication/publishers/rabbitmq_publisher.py[m
[36m@@ -129,8 +129,12 @@[m [mclass RabbitMQPublisher(EventPublisher):[m
 [m
     def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:[m
         """Publish standard analytics event."""[m
[32m+[m[32m        t_start = time.time()[m
         payload_dict = json.loads(serialized_payload)[m
[31m-        return self.publish_raw(exchange="cctv.analytics", routing_key="analytics.event", payload_dict=payload_dict)[m
[32m+[m[32m        res = self.publish_raw(exchange="cctv.analytics", routing_key="analytics.event", payload_dict=payload_dict)[m
[32m+[m[32m        latency_ms = (time.time() - t_start) * 1000.0[m
[32m+[m[32m        self.record_publish_metrics(success=res, latency_ms=latency_ms)[m
[32m+[m[32m        return res[m
 [m
     def on_stop(self) -> None:[m
         with self._lock:[m
[1mdiff --git a/communication/registry.py b/communication/registry.py[m
[1mindex 6f989d5..c6e8bd1 100644[m
[1m--- a/communication/registry.py[m
[1m+++ b/communication/registry.py[m
[36m@@ -24,23 +24,11 @@[m [mclass PublisherRegistry:[m
     """[m
 [m
     _registry: dict[str, Type[EventPublisher]] = {}[m
[32m+[m[32m    _known_classes: dict[str, Type[EventPublisher]] = {}[m
 [m
     @classmethod[m
     def register(cls, type_name: str) -> Callable[[Type[EventPublisher]], Type[EventPublisher]]:[m
[31m-        """Decorator for registering an EventPublisher subclass under a unique type key.[m
[31m-[m
[31m-        Usage::[m
[31m-[m
[31m-            @PublisherRegistry.register("mqtt")[m
[31m-            class MQTTPublisher(EventPublisher):[m
[31m-                ...[m
[31m-[m
[31m-        Args:[m
[31m-            type_name: String identifier for the publisher type (e.g. 'log', 'mqtt', 'kafka').[m
[31m-[m
[31m-        Returns:[m
[31m-            Decorator function.[m
[31m-        """[m
[32m+[m[32m        """Decorator for registering an EventPublisher subclass under a unique type key."""[m
 [m
         def decorator(publisher_cls: Type[EventPublisher]) -> Type[EventPublisher]:[m
             clean_type = type_name.strip().lower()[m
[36m@@ -49,6 +37,7 @@[m [mclass PublisherRegistry:[m
                     "PublisherRegistry: Overwriting existing publisher registration for '%s'", clean_type[m
                 )[m
             cls._registry[clean_type] = publisher_cls[m
[32m+[m[32m            cls._known_classes[clean_type] = publisher_cls[m
             logger.debug([m
                 "PublisherRegistry: Registered publisher '%s' -> %s", clean_type, publisher_cls.__name__[m
             )[m
[36m@@ -57,33 +46,31 @@[m [mclass PublisherRegistry:[m
         return decorator[m
 [m
     @classmethod[m
[31m-    def get(cls, type_name: str) -> Optional[Type[EventPublisher]]:[m
[31m-        """Retrieve registered EventPublisher class by string key.[m
[31m-[m
[31m-        Args:[m
[31m-            type_name: String identifier of publisher type.[m
[32m+[m[32m    def _ensure_defaults(cls) -> None:[m
[32m+[m[32m        """Ensure built-in publishers are registered if registry is empty."""[m
[32m+[m[32m        if not cls._registry:[m
[32m+[m[32m            if cls._known_classes:[m
[32m+[m[32m                cls._registry.update(cls._known_classes)[m
[32m+[m[32m            else:[m
[32m+[m[32m                try:[m
[32m+[m[32m                    import camera_analytics.communication.publishers.console_publisher  # noqa: F401[m
[32m+[m[32m                    import camera_analytics.communication.publishers.log_publisher      # noqa: F401[m
[32m+[m[32m                    import camera_analytics.communication.publishers.mqtt_publisher     # noqa: F401[m
[32m+[m[32m                    import camera_analytics.communication.publishers.rabbitmq_publisher # noqa: F401[m
[32m+[m[32m                    import camera_analytics.communication.publishers.rest_publisher     # noqa: F401[m
[32m+[m[32m                except Exception as exc:[m
[32m+[m[32m                    logger.debug("PublisherRegistry auto-import error: %s", exc)[m
 [m
[31m-        Returns:[m
[31m-            Registered EventPublisher class, or None if not found.[m
[31m-        """[m
[32m+[m[32m    @classmethod[m
[32m+[m[32m    def get(cls, type_name: str) -> Optional[Type[EventPublisher]]:[m
[32m+[m[32m        """Retrieve registered EventPublisher class by string key."""[m
[32m+[m[32m        cls._ensure_defaults()[m
         clean_type = type_name.strip().lower()[m
         return cls._registry.get(clean_type)[m
 [m
     @classmethod[m
     def create(cls, type_name: str, name: Optional[str] = None, **kwargs: Any) -> EventPublisher:[m
[31m-        """Instantiate a registered EventPublisher by type name.[m
[31m-[m
[31m-        Args:[m
[31m-            type_name: String identifier of publisher type (e.g. 'log', 'mqtt').[m
[31m-            name: Optional explicit instance name. Defaults to type_name.[m
[31m-            **kwargs: Additional keyword arguments passed to publisher constructor.[m
[31m-[m
[31m-        Returns:[m
[31m-            Instantiated EventPublisher instance.[m
[31m-[m
[31m-        Raises:[m
[31m-            KeyError: If no publisher is registered under the given type name.[m
[31m-        """[m
[32m+[m[32m        """Instantiate a registered EventPublisher by type name."""[m
         clean_type = type_name.strip().lower()[m
         publisher_cls = cls.get(clean_type)[m
         if publisher_cls is None:[m
[36m@@ -101,11 +88,13 @@[m [mclass PublisherRegistry:[m
     @classmethod[m
     def list_registered(cls) -> list[str]:[m
         """List all registered publisher type string identifiers."""[m
[32m+[m[32m        cls._ensure_defaults()[m
         return sorted(list(cls._registry.keys()))[m
 [m
     @classmethod[m
     def is_registered(cls, type_name: str) -> bool:[m
         """Check if a publisher type is registered."""[m
[32m+[m[32m        cls._ensure_defaults()[m
         return type_name.strip().lower() in cls._registry[m
 [m
     @classmethod[m
[1mdiff --git a/config/schema.py b/config/schema.py[m
[1mindex 9fc656f..522768a 100644[m
[1m--- a/config/schema.py[m
[1m+++ b/config/schema.py[m
[36m@@ -8,6 +8,8 @@[m [mDefines strongly-typed, immutable dataclass schemas for each subsystem:[m
     - TrackerConfig: Object tracking algorithm and matching parameters.[m
     - RunnerConfig: Execution loop parameters (skipping, frame limits).[m
     - AnalyticsConfig: Active analytics modules and module-specific settings.[m
[32m+[m[32m    - LoggingConfig: Detail level settings ('summary', 'standard', 'full').[m
[32m+[m[32m    - SerializationConfig: Granular field inclusion toggles.[m
     - AppConfig: Root configuration combining all subsystem configurations.[m
 """[m
 [m
[36m@@ -117,6 +119,34 @@[m [mclass AnalyticsConfig:[m
     module_settings: dict[str, dict[str, Any]] = field(default_factory=dict)[m
 [m
 [m
[32m+[m[32m@dataclass(frozen=True, slots=True)[m
[32m+[m[32mclass LoggingConfig:[m
[32m+[m[32m    """Configuration for enterprise logging detail levels.[m
[32m+[m
[32m+[m[32m    Attributes:[m
[32m+[m[32m        detail_level: Event logging detail level ('summary', 'standard', 'full').[m
[32m+[m[32m    """[m
[32m+[m
[32m+[m[32m    detail_level: str = "summary"[m
[32m+[m
[32m+[m
[32m+[m[32m@dataclass(frozen=True, slots=True)[m
[32m+[m[32mclass SerializationConfig:[m
[32m+[m[32m    """Configuration for event field inclusions during serialization.[m
[32m+[m
[32m+[m[32m    Attributes:[m
[32m+[m[32m        include_pose: Whether to include 17 COCO pose keypoints.[m
[32m+[m[32m        include_bbox: Whether to include object bounding boxes.[m
[32m+[m[32m        include_velocity: Whether to include velocity speed vectors.[m
[32m+[m[32m        include_runtime_metrics: Whether to include internal kernel diagnostics.[m
[32m+[m[32m    """[m
[32m+[m
[32m+[m[32m    include_pose: bool = False[m
[32m+[m[32m    include_bbox: bool = True[m
[32m+[m[32m    include_velocity: bool = False[m
[32m+[m[32m    include_runtime_metrics: bool = False[m
[32m+[m
[32m+[m
 @dataclass(frozen=True, slots=True)[m
 class AppConfig:[m
     """Root configuration combining all subsystem configurations.[m
[36m@@ -128,6 +158,8 @@[m [mclass AppConfig:[m
         tracker: Tracker algorithm configuration.[m
         runner: Runner execution configuration.[m
         analytics: Analytics modules configuration.[m
[32m+[m[32m        logging: Enterprise logging detail level configuration.[m
[32m+[m[32m        serialization: Field inclusion configuration.[m
     """[m
 [m
     camera: CameraConfig[m
[36m@@ -136,3 +168,5 @@[m [mclass AppConfig:[m
     tracker: TrackerConfig[m
     runner: RunnerConfig[m
     analytics: AnalyticsConfig[m
[32m+[m[32m    logging: LoggingConfig = field(default_factory=LoggingConfig)[m
[32m+[m[32m    serialization: SerializationConfig = field(default_factory=SerializationConfig)[m
[1mdiff --git a/core/frame_context.py b/core/frame_context.py[m
[1mindex a59dd20..20b0282 100644[m
[1m--- a/core/frame_context.py[m
[1m+++ b/core/frame_context.py[m
[36m@@ -69,6 +69,9 @@[m [mclass FrameContext:[m
     _person_tracks: tuple[Track, ...] = field([m
         default=(), repr=False, hash=False, compare=False[m
     )[m
[32m+[m[32m    zone_results: Any = field([m
[32m+[m[32m        default=None, repr=False, hash=False, compare=False[m
[32m+[m[32m    )[m
 [m
     # --- Track Queries ---[m
 [m
[1mdiff --git a/core/pipeline.py b/core/pipeline.py[m
[1mindex d2c572f..3bf40b3 100644[m
[1m--- a/core/pipeline.py[m
[1m+++ b/core/pipeline.py[m
[36m@@ -345,6 +345,15 @@[m [mclass Pipeline:[m
             else [][m
         )[m
 [m
[32m+[m[32m        # Process ZoneEngine spatial evaluation[m
[32m+[m[32m        zone_list = list(self._runtime.zones.values())[m
[32m+[m[32m        zone_results = self._runtime.zone_engine.process([m
[32m+[m[32m            tracks=self._runtime.track_manager.get_active(),[m
[32m+[m[32m            zones=zone_list,[m
[32m+[m[32m            frame_index=frame_id,[m
[32m+[m[32m            timestamp=self._runtime.elapsed_time,[m
[32m+[m[32m        )[m
[32m+[m
         # Build FrameContext[m
         context = build_frame_context([m
             frame_id=frame_id,[m
[36m@@ -355,6 +364,7 @@[m [mclass Pipeline:[m
             tracks=self._runtime.track_manager.get_active(),[m
             zones=self._runtime.zones,[m
         )[m
[32m+[m[32m        object.__setattr__(context, "zone_results", zone_results)[m
 [m
         # Dispatch to modules[m
         frame_start = time.perf_counter()[m
[1mdiff --git a/core/runtime.py b/core/runtime.py[m
[1mindex 5603625..1e7f7ba 100644[m
[1m--- a/core/runtime.py[m
[1m+++ b/core/runtime.py[m
[36m@@ -99,6 +99,8 @@[m [mclass RuntimeState:[m
 [m
         # Extract zones from camera[m
         self._zones: dict[str, Zone] = dict(camera.zones)[m
[32m+[m[32m        from camera_analytics.core.zone_engine import ZoneEngine[m
[32m+[m[32m        self._zone_engine = ZoneEngine()[m
 [m
         # Archive pruning config[m
         self._archive_prune_interval: int = int([m
[36m@@ -145,6 +147,11 @@[m [mclass RuntimeState:[m
         """Dictionary of zones (keyed by zone_id)."""[m
         return self._zones[m
 [m
[32m+[m[32m    @property[m
[32m+[m[32m    def zone_engine(self) -> Any:[m
[32m+[m[32m        """ZoneEngine spatial evaluator instance."""[m
[32m+[m[32m        return self._zone_engine[m
[32m+[m
     # --- Timing ---[m
 [m
     @property[m
[1mdiff --git a/diagnostics/__init__.py b/diagnostics/__init__.py[m
[1mindex 300f06c..9339f2f 100644[m
[1m--- a/diagnostics/__init__.py[m
[1m+++ b/diagnostics/__init__.py[m
[36m@@ -2,10 +2,13 @@[m
 Runtime Diagnostics & Profiling Package.[m
 [m
 Provides RuntimeHealth, RuntimeMetrics, PluginMetrics, DiagnosticsCollector,[m
[31m-and DiagnosticsReport for inspecting platform latency, module execution performance, and health status.[m
[32m+[m[32mHardwareDiagnosticCollector, and DiagnosticsReport for inspecting platform latency, module execution performance, and health status.[m
 """[m
 [m
[31m-from camera_analytics.diagnostics.collector import DiagnosticsCollector[m
[32m+[m[32mfrom camera_analytics.diagnostics.collector import ([m
[32m+[m[32m    DiagnosticsCollector,[m
[32m+[m[32m    HardwareDiagnosticCollector,[m
[32m+[m[32m)[m
 from camera_analytics.diagnostics.metrics import ([m
     PluginMetrics,[m
     RuntimeHealth,[m
[36m@@ -18,5 +21,6 @@[m [m__all__ = [[m
     "RuntimeMetrics",[m
     "PluginMetrics",[m
     "DiagnosticsCollector",[m
[32m+[m[32m    "HardwareDiagnosticCollector",[m
     "DiagnosticsReport",[m
 ][m
[1mdiff --git a/diagnostics/collector.py b/diagnostics/collector.py[m
[1mindex 0e34696..3bc0918 100644[m
[1m--- a/diagnostics/collector.py[m
[1m+++ b/diagnostics/collector.py[m
[36m@@ -2,21 +2,92 @@[m
 Diagnostics Collector Component.[m
 [m
 Provides DiagnosticsCollector class collecting frame execution latencies, per-plugin execution statistics,[m
[31m-and calculating RuntimeHealth status in a thread-safe, passive manner without performing logging.[m
[32m+[m[32mRuntimeHealth status, and HardwareDiagnosticCollector for real-time CPU/GPU system metrics.[m
 """[m
 [m
 from __future__ import annotations[m
 [m
[32m+[m[32mimport logging[m
 import threading[m
 import time[m
 from typing import Any, Optional[m
 [m
[32m+[m[32mimport psutil[m
[32m+[m[32mimport torch[m
[32m+[m
 from camera_analytics.diagnostics.metrics import ([m
     PluginMetrics,[m
     RuntimeHealth,[m
     RuntimeMetrics,[m
 )[m
 [m
[32m+[m[32mlogger = logging.getLogger(__name__)[m
[32m+[m
[32m+[m
[32m+[m[32mclass HardwareDiagnosticCollector:[m
[32m+[m[32m    """Thread-safe hardware resource metrics collector querying CPU, RAM, CUDA, and NVML GPU stats."""[m
[32m+[m
[32m+[m[32m    def __init__(self) -> None:[m
[32m+[m[32m        self._lock = threading.Lock()[m
[32m+[m[32m        self._has_nvml = False[m
[32m+[m[32m        try:[m
[32m+[m[32m            import pynvml[m
[32m+[m[32m            pynvml.nvmlInit()[m
[32m+[m[32m            self._pynvml = pynvml[m
[32m+[m[32m            self._has_nvml = True[m
[32m+[m[32m        except Exception:[m
[32m+[m[32m            self._has_nvml = False[m
[32m+[m
[32m+[m[32m    def collect_system_metrics(self) -> dict[str, Any]:[m
[32m+[m[32m        """Collect current system CPU, RAM, and GPU hardware metrics.[m
[32m+[m
[32m+[m[32m        Returns:[m
[32m+[m[32m            Dict containing cpu_usage_percent, memory_used_mb, memory_total_mb,[m
[32m+[m[32m            and gpu_metrics (gpu_usage_percent, vram_used_mb, vram_total_mb,[m
[32m+[m[32m            gpu_temperature_c, power_draw_watts).[m
[32m+[m[32m        """[m
[32m+[m[32m        with self._lock:[m
[32m+[m[32m            cpu_pct = psutil.cpu_percent(interval=None)[m
[32m+[m[32m            mem = psutil.virtual_memory()[m
[32m+[m
[32m+[m[32m            gpu_metrics = {[m
[32m+[m[32m                "gpu_usage_percent": 0.0,[m
[32m+[m[32m                "vram_used_mb": 0,[m
[32m+[m[32m                "vram_total_mb": 0,[m
[32m+[m[32m                "gpu_temperature_c": 0.0,[m
[32m+[m[32m                "power_draw_watts": 0.0,[m
[32m+[m[32m            }[m
[32m+[m
[32m+[m[32m            if torch.cuda.is_available():[m
[32m+[m[32m                try:[m
[32m+[m[32m                    device_id = 0[m
[32m+[m[32m                    vram_alloc = torch.cuda.memory_allocated(device_id) // (1024 * 1024)[m
[32m+[m[32m                    vram_total = torch.cuda.get_device_properties(device_id).total_memory // (1024 * 1024)[m
[32m+[m[32m                    gpu_metrics["vram_used_mb"] = vram_alloc[m
[32m+[m[32m                    gpu_metrics["vram_total_mb"] = vram_total[m
[32m+[m[32m                except Exception:[m
[32m+[m[32m                    pass[m
[32m+[m
[32m+[m[32m                if self._has_nvml:[m
[32m+[m[32m                    try:[m
[32m+[m[32m                        handle = self._pynvml.nvmlDeviceGetHandleByIndex(0)[m
[32m+[m[32m                        util = self._pynvml.nvmlDeviceGetUtilizationRates(handle)[m
[32m+[m[32m                        temp = self._pynvml.nvmlDeviceGetTemperature(handle, self._pynvml.NVML_TEMPERATURE_GPU)[m
[32m+[m[32m                        power = self._pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0[m
[32m+[m
[32m+[m[32m                        gpu_metrics["gpu_usage_percent"] = float(util.gpu)[m
[32m+[m[32m                        gpu_metrics["gpu_temperature_c"] = float(temp)[m
[32m+[m[32m                        gpu_metrics["power_draw_watts"] = float(power)[m
[32m+[m[32m                    except Exception:[m
[32m+[m[32m                        pass[m
[32m+[m
[32m+[m[32m            return {[m
[32m+[m[32m                "cpu_usage_percent": float(cpu_pct),[m
[32m+[m[32m                "memory_used_mb": mem.used // (1024 * 1024),[m
[32m+[m[32m                "memory_total_mb": mem.total // (1024 * 1024),[m
[32m+[m[32m                "gpu_metrics": gpu_metrics,[m
[32m+[m[32m            }[m
[32m+[m
 [m
 class DiagnosticsCollector:[m
     """Thread-safe passive collector aggregating frame metrics, plugin metrics, and RuntimeHealth."""[m
[36m@@ -32,12 +103,7 @@[m [mclass DiagnosticsCollector:[m
         self._runtime_error_count: int = 0[m
 [m
     def record_frame(self, frame_latency_ms: float, dropped: bool = False) -> None:[m
[31m-        """Record frame execution latency and dropped frame status.[m
[31m-[m
[31m-        Args:[m
[31m-            frame_latency_ms: Execution latency of the frame in milliseconds.[m
[31m-            dropped: Boolean flag indicating if frame was dropped.[m
[31m-        """[m
[32m+[m[32m        """Record frame execution latency and dropped frame status."""[m
         with self._lock:[m
             self._total_frames += 1[m
             self._total_latency_ms += frame_latency_ms[m
[36m@@ -52,19 +118,12 @@[m [mclass DiagnosticsCollector:[m
         execution_time_ms: float,[m
         events_count: int = 0,[m
     ) -> None:[m
[31m-        """Record a successful module execution.[m
[31m-[m
[31m-        Args:[m
[31m-            module_id: Unique string identifier of module.[m
[31m-            execution_time_ms: Execution duration in milliseconds.[m
[31m-            events_count: Number of analytics events generated.[m
[31m-        """[m
[32m+[m[32m        """Record a successful module execution."""[m
         with self._lock:[m
             pm = self._plugin_metrics.setdefault(module_id, PluginMetrics(module_id=module_id))[m
             pm.executed_count += 1[m
             pm.published_events += events_count[m
 [m
[31m-            # Update latency statistics[m
             if pm.executed_count == 1:[m
                 pm.min_execution_time_ms = execution_time_ms[m
                 pm.max_execution_time_ms = execution_time_ms[m
[36m@@ -74,26 +133,17 @@[m [mclass DiagnosticsCollector:[m
                     pm.min_execution_time_ms = execution_time_ms[m
                 if execution_time_ms > pm.max_execution_time_ms:[m
                     pm.max_execution_time_ms = execution_time_ms[m
[31m-                # Cumulative moving average[m
                 prev_total = pm.average_execution_time_ms * (pm.executed_count - 1)[m
                 pm.average_execution_time_ms = (prev_total + execution_time_ms) / pm.executed_count[m
 [m
     def record_plugin_skip(self, module_id: str) -> None:[m
[31m-        """Record a module skip by ExecutionScheduler.[m
[31m-[m
[31m-        Args:[m
[31m-            module_id: Unique string identifier of module.[m
[31m-        """[m
[32m+[m[32m        """Record a module skip by ExecutionScheduler."""[m
         with self._lock:[m
             pm = self._plugin_metrics.setdefault(module_id, PluginMetrics(module_id=module_id))[m
             pm.skipped_count += 1[m
 [m
     def record_plugin_error(self, module_id: str) -> None:[m
[31m-        """Record an exception isolated error for a module.[m
[31m-[m
[31m-        Args:[m
[31m-            module_id: Unique string identifier of module.[m
[31m-        """[m
[32m+[m[32m        """Record an exception isolated error for a module."""[m
         with self._lock:[m
             pm = self._plugin_metrics.setdefault(module_id, PluginMetrics(module_id=module_id))[m
             pm.error_count += 1[m
[36m@@ -136,11 +186,7 @@[m [mclass DiagnosticsCollector:[m
             ][m
 [m
     def evaluate_health(self) -> RuntimeHealth:[m
[31m-        """Evaluate current RuntimeHealth status based on error counts and performance.[m
[31m-[m
[31m-        Returns:[m
[31m-            RuntimeHealth enum status.[m
[31m-        """[m
[32m+[m[32m        """Evaluate current RuntimeHealth status based on error counts and performance."""[m
         with self._lock:[m
             total_plugin_errors = sum(pm.error_count for pm in self._plugin_metrics.values())[m
 [m
[1mdiff --git a/entities/factory.py b/entities/factory.py[m
[1mindex 8d97dca..c2ed446 100644[m
[1m--- a/entities/factory.py[m
[1m+++ b/entities/factory.py[m
[36m@@ -168,8 +168,16 @@[m [mclass EntityFactory:[m
         )[m
 [m
     @classmethod[m
[31m-    def create_zone_entity(cls, zone: Zone, current_state: ZoneState = ZoneState.OUTSIDE, dwell_frames: int = 0) -> ZoneEntity:[m
[32m+[m[32m    def create_zone_entity(cls, zone: Zone | str, current_state: ZoneState = ZoneState.OUTSIDE, dwell_frames: int = 0) -> ZoneEntity:[m
         """Create ZoneEntity from Zone model object."""[m
[32m+[m[32m        if isinstance(zone, str):[m
[32m+[m[32m            return ZoneEntity([m
[32m+[m[32m                zone_id=zone,[m
[32m+[m[32m                zone_name=zone,[m
[32m+[m[32m                zone_type="region",[m
[32m+[m[32m                current_state=current_state,[m
[32m+[m[32m                dwell_frames=dwell_frames,[m
[32m+[m[32m            )[m
         zone_type_str = zone.zone_type.name.lower() if hasattr(zone.zone_type, "name") else str(zone.zone_type)[m
         return ZoneEntity([m
             zone_id=zone.zone_id,[m
[1mdiff --git a/entities/serializer.py b/entities/serializer.py[m
[1mindex 8ea84bd..b930580 100644[m
[1m--- a/entities/serializer.py[m
[1m+++ b/entities/serializer.py[m
[36m@@ -11,7 +11,7 @@[m [mfrom __future__ import annotations[m
 import json[m
 from typing import Any, Optional[m
 [m
[31m-from camera_analytics.communication.models import StandardAnalyticsEvent[m
[32m+[m[32mfrom camera_analytics.communication.models import EventSeverity, StandardAnalyticsEvent[m
 from camera_analytics.entities.models import ([m
     CameraEntity,[m
     FrameEntity,[m
[36m@@ -50,8 +50,12 @@[m [mclass EntitySerializer:[m
         zone: Optional[ZoneEntity] = None,[m
         payload: Optional[AnalyticsPayload | dict[str, Any]] = None,[m
         severity: str = "INFO",[m
[32m+[m[32m        correlation_id: Optional[str] = None,[m
[32m+[m[32m        track_id: Optional[int] = None,[m
[32m+[m[32m        zone_id: Optional[str] = None,[m
[32m+[m[32m        zone_name: Optional[str] = None,[m
     ) -> StandardAnalyticsEvent:[m
[31m-        """Construct a standardized StandardAnalyticsEvent payload from Domain Entities.[m
[32m+[m[32m        """Construct a standardized StandardAnalyticsEvent payload from Domain Entities and raw data.[m
 [m
         Args:[m
             event_type: String identifier of event classification (e.g. 'ZONE_ENTER').[m
[36m@@ -63,6 +67,10 @@[m [mclass EntitySerializer:[m
             zone: Optional ZoneEntity instance.[m
             payload: Optional AnalyticsPayload or dict payload.[m
             severity: Event severity ('INFO', 'WARNING', 'ALERT', 'CRITICAL').[m
[32m+[m[32m            correlation_id: Optional correlation ID string.[m
[32m+[m[32m            track_id: Explicit track ID integer fallback.[m
[32m+[m[32m            zone_id: Explicit zone ID string fallback.[m
[32m+[m[32m            zone_name: Explicit zone name string fallback.[m
 [m
         Returns:[m
             StandardAnalyticsEvent instance ready for Communication Layer enqueueing.[m
[36m@@ -77,30 +85,51 @@[m [mclass EntitySerializer:[m
         if zone is not None and "zone" not in payload_dict:[m
             payload_dict["zone"] = zone.to_dict()[m
 [m
[31m-        camera_id = camera.camera_id if camera else "default_cam"[m
[31m-        camera_name = camera.camera_name if camera else "Default Camera"[m
[31m-        frame_idx = frame.frame_index if frame else 0[m
[31m-        tr_id = track.track_id if track else None[m
[31m-        z_id = zone.zone_id if zone else None[m
[31m-        z_name = zone.zone_name if zone else None[m
[31m-[m
[31m-        return StandardAnalyticsEvent([m
[31m-            event_type=event_type,[m
[31m-            message=message,[m
[31m-            analytics_module=analytics_module,[m
[31m-            camera_id=camera_id,[m
[31m-            camera_name=camera_name,[m
[31m-            severity=severity,[m
[31m-            track_id=tr_id,[m
[31m-            zone_id=z_id,[m
[31m-            zone_name=z_name,[m
[31m-            frame_index=frame_idx,[m
[31m-            payload=payload_dict,[m
[31m-            metadata={[m
[31m-                "frame": frame.to_dict() if frame else None,[m
[31m-                "camera": camera.to_dict() if camera else None,[m
[31m-            },[m
[31m-        )[m
[32m+[m[32m        # Derive camera info[m
[32m+[m[32m        camera_id = camera.camera_id if camera else payload_dict.get("camera_id", "default_cam")[m
[32m+[m[32m        camera_name = camera.camera_name if camera else payload_dict.get("camera_name", "Default Camera")[m
[32m+[m
[32m+[m[32m        # Derive frame info[m
[32m+[m[32m        frame_idx = frame.frame_index if frame else payload_dict.get("frame_index", 0)[m
[32m+[m
[32m+[m[32m        # Derive track ID[m
[32m+[m[32m        derived_track_id = track.track_id if track else (track_id if track_id is not None else payload_dict.get("track_id"))[m
[32m+[m
[32m+[m[32m        # Derive zone ID and zone name[m
[32m+[m[32m        derived_zone_id = zone.zone_id if zone else (zone_id if zone_id else payload_dict.get("zone_id"))[m
[32m+[m[32m        derived_zone_name = zone.zone_name if zone else (zone_name if zone_name else payload_dict.get("zone_name"))[m
[32m+[m
[32m+[m[32m        # Fallback zone_name to zone_id if zone_name is None[m
[32m+[m[32m        if derived_zone_id and not derived_zone_name:[m
[32m+[m[32m            derived_zone_name = str(derived_zone_id)[m
[32m+[m
[32m+[m[32m        # Derive correlation ID if in payload[m
[32m+[m[32m        derived_corr_id = correlation_id or payload_dict.get("correlation_id")[m
[32m+[m
[32m+[m[32m        metadata_dict: dict[str, Any] = {[m
[32m+[m[32m            "camera": camera.to_dict() if camera else {"camera_id": camera_id, "camera_name": camera_name},[m
[32m+[m[32m            "frame": frame.to_dict() if frame else {"frame_index": frame_idx},[m
[32m+[m[32m        }[m
[32m+[m
[32m+[m[32m        # Build StandardAnalyticsEvent[m
[32m+[m[32m        event_kwargs: dict[str, Any] = {[m
[32m+[m[32m            "event_type": event_type,[m
[32m+[m[32m            "message": message,[m
[32m+[m[32m            "analytics_module": analytics_module,[m
[32m+[m[32m            "camera_id": camera_id,[m
[32m+[m[32m            "camera_name": camera_name,[m
[32m+[m[32m            "severity": severity,[m
[32m+[m[32m            "track_id": derived_track_id,[m
[32m+[m[32m            "zone_id": derived_zone_id,[m
[32m+[m[32m            "zone_name": derived_zone_name,[m
[32m+[m[32m            "frame_index": frame_idx,[m
[32m+[m[32m            "payload": payload_dict,[m
[32m+[m[32m            "metadata": metadata_dict,[m
[32m+[m[32m        }[m
[32m+[m[32m        if derived_corr_id:[m
[32m+[m[32m            event_kwargs["correlation_id"] = derived_corr_id[m
[32m+[m
[32m+[m[32m        return StandardAnalyticsEvent(**event_kwargs)[m
 [m
     @classmethod[m
     def to_json(cls, entity: Any) -> str:[m
[1mdiff --git a/models/detection.py b/models/detection.py[m
[1mindex c21d365..1e2eb41 100644[m
[1m--- a/models/detection.py[m
[1m+++ b/models/detection.py[m
[36m@@ -254,7 +254,7 @@[m [mclass Detection:[m
             3. Right ankle if only right ankle is visible.[m
             4. Fallback: Bottom-center of the bounding box.[m
         """[m
[31m-        if self.keypoints is not None:[m
[32m+[m[32m        if self.keypoints is not None and isinstance(self.keypoints, PoseKeypoints):[m
             left_ankle = self.keypoints.left_ankle[m
             right_ankle = self.keypoints.right_ankle[m
 [m
[1mdiff --git a/plugins/dwell_time/manifest.json b/plugins/dwell_time/manifest.json[m
[1mindex fef218a..2550131 100644[m
[1m--- a/plugins/dwell_time/manifest.json[m
[1m+++ b/plugins/dwell_time/manifest.json[m
[36m@@ -1,17 +1,18 @@[m
 {[m
   "plugin_id": "dwell_time",[m
[31m-  "name": "Dwell Time Dynamic",[m
[32m+[m[32m  "name": "Dwell Time Monitoring Plugin",[m
   "version": "1.0.0",[m
   "sdk_version": "1.0.0",[m
[31m-  "entry_point": "camera_analytics.plugins.dwell_time.module.DwellTimeDynamicPlugin",[m
[32m+[m[32m  "entry_point": "camera_analytics.plugins.dwell_time.module.DwellTimeModule",[m
[32m+[m[32m  "author": "Enterprise Analytics Team",[m
[32m+[m[32m  "description": "Measures cumulative dwell duration per track in spatial zones and emits DWELL_TIME events",[m
   "capabilities": [[m
[31m-    "TRACKING",[m
     "ZONE",[m
[31m-    "GROUND_POINT"[m
[32m+[m[32m    "TRACKING"[m
   ],[m
   "execution_policy": {[m
[31m-    "execution_mode": "INTERVAL",[m
[31m-    "interval": 5[m
[32m+[m[32m    "execution_mode": "EVERY_FRAME",[m
[32m+[m[32m    "interval": 1[m
   },[m
[31m-  "priority": 20[m
[32m+[m[32m  "priority": 13[m
 }[m
\ No newline at end of file[m
[1mdiff --git a/plugins/dwell_time/module.py b/plugins/dwell_time/module.py[m
[1mindex d5f6d0c..9ee05fd 100644[m
[1m--- a/plugins/dwell_time/module.py[m
[1m+++ b/plugins/dwell_time/module.py[m
[36m@@ -1,22 +1,106 @@[m
[32m+[m[32m"""[m
[32m+[m[32mDwell Time Analytics Plugin Module.[m
 [m
[31m-from camera_analytics.sdk import AnalyticsModule, AnalyticsResult, AnalyticsEvent, AnalyticsEventType[m
[32m+[m[32mMeasures spatial zone dwell times per track and emits StandardAnalyticsEvent objects.[m
[32m+[m[32m"""[m
[32m+[m
[32m+[m[32mfrom __future__ import annotations[m
[32m+[m
[32m+[m[32mfrom typing import Any, Optional[m
[32m+[m
[32m+[m[32mfrom camera_analytics.entities.models import ZoneState[m
[32m+[m[32mfrom camera_analytics.scene.models import Scene[m
[32m+[m[32mfrom camera_analytics.sdk import ([m
[32m+[m[32m    AnalyticsEvent,[m
[32m+[m[32m    AnalyticsEventType,[m
[32m+[m[32m    AnalyticsModule,[m
[32m+[m[32m    AnalyticsResult,[m
[32m+[m[32m)[m
[32m+[m[32mfrom camera_analytics.sdk.events import EventSeverity, StandardAnalyticsEvent[m
[32m+[m
[32m+[m
[32m+[m[32mclass DwellTimeModule(AnalyticsModule):[m
[32m+[m[32m    """Dwell Time Analytics Module."""[m
 [m
[31m-class DwellTimeDynamicPlugin(AnalyticsModule):[m
     def __init__(self, name: str = "dwell_time") -> None:[m
[31m-        super().__init__(name=name, description="Dynamic Dwell Time Plugin")[m
[32m+[m[32m        super().__init__(name=name, description="Dwell Time Analytics Plugin")[m
[32m+[m[32m        self.dwell_threshold_seconds = 10.0[m
[32m+[m[32m        self._dwell_start: dict[tuple[int, str], float] = {}[m
[32m+[m[32m        self._alerted_tracks: set[tuple[int, str]] = set()[m
 [m
[31m-    def update(self, context) -> AnalyticsResult:[m
[32m+[m[32m    def update(self, context: Any) -> Optional[AnalyticsResult]:[m
[32m+[m[32m        """Backward compatibility update hook."""[m
         return AnalyticsResult(module_name=self.name)[m
 [m
[31m-    def process(self, scene) -> AnalyticsResult:[m
[31m-        events = [][m
[31m-        if scene.frame.frame_index % 50 == 0:[m
[31m-            events.append(AnalyticsEvent([m
[31m-                event_id=f"evt_dt_{scene.frame.frame_index}",[m
[31m-                module_name=self.name,[m
[31m-                event_type=AnalyticsEventType.INFO,[m
[31m-                message=f"[DwellTimeDynamicPlugin] Evaluating dwell times for {len(scene.tracks)} tracks",[m
[31m-                timestamp=scene.frame.timestamp,[m
[31m-                frame_index=scene.frame.frame_index,[m
[31m-            ))[m
[31m-        return AnalyticsResult(module_name=self.name, events=events)[m
[32m+[m[32m    def process_scene(self, scene: Scene) -> AnalyticsResult:[m
[32m+[m[32m        """Process immutable Scene domain snapshot."""[m
[32m+[m[32m        events: list[AnalyticsEvent] = [][m
[32m+[m[32m        active_keys: set[tuple[int, str]] = set()[m
[32m+[m
[32m+[m[32m        for track in scene.tracks:[m
[32m+[m[32m            for zone in scene.zones:[m
[32m+[m[32m                if zone.current_state in (ZoneState.ENTER, ZoneState.INSIDE):[m
[32m+[m[32m                    key = (track.track_id, zone.zone_id)[m
[32m+[m[32m                    active_keys.add(key)[m
[32m+[m
[32m+[m[32m                    if key not in self._dwell_start:[m
[32m+[m[32m                        self._dwell_start[key] = scene.frame.timestamp[m
[32m+[m
[32m+[m[32m                    dwell_secs = scene.frame.timestamp - self._dwell_start[key][m
[32m+[m
[32m+[m[32m                    if dwell_secs >= self.dwell_threshold_seconds and key not in self._alerted_tracks:[m
[32m+[m[32m                        self._alerted_tracks.add(key)[m
[32m+[m[32m                        msg = f"Track #{track.track_id} dwell time in zone '{zone.zone_name}' ({zone.zone_id}) exceeded threshold ({dwell_secs:.1f}s >= {self.dwell_threshold_seconds}s)"[m
[32m+[m
[32m+[m[32m                        std_event = StandardAnalyticsEvent([m
[32m+[m[32m                            event_type="DWELL_TIME",[m
[32m+[m[32m                            analytics_module=self.name,[m
[32m+[m[32m                            source_module=self.name,[m
[32m+[m[32m                            message=msg,[m
[32m+[m[32m                            timestamp=str(scene.frame.timestamp),[m
[32m+[m[32m                            camera_id=scene.camera.camera_id,[m
[32m+[m[32m                            camera_name=scene.camera.camera_name,[m
[32m+[m[32m                            track_id=track.track_id,[m
[32m+[m[32m                            zone_id=zone.zone_id,[m
[32m+[m[32m                            zone_name=zone.zone_name,[m
[32m+[m[32m                            severity=EventSeverity.WARNING.value,[m
[32m+[m[32m                            payload={[m
[32m+[m[32m                                "track_id": track.track_id,[m
[32m+[m[32m                                "zone_id": zone.zone_id,[m
[32m+[m[32m                                "zone_name": zone.zone_name,[m
[32m+[m[32m                                "camera_id": scene.camera.camera_id,[m
[32m+[m[32m                                "timestamp": scene.frame.timestamp,[m
[32m+[m[32m                                "dwell_duration_seconds": round(dwell_secs, 2),[m
[32m+[m[32m                                "threshold_seconds": self.dwell_threshold_seconds,[m
[32m+[m[32m                            },[m
[32m+[m[32m                            metadata={[m
[32m+[m[32m                                "frame_index": scene.frame.frame_index,[m
[32m+[m[32m                                "camera": scene.camera.to_dict(),[m
[32m+[m[32m                                "frame": scene.frame.to_dict(),[m
[32m+[m[32m                            },[m
[32m+[m[32m                        )[m
[32m+[m
[32m+[m[32m                        legacy_event = AnalyticsEvent([m
[32m+[m[32m                            event_id=std_event.event_id,[m
[32m+[m[32m                            module_name=self.name,[m
[32m+[m[32m                            event_type=AnalyticsEventType.THRESHOLD_EXCEEDED,[m
[32m+[m[32m                            message=msg,[m
[32m+[m[32m                            timestamp=scene.frame.timestamp,[m
[32m+[m[32m                            frame_index=scene.frame.frame_index,[m
[32m+[m[32m                            track_id=track.track_id,[m
[32m+[m[32m                            zone_id=zone.zone_id,[m
[32m+[m[32m                            data=std_event.to_dict(),[m
[32m+[m[32m                        )[m
[32m+[m[32m                        events.append(legacy_event)[m
[32m+[m
[32m+[m[32m        # Automatic garbage collection of state[m
[32m+[m[32m        stale_keys = set(self._dwell_start.keys()) - active_keys[m
[32m+[m[32m        for k in stale_keys:[m
[32m+[m[32m            self._dwell_start.pop(k, None)[m
[32m+[m[32m            self._alerted_tracks.discard(k)[m
[32m+[m
[32m+[m[32m        return AnalyticsResult([m
[32m+[m[32m            module_name=self.name,[m
[32m+[m[32m            events=events,[m
[32m+[m[32m            metrics={"monitored_dwell_tracks": len(self._dwell_start)},[m
[32m+[m[32m        )[m
[1mdiff --git a/samples/output_analytics_sdk_validation.mp4 b/samples/output_analytics_sdk_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex 6d6a269..0000000[m
Binary files a/samples/output_analytics_sdk_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_botsort_tracking_validation.mp4 b/samples/output_botsort_tracking_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex 8a17026..0000000[m
Binary files a/samples/output_botsort_tracking_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_capability_validation.mp4 b/samples/output_capability_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex 67fe356..0000000[m
Binary files a/samples/output_capability_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_communication_validation.mp4 b/samples/output_communication_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex 9fcf045..0000000[m
Binary files a/samples/output_communication_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_entities_validation.mp4 b/samples/output_entities_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex 4a21a07..0000000[m
Binary files a/samples/output_entities_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_live_rtsp_validation.mp4 b/samples/output_live_rtsp_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex 0e3d0ff..0000000[m
Binary files a/samples/output_live_rtsp_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_registry_validation.mp4 b/samples/output_registry_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex 546191d..0000000[m
Binary files a/samples/output_registry_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_runtime_hardening.mp4 b/samples/output_runtime_hardening.mp4[m
[1mdeleted file mode 100644[m
[1mindex f7724ea..0000000[m
Binary files a/samples/output_runtime_hardening.mp4 and /dev/null differ
[1mdiff --git a/samples/output_runtime_validation.mp4 b/samples/output_runtime_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex 2a585bf..0000000[m
Binary files a/samples/output_runtime_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_scene_validation.mp4 b/samples/output_scene_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex 645baaa..0000000[m
Binary files a/samples/output_scene_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_scheduler_validation.mp4 b/samples/output_scheduler_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex ce53c0a..0000000[m
Binary files a/samples/output_scheduler_validation.mp4 and /dev/null differ
[1mdiff --git a/samples/output_tracking_visualization.mp4 b/samples/output_tracking_visualization.mp4[m
[1mdeleted file mode 100644[m
[1mindex 8f6b4cc..0000000[m
Binary files a/samples/output_tracking_visualization.mp4 and /dev/null differ
[1mdiff --git a/samples/output_zone_engine_validation.mp4 b/samples/output_zone_engine_validation.mp4[m
[1mdeleted file mode 100644[m
[1mindex a5a9617..0000000[m
Binary files a/samples/output_zone_engine_validation.mp4 and /dev/null differ
[1mdiff --git a/sdk/__init__.py b/sdk/__init__.py[m
[1mindex 7566b6a..5b12d5b 100644[m
[1m--- a/sdk/__init__.py[m
[1m+++ b/sdk/__init__.py[m
[36m@@ -17,9 +17,13 @@[m [mfrom camera_analytics.sdk.models import ([m
 from camera_analytics.sdk.module import AnalyticsModule[m
 from camera_analytics.sdk.registry import AnalyticsRegistry, register_analytics[m
 [m
[32m+[m[32mfrom camera_analytics.sdk.events import EventSeverity, StandardAnalyticsEvent[m
[32m+[m
 __all__ = [[m
     "AnalyticsEventType",[m
     "AnalyticsEvent",[m
[32m+[m[32m    "EventSeverity",[m
[32m+[m[32m    "StandardAnalyticsEvent",[m
     "AnalyticsContext",[m
     "AnalyticsResult",[m
     "AggregatedAnalyticsResult",[m
[1mdiff --git a/tests/test_communication.py b/tests/test_communication.py[m
[1mindex 8ddf107..6b3747f 100644[m
[1m--- a/tests/test_communication.py[m
[1m+++ b/tests/test_communication.py[m
[36m@@ -18,6 +18,7 @@[m [mimport time[m
 import unittest[m
 from pathlib import Path[m
 [m
[32m+[m[32mimport camera_analytics.communication[m
 from camera_analytics.communication.manager import CommunicationManager[m
 from camera_analytics.communication.models import ([m
     AnalyticsEventSerializer,[m
[1mdiff --git a/tests/test_runtime_diagnostics.py b/tests/test_runtime_diagnostics.py[m
[1mindex 691b919..591bf2d 100644[m
[1m--- a/tests/test_runtime_diagnostics.py[m
[1m+++ b/tests/test_runtime_diagnostics.py[m
[36m@@ -1,11 +1,12 @@[m
 """[m
[31m-Unit tests for Runtime Diagnostics & Profiling Component (Sprint 10I).[m
[32m+[m[32mUnit tests for Runtime Diagnostics & Profiling Component (Sprint 10I & Sprint 12.6).[m
 [m
 Verifies:[m
     1. RuntimeMetrics aggregation (frame counts, FPS calculation, latency averages).[m
     2. PluginMetrics per-module calculations (executed count, skipped count, events, min/max/avg execution time).[m
     3. RuntimeHealth evaluation rules (HEALTHY, WARNING, DEGRADED, FAILED).[m
     4. DiagnosticsReport snapshot generation breakdown (slowest/fastest plugin, top producer, top skip ratio).[m
[32m+[m[32m    5. HardwareDiagnosticCollector system CPU, RAM, and GPU hardware metrics collection.[m
 """[m
 [m
 import time[m
[36m@@ -15,6 +16,7 @@[m [mfrom typing import Any, Optional[m
 from camera_analytics.diagnostics import ([m
     DiagnosticsCollector,[m
     DiagnosticsReport,[m
[32m+[m[32m    HardwareDiagnosticCollector,[m
     PluginMetrics,[m
     RuntimeHealth,[m
     RuntimeMetrics,[m
[36m@@ -178,6 +180,26 @@[m [mclass TestRuntimeDiagnostics(unittest.TestCase):[m
             self.assertEqual(report.fastest_plugin.module_id, "fast_mod")[m
             self.assertEqual(report.highest_event_producer.module_id, "fast_mod")[m
 [m
[32m+[m[32m    def test_hardware_diagnostic_collector(self) -> None:[m
[32m+[m[32m        """Test HardwareDiagnosticCollector system CPU, RAM, and GPU hardware metrics collection."""[m
[32m+[m[32m        collector = HardwareDiagnosticCollector()[m
[32m+[m[32m        metrics = collector.collect_system_metrics()[m
[32m+[m
[32m+[m[32m        self.assertIn("cpu_usage_percent", metrics)[m
[32m+[m[32m        self.assertIn("memory_used_mb", metrics)[m
[32m+[m[32m        self.assertIn("memory_total_mb", metrics)[m
[32m+[m[32m        self.assertIn("gpu_metrics", metrics)[m
[32m+[m
[32m+[m[32m        gpu_metrics = metrics["gpu_metrics"][m
[32m+[m[32m        self.assertIn("gpu_usage_percent", gpu_metrics)[m
[32m+[m[32m        self.assertIn("vram_used_mb", gpu_metrics)[m
[32m+[m[32m        self.assertIn("vram_total_mb", gpu_metrics)[m
[32m+[m[32m        self.assertIn("gpu_temperature_c", gpu_metrics)[m
[32m+[m[32m        self.assertIn("power_draw_watts", gpu_metrics)[m
[32m+[m
[32m+[m[32m        self.assertGreaterEqual(metrics["cpu_usage_percent"], 0.0)[m
[32m+[m[32m        self.assertGreaterEqual(metrics["memory_total_mb"], 0)[m
[32m+[m
 [m
 if __name__ == "__main__":[m
     unittest.main()[m
