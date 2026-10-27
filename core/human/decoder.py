"""
Attribute Decoder & InferenceResult DTO Infrastructure (Sprint H1.4.7).

Isolates model-specific tensor output formats from HumanState, producing standardized
domain objects (HumanAttributes and InferenceResult) for downstream stabilization and state updating.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class HumanAttributes:
    """Standardized domain DTO containing parsed human analytics attributes."""

    age: Optional[float] = None
    gender: Optional[str] = None           # "male" | "female"
    emotion: Optional[str] = None          # "neutral" | "happy" | "sad" | "angry" | "surprised" | etc.
    identity_id: Optional[str] = None      # ReID feature embedding ID or face match ID
    face_embedding: Optional[list[float]] = None
    ppe_helmet: Optional[bool] = None
    ppe_mask: Optional[bool] = None
    ppe_vest: Optional[bool] = None
    clothing_upper_color: Optional[str] = None
    clothing_lower_color: Optional[str] = None
    gesture: Optional[str] = None
    confidence: float = 1.0
    raw_outputs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InferenceResult:
    """Decoupled inference result DTO emitted by attribute decoders."""

    track_id: int
    module_id: str
    attributes: HumanAttributes
    confidence: float = 1.0
    execution_time_ms: float = 0.0
    timestamp_utc: float = field(default_factory=time.time)
    status: str = "SUCCESS"               # "SUCCESS" | "DEGRADED" | "FAILED"
    error_message: Optional[str] = None


class IAttributeDecoder(ABC):
    """Abstract interface for model output decoders.

    Converts raw model output tensors into standardized InferenceResult & HumanAttributes DTOs.
    """

    @property
    @abstractmethod
    def module_id(self) -> str:
        """Identifier of the target model module."""
        pass

    @abstractmethod
    def decode(
        self,
        raw_output: Any,
        request: Any,
        execution_time_ms: float = 0.0,
    ) -> InferenceResult:
        """Decode raw neural output into a standardized InferenceResult DTO."""
        pass
