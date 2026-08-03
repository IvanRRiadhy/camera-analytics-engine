"""
IConfigurationProvider Abstract Interface Contract.

Defines the strategy interface for loading strongly typed EngineConfiguration or ConfigurationSnapshot
regardless of the underlying source (Backend REST API, Local JSON, Cloud, CLI).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from camera_analytics.bootstrap.providers.base import ConfigurationProvider

# Alias for strategy consistency
IConfigurationProvider = ConfigurationProvider

__all__ = ["IConfigurationProvider", "ConfigurationProvider"]
