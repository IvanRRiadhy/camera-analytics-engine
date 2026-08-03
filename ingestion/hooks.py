"""
Ingestion Event Hooks & Health Monitoring Hooks Component.

Provides internal event callback hooks and health observability placeholders for the Video Ingestion Layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from camera_analytics.ingestion.models import IngestedFrame, IngestionMetrics

logger = logging.getLogger(__name__)


@dataclass
class IngestionEventHooks:
    """Internal event hooks container for video ingestion lifecycle events.

    Callbacks can be attached for observability without requiring an external EventBus.
    """

    on_reader_started: Optional[Callable[[str], None]] = None
    on_reader_stopped: Optional[Callable[[str], None]] = None
    on_reader_failed: Optional[Callable[[str, str], None]] = None
    on_reader_recovered: Optional[Callable[[str], None]] = None
    on_frame_produced: Optional[Callable[[IngestedFrame], None]] = None
    on_buffer_overflow: Optional[Callable[[str], None]] = None
    on_queue_full: Optional[Callable[[str], None]] = None

    def trigger_started(self, pipeline_id: str) -> None:
        if self.on_reader_started:
            try:
                self.on_reader_started(pipeline_id)
            except Exception as exc:
                logger.error("IngestionEventHooks error on_reader_started: %s", exc)

    def trigger_stopped(self, pipeline_id: str) -> None:
        if self.on_reader_stopped:
            try:
                self.on_reader_stopped(pipeline_id)
            except Exception as exc:
                logger.error("IngestionEventHooks error on_reader_stopped: %s", exc)

    def trigger_failed(self, pipeline_id: str, error: str) -> None:
        if self.on_reader_failed:
            try:
                self.on_reader_failed(pipeline_id, error)
            except Exception as exc:
                logger.error("IngestionEventHooks error on_reader_failed: %s", exc)

    def trigger_recovered(self, pipeline_id: str) -> None:
        if self.on_reader_recovered:
            try:
                self.on_reader_recovered(pipeline_id)
            except Exception as exc:
                logger.error("IngestionEventHooks error on_reader_recovered: %s", exc)

    def trigger_frame_produced(self, frame: IngestedFrame) -> None:
        if self.on_frame_produced:
            try:
                self.on_frame_produced(frame)
            except Exception as exc:
                logger.error("IngestionEventHooks error on_frame_produced: %s", exc)

    def trigger_buffer_overflow(self, pipeline_id: str) -> None:
        if self.on_buffer_overflow:
            try:
                self.on_buffer_overflow(pipeline_id)
            except Exception as exc:
                logger.error("IngestionEventHooks error on_buffer_overflow: %s", exc)

    def trigger_queue_full(self, pipeline_id: str) -> None:
        if self.on_queue_full:
            try:
                self.on_queue_full(pipeline_id)
            except Exception as exc:
                logger.error("IngestionEventHooks error on_queue_full: %s", exc)
