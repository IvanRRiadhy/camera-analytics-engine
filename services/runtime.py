"""
Event Service Runtime Kernel.

Core execution kernel managing service lifecycles, event dispatching, execution engine,
and Exception Isolation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing.event_bus import PlatformEventBus
from camera_analytics.eventing.models import PlatformEvent
from camera_analytics.services.context import ServiceContext
from camera_analytics.services.dependency_graph import ServiceDependencyGraph
from camera_analytics.services.dispatcher import EventDispatcher
from camera_analytics.services.execution_engine import ServiceExecutionEngine
from camera_analytics.services.health import HierarchicalHealthMonitor
from camera_analytics.services.lifecycle import ServiceLifecycleState
from camera_analytics.services.loader import ServiceLoader
from camera_analytics.services.manifest import ServiceManifest
from camera_analytics.services.registry import ServiceRegistry
from camera_analytics.services.scheduler import ServiceScheduler

logger = logging.getLogger(__name__)


class EventServiceRuntime:
    """Core Kernel for Event-Driven Platform Services."""

    def __init__(
        self,
        event_bus: Optional[PlatformEventBus] = None,
        max_workers: int = 4,
        storage_dir: Optional[str | Path] = None,
    ) -> None:
        self.event_bus = event_bus or PlatformEventBus()
        self.registry = ServiceRegistry()
        self.dispatcher = EventDispatcher(self.registry)
        self.execution_engine = ServiceExecutionEngine(max_workers=max_workers)
        self.scheduler = ServiceScheduler()
        self.health_monitor = HierarchicalHealthMonitor(self.registry)
        self.storage_dir = Path(storage_dir or "camera_analytics/storage").resolve()
        self._is_running = False

    def load_and_initialize_service(
        self,
        manifest: ServiceManifest,
        plugin_dir: Path,
        config: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Load service plugin module and initialize instance.

        Args:
            manifest: ServiceManifest dataclass.
            plugin_dir: Absolute path to plugin folder.
            config: Optional service configuration dict.

        Returns:
            True if initialized successfully, False otherwise.
        """
        instance = ServiceLoader.load_service(manifest, plugin_dir)
        if not instance:
            return False

        instance.event_bus = self.event_bus

        context = ServiceContext(
            service_name=manifest.service_name,
            config=config,
            registry=self.registry,
            event_bus=self.event_bus,
            storage_dir=self.storage_dir,
        )

        try:
            instance.initialize(context)
            self.registry.register(manifest, instance)
            logger.info("EventServiceRuntime: Initialized service '%s'", manifest.service_name)
            return True
        except Exception as exc:
            logger.error("EventServiceRuntime: Exception barrier caught initialization failure in '%s': %s", manifest.service_name, exc)
            return False

    def start_all_services(self) -> None:
        """Start execution engine, scheduler, and all registered services in topological order."""
        if self._is_running:
            return

        self.execution_engine.start()
        self.scheduler.start()

        # Compute topological order
        graph = ServiceDependencyGraph()
        entries = self.registry.list_services()
        for entry in entries:
            graph.add_manifest(entry.manifest)

        try:
            startup_order = graph.compute_startup_order()
        except Exception as exc:
            logger.warning("EventServiceRuntime: Topological sort warning: %s. Falling back to priority order.", exc)
            startup_order = [e.manifest.service_name for e in sorted(entries, key=lambda x: x.manifest.priority)]

        for s_name in startup_order:
            entry = self.registry.get(s_name)
            if entry and entry.manifest.enabled:
                try:
                    entry.instance.start()
                    entry.state = ServiceLifecycleState.RUNNING
                    logger.info("EventServiceRuntime: Started service '%s'", s_name)
                except Exception as exc:
                    entry.state = ServiceLifecycleState.FAILED
                    entry.last_error = str(exc)
                    logger.error("EventServiceRuntime: Exception barrier caught start failure in '%s': %s", s_name, exc)

        self._is_running = True

    def process_event(self, event: StandardAnalyticsEvent | PlatformEvent) -> int:
        """Process event by routing to target services.

        Args:
            event: StandardAnalyticsEvent or PlatformEvent.

        Returns:
            Number of target services receiving the event.
        """
        targets = self.dispatcher.resolve_target_services(event)
        for target in targets:
            self.execution_engine.execute_event(target, event)
        return len(targets)

    def stop_all_services(self) -> None:
        """Stop all running services, worker threads, and scheduler cleanly."""
        if not self._is_running:
            return

        for entry in self.registry.list_services():
            if entry.state == ServiceLifecycleState.RUNNING:
                try:
                    entry.instance.stop()
                    entry.instance.dispose()
                    entry.state = ServiceLifecycleState.STOPPED
                except Exception as exc:
                    logger.error("EventServiceRuntime: Stop error in '%s': %s", entry.manifest.service_name, exc)

        self.execution_engine.stop()
        self.scheduler.stop()
        self._is_running = False
        logger.info("EventServiceRuntime stopped cleanly")
