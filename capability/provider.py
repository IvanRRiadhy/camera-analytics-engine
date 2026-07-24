"""
Runtime Capability Provider Component.

Provides RuntimeCapabilityProvider class inspecting Vision Runtime Engine and Immutable Scene snapshots
to construct the active platform CapabilitySet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence, Union

from camera_analytics.capability.models import Capability, CapabilitySet

if TYPE_CHECKING:
    from camera_analytics.scene.models import Scene


class RuntimeCapabilityProvider:
    """Provider inspecting Vision Engine & Scene snapshot to build active platform CapabilitySet."""

    def __init__(self, static_capabilities: Optional[Sequence[Union[Capability, str]]] = None) -> None:
        default_caps = [
            Capability.TRACKING,
            Capability.POSE,
            Capability.GROUND_POINT,
            Capability.ZONE,
            Capability.KEYPOINTS,
            Capability.VELOCITY,
            Capability.DIRECTION,
        ]
        items = list(static_capabilities) if static_capabilities is not None else default_caps
        self._static_caps = CapabilitySet.create(items)

    def get_capabilities(self, scene: Optional[Scene] = None) -> CapabilitySet:
        """Get current active CapabilitySet supported by Runtime and Scene.

        Args:
            scene: Optional Scene snapshot to inspect dynamic capabilities.

        Returns:
            CapabilitySet representing current platform capabilities.
        """
        if scene is None:
            return self._static_caps

        dynamic_caps: set[Capability] = set(self._static_caps.capabilities)

        # Inspect Scene snapshot dynamically
        if scene.tracks:
            dynamic_caps.add(Capability.TRACKING)
            sample_track = scene.tracks[0]
            if sample_track.pose is not None:
                dynamic_caps.add(Capability.POSE)
                dynamic_caps.add(Capability.KEYPOINTS)
            if sample_track.ground_point is not None:
                dynamic_caps.add(Capability.GROUND_POINT)
            if sample_track.velocity is not None:
                dynamic_caps.add(Capability.VELOCITY)
            if sample_track.direction is not None:
                dynamic_caps.add(Capability.DIRECTION)

        if scene.zones:
            dynamic_caps.add(Capability.ZONE)

        return CapabilitySet(capabilities=frozenset(dynamic_caps))
