"""
Frame Presentation Builder Component.

Transforms raw AI Domain structures (SharedAnalyticsContext, FrameContext, IngestedFrame, IngestionMetrics)
into decoupled FramePresentation view models for UI visualizers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from camera_analytics.adapters.bridge.inference_pipeline import FrameProcessingSummary
from camera_analytics.ingestion.models import IngestedFrame, IngestionMetrics
from camera_analytics.models.camera import Camera
from camera_analytics.viewer.models import (
    FramePresentation,
    PresentedBox,
    PresentedEvent,
    PresentedMetrics,
    PresentedPoint,
    PresentedSkeleton,
    PresentedTrack,
    PresentedZone,
)

logger = logging.getLogger(__name__)


class FramePresentationBuilder:
    """Builder converting AI Domain objects into UI View Models (FramePresentation)."""

    @classmethod
    def build(
        cls,
        frame: IngestedFrame,
        camera: Camera,
        frame_context: Optional[Any] = None,
        summary: Optional[FrameProcessingSummary] = None,
        metrics: Optional[IngestionMetrics] = None,
        gpu_id: int = 0,
        queue_size: int = 0,
    ) -> FramePresentation:
        """Construct a FramePresentation view model from runtime AI outputs.

        Args:
            frame: IngestedFrame instance.
            camera: Camera domain configuration snapshot.
            frame_context: Optional SharedAnalyticsContext or FrameContext instance.
            summary: Optional FrameProcessingSummary.
            metrics: Optional IngestionMetrics.
            gpu_id: GPU index.
            queue_size: Current transport queue size.

        Returns:
            Immutable FramePresentation view model.
        """
        boxes: list[PresentedBox] = []
        skeletons: list[PresentedSkeleton] = []
        tracks: list[PresentedTrack] = []
        zone_occupancy_counts: dict[str, int] = {}
        confirmed_track_ids: set[int] = set()

        if frame_context is not None and hasattr(frame_context, "tracks") and frame_context.tracks:
            for track in frame_context.tracks:
                if isinstance(track, dict):
                    t_id = int(track.get("track_id", 1))
                    bbox_raw = track.get("bbox", [0, 0, 100, 100])
                    conf = float(track.get("confidence", 0.95))
                    st_name = "CONFIRMED"
                    confirmed_track_ids.add(t_id)

                    x1, y1, x2, y2 = (
                        int(bbox_raw[0]),
                        int(bbox_raw[1]),
                        int(bbox_raw[2]),
                        int(bbox_raw[3]),
                    )
                    box_color = (0, 255, 0)
                    # Extract Human Representation metrics if present
                    human_reps = getattr(frame_context, "human_representations", {})
                    rep = human_reps.get(t_id)
                    q_tag = f" Q:{rep.face_quality_score:.2f}" if rep and rep.face_quality_score > 0 else ""
                    box_label = f"Track #{t_id} [{st_name}] ({conf:.2f}){q_tag}"

                    # Extract Keypoints from track object graph for Skeleton Rendering
                    kps_obj = track.get("keypoints")
                    if not kps_obj and isinstance(track.get("detection"), object):
                        kps_obj = getattr(track.get("detection"), "keypoints", None)

                    if kps_obj:
                        raw_kps = getattr(kps_obj, "keypoints", ())
                        if raw_kps:
                            pres_kps = tuple(
                                PresentedPoint(x=int(kp.x), y=int(kp.y), confidence=float(kp.confidence))
                                for kp in raw_kps
                            )
                            skeletons.append(
                                PresentedSkeleton(
                                    track_id=t_id,
                                    keypoints=pres_kps,
                                    color_rgb=(0, 255, 255),
                                )
                            )

                    boxes.append(
                        PresentedBox(
                            track_id=t_id,
                            x1=x1,
                            y1=y1,
                            x2=x2,
                            y2=y2,
                            confidence=conf,
                            color_rgb=box_color,
                            label=box_label,
                        )
                    )
                    tracks.append(
                        PresentedTrack(
                            track_id=t_id,
                            state=st_name,
                            history=(),
                        )
                    )
                else:
                    t_id = getattr(track, "track_id", 1)
                    bbox = getattr(track, "bbox", None)
                    det = getattr(track, "detection", None)
                    st_obj = getattr(track, "state", None)
                    st_name = st_obj.name.upper() if hasattr(st_obj, "name") else "CONFIRMED"

                    if st_name == "CONFIRMED":
                        box_color = (0, 255, 0)
                        confirmed_track_ids.add(t_id)
                    elif st_name == "TENTATIVE":
                        box_color = (0, 215, 255)
                    else:
                        box_color = (0, 0, 255)

                    conf = det.confidence if det and hasattr(det, "confidence") else 0.95
                    x1 = int(bbox.x1) if bbox and hasattr(bbox, "x1") else 0
                    y1 = int(bbox.y1) if bbox and hasattr(bbox, "y1") else 0
                    x2 = int(bbox.x2) if bbox and hasattr(bbox, "x2") else 100
                    y2 = int(bbox.y2) if bbox and hasattr(bbox, "y2") else 100

                    box_label = f"Track #{t_id} [{st_name}] ({conf:.2f})"
                    boxes.append(
                        PresentedBox(
                            track_id=t_id,
                            x1=x1,
                            y1=y1,
                            x2=x2,
                            y2=y2,
                            confidence=conf,
                            color_rgb=box_color,
                            label=box_label,
                        )
                    )

        # Build PresentedZones from camera domain zones
        presented_zones: list[PresentedZone] = []
        for zone in camera.zones.values():
            pts = tuple(PresentedPoint(x=p.x, y=p.y) for p in zone.points)
            occ_count = len(confirmed_track_ids)
            z_label = f"{zone.name} | Occupancy: {occ_count}"
            presented_zones.append(
                PresentedZone(
                    zone_id=zone.zone_id,
                    name=zone.name,
                    zone_type=zone.zone_type.name if hasattr(zone.zone_type, "name") else str(zone.zone_type),
                    points=pts,
                    color_rgb=zone.color,
                    occupancy_count=occ_count,
                    status="NORMAL" if occ_count == 0 else "OCCUPIED",
                    label=z_label,
                )
            )

        # Build PresentedMetrics
        fps_in = metrics.fps_input if metrics else 0.0
        fps_exec = 30.0
        read_lat = frame.read_latency_ms
        pipe_lat = summary.total_pipeline_latency_ms if summary else 0.0
        active_tracks_cnt = len(tracks)
        active_zones_cnt = len(presented_zones)

        pres_metrics = PresentedMetrics(
            camera_id=camera.camera_id,
            camera_name=camera.name,
            fps_input=fps_in,
            fps_execution=fps_exec,
            read_latency_ms=read_lat,
            pipeline_latency_ms=pipe_lat,
            gpu_id=gpu_id,
            queue_size=queue_size,
            active_tracks_count=active_tracks_cnt,
            active_zones_count=active_zones_cnt,
        )

        sp_snap = getattr(frame_context, "spatial_snapshot", None) if frame_context is not None else None
        # Map HumanState domain objects through HumanStatePresenter
        human_vms = []
        if frame_context is not None and hasattr(frame_context, "human_states") and frame_context.human_states:
            from camera_analytics.viewer.presenter import HumanStatePresenter
            presenter = HumanStatePresenter()
            for h_state in frame_context.human_states.values():
                human_vms.append(presenter.present(h_state))

        return FramePresentation(
            camera_id=camera.camera_id,
            camera_name=camera.name,
            frame_number=frame.frame_number,
            timestamp=frame.timestamp,
            image=frame.image,
            boxes=tuple(boxes),
            skeletons=tuple(skeletons),
            tracks=tuple(tracks),
            zones=tuple(presented_zones),
            events=(),
            metrics=pres_metrics,
            spatial_snapshot=sp_snap,
            human_view_models=tuple(human_vms),
        )
