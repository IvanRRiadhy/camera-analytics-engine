"""
Inference visualization and validation utility.

Renders visual overlays on video frames for validating YOLO26m-Pose detections, BoT-SORT tracks,
Zone Engine, and Live Camera Performance Benchmark Metrics:
    - Polygon Zones (translucent fill, border outline, zone name label)
    - Track ID, Bounding Box & Confidence score
    - Track Age, Hit count, Track State (GREEN: Confirmed, YELLOW: Tentative, RED: Lost), and Current Zone status
    - 17 COCO Keypoints & skeleton limb connections
    - Color-coded Ground Point estimation (Green: Both Ankles, Yellow: Single Ankle, Red: BBox Fallback)
    - Structured Live Performance Benchmark Panel (FPS, Latencies, Hardware CPU/GPU, Track Stats, Frame Info)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional, Sequence

import numpy as np

from camera_analytics.models.detection import Detection, Keypoint, PoseKeypoints

if TYPE_CHECKING:
    from camera_analytics.core.zone_engine import TrackZoneState
    from camera_analytics.models.track import Track
    from camera_analytics.models.zone import Zone
    from camera_analytics.utils.resource_monitor import BenchmarkCollector

logger = logging.getLogger(__name__)

# COCO 17-Keypoint skeleton connection pairs (indices 0 to 16)
COCO_SKELETON_PAIRS: tuple[tuple[int, int], ...] = (
    (0, 1),   # nose -> left_eye
    (0, 2),   # nose -> right_eye
    (1, 3),   # left_eye -> left_ear
    (2, 4),   # right_eye -> right_ear
    (5, 6),   # left_shoulder -> right_shoulder
    (5, 7),   # left_shoulder -> left_elbow
    (7, 9),   # left_elbow -> left_wrist
    (6, 8),   # right_shoulder -> right_elbow
    (8, 10),  # right_elbow -> right_wrist
    (5, 11),  # left_shoulder -> left_hip
    (6, 12),  # right_shoulder -> right_hip
    (11, 12), # left_hip -> right_hip
    (11, 13), # left_hip -> left_knee
    (13, 15), # left_knee -> left_ankle
    (12, 14), # right_hip -> right_knee
    (14, 16), # right_knee -> right_ankle
)

# Color constants (BGR format for OpenCV)
COLOR_BBOX_DETECTION = (255, 178, 50) # Cyan/Blue-Orange for raw detections
COLOR_BBOX_CONFIRMED = (0, 220, 0)    # Green for Confirmed Tracks
COLOR_BBOX_TENTATIVE = (0, 220, 255)  # Yellow/Gold for Tentative Tracks
COLOR_BBOX_LOST = (0, 0, 255)         # Red for Lost Tracks
COLOR_KEYPOINT = (0, 215, 255)        # Yellow/Gold
COLOR_SKELETON = (255, 255, 0)        # Cyan
COLOR_GROUND_BOTH = (0, 255, 0)       # Green: Both Ankles
COLOR_GROUND_SINGLE = (0, 255, 255)   # Yellow: Single Ankle
COLOR_GROUND_FALLBACK = (0, 0, 255)   # Red: BBox Fallback
COLOR_PANEL_BG = (20, 20, 20)         # Dark Gray Background
COLOR_PANEL_TEXT = (240, 240, 240)    # White Text
COLOR_PANEL_HEADER = (0, 215, 255)  # Yellow Header Text


class PoseVisualizer:
    """Renders visual validation overlays on image frames for pose detection, object tracking, and live performance monitoring."""

    def __init__(self, keypoint_threshold: float = 0.5) -> None:
        self._keypoint_threshold = keypoint_threshold
        try:
            import cv2
            self._cv2 = cv2
        except ImportError as err:
            raise RuntimeError(
                "OpenCV (cv2) is required for visualization. "
                "Install via 'pip install opencv-python'."
            ) from err

    def draw_frame(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        frame_id: int = 0,
        fps: float = 0.0,
        device: str = "CPU",
        model_name: str = "YOLO26m-Pose",
    ) -> np.ndarray:
        """Render raw detection overlays onto a copy of the given image frame."""
        cv2 = self._cv2
        canvas = frame.copy()
        h, w = canvas.shape[:2]

        for idx, det in enumerate(detections, start=1):
            self._draw_detection(canvas, det, det_index=idx)

        self._draw_debug_panel(
            canvas,
            device=device,
            model_name=model_name,
            resolution=(w, h),
            fps=fps,
            detection_count=len(detections),
            frame_id=frame_id,
        )

        return canvas

    def draw_tracks(
        self,
        frame: np.ndarray,
        tracks: Sequence[Track],
        zones: Optional[Sequence[Zone]] = None,
        track_zone_states: Optional[dict[int, dict[str, TrackZoneState]]] = None,
        frame_id: int = 0,
        fps: float = 0.0,
        device: str = "CPU",
        model_name: str = "YOLO26m-Pose",
        tracker_name: str = "BoT-SORT",
        benchmark_collector: Optional[BenchmarkCollector] = None,
    ) -> np.ndarray:
        """Render active track overlays, Polygon Zones, and optional Live Performance Panel onto frame."""
        cv2 = self._cv2
        canvas = frame.copy()

        if zones:
            self._draw_polygon_zones(canvas, zones)

        confirmed_count = 0
        lost_count = 0
        tentative_count = 0
        for track in tracks:
            if getattr(track, "is_lost", False):
                lost_count += 1
            elif track.is_confirmed:
                confirmed_count += 1
            else:
                tentative_count += 1

            zone_label_suffix = ""
            if track_zone_states and track.track_id in track_zone_states and zones:
                inside_zone_names = []
                for z in zones:
                    st = track_zone_states[track.track_id].get(z.zone_id)
                    if st and st.name in ("ENTER", "INSIDE"):
                        inside_zone_names.append(z.name)
                if inside_zone_names:
                    zone_label_suffix = f" [{', '.join(inside_zone_names)}]"

            self._draw_single_track(canvas, track, zone_suffix=zone_label_suffix)

        if benchmark_collector is not None:
            benchmark_collector.update_track_counts(
                active=len(tracks),
                confirmed=confirmed_count,
                tentative=tentative_count,
                lost=lost_count,
            )
            self._draw_live_benchmark_panel(canvas, benchmark_collector, frame_id=frame_id)
        else:
            extra_lines = [
                f"Tracker: {tracker_name}",
                f"Active Tracks: {len(tracks)} ({confirmed_count} Conf, {lost_count} Lost)",
            ]
            if zones:
                extra_lines.append(f"Configured Zones: {len(zones)}")

            self._draw_debug_panel(
                canvas,
                device=device,
                model_name=model_name,
                resolution=(canvas.shape[1], canvas.shape[0]),
                fps=fps,
                detection_count=len(tracks),
                frame_id=frame_id,
                extra_lines=extra_lines,
            )

        return canvas

    def _draw_live_benchmark_panel(
        self, canvas: np.ndarray, collector: BenchmarkCollector, frame_id: int
    ) -> None:
        """Draw structured live performance panel on top-left of the canvas."""
        cv2 = self._cv2
        hw = collector.latest_hw
        sample = collector._samples[-1] if collector._samples else None

        tot_lat = sample.total_latency_ms if sample else 0.0
        disp_fps = sample.fps if sample else 0.0
        det_ms = sample.detection_time_ms if sample else 0.0
        trk_ms = sample.tracking_time_ms if sample else 0.0

        lines = [
            "--- LIVE CAMERA PERFORMANCE & STABILITY ---",
            f"FPS: Display {disp_fps:.1f} | Cap {collector.input_resolution[0]}x{collector.input_resolution[1]}",
            f"Latency: Total {tot_lat:.1f}ms (Det {det_ms:.1f}ms, Trk {trk_ms:.1f}ms)",
            f"Hardware: GPU {hw.gpu_percent:.1f}% | VRAM {hw.vram_used_mb:.0f}/{hw.vram_total_mb:.0f} MB",
            f"          CPU {hw.cpu_percent:.1f}% | RAM  {hw.ram_used_mb:.0f}/{hw.ram_total_mb:.0f} MB",
            f"Tracking: Active {collector.current_active_tracks} (Conf {collector.current_confirmed_tracks}, Lost {collector.current_lost_tracks})",
            f"          Created {collector.tracks_created} | Removed {collector.tracks_removed}",
            f"Model: YOLO26m-Pose | Tracker: BoT-SORT",
            f"Frame: #{frame_id} | Drops: {collector.dropped_frames} | Reconnects: {collector.reconnect_count}",
        ]

        panel_w = 390
        panel_h = len(lines) * 20 + 16
        px, py = 15, 15

        sub_img = canvas[py : py + panel_h, px : px + panel_w]
        panel = np.full_like(sub_img, COLOR_PANEL_BG)
        blended = cv2.addWeighted(sub_img, 0.25, panel, 0.75, 0)
        canvas[py : py + panel_h, px : px + panel_w] = blended
        cv2.rectangle(canvas, (px, py), (px + panel_w, py + panel_h), (80, 80, 80), thickness=1)

        y_offset = py + 20
        for idx, line in enumerate(lines):
            txt_color = COLOR_PANEL_HEADER if idx == 0 else COLOR_PANEL_TEXT
            cv2.putText(
                canvas,
                line,
                (px + 10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                txt_color,
                thickness=1,
                lineType=cv2.LINE_AA,
            )
            y_offset += 20

    def _draw_polygon_zones(self, canvas: np.ndarray, zones: Sequence[Zone]) -> None:
        """Draw translucent filled polygon zones with boundary outlines and zone names."""
        cv2 = self._cv2

        for zone in zones:
            if not zone.is_valid or not zone.points:
                continue

            pts = np.array(zone.as_polygon, dtype=np.int32)
            overlay = canvas.copy()
            r, g, b = zone.color
            bgr_color = (b, g, r)

            cv2.fillPoly(overlay, [pts], color=bgr_color)
            cv2.addWeighted(overlay, 0.20, canvas, 0.80, 0, canvas)
            cv2.polylines(canvas, [pts], isClosed=True, color=bgr_color, thickness=2, lineType=cv2.LINE_AA)

            top_pt = min(zone.points, key=lambda p: (p.y, p.x))
            label = f"Zone: {zone.name}"
            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)

            cv2.rectangle(
                canvas,
                (top_pt.x, top_pt.y - th - 6),
                (top_pt.x + tw + 8, top_pt.y + baseline),
                bgr_color,
                thickness=-1,
            )
            cv2.putText(
                canvas,
                label,
                (top_pt.x + 4, top_pt.y - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                thickness=1,
                lineType=cv2.LINE_AA,
            )

    def _draw_single_track(
        self, canvas: np.ndarray, track: Track, zone_suffix: str = ""
    ) -> None:
        """Draw BBox, Track ID, status, keypoint skeleton, and ground point for a single Track object."""
        cv2 = self._cv2
        bbox = track.bbox

        if getattr(track, "is_lost", False):
            bbox_color = COLOR_BBOX_LOST
            state_str = "LOST"
        elif track.is_confirmed:
            bbox_color = COLOR_BBOX_CONFIRMED
            state_str = "CONFIRMED"
        else:
            bbox_color = COLOR_BBOX_TENTATIVE
            state_str = "TENTATIVE"

        cv2.rectangle(
            canvas,
            (bbox.x1, bbox.y1),
            (bbox.x2, bbox.y2),
            bbox_color,
            thickness=2,
        )

        label = f"ID: {track.track_id} [{state_str}] hits:{track.hit_count}{zone_suffix}"
        (tw, th), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1
        )
        label_y = max(bbox.y1 - 8, th + 4)

        cv2.rectangle(
            canvas,
            (bbox.x1, label_y - th - 4),
            (bbox.x1 + tw + 6, label_y + baseline),
            bbox_color,
            thickness=-1,
        )
        cv2.putText(
            canvas,
            label,
            (bbox.x1 + 3, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 0),
            thickness=1,
            lineType=cv2.LINE_AA,
        )

        if track.detection.keypoints is not None:
            self._draw_pose_skeleton(canvas, track.detection.keypoints)

        self._draw_ground_point(canvas, track.detection)

    def _draw_detection(
        self, canvas: np.ndarray, det: Detection, det_index: int
    ) -> None:
        """Draw BBox, keypoint skeleton, and ground point for a single detection."""
        cv2 = self._cv2
        bbox = det.bbox

        cv2.rectangle(
            canvas,
            (bbox.x1, bbox.y1),
            (bbox.x2, bbox.y2),
            COLOR_BBOX_DETECTION,
            thickness=2,
        )

        label = f"#{det_index} Person {det.confidence:.2f}"
        (tw, th), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        label_y = max(bbox.y1 - 8, th + 4)
        cv2.rectangle(
            canvas,
            (bbox.x1, label_y - th - 4),
            (bbox.x1 + tw + 6, label_y + baseline),
            COLOR_BBOX_DETECTION,
            thickness=-1,
        )
        cv2.putText(
            canvas,
            label,
            (bbox.x1 + 3, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            thickness=1,
            lineType=cv2.LINE_AA,
        )

        if det.keypoints is not None:
            self._draw_pose_skeleton(canvas, det.keypoints)

        self._draw_ground_point(canvas, det)

    def _draw_pose_skeleton(
        self, canvas: np.ndarray, pose: PoseKeypoints
    ) -> None:
        """Draw COCO 17-keypoint skeleton lines and joint points."""
        cv2 = self._cv2
        kps = pose.keypoints

        for p1_idx, p2_idx in COCO_SKELETON_PAIRS:
            if p1_idx < len(kps) and p2_idx < len(kps):
                kp1 = kps[p1_idx]
                kp2 = kps[p2_idx]
                if kp1.confidence >= self._keypoint_threshold and kp2.confidence >= self._keypoint_threshold:
                    pt1 = (int(kp1.x), int(kp1.y))
                    pt2 = (int(kp2.x), int(kp2.y))
                    cv2.line(canvas, pt1, pt2, COLOR_SKELETON, thickness=2, lineType=cv2.LINE_AA)

        for kp in kps:
            if kp.confidence >= self._keypoint_threshold:
                pt = (int(kp.x), int(kp.y))
                cv2.circle(canvas, pt, radius=4, color=COLOR_KEYPOINT, thickness=-1)
                cv2.circle(canvas, pt, radius=5, color=(0, 0, 0), thickness=1)

    def _draw_ground_point(self, canvas: np.ndarray, det: Detection) -> None:
        """Determine ground point source, choose color code, and render crosshair marker."""
        cv2 = self._cv2
        gp_x, gp_y = det.ground_point
        pt = (int(gp_x), int(gp_y))

        color = COLOR_GROUND_FALLBACK
        source_label = "Ground: Fallback (BBox)"

        if det.keypoints is not None:
            left_ankle = det.keypoints.left_ankle
            right_ankle = det.keypoints.right_ankle
            l_vis = left_ankle is not None and left_ankle.confidence >= self._keypoint_threshold
            r_vis = right_ankle is not None and right_ankle.confidence >= self._keypoint_threshold

            if l_vis and r_vis:
                color = COLOR_GROUND_BOTH
                source_label = "Ground: Both Ankles"
            elif l_vis or r_vis:
                color = COLOR_GROUND_SINGLE
                source_label = "Ground: Single Ankle"

        cv2.circle(canvas, pt, radius=7, color=color, thickness=-1)
        cv2.circle(canvas, pt, radius=10, color=(255, 255, 255), thickness=2)
        cv2.line(canvas, (pt[0] - 12, pt[1]), (pt[0] + 12, pt[1]), color, thickness=2)
        cv2.line(canvas, (pt[0], pt[1] - 12), (pt[0], pt[1] + 12), color, thickness=2)

        cv2.putText(
            canvas,
            source_label,
            (pt[0] + 14, pt[1] + 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            thickness=1,
            lineType=cv2.LINE_AA,
        )

    def _draw_debug_panel(
        self,
        canvas: np.ndarray,
        device: str,
        model_name: str,
        resolution: tuple[int, int],
        fps: float,
        detection_count: int,
        frame_id: int,
        extra_lines: Optional[list[str]] = None,
    ) -> None:
        """Draw a dark translucent debug panel on top-left with system information."""
        cv2 = self._cv2

        lines = [
            f"Device: {device}",
            f"Model: {model_name}",
        ]
        if extra_lines:
            lines.extend(extra_lines)
        lines.extend([
            f"Resolution: {resolution[0]}x{resolution[1]}",
            f"Processing FPS: {fps:.1f}",
            f"Frame #: {frame_id}",
        ])

        panel_w = 280
        panel_h = len(lines) * 22 + 16
        px, py = 15, 15

        sub_img = canvas[py : py + panel_h, px : px + panel_w]
        panel = np.full_like(sub_img, COLOR_PANEL_BG)
        blended = cv2.addWeighted(sub_img, 0.25, panel, 0.75, 0)
        canvas[py : py + panel_h, px : px + panel_w] = blended
        cv2.rectangle(canvas, (px, py), (px + panel_w, py + panel_h), (80, 80, 80), thickness=1)

        y_offset = py + 22
        for line in lines:
            cv2.putText(
                canvas,
                line,
                (px + 10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                COLOR_PANEL_TEXT,
                thickness=1,
                lineType=cv2.LINE_AA,
            )
            y_offset += 22
