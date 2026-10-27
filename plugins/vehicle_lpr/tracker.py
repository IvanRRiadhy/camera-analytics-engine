from typing import List, Tuple, Dict, Any, Optional


def compute_iou(box1: Tuple[float, float, float, float], box2: Tuple[float, float, float, float]) -> float:
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - intersection

    return (intersection / union) if union > 0 else 0.0


class PlateTrack:
    """Internal spatial track for a detected license plate."""

    def __init__(self, track_id: int, bbox: Tuple[float, float, float, float], conf: float, frame_idx: int):
        self.track_id = track_id
        self.bbox = bbox
        self.conf = conf
        self.first_frame = frame_idx
        self.last_frame = frame_idx
        self.age = 0
        self.hits = 1
        self.time_since_update = 0
        self.has_emitted = False

    def update(self, bbox: Tuple[float, float, float, float], conf: float, frame_idx: int) -> None:
        self.bbox = bbox
        self.conf = conf
        self.last_frame = frame_idx
        self.hits += 1
        self.time_since_update = 0


class PlateIoUTracker:
    """Lightweight internal IoU tracker for license plate detections per camera pipeline."""

    def __init__(self, max_lost_strides: int = 10, min_iou: float = 0.30):
        self.max_lost_strides = max_lost_strides
        self.min_iou = min_iou
        self.next_track_id = 1
        self.tracks: Dict[int, PlateTrack] = {}

    def update(
        self, detections: List[Tuple[float, float, float, float, float]], frame_idx: int
    ) -> Tuple[List[Tuple[PlateTrack, bool]], List[PlateTrack]]:
        """Updates tracks with new detections. Returns (list of (PlateTrack, is_updated), list of expired PlateTrack)."""
        updated_pairs: List[Tuple[PlateTrack, bool]] = []
        unmatched_dets = list(range(len(detections)))

        # Age existing tracks (measured in strides)
        for t in self.tracks.values():
            t.age += 1
            t.time_since_update += 1

        # Match existing tracks with detections via greedy IoU (one-to-one globally optimal)
        candidates = []
        for d_idx, det in enumerate(detections):
            d_box = det[:4]
            for tid, track in self.tracks.items():
                iou = compute_iou(d_box, track.bbox)
                if iou >= self.min_iou:
                    candidates.append((iou, d_idx, tid))

        candidates.sort(key=lambda c: c[0], reverse=True)

        matched_tracks = set()
        matched_dets = set()
        for iou, d_idx, tid in candidates:
            if tid in matched_tracks or d_idx in matched_dets:
                continue
            track = self.tracks[tid]
            det = detections[d_idx]
            track.update(det[:4], det[4], frame_idx)
            matched_tracks.add(tid)
            matched_dets.add(d_idx)
            updated_pairs.append((track, True))
            if d_idx in unmatched_dets:
                unmatched_dets.remove(d_idx)

        # Create new tracks for unmatched detections
        for d_idx in unmatched_dets:
            det = detections[d_idx]
            new_track = PlateTrack(self.next_track_id, det[:4], det[4], frame_idx)
            self.tracks[self.next_track_id] = new_track
            self.next_track_id += 1
            updated_pairs.append((new_track, True))

        # Prune expired tracks
        expired_tracks: List[PlateTrack] = []
        expired_ids = [tid for tid, track in self.tracks.items() if track.time_since_update > self.max_lost_strides]
        for tid in expired_ids:
            expired_tracks.append(self.tracks[tid])
            del self.tracks[tid]

        return updated_pairs, expired_tracks

    def reset(self) -> None:
        self.tracks.clear()
        self.next_track_id = 1
