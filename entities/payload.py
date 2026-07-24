"""
Analytics Payload SDK & Builders.

Provides strongly typed payload builders for all analytics domains:
    - PeoplePayload (payload.people)
    - PPEPayload (payload.ppe)
    - CrowdPayload (payload.crowd)
    - LineCrossingPayload (payload.line_crossing)
    - LoiteringPayload (payload.loitering)
    - DwellTimePayload (payload.dwell_time)
    - BehaviorPayload (payload.behavior)
    - ReIDPayload (payload.reid)
    - HeatmapPayload (payload.heatmap)
    - Dynamic custom extension namespace (payload.custom)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class PeoplePayload:
    """People analytics payload namespace."""

    count: int = 0
    confirmed_count: int = 0
    tentative_count: int = 0
    active_track_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "confirmed_count": self.confirmed_count,
            "tentative_count": self.tentative_count,
            "active_track_ids": list(self.active_track_ids),
        }


@dataclass(slots=True)
class PPEPayload:
    """Personal Protective Equipment (PPE) analytics payload namespace."""

    helmet_violations: int = 0
    vest_violations: int = 0
    gloves_violations: int = 0
    compliant_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "helmet_violations": self.helmet_violations,
            "vest_violations": self.vest_violations,
            "gloves_violations": self.gloves_violations,
            "compliant_count": self.compliant_count,
        }


@dataclass(slots=True)
class CrowdPayload:
    """Crowd density analytics payload namespace."""

    density_level: str = "NORMAL"  # LOW, NORMAL, HIGH, CRITICAL
    total_people: int = 0
    is_crowd_alert: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "density_level": self.density_level,
            "total_people": self.total_people,
            "is_crowd_alert": self.is_crowd_alert,
        }


@dataclass(slots=True)
class LineCrossingPayload:
    """Line crossing analytics payload namespace."""

    line_id: str = ""
    line_name: str = ""
    in_count: int = 0
    out_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_id": self.line_id,
            "line_name": self.line_name,
            "in_count": self.in_count,
            "out_count": self.out_count,
        }


@dataclass(slots=True)
class LoiteringPayload:
    """Loitering detection analytics payload namespace."""

    loitering_count: int = 0
    threshold_seconds: float = 30.0
    warning_track_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "loitering_count": self.loitering_count,
            "threshold_seconds": self.threshold_seconds,
            "warning_track_ids": list(self.warning_track_ids),
        }


@dataclass(slots=True)
class DwellTimePayload:
    """Dwell time analytics payload namespace."""

    average_dwell_seconds: float = 0.0
    max_dwell_seconds: float = 0.0
    zone_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "average_dwell_seconds": round(self.average_dwell_seconds, 1),
            "max_dwell_seconds": round(self.max_dwell_seconds, 1),
            "zone_id": self.zone_id,
        }


@dataclass(slots=True)
class BehaviorPayload:
    """Abnormal behavior analytics payload namespace."""

    running_count: int = 0
    falling_count: int = 0
    fighting_alert: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "running_count": self.running_count,
            "falling_count": self.falling_count,
            "fighting_alert": self.fighting_alert,
        }


@dataclass(slots=True)
class ReIDPayload:
    """Global Re-Identification analytics payload namespace."""

    global_id: Optional[int] = None
    gallery_match_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_id": self.global_id,
            "gallery_match_score": round(self.gallery_match_score, 3),
        }


@dataclass(slots=True)
class HeatmapPayload:
    """Occupancy Heatmap analytics payload namespace."""

    active_grid_cells: int = 0
    max_density_cell: tuple[int, int] = (0, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_grid_cells": self.active_grid_cells,
            "max_density_cell": list(self.max_density_cell),
        }


@dataclass(slots=True)
class AnalyticsPayload:
    """Central strongly typed Analytics Payload container.

    Analytics Modules fill properties on this builder without manually constructing JSON strings.

    Usage::

        payload = AnalyticsPayload()
        payload.people.count = 5
        payload.loitering.loitering_count = 2
        payload.custom["forklift"] = {"status": "ACTIVE", "speed": 12.5}
    """

    people: PeoplePayload = field(default_factory=PeoplePayload)
    ppe: PPEPayload = field(default_factory=PPEPayload)
    crowd: CrowdPayload = field(default_factory=CrowdPayload)
    line_crossing: LineCrossingPayload = field(default_factory=LineCrossingPayload)
    loitering: LoiteringPayload = field(default_factory=LoiteringPayload)
    dwell_time: DwellTimePayload = field(default_factory=DwellTimePayload)
    behavior: BehaviorPayload = field(default_factory=BehaviorPayload)
    reid: ReIDPayload = field(default_factory=ReIDPayload)
    heatmap: HeatmapPayload = field(default_factory=HeatmapPayload)
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert entire payload hierarchy to dictionary payload."""
        result: dict[str, Any] = {}

        if self.people.count > 0 or self.people.active_track_ids:
            result["people"] = self.people.to_dict()
        if self.ppe.helmet_violations > 0 or self.ppe.vest_violations > 0 or self.ppe.compliant_count > 0:
            result["ppe"] = self.ppe.to_dict()
        if self.crowd.total_people > 0 or self.crowd.is_crowd_alert:
            result["crowd"] = self.crowd.to_dict()
        if self.line_crossing.in_count > 0 or self.line_crossing.out_count > 0:
            result["line_crossing"] = self.line_crossing.to_dict()
        if self.loitering.loitering_count > 0 or self.loitering.warning_track_ids:
            result["loitering"] = self.loitering.to_dict()
        if self.dwell_time.average_dwell_seconds > 0.0 or self.dwell_time.max_dwell_seconds > 0.0:
            result["dwell_time"] = self.dwell_time.to_dict()
        if self.behavior.running_count > 0 or self.behavior.falling_count > 0 or self.behavior.fighting_alert:
            result["behavior"] = self.behavior.to_dict()
        if self.reid.global_id is not None:
            result["reid"] = self.reid.to_dict()
        if self.heatmap.active_grid_cells > 0:
            result["heatmap"] = self.heatmap.to_dict()

        for k, v in self.custom.items():
            result[k] = v.to_dict() if hasattr(v, "to_dict") else v

        return result
