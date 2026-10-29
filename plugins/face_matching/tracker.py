"""
Lightweight IoU Tracker for Face Detection Trajectories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from camera_analytics.plugins.face_matching.detector import FaceDetection

logger = logging.getLogger(__name__)


def compute_iou(box1: Tuple[float, float, float, float], box2: Tuple[float, float, float, float]) -> float:
    """Calculate Intersection-over-Union (IoU) for two [x1, y1, x2, y2] bounding boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - intersection

    return (intersection / union) if union > 0 else 0.0


class FaceTrack:
    """Represents a continuous facial trajectory across video frames."""

    def __init__(
        self,
        track_id: int,
        bbox: Tuple[float, float, float, float],
        conf: float,
        landmarks: List[Tuple[float, float]],
        frame_idx: int,
    ) -> None:
        self.track_id = track_id
        self.bbox = bbox  # (x1, y1, x2, y2)
        self.conf = conf
        self.landmarks = landmarks
        self.first_frame = frame_idx
        self.last_frame = frame_idx
        self.hits = 1
        self.time_since_update = 0
        self.has_emitted = False

        # Consensus identification status
        self.state: str = "tracking"  # "tracking" | "identified" | "unknown"
        self.identified_person_id: Optional[str] = None
        self.identified_full_name: Optional[str] = None
        self.identified_score: float = 0.0
        self.identified_margin: float = 0.0
        self.identified_meta: Dict[str, Any] = {}

    @property
    def x1(self) -> float:
        return self.bbox[0]

    @property
    def y1(self) -> float:
        return self.bbox[1]

    @property
    def x2(self) -> float:
        return self.bbox[2]

    @property
    def y2(self) -> float:
        return self.bbox[3]

    @property
    def w(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def h(self) -> float:
        return self.bbox[3] - self.bbox[1]

    def update(
        self,
        bbox: Tuple[float, float, float, float],
        conf: float,
        landmarks: List[Tuple[float, float]],
        frame_idx: int,
    ) -> None:
        """Update track state with a newly associated face detection."""
        self.bbox = bbox
        self.conf = conf
        self.landmarks = landmarks
        self.last_frame = frame_idx
        self.hits += 1
        self.time_since_update = 0


class FaceIoUTracker:
    """Lightweight 2D spatial IoU tracker for face detections."""

    def __init__(self, max_lost_strides: int = 10, min_iou: float = 0.30) -> None:
        self.max_lost_strides = int(max_lost_strides)
        self.min_iou = float(min_iou)
        self.next_track_id: int = 1
        self.tracks: Dict[int, FaceTrack] = {}

    def update(
        self,
        detections: List[FaceDetection],
        frame_idx: int,
    ) -> Tuple[List[FaceTrack], List[FaceTrack]]:
        """Associate detections with active tracks, create new tracks, and expire stale ones.

        Returns:
            Tuple of (active_tracks, expired_tracks).
        """
        # Formulate detection bboxes as [x1, y1, x2, y2]
        det_bboxes = [(d.x1, d.y1, d.x2, d.y2) for d in detections]
        det_matched: set[int] = set()
        track_matched: set[int] = set()

        active_track_ids = list(self.tracks.keys())

        # Greedy bipartite matching based on IoU overlap
        if active_track_ids and det_bboxes:
            iou_matrix = []
            for tid in active_track_ids:
                row = [compute_iou(self.tracks[tid].bbox, dbox) for dbox in det_bboxes]
                iou_matrix.append(row)

            # Match highest IoU pairs first
            matches = []
            for t_idx, tid in enumerate(active_track_ids):
                for d_idx, _ in enumerate(det_bboxes):
                    iou_score = iou_matrix[t_idx][d_idx]
                    if iou_score >= self.min_iou:
                        matches.append((iou_score, tid, d_idx))

            matches.sort(key=lambda x: x[0], reverse=True)

            for _, tid, d_idx in matches:
                if tid not in track_matched and d_idx not in det_matched:
                    track_matched.add(tid)
                    det_matched.add(d_idx)
                    det = detections[d_idx]
                    self.tracks[tid].update(
                        bbox=(det.x1, det.y1, det.x2, det.y2),
                        conf=det.score,
                        landmarks=det.landmarks,
                        frame_idx=frame_idx,
                    )

        # Increment age/lost count for unmatched tracks
        expired_tracks: List[FaceTrack] = []
        for tid in active_track_ids:
            if tid not in track_matched:
                self.tracks[tid].time_since_update += 1
                if self.tracks[tid].time_since_update > self.max_lost_strides:
                    expired_tracks.append(self.tracks.pop(tid))

        # Instantiate new tracks for unmatched detections
        for d_idx, det in enumerate(detections):
            if d_idx not in det_matched:
                new_track = FaceTrack(
                    track_id=self.next_track_id,
                    bbox=(det.x1, det.y1, det.x2, det.y2),
                    conf=det.score,
                    landmarks=det.landmarks,
                    frame_idx=frame_idx,
                )
                self.tracks[self.next_track_id] = new_track
                self.next_track_id += 1

        active_tracks = list(self.tracks.values())
        return active_tracks, expired_tracks

