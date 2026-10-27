"""
Human Module Context and Decoupled Module Result Data Models (Sprint H1.5A).

Defines HumanModuleContext (slots=True for high performance and pipeline flexibility)
and ModuleResult (decoupled output produced by Human Analytics modules).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
import numpy as np
from numpy.typing import NDArray

from camera_analytics.core.human.models import HumanRepresentation, HumanState

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HumanModuleContext:
    """Standardized, mutable execution context passed to every Human Analytics module."""

    representation: HumanRepresentation
    state: HumanState
    frame: Optional[NDArray[np.uint8]] = None
    runtime_context: Optional[Any] = None
    shared_context: Optional[Any] = None
    scheduler_context: dict[str, Any] = field(default_factory=dict)
    model_context: dict[str, Any] = field(default_factory=dict)
    batch_context: dict[str, Any] = field(default_factory=dict)
    frame_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModuleResult:
    """Decoupled inference/processing output produced by a Human Analytics module."""

    module_id: str
    track_id: int
    outputs: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    execution_time_ms: float = 0.0
    status: str = "SUCCESS"              # SUCCESS, SKIPPED, LOCKED, ERROR
