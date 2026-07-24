"""
Dynamic Plugin Loader Package.

Provides PluginInstanceRecord, PluginLoadingReport, and PluginLoader for performing
dynamic import, reflection, type checking, and instantiation of Analytics Modules specified in PluginManifests.
"""

from camera_analytics.loader.core import PluginLoader
from camera_analytics.loader.models import PluginInstanceRecord, PluginLoadingReport

__all__ = [
    "PluginInstanceRecord",
    "PluginLoadingReport",
    "PluginLoader",
]
