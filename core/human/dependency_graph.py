"""
Module Dependency Graph (DAG).

Manages module execution priority, topological sorting, and cycle detection across AI modules.
Example: Face ROI -> Quality -> Alignment -> Embedding -> Recognition
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class ModuleNode:
    """Node in the Module Dependency Graph."""

    module_id: str
    priority: int = 3                      # Lower number = Higher priority
    dependencies: list[str] = field(default_factory=list)


class ModuleDependencyGraph:
    """DAG managing module resolution order and dependency validation."""

    def __init__(self) -> None:
        self._nodes: dict[str, ModuleNode] = {}

    def add_module(self, module_id: str, priority: int = 3, dependencies: Optional[list[str]] = None) -> None:
        """Add or update a module node in the dependency graph."""
        deps = list(dependencies or [])
        self._nodes[module_id] = ModuleNode(module_id=module_id, priority=priority, dependencies=deps)

    def resolve_execution_order(self) -> list[str]:
        """Perform topological sort combined with priority ordering.
        
        Returns:
            Ordered list of module_id strings matching dependency and priority constraints.

        Raises:
            ValueError: If a circular dependency is detected.
        """
        in_degree: dict[str, int] = {m_id: 0 for m_id in self._nodes}
        adj: dict[str, list[str]] = {m_id: [] for m_id in self._nodes}

        for m_id, node in self._nodes.items():
            for dep in node.dependencies:
                if dep in self._nodes:
                    adj[dep].append(m_id)
                    in_degree[m_id] += 1
                else:
                    logger.warning("[ModuleDependencyGraph] Module '%s' depends on unknown module '%s'", m_id, dep)

        # Priority queue / sorted candidates (higher priority / lower priority number first)
        ready = [m_id for m_id, deg in in_degree.items() if deg == 0]
        ordered: list[str] = []

        while ready:
            # Sort ready queue by node priority
            ready.sort(key=lambda m: (self._nodes[m].priority, m))
            current = ready.pop(0)
            ordered.append(current)

            for neighbor in adj[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    ready.append(neighbor)

        if len(ordered) != len(self._nodes):
            unresolved = set(self._nodes.keys()) - set(ordered)
            raise ValueError(f"[ModuleDependencyGraph] Circular dependency detected involving modules: {unresolved}")

        return ordered

    def clear(self) -> None:
        """Clear all nodes in graph."""
        self._nodes.clear()
