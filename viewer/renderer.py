"""
Overlay Renderer Component.

Complete drawing engine rendering FramePresentation view models onto image frames:
    Bounding Boxes, 17-Point COCO Pose Skeletons, Ground Points, Track History Trails,
    Track Labels, Zone Polygons, Zone Occupancy Banners, Event Alerts, and Runtime HUD Metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import cv2
import numpy as np

from camera_analytics.viewer.models import FramePresentation

logger = logging.getLogger(__name__)

# COCO 17-Keypoint Pair Connections for Pose Skeleton Lines
_COCO_SKELETON_CONNECTIONS = (
    (0, 1), (0, 2), (1, 3), (2, 4),        # Facial keypoints (Nose, Eyes, Ears)
    (5, 6),                               # Shoulders
    (5, 7), (7, 9),                       # Left Arm (Shoulder -> Elbow -> Wrist)
    (6, 8), (8, 10),                      # Right Arm (Shoulder -> Elbow -> Wrist)
    (5, 11), (6, 12),                     # Torso (Shoulder -> Hip)
    (11, 12),                             # Hips
    (11, 13), (13, 15),                   # Left Leg (Hip -> Knee -> Ankle)
    (12, 14), (14, 16),                   # Right Leg (Hip -> Knee -> Ankle)
)


@dataclass(slots=True)
class RenderOptions:
    """Boolean toggles for controlling visual element rendering."""

    draw_bbox: bool = True
    draw_skeleton: bool = True
    draw_ground_point: bool = True
    draw_track_id: bool = True
    draw_track_history: bool = True
    draw_zones: bool = True
    draw_metrics: bool = True
    draw_events: bool = True


class OverlayRenderer:
    """Complete drawing engine rendering FramePresentation view models onto OpenCV images."""

    def __init__(self, options: Optional[RenderOptions] = None) -> None:
        self.options = options or RenderOptions()

    def render(self, presentation: FramePresentation) -> np.ndarray:
        """Render complete presentation overlay on image copy.

        Args:
            presentation: FramePresentation view model.

        Returns:
            Rendered NumPy BGR image array.
        """
        canvas = presentation.image.copy()

        # 1. Render Zones & Spatial Snapshots via SpatialVisualizer
        if self.options.draw_zones:
            if hasattr(presentation, "spatial_snapshot") and presentation.spatial_snapshot is not None:
                from camera_analytics.core.spatial.visualizer import SpatialVisualizer
                visualizer = SpatialVisualizer()
                canvas = visualizer.render_snapshot(canvas, presentation.spatial_snapshot)
            elif presentation.zones:
                for zone in presentation.zones:
                    if len(zone.points) >= 3:
                        pts = np.array([[p.x, p.y] for p in zone.points], np.int32)
                        pts = pts.reshape((-1, 1, 2))
                        
                        # Draw Zone Polygon
                        cv2.polylines(canvas, [pts], isClosed=True, color=zone.color_rgb, thickness=2)
                        
                        # Fill semi-transparent polygon
                        overlay = canvas.copy()
                        cv2.fillPoly(overlay, [pts], color=zone.color_rgb)
                        cv2.addWeighted(overlay, 0.25, canvas, 0.75, 0, canvas)

                        # Draw Zone Name & Occupancy Label Header
                        label_pos = (zone.points[0].x, max(25, zone.points[0].y - 10))
                        cv2.putText(
                            canvas,
                            zone.label,
                            label_pos,
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            zone.color_rgb,
                            2,
                        )

        # 2. Render Track History Trails
        if self.options.draw_track_history and presentation.tracks:
            for trk in presentation.tracks:
                if len(trk.history) >= 2:
                    h_pts = np.array([[p.x, p.y] for p in trk.history], np.int32)
                    h_pts = h_pts.reshape((-1, 1, 2))
                    cv2.polylines(canvas, [h_pts], isClosed=False, color=(255, 200, 0), thickness=2)

        # 3. Render Ground Points
        if self.options.draw_ground_point and presentation.skeletons:
            for skel in presentation.skeletons:
                if skel.ground_point is not None:
                    gp = skel.ground_point
                    cv2.circle(canvas, (gp.x, gp.y), radius=6, color=(0, 0, 255), thickness=-1)
                    cv2.circle(canvas, (gp.x, gp.y), radius=8, color=(255, 255, 255), thickness=1)

        # 4. Render 17-Point COCO Pose Skeletons
        if self.options.draw_skeleton and presentation.skeletons:
            for skel in presentation.skeletons:
                kps = skel.keypoints
                if len(kps) >= 17:
                    # Draw connecting bone lines
                    for idx1, idx2 in _COCO_SKELETON_CONNECTIONS:
                        if idx1 < len(kps) and idx2 < len(kps):
                            p1, p2 = kps[idx1], kps[idx2]
                            if p1.confidence > 0.3 and p2.confidence > 0.3:
                                cv2.line(canvas, (p1.x, p1.y), (p2.x, p2.y), color=skel.color_rgb, thickness=2)

                    # Draw keypoint joint circles
                    for kp in kps:
                        if kp.confidence > 0.3:
                            cv2.circle(canvas, (kp.x, kp.y), radius=3, color=(0, 255, 255), thickness=-1)

        # 5. Render Bounding Boxes & Track Header Labels
        if self.options.draw_bbox and presentation.boxes:
            for box in presentation.boxes:
                # Bounding Box Rectangle
                cv2.rectangle(
                    canvas,
                    (box.x1, box.y1),
                    (box.x2, box.y2),
                    color=box.color_rgb,
                    thickness=2,
                )

                # Header Tag Label
                if self.options.draw_track_id and box.label:
                    label_size, _ = cv2.getTextSize(box.label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    lbl_w, lbl_h = label_size
                    cv2.rectangle(
                        canvas,
                        (box.x1, max(0, box.y1 - lbl_h - 10)),
                        (box.x1 + lbl_w + 6, max(lbl_h + 10, box.y1)),
                        color=box.color_rgb,
                        thickness=-1,
                    )
                    cv2.putText(
                        canvas,
                        box.label,
                        (box.x1 + 3, max(lbl_h + 4, box.y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 0),
                        2,
                    )

        # 6. Render HUD Runtime Metrics with Semi-Transparent Background Box
        if self.options.draw_metrics and presentation.metrics:
            m = presentation.metrics
            lines = [
                f"CAMERA: {m.camera_name} ({m.camera_id}) | GPU:{m.gpu_id}",
                f"FPS In: {m.fps_input:.1f} | Latency: {m.read_latency_ms:.1f}ms + {m.pipeline_latency_ms:.1f}ms",
                f"Queue Size: {m.queue_size} | Active Tracks: {m.active_tracks_count} | Zones: {m.active_zones_count}",
            ]

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.55
            thickness = 2
            line_height = 24
            padding = 10

            # Calculate box dimensions for text block
            max_w = 0
            for line in lines:
                (tw, _), _ = cv2.getTextSize(line, font, font_scale, thickness)
                if tw > max_w:
                    max_w = tw

            box_x1 = 12
            box_y1 = 10
            box_x2 = box_x1 + max_w + (padding * 2)
            box_y2 = box_y1 + (len(lines) * line_height) + padding

            # Draw semi-transparent dark grey background box
            h_c, w_c = canvas.shape[:2]
            box_x2 = min(w_c - 5, box_x2)
            box_y2 = min(h_c - 5, box_y2)

            overlay = canvas.copy()
            cv2.rectangle(overlay, (box_x1, box_y1), (box_x2, box_y2), (30, 30, 30), -1)
            cv2.addWeighted(overlay, 0.65, canvas, 0.35, 0, canvas)
            cv2.rectangle(canvas, (box_x1, box_y1), (box_x2, box_y2), (80, 80, 80), 1)

            # Render yellow text over the background box
            y0 = box_y1 + padding + 15
            for line in lines:
                cv2.putText(
                    canvas,
                    line,
                    (box_x1 + padding, y0),
                    font,
                    font_scale,
                    (0, 255, 255),
                    thickness,
                    cv2.LINE_AA,
                )
                y0 += line_height

        return canvas
