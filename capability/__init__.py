"""
Capability Negotiation Framework Package.

Provides Capability Enum, CapabilitySet, RuntimeCapabilityProvider, CapabilityNegotiator,
and CapabilityValidationReport for evaluating plugin compatibility with the Analytics Runtime Kernel.
"""

from camera_analytics.capability.models import Capability, CapabilitySet
from camera_analytics.capability.negotiator import (
    CapabilityNegotiator,
    CapabilityValidationReport,
)
from camera_analytics.capability.provider import RuntimeCapabilityProvider

__all__ = [
    "Capability",
    "CapabilitySet",
    "RuntimeCapabilityProvider",
    "CapabilityNegotiator",
    "CapabilityValidationReport",
]
