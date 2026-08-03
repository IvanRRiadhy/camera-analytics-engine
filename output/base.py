"""
Output Abstraction Layer base contract.

Defines the abstract base class `OutputProvider` decoupling event presentation
(Console Human, Enterprise JSON, RabbitMQ, MQTT) from core engine analytics loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from camera_analytics.communication.models import StandardAnalyticsEvent


class OutputProvider(ABC):
    """Abstract Base Class for event output formatting and rendering providers."""

    def __init__(self, name: str, enabled: bool = True) -> None:
        self._name = name
        self._enabled = enabled

    @property
    def name(self) -> str:
        """Name identifier of the output provider."""
        return self._name

    @property
    def is_enabled(self) -> bool:
        """Whether output provider is active."""
        return self._enabled

    @abstractmethod
    def output(self, event: StandardAnalyticsEvent) -> bool:
        """Format and emit an analytics event.

        Args:
            event: StandardAnalyticsEvent instance.

        Returns:
            True if output succeeded, False otherwise.
        """

    @abstractmethod
    def flush(self) -> None:
        """Flush buffered outputs if applicable."""
