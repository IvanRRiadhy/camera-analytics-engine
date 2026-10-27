from typing import List, Tuple, Optional, Any
import numpy as np


class PlateLocalizer:
    """Localizes plate bounding boxes using either a direct YOLO detector or fixed ROI."""

    def __init__(self, mode: str = "detector", roi: Optional[List[float]] = None):
        self.mode = mode
        self.roi = roi  # [x1, y1, x2, y2] normalized

    def localize(
        self,
        frame: np.ndarray,
        detector: Any = None,
        conf: float = 0.25,
        iou: float = 0.45,
        imgsz: int = 640,
        device: Any = 0,
    ) -> List[Tuple[float, float, float, float, float]]:
        """Returns list of plate detections: (x1, y1, x2, y2, confidence)."""
        h, w = frame.shape[:2]
        if self.mode == "roi":
            if self.roi and len(self.roi) == 4:
                rx1, ry1, rx2, ry2 = self.roi
                x1, y1 = float(rx1 * w), float(ry1 * h)
                x2, y2 = float(rx2 * w), float(ry2 * h)
                return [(x1, y1, x2, y2, 1.0)]
            # Fallback to center 50% ROI if none configured
            return [(w * 0.25, h * 0.25, w * 0.75, h * 0.75, 1.0)]

        if detector is None:
            return []

        res = detector.predict(
            source=frame,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            device=device,
            verbose=False,
        )

        detections = []
        if res and len(res) > 0 and len(res[0].boxes) > 0:
            for b in res[0].boxes:
                xyxy = b.xyxy[0].cpu().numpy().tolist()
                c = float(b.conf[0].item())
                detections.append((float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3]), c))

        # Intra-frame duplicate suppression (handles models with end2end=True bypassing internal NMS)
        if len(detections) > 1:
            detections = self.deduplicate_boxes(detections, iou_threshold=iou)

        return detections

    @staticmethod
    def deduplicate_boxes(
        detections: List[Tuple[float, float, float, float, float]],
        iou_threshold: float = 0.5,
    ) -> List[Tuple[float, float, float, float, float]]:
        """Suppresses lower-confidence overlapping duplicate boxes in the same frame."""
        if len(detections) <= 1:
            return detections
        # Sort descending by confidence
        sorted_dets = sorted(detections, key=lambda d: d[4], reverse=True)
        kept: List[Tuple[float, float, float, float, float]] = []
        for det in sorted_dets:
            d_box = det[:4]
            is_dup = False
            for k in kept:
                k_box = k[:4]
                x1 = max(d_box[0], k_box[0])
                y1 = max(d_box[1], k_box[1])
                x2 = min(d_box[2], k_box[2])
                y2 = min(d_box[3], k_box[3])
                inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
                a1 = max(0.0, d_box[2] - d_box[0]) * max(0.0, d_box[3] - d_box[1])
                a2 = max(0.0, k_box[2] - k_box[0]) * max(0.0, k_box[3] - k_box[1])
                u = a1 + a2 - inter
                iou = (inter / u) if u > 0 else 0.0
                if iou >= iou_threshold:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(det)
        return kept

    @staticmethod
    def crop_plate(
        frame: np.ndarray,
        box: Tuple[float, float, float, float],
        pad_x: float = 0.08,
        pad_y: float = 0.15,
    ) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """Applies proportional padding matching anpr.geometry.apply_proportional_padding."""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = box[:4]
        bw = x2 - x1
        bh = y2 - y1

        px = int(round(bw * pad_x))
        py = int(round(bh * pad_y))

        cx1 = max(0, int(round(x1 - px)))
        cy1 = max(0, int(round(y1 - py)))
        cx2 = min(w, int(round(x2 + px)))
        cy2 = min(h, int(round(y2 + py)))

        if cx2 <= cx1 or cy2 <= cy1:
            return np.empty((0, 0, 3), dtype=np.uint8), (0, 0, 0, 0)

        crop = frame[cy1:cy2, cx1:cx2]
        return crop, (cx1, cy1, cx2, cy2)
