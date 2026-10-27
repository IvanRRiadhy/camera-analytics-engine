"""
Enterprise Runtime Logger & Logging Mode Framework (Sprint H1.5D1.6E).

Manages centralized logging modes:
- PRODUCTION: High-level operational events only. Zero per-frame or per-track debug/forensic spam.
- DEBUG: Operational events + inference FPS, tracker FPS, pipeline latency, counts. Zero per-track spam.
- FORENSIC: Full verbose diagnostic execution tracing (Stage 1..10, presenter, overlay, tensor values).
"""

from __future__ import annotations

import logging
import sys
from enum import Enum
from typing import Any, Optional


class LoggingMode(str, Enum):
    PRODUCTION = "production"
    DEBUG = "debug"
    FORENSIC = "forensic"


class RuntimeLogger:
    """Centralized enterprise runtime logger manager."""

    _mode: LoggingMode = LoggingMode.PRODUCTION

    @classmethod
    def set_mode(cls, mode: str | LoggingMode) -> None:
        """Set active logging mode ('production', 'debug', 'forensic')."""
        if isinstance(mode, str):
            mode_str = mode.lower().strip()
            if mode_str == "forensic":
                cls._mode = LoggingMode.FORENSIC
            elif mode_str == "debug":
                cls._mode = LoggingMode.DEBUG
            else:
                cls._mode = LoggingMode.PRODUCTION
        else:
            cls._mode = mode

    @classmethod
    def get_mode(cls) -> LoggingMode:
        return cls._mode

    @classmethod
    def is_production(cls) -> bool:
        return cls._mode == LoggingMode.PRODUCTION

    @classmethod
    def is_debug(cls) -> bool:
        return cls._mode in (LoggingMode.DEBUG, LoggingMode.FORENSIC)

    @classmethod
    def is_forensic(cls) -> bool:
        return cls._mode == LoggingMode.FORENSIC

    @classmethod
    def forensic(cls, logger: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
        """Emit log ONLY when logging mode is FORENSIC."""
        if cls.is_forensic():
            logger.info(message, *args, **kwargs)

    @classmethod
    def debug_metric(cls, logger: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
        """Emit debug metric log when logging mode is DEBUG or FORENSIC."""
        if cls.is_debug():
            logger.info(message, *args, **kwargs)
