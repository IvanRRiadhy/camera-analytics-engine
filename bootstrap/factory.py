"""
Runtime Mode Resolver & Configuration Provider Factory.

Decouples CLI argument parsing from engine bootstrapping by resolving runtime modes
and instantiating the appropriate strategy implementation of `IConfigurationProvider`.
"""

from __future__ import annotations

import argparse
import logging
import os
from enum import Enum
from typing import Any, Optional

from camera_analytics.bootstrap.providers.base import ConfigurationProvider
from camera_analytics.bootstrap.providers.backend_provider import BackendConfigurationProvider
from camera_analytics.bootstrap.providers.standalone_provider import StandaloneConfigurationProvider

logger = logging.getLogger(__name__)


class RuntimeMode(str, Enum):
    """Supported execution runtime modes."""
    ENTERPRISE = "enterprise"
    STANDALONE = "standalone"


class RuntimeModeResolver:
    """Resolves target RuntimeMode from CLI arguments, environment variables, or default fallback."""

    @staticmethod
    def resolve(cli_args: Optional[argparse.Namespace] = None) -> RuntimeMode:
        """Resolve RuntimeMode enum from CLI args or environment variables."""
        if cli_args is not None:
            if getattr(cli_args, "standalone", False):
                logger.info("RuntimeModeResolver: Resolved STANDALONE mode via CLI flag '--standalone'")
                return RuntimeMode.STANDALONE

            mode_str = getattr(cli_args, "mode", None)
            if mode_str and str(mode_str).lower() == "standalone":
                logger.info("RuntimeModeResolver: Resolved STANDALONE mode via CLI option '--mode standalone'")
                return RuntimeMode.STANDALONE

        # Environment variable fallback
        env_mode = os.getenv("CAMERA_ANALYTICS_MODE", "").strip().lower()
        if env_mode == "standalone":
            logger.info("RuntimeModeResolver: Resolved STANDALONE mode via environment variable CAMERA_ANALYTICS_MODE='standalone'")
            return RuntimeMode.STANDALONE

        logger.info("RuntimeModeResolver: Resolved ENTERPRISE mode (default)")
        return RuntimeMode.ENTERPRISE


class ConfigurationProviderFactory:
    """Factory for instantiating `IConfigurationProvider` strategies based on RuntimeMode."""

    @staticmethod
    def create(mode: RuntimeMode, cli_args: Optional[argparse.Namespace] = None) -> ConfigurationProvider:
        """Instantiate appropriate ConfigurationProvider strategy.
        
        Args:
            mode: Resolved RuntimeMode enum.
            cli_args: Optional parsed CLI argument namespace.
            
        Returns:
            ConfigurationProvider instance (BackendConfigurationProvider or StandaloneConfigurationProvider).
        """
        if mode == RuntimeMode.STANDALONE:
            config_file = getattr(cli_args, "config_file", "configs/standalone.json") if cli_args else "configs/standalone.json"
            logger.info("ConfigurationProviderFactory: Instantiating StandaloneConfigurationProvider(file='%s')", config_file)
            return StandaloneConfigurationProvider(config_file_path=config_file)
        else:
            backend_url = getattr(cli_args, "backend_url", "http://localhost:5100") if cli_args else "http://localhost:5100"
            logger.info("ConfigurationProviderFactory: Instantiating BackendConfigurationProvider(url='%s')", backend_url)
            return BackendConfigurationProvider(backend_url=backend_url)
