"""
Capability Models Component.

Provides Capability Enum defining supported platform capabilities and CapabilitySet immutable
collection for capability negotiation between Runtime Kernel and Analytics Modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Iterable, Sequence, Set, Union


class Capability(Enum):
    """Enumeration of platform capabilities supported by Vision Engine Runtime and required by Analytics Modules."""

    TRACKING = auto()
    POSE = auto()
    GROUND_POINT = auto()
    ZONE = auto()
    REID = auto()
    VELOCITY = auto()
    DIRECTION = auto()
    KEYPOINTS = auto()
    SEGMENTATION = auto()
    CLASSIFICATION = auto()
    DEPTH = auto()
    CUSTOM = auto()

    @classmethod
    def from_string(cls, name: str) -> Capability:
        """Convert string identifier to Capability enum safely.

        Args:
            name: String name (e.g. 'tracking', 'POSE').

        Returns:
            Matching Capability enum or Capability.CUSTOM.
        """
        clean_name = name.strip().upper()
        try:
            return cls[clean_name]
        except KeyError:
            return cls.CUSTOM


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    """Immutable collection of Capability enums.

    Attributes:
        capabilities: Immutable frozenset of Capability items.
    """

    capabilities: frozenset[Capability] = field(default_factory=frozenset)

    @classmethod
    def create(cls, items: Iterable[Union[Capability, str]]) -> CapabilitySet:
        """Factory method to construct CapabilitySet from strings or Capability enums.

        Args:
            items: Iterable of Capability enums or string names.

        Returns:
            Immutable CapabilitySet instance.
        """
        cap_set: set[Capability] = set()
        for item in items:
            if isinstance(item, Capability):
                cap_set.add(item)
            elif isinstance(item, str):
                cap_set.add(Capability.from_string(item))
        return cls(capabilities=frozenset(cap_set))

    def contains(self, item: Union[Capability, str]) -> bool:
        """Check if capability is contained in set.

        Args:
            item: Capability enum or string name.

        Returns:
            True if contained, False otherwise.
        """
        cap = item if isinstance(item, Capability) else Capability.from_string(item)
        return cap in self.capabilities

    def is_subset_of(self, available: CapabilitySet) -> bool:
        """Check if all capabilities in this set are contained in available set.

        Args:
            available: Available CapabilitySet.

        Returns:
            True if subset, False otherwise.
        """
        return self.capabilities.issubset(available.capabilities)

    def missing_from(self, available: CapabilitySet) -> CapabilitySet:
        """Get set of capabilities in this set that are missing from available set.

        Args:
            available: Available CapabilitySet.

        Returns:
            CapabilitySet containing missing capabilities.
        """
        missing = self.capabilities - available.capabilities
        return CapabilitySet(capabilities=frozenset(missing))

    def to_list(self) -> list[str]:
        """Convert CapabilitySet to list of sorted string names."""
        return sorted([cap.name for cap in self.capabilities])
