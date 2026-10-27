"""
Human Representation Extractor.

Extracts geometric ROIs (Head, Face, Torso, Upper/Lower Body), pose keypoints,
ground point provenance, and lazily populates ROICropCache from frame context.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Sequence
import numpy as np
from numpy.typing import NDArray

from camera_analytics.core.human.models import HumanRepresentation, ROICropCache
from camera_analytics.core.human.quality_estimator import FaceQualityEstimator
from camera_analytics.core.spatial.models import GroundPointSource, PixelPoint
from camera_analytics.models.detection import BoundingBox, Keypoint, PoseKeypoints

logger = logging.getLogger(__name__)


class HumanRepresentationExtractor:
    """Extracts non-inference HumanRepresentation & ROICropCache from tracks & pose keypoints."""

    @staticmethod
    def extract(
        track: dict[str, Any],
        frame: Optional[NDArray[np.uint8]] = None,
        frame_index: int = 0,
        timestamp_utc: float = 0.0,
    ) -> HumanRepresentation:
        """Construct HumanRepresentation for a track item."""
        t_id = int(track.get("track_id", 1))
        bbox_raw = track.get("bbox", [0.0, 0.0, 100.0, 100.0])
        body_bbox = BoundingBox(
            x1=float(bbox_raw[0]),
            y1=float(bbox_raw[1]),
            x2=float(bbox_raw[2]),
            y2=float(bbox_raw[3]),
        )

        # 1. Keypoints Extraction
        kps_obj: Optional[PoseKeypoints] = track.get("keypoints")
        if kps_obj is None and isinstance(track.get("detection"), object):
            kps_obj = getattr(track.get("detection"), "keypoints", None)

        # 2. Derive Head & Face ROI from Pose Keypoints or Upper Body
        head_roi: Optional[BoundingBox] = None
        face_roi: Optional[BoundingBox] = None
        visibility_score = 1.0

        if kps_obj and hasattr(kps_obj, "keypoints"):
            raw_kps = kps_obj.keypoints
            if len(raw_kps) >= 5:
                # Keypoints #0-#4: Nose, Left/Right Eye, Left/Right Ear
                head_kps = [kp for kp in raw_kps[:5] if getattr(kp, "confidence", 0.0) > 0.3]
                vis_count = sum(1 for kp in raw_kps if getattr(kp, "confidence", 0.0) > 0.3)
                visibility_score = round(vis_count / float(len(raw_kps)), 2)

                if head_kps:
                    hx1 = min(kp.x for kp in head_kps)
                    hy1 = min(kp.y for kp in head_kps)
                    hx2 = max(kp.x for kp in head_kps)
                    hy2 = max(kp.y for kp in head_kps)

                    # Add padding margin for head & face ROI
                    margin_x = max(15.0, (hx2 - hx1) * 0.4)
                    margin_y = max(15.0, (hy2 - hy1) * 0.4)

                    head_roi = BoundingBox(
                        x1=max(0.0, hx1 - margin_x),
                        y1=max(0.0, hy1 - margin_y),
                        x2=hx2 + margin_x,
                        y2=hy2 + margin_y,
                    )
                    face_roi = BoundingBox(
                        x1=max(0.0, hx1 - margin_x * 0.5),
                        y1=max(0.0, hy1 - margin_y * 0.5),
                        x2=hx2 + margin_x * 0.5,
                        y2=hy2 + margin_y * 0.5,
                    )

        # Fallback Head & Face ROI (Top 25% of Bounding Box) if no keypoints
        if head_roi is None:
            bw = body_bbox.x2 - body_bbox.x1
            bh = body_bbox.y2 - body_bbox.y1
            head_roi = BoundingBox(
                x1=body_bbox.x1 + bw * 0.2,
                y1=body_bbox.y1,
                x2=body_bbox.x1 + bw * 0.8,
                y2=body_bbox.y1 + bh * 0.3,
            )
            face_roi = head_roi

        # 3. Ground Point Estimation
        gp_x = int(round((body_bbox.x1 + body_bbox.x2) / 2.0))
        gp_y = int(round(body_bbox.y2))
        ground_point = PixelPoint(x=gp_x, y=gp_y)

        # 4. Lazy Crop Cache Initialization
        crop_cache = ROICropCache()
        face_quality = 0.0

        if frame is not None and frame.size > 0:
            img_h, img_w = frame.shape[:2]
            # 1. Crop face region if frame is provided
            fx1 = max(0, int(face_roi.x1))
            fy1 = max(0, int(face_roi.y1))
            fx2 = min(img_w, int(face_roi.x2))
            fy2 = min(img_h, int(face_roi.y2))

            if fx2 > fx1 and fy2 > fy1:
                face_crop = frame[fy1:fy2, fx1:fx2].copy()
                crop_cache.face_crop = face_crop
                face_quality = FaceQualityEstimator.evaluate_quality(
                    face_crop=face_crop,
                    face_bbox=face_roi,
                    pose_keypoints=kps_obj,
                )

            # 2. Crop full body region
            bx1 = max(0, int(body_bbox.x1))
            by1 = max(0, int(body_bbox.y1))
            bx2 = min(img_w, int(body_bbox.x2))
            by2 = min(img_h, int(body_bbox.y2))
            if bx2 > bx1 and by2 > by1:
                crop_cache.body_crop = frame[by1:by2, bx1:bx2].copy()

        return HumanRepresentation(
            track_id=t_id,
            frame_index=frame_index,
            timestamp_utc=timestamp_utc or time.time(),
            body_bbox=body_bbox,
            head_roi=head_roi,
            face_roi=face_roi,
            pose_keypoints=kps_obj,
            ground_point=ground_point,
            ground_point_source=GroundPointSource.BBOX_BOTTOM_CENTER,
            visibility_score=visibility_score,
            occlusion_state="NONE" if visibility_score > 0.5 else "PARTIAL",
            face_quality_score=face_quality,
            body_quality_score=float(track.get("confidence", 0.9)),
            crop_cache=crop_cache,
        )
