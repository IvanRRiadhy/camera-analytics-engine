"""
Abstract Configuration Provider contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from camera_analytics.bootstrap.models import ConfigurationSnapshot


class ConfigurationProvider(ABC):
    """Abstract Base Class for loading and validating AI Engine configuration snapshots."""

    @abstractmethod
    def load(self) -> ConfigurationSnapshot:
        """Load, parse, validate, and construct an immutable ConfigurationSnapshot.

        Returns:
            Validated ConfigurationSnapshot instance.

        Raises:
            ConfigValidationError: If configuration format, schema version, or fields fail validation.
        """
