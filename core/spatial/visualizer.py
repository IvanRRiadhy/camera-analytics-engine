"""
Decoupled Multi-Pass Spatial Rendering Engine (RenderPass / RenderCommand Architecture).

Eliminates hardcoded OpenCV calls from visualizer logic by executing a 7-pass
graphics rendering pipeline over an intermediate RenderCommand buffer.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

import cv2
import numpy as np

from camera_analytics.core.spatial.models import (
    BoundingBox2D,
    FrameSpatialSnapshot,
    PixelPoint,
    ZoneModel,
    ZoneType,
)

logger = logging.getLogger(__name__)


# --- Render Commands ---

class RenderCommand(ABC):
    """Abstract Graphics Render Command."""


@dataclass(frozen=True, slots=True)
class DrawPolygonCommand(RenderCommand):
    points: list[Tuple[int, int]]
    color_bgr: Tuple[int, int, int]
    thickness: int = 2
    fill: bool = False
    alpha: float = 0.25
    is_closed: bool = True


@dataclass(frozen=True, slots=True)
class DrawCircleCommand(RenderCommand):
    center: Tuple[int, int]
    radius: int
    color_bgr: Tuple[int, int, int]
    thickness: int = -1


@dataclass(frozen=True, slots=True)
class DrawRectangleCommand(RenderCommand):
    min_pt: Tuple[int, int]
    max_pt: Tuple[int, int]
    color_bgr: Tuple[int, int, int]
    thickness: int = 2


@dataclass(frozen=True, slots=True)
class DrawTextCommand(RenderCommand):
    text: str
    position: Tuple[int, int]
    color_bgr: Tuple[int, int, int]
    font_scale: float = 0.5
    thickness: int = 1
    bg_color_bgr: Tuple[int, int, int] | None = None


# --- Render Passes ---

class RenderPass(ABC):
    """Abstract Multi-Pass Graphics Rendering Pass."""

    @abstractmethod
    def execute(self, snapshot: FrameSpatialSnapshot, commands: list[RenderCommand]) -> None:
        """Execute pass logic and emit RenderCommands into command buffer."""


class ZoneFillPass(RenderPass):
    """Pass 1: Polygon Semi-Transparent Fill."""

    def execute(self, snapshot: FrameSpatialSnapshot, commands: list[RenderCommand]) -> None:
        for zone in snapshot.active_zones:
            if zone.type == ZoneType.FULL_FRAME or len(zone.polygon_pixels) < 3:
                continue
            pts = [p.to_tuple() for p in zone.polygon_pixels]
            b, g, r = zone.color
            commands.append(
                DrawPolygonCommand(
                    points=pts,
                    color_bgr=(b, g, r),
                    fill=True,
                    alpha=0.20,
                )
            )


class ZoneBorderPass(RenderPass):
    """Pass 2: Polygon Borders & Vertices."""

    def execute(self, snapshot: FrameSpatialSnapshot, commands: list[RenderCommand]) -> None:
        for zone in snapshot.active_zones:
            if zone.type == ZoneType.FULL_FRAME or len(zone.polygon_pixels) < 2:
                continue
            pts = [p.to_tuple() for p in zone.polygon_pixels]
            b, g, r = zone.color
            commands.append(
                DrawPolygonCommand(
                    points=pts,
                    color_bgr=(b, g, r),
                    thickness=2,
                    fill=False,
                    is_closed=(zone.type != ZoneType.LINE),
                )
            )
            # Render vertex circles
            for p in zone.polygon_pixels:
                commands.append(
                    DrawCircleCommand(
                        center=p.to_tuple(),
                        radius=4,
                        color_bgr=(0, 255, 255),
                        thickness=-1,
                    )
                )


class ZoneLabelPass(RenderPass):
    """Pass 3: Zone Labels & Centroid Markers."""

    def execute(self, snapshot: FrameSpatialSnapshot, commands: list[RenderCommand]) -> None:
        for zone in snapshot.active_zones:
            cx, cy = zone.centroid.x, zone.centroid.y
            count = snapshot.occupancy_counts.get(zone.id, 0)
            lbl = f"{zone.name} [{count} Persons]"
            commands.append(
                DrawCircleCommand(
                    center=(cx, cy),
                    radius=4,
                    color_bgr=(255, 255, 255),
                    thickness=-1,
                )
            )
            commands.append(
                DrawTextCommand(
                    text=lbl,
                    position=(cx - 30, max(20, cy - 8)),
                    color_bgr=(255, 255, 255),
                    font_scale=0.5,
                    thickness=2,
                    bg_color_bgr=(0, 0, 0),
                )
            )


class TrackGroundPointPass(RenderPass):
    """Pass 6: Pose-Based Ground Point Circles & Track ID Badges."""

    def execute(self, snapshot: FrameSpatialSnapshot, commands: list[RenderCommand]) -> None:
        for tid, st in snapshot.track_states.items():
            gp = st.ground_point.to_tuple()
            # Draw Ground Point Marker
            commands.append(
                DrawCircleCommand(
                    center=gp,
                    radius=5,
                    color_bgr=(0, 0, 255),
                    thickness=-1,
                )
            )
            commands.append(
                DrawCircleCommand(
                    center=gp,
                    radius=7,
                    color_bgr=(255, 255, 255),
                    thickness=1,
                )
            )
            # Render ID Badge
            zones_str = ",".join(st.active_zone_ids) if st.active_zone_ids else "OUT"
            commands.append(
                DrawTextCommand(
                    text=f"ID:{tid} ({zones_str})",
                    position=(gp[0] + 8, gp[1] - 8),
                    color_bgr=(0, 255, 255),
                    font_scale=0.45,
                    thickness=1,
                    bg_color_bgr=(0, 0, 0),
                )
            )


# --- OpenCV Canvas Renderer Backend ---

class OpenCVCanvasRenderer:
    """Low-Level Backend Executor rendering RenderCommands onto OpenCV frames."""

    def render(self, frame: np.ndarray, commands: Sequence[RenderCommand]) -> np.ndarray:
        canvas = frame.copy()

        for cmd in commands:
            if isinstance(cmd, DrawPolygonCommand):
                pts = np.array(cmd.points, dtype=np.int32).reshape((-1, 1, 2))
                if cmd.fill:
                    overlay = canvas.copy()
                    cv2.fillPoly(overlay, [pts], cmd.color_bgr)
                    cv2.addWeighted(overlay, cmd.alpha, canvas, 1.0 - cmd.alpha, 0, canvas)
                else:
                    cv2.polylines(canvas, [pts], isClosed=cmd.is_closed, color=cmd.color_bgr, thickness=cmd.thickness, lineType=cv2.LINE_AA)

            elif isinstance(cmd, DrawCircleCommand):
                cv2.circle(canvas, cmd.center, cmd.radius, cmd.color_bgr, cmd.thickness, cv2.LINE_AA)

            elif isinstance(cmd, DrawRectangleCommand):
                cv2.rectangle(canvas, cmd.min_pt, cmd.max_pt, cmd.color_bgr, cmd.thickness, cv2.LINE_AA)

            elif isinstance(cmd, DrawTextCommand):
                x, y = cmd.position
                if cmd.bg_color_bgr:
                    size, _ = cv2.getTextSize(cmd.text, cv2.FONT_HERSHEY_SIMPLEX, cmd.font_scale, cmd.thickness)
                    w, h = size
                    cv2.rectangle(canvas, (x - 2, max(0, y - h - 4)), (x + w + 4, y + 4), cmd.bg_color_bgr, -1)
                cv2.putText(canvas, cmd.text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, cmd.font_scale, cmd.color_bgr, cmd.thickness, cv2.LINE_AA)

        return canvas


# --- Multi-Pass Spatial Visualizer Pipeline ---

class SpatialVisualizer:
    """Decoupled Multi-Pass Spatial Visualizer Pipeline."""

    def __init__(self) -> None:
        self.passes: list[RenderPass] = [
            ZoneFillPass(),
            ZoneBorderPass(),
            ZoneLabelPass(),
            TrackGroundPointPass(),
        ]
        self.renderer = OpenCVCanvasRenderer()

    def render_snapshot(self, frame: np.ndarray, snapshot: FrameSpatialSnapshot) -> np.ndarray:
        command_buffer: list[RenderCommand] = []

        # Execute all graphics passes sequentially into command buffer
        for r_pass in self.passes:
            r_pass.execute(snapshot, command_buffer)

        # Execute command buffer on backend renderer
        return self.renderer.render(frame, command_buffer)
