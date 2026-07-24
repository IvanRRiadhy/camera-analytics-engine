"""
Analytics SDK Core Data Models.

Defines decoupled, AI-agnostic data structures used by Analytics Modules:
    - AnalyticsEventType: Classification of analytics domain events.
    - AnalyticsEvent: Structured event payload emitted by analytics modules.
    - AnalyticsContext: Frame & runtime context passed to analytics modules.
    - AnalyticsResult: Individual module execution output payload.
    - AggregatedAnalyticsResult: Combined output payload from all active modules.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional, Sequence

if TYPE_CHECKING:
    from camera_analytics.core.frame_context import FrameContext
    from camera_analytics.core.runtime import RuntimeState
    from camera_analytics.core.track_manager import TrackManager
    from camera_analytics.core.zone_engine import ZoneEngineResult
    from camera_analytics.models.track import Track
    from camera_analytics.models.zone import Zone


class AnalyticsEventType(Enum):
    """Classification of Analytics domain events."""

    INFO = auto()
    COUNT_CHANGE = auto()
    THRESHOLD_EXCEEDED = auto()
    ZONE_INTRUSION = auto()
    LOITERING_WARNING = auto()
    LINE_CROSSED = auto()
    CROWD_DETECTED = auto()
    CUSTOM = auto()


@dataclass(frozen=True, slots=True)
class AnalyticsEvent:
    """Structured event emitted by an Analytics Module.

    Attributes:
        event_id: Unique string identifier for this event.
        module_name: Name of the originating Analytics Module.
        event_type: Classification of the event.
        message: Human-readable event description.
        timestamp: Event creation timestamp (seconds).
        frame_index: Sequential frame number.
        track_id: Optional associated Track ID.
        zone_id: Optional associated Zone ID.
        data: Optional dictionary payload containing module-specific metrics.
    """

    event_id: str
    module_name: str
    event_type: AnalyticsEventType
    message: str
    timestamp: float
    frame_index: int
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalyticsContext:
    """Execution context supplied to Analytics Modules during each update frame iteration.

    Isolates Analytics Modules from internal Pipeline details.

    Attributes:
        frame_context: Read-only FrameContext for current frame.
        runtime_state: Access to RuntimeState references.
        track_manager: Reference to TrackManager.
        active_tracks: Sequence of active Track objects in current frame.
        zones: Configured camera spatial Zones.
        zone_result: Spatial output produced by ZoneEngine for current frame.
        frame_index: Sequential frame number.
        timestamp: Video frame timestamp in seconds.
        config: Optional module-specific configuration dictionary.
    """

    frame_context: Optional[FrameContext]
    runtime_state: Optional[RuntimeState]
    track_manager: Optional[TrackManager]
    active_tracks: Sequence[Track] = field(default_factory=list)
    zones: Sequence[Zone] = field(default_factory=list)
    zone_result: Optional[ZoneEngineResult] = None
    frame_index: int = 0
    timestamp: float = 0.0
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalyticsResult:
    """Execution output payload returned by an individual Analytics Module per frame.

    Attributes:
        module_name: Name of the Analytics Module.
        events: List of new AnalyticsEvent objects generated during this frame.
        metrics: Key-value metric values (e.g. {'count': 5, 'density': 0.12}).
        warnings: List of warning strings.
        statistics: Additional module statistics dictionary.
        execution_time_ms: Processing duration in milliseconds.
    """

    module_name: str
    events: list[AnalyticsEvent] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0


@dataclass(slots=True)
class AggregatedAnalyticsResult:
    """Combined output payload from all active Analytics Modules for a frame.

    Attributes:
        frame_index: Sequential frame number.
        timestamp: Video frame timestamp in seconds.
        results: Mapping of module_name -> AnalyticsResult.
        all_events: Combined list of all AnalyticsEvents emitted across modules.
        summary_metrics: Combined key-value metrics summary.
        errors: List of error messages caught during module execution (Exception Isolation).
        total_execution_time_ms: Sum of all module processing durations.
    """

    frame_index: int = 0
    timestamp: float = 0.0
    results: dict[str, AnalyticsResult] = field(default_factory=dict)
    all_events: list[AnalyticsEvent] = field(default_factory=list)
    summary_metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    total_execution_time_ms: float = 0.0
