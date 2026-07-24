"""
Lifecycle Manager Component.

Manages state transitions and lifecycle hooks (initialize, start, pause, stop, dispose)
for Analytics Modules registered within the ModuleRegistry and Analytics Runtime Kernel.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, Optional

from camera_analytics.registry.descriptor import ModuleDescriptor, ModuleState
from camera_analytics.registry.manager import ModuleManager
from camera_analytics.runtime.context import RuntimeContext
from camera_analytics.sdk import AnalyticsContext, AnalyticsModule

if TYPE_CHECKING:
    from camera_analytics.scene.models import Scene

logger = logging.getLogger(__name__)


class ModuleRecord:
    """Internal tracking record for a managed Analytics Module."""

    def __init__(self, module: AnalyticsModule, name: str, descriptor: Optional[ModuleDescriptor] = None) -> None:
        self.module = module
        self.name = name
        self.descriptor = descriptor or ModuleDescriptor(module_id=name, module_name=name)
        self.error_count = 0
        self.last_error: Optional[str] = None

    @property
    def state(self) -> ModuleState:
        """Get current state from descriptor."""
        return self.descriptor.state

    @state.setter
    def state(self, value: ModuleState) -> None:
        """Set current state in descriptor."""
        self.descriptor.state = value


class LifecycleManager:
    """Manager responsible for controlling state transitions and invoking lifecycle hooks on Analytics Modules via ModuleManager."""

    def __init__(
        self,
        runtime_context: Optional[RuntimeContext] = None,
        module_manager: Optional[ModuleManager] = None,
    ) -> None:
        self._context = runtime_context or RuntimeContext()
        self._module_manager = module_manager or ModuleManager()
        self._records: dict[str, ModuleRecord] = {}
        self._lock = threading.Lock()

    @property
    def module_manager(self) -> ModuleManager:
        """Reference to ModuleManager."""
        return self._module_manager

    @property
    def modules(self) -> dict[str, AnalyticsModule]:
        """Dictionary of registered AnalyticsModule instances."""
        with self._lock:
            return {name: rec.module for name, rec in self._records.items()}

    def get_state(self, module_name: str) -> ModuleState:
        """Get the current lifecycle state of a module.

        Args:
            module_name: Unique string name of registered module.

        Returns:
            ModuleState enum value.
        """
        with self._lock:
            rec = self._records.get(module_name)
            return rec.state if rec else ModuleState.REGISTERED

    def register(self, module: AnalyticsModule, descriptor: Optional[ModuleDescriptor] = None) -> ModuleDescriptor:
        """Register an AnalyticsModule instance under lifecycle and module management.

        Args:
            module: AnalyticsModule instance.
            descriptor: Optional ModuleDescriptor override.

        Returns:
            Registered ModuleDescriptor instance.
        """
        with self._lock:
            desc = self._module_manager.register_module(module, descriptor)
            rec = ModuleRecord(module=module, name=module.name, descriptor=desc)
            self._records[module.name] = rec
            logger.info("LifecycleManager: Registered module '%s' via ModuleManager", module.name)
            return desc

    def initialize_module(self, module_name: str, config: Optional[dict[str, Any]] = None) -> bool:
        """Initialize a registered module using AnalyticsContext.

        Args:
            module_name: Name of module to initialize.
            config: Optional configuration dictionary overrides.

        Returns:
            True if initialized successfully, False otherwise.
        """
        with self._lock:
            rec = self._records.get(module_name)
            if not rec:
                logger.error("LifecycleManager: Cannot initialize unknown module '%s'", module_name)
                return False

            if not rec.descriptor.enabled:
                logger.warning("LifecycleManager: Cannot initialize disabled module '%s'", module_name)
                return False

            if rec.state not in (ModuleState.REGISTERED, ModuleState.STOPPED):
                logger.debug("LifecycleManager: Module '%s' is already initialized (state=%s)", module_name, rec.state.name)
                return True

            try:
                # Construct AnalyticsContext for module initialization
                sdk_ctx = AnalyticsContext(
                    frame_context=None,
                    runtime_state=None,
                    track_manager=None,
                    zones=[],
                )
                rec.module.initialize(sdk_ctx)
                rec.state = ModuleState.INITIALIZED
                logger.info("LifecycleManager: Initialized module '%s'", module_name)
                return True
            except Exception as exc:
                rec.state = ModuleState.FAILED
                rec.error_count += 1
                rec.last_error = str(exc)
                logger.error("LifecycleManager: Error initializing module '%s': %s", module_name, exc)
                return False

    def start_module(self, module_name: str) -> bool:
        """Start an initialized module to transition it to RUNNING state.

        Args:
            module_name: Name of module to start.

        Returns:
            True if started successfully, False otherwise.
        """
        with self._lock:
            rec = self._records.get(module_name)
            if not rec:
                return False

            if not rec.descriptor.enabled:
                return False

            if rec.state == ModuleState.RUNNING:
                return True

            if rec.state not in (ModuleState.INITIALIZED, ModuleState.STOPPED, ModuleState.REGISTERED, ModuleState.DISABLED):
                logger.warning("LifecycleManager: Cannot start module '%s' in state %s", module_name, rec.state.name)
                return False

            try:
                rec.module.start()
                rec.state = ModuleState.RUNNING
                logger.info("LifecycleManager: Started module '%s' (State=RUNNING)", module_name)
                return True
            except Exception as exc:
                rec.state = ModuleState.FAILED
                rec.error_count += 1
                rec.last_error = str(exc)
                logger.error("LifecycleManager: Error starting module '%s': %s", module_name, exc)
                return False

    def pause_module(self, module_name: str) -> bool:
        """Pause a running module.

        Args:
            module_name: Name of module to pause.

        Returns:
            True if paused successfully, False otherwise.
        """
        with self._lock:
            rec = self._records.get(module_name)
            if not rec or rec.state != ModuleState.RUNNING:
                return False

            rec.state = ModuleState.STOPPED
            logger.info("LifecycleManager: Paused module '%s'", module_name)
            return True

    def stop_module(self, module_name: str) -> bool:
        """Stop a running module.

        Args:
            module_name: Name of module to stop.

        Returns:
            True if stopped successfully, False otherwise.
        """
        with self._lock:
            rec = self._records.get(module_name)
            if not rec:
                return False

            if rec.state in (ModuleState.STOPPED, ModuleState.REGISTERED):
                return True

            try:
                rec.module.stop()
                rec.state = ModuleState.STOPPED
                logger.info("LifecycleManager: Stopped module '%s' (State=STOPPED)", module_name)
                return True
            except Exception as exc:
                rec.state = ModuleState.FAILED
                rec.error_count += 1
                rec.last_error = str(exc)
                logger.error("LifecycleManager: Error stopping module '%s': %s", module_name, exc)
                return False

    def dispose_module(self, module_name: str) -> bool:
        """Dispose a module and release its resources.

        Args:
            module_name: Name of module to dispose.

        Returns:
            True if disposed successfully, False otherwise.
        """
        with self._lock:
            rec = self._records.get(module_name)
            if not rec:
                return False

            try:
                if rec.state == ModuleState.RUNNING:
                    rec.module.stop()
                rec.module.dispose()
                rec.state = ModuleState.DISPOSED
                logger.info("LifecycleManager: Disposed module '%s'", module_name)
                return True
            except Exception as exc:
                rec.state = ModuleState.FAILED
                rec.last_error = str(exc)
                logger.error("LifecycleManager: Error disposing module '%s': %s", module_name, exc)
                return False

    def start_all(self) -> None:
        """Initialize and start all enabled registered modules."""
        for desc, mod in self._module_manager.registry.get_enabled():
            if desc.state == ModuleState.REGISTERED:
                self.initialize_module(desc.module_id)
            self.start_module(desc.module_id)

    def stop_all(self) -> None:
        """Stop all running modules."""
        for desc, mod in self._module_manager.registry.get_all():
            if desc.state == ModuleState.RUNNING:
                self.stop_module(desc.module_id)

    def dispose_all(self) -> None:
        """Dispose all registered modules."""
        self.stop_all()
        for desc, mod in self._module_manager.registry.get_all():
            self.dispose_module(desc.module_id)
        with self._lock:
            self._records.clear()
