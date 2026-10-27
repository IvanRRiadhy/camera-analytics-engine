"""
RefreshScheduler Infrastructure (Sprint H1.5D1.5).

Manages adaptive refresh rate intervals for Studio rendering loops (Idle: 2 FPS, Normal: 5 FPS, Debug: 10 FPS, Benchmark: 20 FPS).
Separates refresh loop control from EngineStudioCoordinator.
"""

from __future__ import annotations

from enum import Enum


class AdaptiveRefreshMode(str, Enum):
    """Adaptive refresh rate modes."""

    IDLE = "IDLE"             # 2 FPS
    NORMAL = "NORMAL"         # 5 FPS
    DEBUG = "DEBUG"           # 10 FPS
    BENCHMARK = "BENCHMARK"   # 20 FPS


class RefreshScheduler:
    """Manages refresh rate target and interval calculations."""

    REFRESH_RATES: dict[AdaptiveRefreshMode, float] = {
        AdaptiveRefreshMode.IDLE: 2.0,
        AdaptiveRefreshMode.NORMAL: 5.0,
        AdaptiveRefreshMode.DEBUG: 10.0,
        AdaptiveRefreshMode.BENCHMARK: 20.0,
    }

    def __init__(self, default_mode: AdaptiveRefreshMode = AdaptiveRefreshMode.DEBUG) -> None:
        self.mode = default_mode

    @property
    def target_fps(self) -> float:
        """Return target FPS for current refresh mode."""
        return self.REFRESH_RATES.get(self.mode, 10.0)

    @property
    def interval_seconds(self) -> float:
        """Return target refresh interval in seconds."""
        return round(1.0 / self.target_fps, 4)

    def set_mode(self, mode: AdaptiveRefreshMode) -> None:
        """Set active adaptive refresh mode."""
        self.mode = mode
