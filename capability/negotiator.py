"""
Capability Negotiator Component.

Provides CapabilityNegotiator matching Analytics Module descriptors against Runtime CapabilitySet,
updating descriptor state to UNSUPPORTED if capabilities are missing, and generating CapabilityValidationReport.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from camera_analytics.capability.models import Capability, CapabilitySet
from camera_analytics.capability.provider import RuntimeCapabilityProvider
from camera_analytics.registry.descriptor import ModuleDescriptor, ModuleState
from camera_analytics.registry.store import ModuleRegistry

if TYPE_CHECKING:
    from camera_analytics.scene.models import Scene

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CapabilityValidationReport:
    """Report summarizing capability negotiation results for Analytics Modules in the kernel.

    Attributes:
        runtime_capabilities: CapabilitySet supported by current runtime environment.
        supported_modules: List of module_ids whose capabilities are fully satisfied.
        unsupported_modules: List of module_ids missing required capabilities.
        missing_capabilities: Dictionary mapping module_id -> list of missing capability names.
    """

    runtime_capabilities: CapabilitySet = field(default_factory=CapabilitySet)
    supported_modules: list[str] = field(default_factory=list)
    unsupported_modules: list[str] = field(default_factory=list)
    missing_capabilities: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report summary to dictionary."""
        return {
            "runtime_capability_summary": self.runtime_capabilities.to_list(),
            "supported_modules_count": len(self.supported_modules),
            "supported_modules": list(self.supported_modules),
            "unsupported_modules_count": len(self.unsupported_modules),
            "unsupported_modules": list(self.unsupported_modules),
            "missing_capabilities": dict(self.missing_capabilities),
        }


class CapabilityNegotiator:
    """Negotiator matching ModuleDescriptor requirements against RuntimeCapabilityProvider."""

    def __init__(self, provider: Optional[RuntimeCapabilityProvider] = None) -> None:
        self._provider = provider or RuntimeCapabilityProvider()

    @property
    def provider(self) -> RuntimeCapabilityProvider:
        """Reference to underlying RuntimeCapabilityProvider."""
        return self._provider

    def negotiate(
        self,
        registry: ModuleRegistry,
        scene: Optional[Scene] = None,
    ) -> CapabilityValidationReport:
        """Negotiate capabilities for all registered modules in ModuleRegistry against Runtime Capabilities.

        If a module requires capabilities not provided by the Runtime:
            - The module descriptor state is updated to UNSUPPORTED.
            - The module is skipped during execution cleanly (no exception raised).

        Args:
            registry: ModuleRegistry instance containing registered descriptors.
            scene: Optional Scene snapshot for dynamic capability inspection.

        Returns:
            CapabilityValidationReport containing negotiation breakdown.
        """
        runtime_caps = self._provider.get_capabilities(scene)
        report = CapabilityValidationReport(runtime_capabilities=runtime_caps)

        for desc, _ in registry.get_all():
            req_set = CapabilitySet.create(desc.capabilities)

            if req_set.is_subset_of(runtime_caps):
                report.supported_modules.append(desc.module_id)
                # If state was UNSUPPORTED and enabled, reset to REGISTERED / INITIALIZED
                if desc.state == ModuleState.UNSUPPORTED and desc.enabled:
                    desc.state = ModuleState.REGISTERED
            else:
                missing_set = req_set.missing_from(runtime_caps)
                report.unsupported_modules.append(desc.module_id)
                report.missing_capabilities[desc.module_id] = missing_set.to_list()

                # Mark descriptor state as UNSUPPORTED
                desc.state = ModuleState.UNSUPPORTED
                logger.info(
                    "CapabilityNegotiator: Module '%s' UNSUPPORTED (Missing capabilities: %s)",
                    desc.module_id,
                    missing_set.to_list(),
                )

        return report
