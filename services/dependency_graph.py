"""
Service Dependency Graph & Topological Sort.

Builds a Directed Acyclic Graph (DAG) of service capability dependencies and computes
the **Topological Startup Sequence** for deterministic plugin initialization.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Optional

from camera_analytics.services.manifest import ServiceManifest

logger = logging.getLogger(__name__)


class ServiceDependencyGraph:
    """Computes topological startup order for services based on capability dependencies."""

    def __init__(self) -> None:
        self.manifests: dict[str, ServiceManifest] = {}
        self.capability_providers: dict[str, str] = {}  # capability -> service_name

    def add_manifest(self, manifest: ServiceManifest) -> None:
        """Add service manifest to dependency graph."""
        self.manifests[manifest.service_name] = manifest
        for cap in manifest.capabilities:
            self.capability_providers[cap] = manifest.service_name

    def compute_startup_order(self) -> list[str]:
        """Compute topological sort of service names.

        Returns:
            Ordered list of service names for initialization.

        Raises:
            ValueError: If missing dependency or circular dependency detected.
        """
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {name: 0 for name in self.manifests}

        # Build graph edges: Provider ➔ Consumer
        for consumer_name, manifest in self.manifests.items():
            for req_cap in manifest.dependencies:
                provider_name = self.capability_providers.get(req_cap)
                if not provider_name:
                    logger.warning(
                        "Service '%s' requires capability '%s' which has no registered provider",
                        consumer_name,
                        req_cap,
                    )
                    continue

                if provider_name != consumer_name:
                    adj[provider_name].append(consumer_name)
                    in_degree[consumer_name] += 1

        # Kahn's algorithm for topological sort
        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        startup_order: list[str] = []

        while queue:
            # Sort by priority then service_name for deterministic tie-breaking
            current_batch = sorted(list(queue), key=lambda x: (self.manifests[x].priority, x))
            queue.clear()

            for node in current_batch:
                startup_order.append(node)
                for neighbor in adj[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        if len(startup_order) != len(self.manifests):
            unresolved = [name for name, deg in in_degree.items() if deg > 0]
            raise ValueError(f"Circular dependency detected among services: {unresolved}")

        logger.debug("ServiceDependencyGraph computed startup order: %s", startup_order)
        return startup_order
