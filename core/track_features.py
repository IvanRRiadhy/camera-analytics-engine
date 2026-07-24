"""
Track feature store.

Provides namespaced, typed storage for per-track data contributed
by different analytics modules. Replaces the unsafe `metadata: dict`
pattern with namespace isolation and lifecycle management.

Each analytics module writes to its own namespace, preventing
accidental key collisions between modules.

Example::

    store = TrackFeatureStore()

    # PeopleAnalytics writes
    store.set("people", "pose", "standing")
    store.set("people", "dwell_time", 45.2)

    # PPEAnalytics writes (isolated namespace)
    store.set("ppe", "helmet", True)
    store.set("ppe", "vest", False)

    # BehaviorAnalytics reads from People, writes own
    pose = store.get("people", "pose", "unknown")
    store.set("behavior", "loitering_score", 0.8)

    # On module unregister — clean up only its data
    store.clear_namespace("ppe")
"""

from __future__ import annotations

from typing import Any, Iterator, TypeVar

T = TypeVar("T")


class TrackFeatureStore:
    """Namespaced key-value store for per-track features.

    Each analytics module uses its own namespace (typically the
    module name) to store and retrieve features on a Track.
    This prevents collisions and enables per-module cleanup.

    Internally stored as a flat dict with composite keys
    ``"namespace.key"`` for O(1) access.
    """

    __slots__ = ("_data",)

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @staticmethod
    def _composite_key(namespace: str, key: str) -> str:
        """Build a composite key from namespace and key."""
        return f"{namespace}.{key}"

    def set(self, namespace: str, key: str, value: Any) -> None:
        """Store a feature value.

        Args:
            namespace: Module namespace (e.g., 'people', 'ppe').
            key: Feature key within the namespace.
            value: The value to store.
        """
        self._data[self._composite_key(namespace, key)] = value

    def get(self, namespace: str, key: str, default: T = None) -> Any | T:
        """Retrieve a feature value.

        Args:
            namespace: Module namespace.
            key: Feature key within the namespace.
            default: Value to return if not found.

        Returns:
            The stored value, or the default.
        """
        return self._data.get(self._composite_key(namespace, key), default)

    def has(self, namespace: str, key: str) -> bool:
        """Check if a feature exists.

        Args:
            namespace: Module namespace.
            key: Feature key within the namespace.

        Returns:
            True if the feature is stored.
        """
        return self._composite_key(namespace, key) in self._data

    def remove(self, namespace: str, key: str) -> bool:
        """Remove a single feature.

        Args:
            namespace: Module namespace.
            key: Feature key within the namespace.

        Returns:
            True if the feature was found and removed.
        """
        ckey = self._composite_key(namespace, key)
        if ckey in self._data:
            del self._data[ckey]
            return True
        return False

    def get_namespace(self, namespace: str) -> dict[str, Any]:
        """Retrieve all features in a namespace.

        Args:
            namespace: Module namespace to retrieve.

        Returns:
            Dictionary of ``{key: value}`` for the namespace.
            Keys are stripped of the namespace prefix.
        """
        prefix = f"{namespace}."
        return {
            k[len(prefix):]: v
            for k, v in self._data.items()
            if k.startswith(prefix)
        }

    def clear_namespace(self, namespace: str) -> int:
        """Remove all features in a namespace.

        Called when a module is unregistered to clean up its data.

        Args:
            namespace: Module namespace to clear.

        Returns:
            Number of features removed.
        """
        prefix = f"{namespace}."
        keys_to_remove = [k for k in self._data if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._data[k]
        return len(keys_to_remove)

    def namespaces(self) -> set[str]:
        """Return the set of all namespaces that have stored features.

        Returns:
            Set of namespace strings.
        """
        return {k.split(".", 1)[0] for k in self._data if "." in k}

    def clear(self) -> None:
        """Remove all features from all namespaces."""
        self._data.clear()

    @property
    def total_count(self) -> int:
        """Total number of features across all namespaces."""
        return len(self._data)

    @property
    def is_empty(self) -> bool:
        """Whether the store has no features."""
        return len(self._data) == 0

    def __repr__(self) -> str:
        ns = self.namespaces()
        return f"TrackFeatureStore(namespaces={ns}, count={len(self._data)})"
