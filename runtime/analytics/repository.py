"""
Plugin State Repository Component.

Thread-safe pipeline-scoped repository storing plugin metric entries, per-zone breakdowns,
and per-camera contributions for enterprise analytics snapshot construction.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Type, TypeVar

T = TypeVar("T")


class PluginStateRepository:
    """Thread-safe pipeline-scoped repository storing plugin states and zone/camera breakdowns."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._states: Dict[str, Any] = {}
        self._zone_metrics: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._camera_metrics: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def update_state(self, plugin_key: str, state_object: Any) -> None:
        """Update or insert typed plugin state object."""
        with self._lock:
            self._states[plugin_key] = state_object

    def update_zone_metric(self, plugin_key: str, zone_id: str, metrics: Dict[str, Any], camera_id: str = "") -> None:
        """Record zone-specific analytics metrics for a plugin."""
        with self._lock:
            if plugin_key not in self._zone_metrics:
                self._zone_metrics[plugin_key] = {}
            if zone_id not in self._zone_metrics[plugin_key]:
                self._zone_metrics[plugin_key][zone_id] = {"metrics": {}, "cameras": set()}
            
            self._zone_metrics[plugin_key][zone_id]["metrics"].update(metrics)
            if camera_id:
                self._zone_metrics[plugin_key][zone_id]["cameras"].add(camera_id)

    def update_camera_metric(self, plugin_key: str, camera_id: str, metrics: Dict[str, Any], camera_name: str = "") -> None:
        """Record camera-specific analytics metrics for a plugin."""
        with self._lock:
            if plugin_key not in self._camera_metrics:
                self._camera_metrics[plugin_key] = {}
            self._camera_metrics[plugin_key][camera_id] = {
                "cameraId": camera_id,
                "cameraName": camera_name or camera_id,
                "metrics": metrics
            }

    def get_state(self, plugin_key: str, state_type: Type[T]) -> Optional[T]:
        """Retrieve strongly typed plugin state object."""
        with self._lock:
            val = self._states.get(plugin_key)
            if isinstance(val, state_type):
                return val
            return None

    def get_zone_metrics(self, plugin_key: str) -> Dict[str, Dict[str, Any]]:
        """Get all zone metrics recorded for a plugin."""
        with self._lock:
            return dict(self._zone_metrics.get(plugin_key, {}))

    def get_camera_metrics(self, plugin_key: str) -> Dict[str, Dict[str, Any]]:
        """Get all camera metrics recorded for a plugin."""
        with self._lock:
            return dict(self._camera_metrics.get(plugin_key, {}))

    def get_all_states(self) -> Dict[str, Any]:
        """Get copy of all current plugin states."""
        with self._lock:
            return dict(self._states)

    def clear(self) -> None:
        """Clear all registered plugin states and metrics."""
        with self._lock:
            self._states.clear()
            self._zone_metrics.clear()
            self._camera_metrics.clear()
