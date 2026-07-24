"""
Analytics Runtime Kernel Component.

Central orchestrator for the Analytics Runtime Kernel, managing RuntimeContext,
ModuleManager, ModuleRegistry, LifecycleManager, ExecutionEngine, CapabilityNegotiator,
ExecutionScheduler, PluginLoader, and DiagnosticsCollector.
Receives immutable Scene snapshots and dispatches execution to registered enabled Analytics Modules.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Sequence, Union

from camera_analytics.capability import (
    CapabilityNegotiator,
    CapabilityValidationReport,
)
from camera_analytics.diagnostics import DiagnosticsCollector, DiagnosticsReport
from camera_analytics.discovery import PluginDiscovery, PluginManifest
from camera_analytics.loader import PluginLoader, PluginLoadingReport
from camera_analytics.registry import ModuleDescriptor, ModuleManager, ModuleRegistry
from camera_analytics.runtime.context import RuntimeContext
from camera_analytics.runtime.execution import ExecutionEngine
from camera_analytics.runtime.lifecycle import LifecycleManager
from camera_analytics.scheduler import ExecutionScheduler
from camera_analytics.sdk import AggregatedAnalyticsResult, AnalyticsModule

if TYPE_CHECKING:
    from camera_analytics.scene.models import Scene

logger = logging.getLogger(__name__)


class AnalyticsRuntime:
    """Central Kernel Manager for Analytics Runtime execution.

    Coordinates RuntimeContext, ModuleManager, ModuleRegistry, LifecycleManager, ExecutionEngine,
    CapabilityNegotiator, ExecutionScheduler, PluginLoader, and DiagnosticsCollector.

    Usage::

        runtime = AnalyticsRuntime()
        report = runtime.load_plugins_from_directory("camera_analytics/plugins")
        runtime.start()

        # In frame loop:
        aggregated_result = runtime.process_scene(scene)

        # Get Diagnostics Report:
        diag = runtime.get_diagnostics_report()
    """

    def __init__(
        self,
        context: Optional[RuntimeContext] = None,
        module_manager: Optional[ModuleManager] = None,
        capability_negotiator: Optional[CapabilityNegotiator] = None,
        execution_scheduler: Optional[ExecutionScheduler] = None,
        plugin_loader: Optional[PluginLoader] = None,
        plugin_discovery: Optional[PluginDiscovery] = None,
        diagnostics_collector: Optional[DiagnosticsCollector] = None,
    ) -> None:
        self._context = context or RuntimeContext()
        self._module_manager = module_manager or ModuleManager()
        self._lifecycle_manager = LifecycleManager(
            runtime_context=self._context,
            module_manager=self._module_manager,
        )
        self._scheduler = execution_scheduler or ExecutionScheduler()
        self._diagnostics = diagnostics_collector or DiagnosticsCollector()
        self._execution_engine = ExecutionEngine(
            lifecycle_manager=self._lifecycle_manager,
            runtime_context=self._context,
            scheduler=self._scheduler,
            diagnostics_collector=self._diagnostics,
        )
        self._capability_negotiator = capability_negotiator or CapabilityNegotiator()
        self._plugin_loader = plugin_loader or PluginLoader()
        self._plugin_discovery = plugin_discovery or PluginDiscovery()
        self._is_running = False
        self._lock = threading.Lock()

    @property
    def context(self) -> RuntimeContext:
        """Reference to RuntimeContext."""
        return self._context

    @property
    def module_manager(self) -> ModuleManager:
        """Reference to ModuleManager."""
        return self._module_manager

    @property
    def registry(self) -> ModuleRegistry:
        """Reference to underlying ModuleRegistry."""
        return self._module_manager.registry

    @property
    def lifecycle_manager(self) -> LifecycleManager:
        """Reference to LifecycleManager."""
        return self._lifecycle_manager

    @property
    def execution_engine(self) -> ExecutionEngine:
        """Reference to ExecutionEngine."""
        return self._execution_engine

    @property
    def capability_negotiator(self) -> CapabilityNegotiator:
        """Reference to CapabilityNegotiator."""
        return self._capability_negotiator

    @property
    def scheduler(self) -> ExecutionScheduler:
        """Reference to ExecutionScheduler."""
        return self._scheduler

    @property
    def plugin_loader(self) -> PluginLoader:
        """Reference to PluginLoader."""
        return self._plugin_loader

    @property
    def plugin_discovery(self) -> PluginDiscovery:
        """Reference to PluginDiscovery."""
        return self._plugin_discovery

    @property
    def diagnostics(self) -> DiagnosticsCollector:
        """Reference to DiagnosticsCollector."""
        return self._diagnostics

    @property
    def is_running(self) -> bool:
        """Whether the Analytics Runtime Kernel is running."""
        return self._is_running

    def register_module(
        self,
        module: AnalyticsModule,
        descriptor: Optional[ModuleDescriptor] = None,
    ) -> ModuleDescriptor:
        """Register an AnalyticsModule instance into the ModuleRegistry & LifecycleManager.

        Args:
            module: AnalyticsModule instance.
            descriptor: Optional custom ModuleDescriptor.

        Returns:
            Registered ModuleDescriptor instance.
        """
        return self._lifecycle_manager.register(module, descriptor)

    def load_plugins_from_manifests(self, manifests: Sequence[PluginManifest]) -> PluginLoadingReport:
        """Dynamically load Analytics Modules from a sequence of PluginManifest instances and register them.

        Args:
            manifests: Sequence of PluginManifest objects.

        Returns:
            PluginLoadingReport summarizing loaded vs rejected records.
        """
        report = self._plugin_loader.load_all(manifests)
        for record in report.loaded_records:
            if record.instance is not None:
                self.register_module(record.instance, record.descriptor)
        return report

    def load_plugins_from_directory(self, plugins_dir: Union[str, Path]) -> PluginLoadingReport:
        """Discover manifest.json files in a directory tree and dynamically load valid Analytics Modules.

        Args:
            plugins_dir: Root directory path (e.g. 'camera_analytics/plugins').

        Returns:
            PluginLoadingReport summarizing loaded vs rejected records.
        """
        discovery_report = self._plugin_discovery.discover(plugins_dir)
        return self.load_plugins_from_manifests(discovery_report.valid_plugins)

    def get_diagnostics_report(self) -> DiagnosticsReport:
        """Generate a snapshot DiagnosticsReport summarizing kernel performance, plugin metrics, and health.

        Returns:
            DiagnosticsReport object.
        """
        return DiagnosticsReport.generate(self._diagnostics)

    def enable_module(self, module_id: str) -> bool:
        """Enable an administrative disabled module.

        Args:
            module_id: Module string identifier.

        Returns:
            True if enabled, False otherwise.
        """
        res = self._module_manager.enable_module(module_id)
        if res and self._is_running:
            self._capability_negotiator.negotiate(self._module_manager.registry)
            self._lifecycle_manager.initialize_module(module_id)
            self._lifecycle_manager.start_module(module_id)
        return res

    def disable_module(self, module_id: str) -> bool:
        """Disable a running module.

        Args:
            module_id: Module string identifier.

        Returns:
            True if disabled, False otherwise.
        """
        if self._is_running:
            self._lifecycle_manager.stop_module(module_id)
        return self._module_manager.disable_module(module_id)

    def get_capability_report(self, scene: Optional[Scene] = None) -> CapabilityValidationReport:
        """Generate CapabilityValidationReport for currently registered modules against RuntimeCapabilities.

        Args:
            scene: Optional Scene snapshot for dynamic capability checking.

        Returns:
            CapabilityValidationReport instance.
        """
        return self._capability_negotiator.negotiate(self._module_manager.registry, scene)

    def initialize(self, global_config: Optional[dict[str, Any]] = None) -> None:
        """Initialize all registered enabled analytics modules after capability negotiation."""
        with self._lock:
            if global_config:
                self._context.config.update(global_config)

            # Run capability negotiation
            report = self._capability_negotiator.negotiate(self._module_manager.registry)
            logger.info(
                "AnalyticsRuntime: Capability Negotiation Complete (Supported: %d, Unsupported: %d)",
                len(report.supported_modules),
                len(report.unsupported_modules),
            )

            for desc, _ in self._module_manager.registry.get_enabled():
                if desc.module_id in report.supported_modules:
                    self._lifecycle_manager.initialize_module(desc.module_id)

            logger.info("AnalyticsRuntime: Initialized kernel context and supported modules")

    def start(self) -> None:
        """Start the Analytics Runtime Kernel and transition supported modules to RUNNING state."""
        with self._lock:
            if self._is_running:
                return

            # Re-negotiate capabilities prior to starting
            self._capability_negotiator.negotiate(self._module_manager.registry)
            self._lifecycle_manager.start_all()
            self._is_running = True
            logger.info("AnalyticsRuntime: Started Analytics Runtime Kernel")

    def process_scene(self, scene: Scene) -> AggregatedAnalyticsResult:
        """Dispatch an immutable Scene snapshot to enabled RUNNING Analytics Modules according to ExecutionScheduler.

        Args:
            scene: Immutable Scene domain snapshot.

        Returns:
            AggregatedAnalyticsResult instance.
        """
        if not self._is_running:
            logger.warning("AnalyticsRuntime: process_scene called while kernel is not running")
            return AggregatedAnalyticsResult(
                frame_index=scene.frame.frame_index,
                timestamp=scene.frame.timestamp,
            )

        return self._execution_engine.execute_scene(scene)

    def stop(self) -> None:
        """Stop the Analytics Runtime Kernel and active modules."""
        with self._lock:
            if not self._is_running:
                return

            self._lifecycle_manager.stop_all()
            self._is_running = False
            logger.info("AnalyticsRuntime: Stopped Analytics Runtime Kernel")

    def dispose(self) -> None:
        """Dispose the Analytics Runtime Kernel and release all resources."""
        self.stop()
        with self._lock:
            self._lifecycle_manager.dispose_all()
            logger.info("AnalyticsRuntime: Disposed Analytics Runtime Kernel")
