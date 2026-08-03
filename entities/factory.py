"""
Domain Entity Factory.

Constructs strongly typed domain Entity instances (TrackEntity, CameraEntity, FrameEntity, ZoneEntity)
directly from Runtime objects (Track, Camera, FrameContext, Zone).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, Sequence

from camera_analytics.entities.models import (
    BoundingBoxEntity,
    CameraEntity,
    DirectionEntity,
    FrameEntity,
    GroundPointEntity,
    GroundPointSource,
    KeypointEntity,
    PoseEntity,
    TrackEntity,
    VelocityEntity,
    ZoneEntity,
    ZoneState,
)

if TYPE_CHECKING:
    from camera_analytics.core.frame_context import FrameContext
    from camera_analytics.core.runtime import RuntimeState
    from camera_analytics.models.camera import Camera
    from camera_analytics.models.detection import Detection, Keypoint, PoseKeypoints
    from camera_analytics.models.track import Track
    from camera_analytics.models.zone import Zone

COCO_KEYPOINT_NAMES: list[str] = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]


class EntityFactory:
    """Factory for manufacturing strongly typed domain Entities from Runtime framework objects."""

    @classmethod
    def create_bounding_box(cls, bbox_obj: Any) -> BoundingBoxEntity:
        """Create BoundingBoxEntity from BoundingBox object."""
        return BoundingBoxEntity(
            x1=int(bbox_obj.x1),
            y1=int(bbox_obj.y1),
            x2=int(bbox_obj.x2),
            y2=int(bbox_obj.y2),
        )

    @classmethod
    def create_ground_point(cls, detection: Detection) -> GroundPointEntity:
        """Create GroundPointEntity and determine source origin from detection keypoints."""
        gp_x, gp_y = detection.ground_point
        source = GroundPointSource.BBOX

        if detection.keypoints is not None:
            l_ankle = detection.keypoints.left_ankle
            r_ankle = detection.keypoints.right_ankle
            l_vis = l_ankle is not None and l_ankle.confidence >= 0.5
            r_vis = r_ankle is not None and r_ankle.confidence >= 0.5

            if l_vis or r_vis:
                source = GroundPointSource.ANKLE
            else:
                l_knee = detection.keypoints.left_knee
                r_knee = detection.keypoints.right_knee
                lk_vis = l_knee is not None and l_knee.confidence >= 0.5
                rk_vis = r_knee is not None and r_knee.confidence >= 0.5
                if lk_vis or rk_vis:
                    source = GroundPointSource.KNEE
                else:
                    l_hip = detection.keypoints.left_hip
                    r_hip = detection.keypoints.right_hip
                    lh_vis = l_hip is not None and l_hip.confidence >= 0.5
                    rh_vis = r_hip is not None and r_hip.confidence >= 0.5
                    if lh_vis or rh_vis:
                        source = GroundPointSource.HIP

        return GroundPointEntity(x=int(gp_x), y=int(gp_y), source=source)

    @classmethod
    def create_pose(cls, pose_keypoints: Optional[PoseKeypoints]) -> Optional[PoseEntity]:
        """Create PoseEntity from PoseKeypoints object."""
        if pose_keypoints is None or not pose_keypoints.keypoints:
            return None

        kp_entities: list[KeypointEntity] = []
        for idx, kp in enumerate(pose_keypoints.keypoints):
            name = COCO_KEYPOINT_NAMES[idx] if idx < len(COCO_KEYPOINT_NAMES) else f"kp_{idx}"
            kp_entities.append(
                KeypointEntity(
                    index=idx,
                    name=name,
                    x=float(kp.x),
                    y=float(kp.y),
                    confidence=float(kp.confidence),
                )
            )

        avg_conf = (
            sum(kp.confidence for kp in kp_entities) / max(len(kp_entities), 1)
            if kp_entities
            else 0.0
        )
        return PoseEntity(keypoints=kp_entities, confidence=float(avg_conf))

    @classmethod
    def calculate_velocity_and_direction(
        cls, track: Track
    ) -> tuple[VelocityEntity, DirectionEntity]:
        """Calculate VelocityEntity and DirectionEntity from Track movement history."""
        if not track.history or len(track.history) < 2:
            return VelocityEntity(vx=0.0, vy=0.0), DirectionEntity(heading_degrees=0.0, cardinal_direction="N")

        recent = list(track.history)[-5:]
        p1 = recent[0].bbox.center
        p2 = recent[-1].bbox.center

        dt_frames = max(len(recent) - 1, 1)
        vx = float(p2[0] - p1[0]) / dt_frames
        vy = float(p2[1] - p1[1]) / dt_frames

        velocity = VelocityEntity(vx=vx, vy=vy)

        if velocity.speed < 0.5:
            return velocity, DirectionEntity(heading_degrees=0.0, cardinal_direction="STATIONARY")

        # Heading angle in degrees (0 = East, 90 = South, 180 = West, 270 = North)
        angle_rad = math.atan2(vy, vx)
        heading_deg = (math.degrees(angle_rad) + 360.0) % 360.0

        cardinals = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
        idx = int((heading_deg + 22.5) // 45) % 8
        cardinal = cardinals[idx]

        direction = DirectionEntity(heading_degrees=heading_deg, cardinal_direction=cardinal)
        return velocity, direction

    @classmethod
    def create_track_entity(cls, track: Track) -> TrackEntity:
        """Create strongly typed TrackEntity from a Track object."""
        bbox_ent = cls.create_bounding_box(track.bbox)
        gp_ent = cls.create_ground_point(track.detection)
        pose_ent = cls.create_pose(track.detection.keypoints)
        vel_ent, dir_ent = cls.calculate_velocity_and_direction(track)

        state_str = track.state.name if hasattr(track.state, "name") else str(track.state)

        return TrackEntity(
            track_id=track.track_id,
            track_age=track.hit_count,
            track_state=state_str,
            confidence=float(track.detection.confidence),
            global_id=track.global_id,
            bbox=bbox_ent,
            ground_point=gp_ent,
            velocity=vel_ent,
            direction=dir_ent,
            pose=pose_ent,
            feature_store=track.features,
        )

    @classmethod
    def create_zone_entity(cls, zone: Zone | str, current_state: ZoneState = ZoneState.OUTSIDE, dwell_frames: int = 0) -> ZoneEntity:
        """Create ZoneEntity from Zone model object."""
        if isinstance(zone, str):
            return ZoneEntity(
                zone_id=zone,
                zone_name=zone,
                zone_type="region",
                current_state=current_state,
                dwell_frames=dwell_frames,
            )
        zone_type_str = zone.zone_type.name.lower() if hasattr(zone.zone_type, "name") else str(zone.zone_type)
        return ZoneEntity(
            zone_id=zone.zone_id,
            zone_name=zone.name,
            zone_type=zone_type_str,
            current_state=current_state,
            dwell_frames=dwell_frames,
        )

    @classmethod
    def create_camera_entity(cls, camera: Camera) -> CameraEntity:
        """Create CameraEntity from Camera model object."""
        return CameraEntity(
            camera_id=camera.camera_id,
            camera_name=camera.name,
            resolution=camera.resolution,
            fps=camera.fps,
        )

    @classmethod
    def create_frame_entity(
        cls, frame_context: Optional[FrameContext], frame_index: int = 0, timestamp: float = 0.0
    ) -> FrameEntity:
        """Create FrameEntity from FrameContext object."""
        w, h = 1920, 1080
        fps = 30.0
        idx = frame_index
        ts = timestamp

        if frame_context is not None:
            idx = frame_context.frame_id
            ts = frame_context.timestamp
            if frame_context.image is not None:
                h, w = frame_context.image.shape[:2]

        return FrameEntity(
            frame_index=idx,
            timestamp=ts,
            frame_width=w,
            frame_height=h,
            fps=fps,
        )
