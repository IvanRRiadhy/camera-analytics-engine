import numpy as np
from camera_analytics.context.services import ContextBuilder
from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.models.camera import Camera

# Import FrameProcessingSummary first to break circular import cycle
from camera_analytics.adapters.bridge.inference_pipeline import FrameProcessingSummary
from camera_analytics.viewer.builder import FramePresentationBuilder

img = np.zeros((480, 640, 3), dtype=np.uint8)
frame = IngestedFrame(
    pipeline_id='p1',
    camera_id='c1',
    frame_number=1,
    timestamp=1.0,
    image=img,
    read_latency_ms=1.0,
    width=640,
    height=480
)
cam = Camera(camera_id='c1', name='Test Cam', source='rtsp://test')
builder = ContextBuilder()
ctx = builder.build_context(img, 1, 'c1', 'Test Cam', 'pipe_1')

print("1. YOLO Detections count:", len(ctx.detections), "id:", id(ctx.detections))
print("2. Tracker Output count:", len(ctx.tracks), "id:", id(ctx.tracks))
print("3. SharedAnalyticsContext.detections count:", len(ctx.detections), "id:", id(ctx.detections))
print("4. SharedAnalyticsContext.tracks count:", len(ctx.tracks), "id:", id(ctx.tracks))
print("5. latest_frame_context id:", id(ctx))
print("6. last_context id:", id(ctx))

summary = FrameProcessingSummary(
    frame_number=1,
    timestamp=1.0,
    detected_persons_count=len(ctx.detections),
    active_tracks_count=len(ctx.tracks),
    events_emitted_count=0,
    total_pipeline_latency_ms=10.0
)

try:
    pres = FramePresentationBuilder.build(frame=frame, camera=cam, frame_context=ctx, summary=summary)
    print("7. FramePresentationBuilder input id:", id(ctx))
    print("8. FramePresentationBuilder draw_detections boxes count:", len(pres.boxes), "tracks count:", len(pres.tracks))
    print("9. OpenCV Renderer frame shape:", pres.frame.shape if pres.frame is not None else None)
except Exception as e:
    print("FramePresentationBuilder exception:", type(e), e)
