"""
End-to-End Pipeline Integration Test Tool with Ingestion & Simple Object Detection.

Demonstrates reading video frames from `AI/data/Screen_Recording_20260622_113428_EZVIZ.mp4`
via the Sprint 11.3 Video Ingestion Layer (ReaderWorker + FrameQueue), running detection
(YOLOPoseAdapter or FakeDetector fallback), and rendering detection results to an output video.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Optional

import cv2

from camera_analytics.adapters import FakeDetector, YOLOPoseAdapter
from camera_analytics.core.ports import DetectorPort
from camera_analytics.ingestion import (
    FrameQueue,
    IngestedFrame,
    ReaderWorker,
    VideoFileSource,
    VideoReader,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("test_detection")


def create_detector(model_path: str = "yolo26m-pose.pt") -> DetectorPort:
    """Instantiate a DetectorPort (YOLOPoseAdapter or FakeDetector fallback)."""
    if Path(model_path).exists() or Path("yolov8n-pose.pt").exists():
        actual_weights = model_path if Path(model_path).exists() else "yolov8n-pose.pt"
        try:
            adapter = YOLOPoseAdapter(confidence_threshold=0.5, iou_threshold=0.45)
            adapter.load(actual_weights, device="cuda")
            logger.info("[+] YOLOPoseAdapter loaded successfully on CUDA with weights '%s'", actual_weights)
            return adapter
        except Exception as exc:
            logger.warning("[!] YOLOPoseAdapter CUDA initialization notice (%s). Falling back to CPU/FakeDetector.", exc)

    logger.info("[!] Using FakeDetector fallback for simple detection test.")
    fake = FakeDetector(person_count=3, confidence_range=(0.6, 0.95), seed=42)
    fake.load(model_path, device="cpu")
    return fake


def main() -> int:
    logger.info("=" * 70)
    logger.info("End-to-End Testing: Video Ingestion + Simple Detection Pipeline")
    logger.info("=" * 70)

    # 1. Target Video Path
    video_path = Path("AI/data/Screen_Recording_20260622_113428_EZVIZ.mp4")
    if not video_path.exists():
        # Fallback check
        video_path = Path("camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4")

    if not video_path.exists():
        logger.error("[-] Video file not found at '%s'", video_path)
        return 1

    logger.info("[+] Using input video stream: %s", video_path)

    # 2. Instantiate Ingestion Layer (VideoSource -> VideoReader -> ReaderWorker)
    source = VideoFileSource(str(video_path))
    reader = VideoReader(source=source)
    worker = ReaderWorker(
        pipeline_id="pipe_test_ezviz",
        camera_id="cam_ezviz_01",
        reader=reader,
        buffer_capacity=30,
        queue_capacity=30,
    )

    # 3. Instantiate Detector
    detector = create_detector()

    # 4. Prepare Output Video Writer
    output_dir = Path("camera_analytics/samples")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_video_path = output_dir / "output_simple_detection.mp4"

    logger.info("[+] Starting ReaderWorker background thread...")
    worker.start()

    writer: Optional[cv2.VideoWriter] = None
    processed_count = 0
    max_frames_to_process = 100
    start_time = time.time()

    logger.info("[+] Processing frames from FrameQueue...")

    try:
        while processed_count < max_frames_to_process:
            # Dequeue ingested frame from FrameQueue (Producer-Consumer pattern)
            frame: Optional[IngestedFrame] = worker.queue.get(timeout=1.0)
            if frame is None:
                if worker.state.name in ("STOPPED", "FAILED"):
                    logger.info("[-] ReaderWorker stopped or finished stream.")
                    break
                continue

            # Run Object Detection on frame image
            img_bgr = frame.image.copy()  # Mutable copy for drawing overlay
            det_result = detector.detect(img_bgr)

            # Draw detection bounding boxes & keypoints on image
            person_count = len(det_result.detections)
            for det in det_result.detections:
                x1, y1, x2, y2 = det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2
                cv2.rectangle(img_bgr, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                label = f"Person {det.confidence:.2f}"
                cv2.putText(img_bgr, label, (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                if det.keypoints and det.keypoints.keypoints:
                    for kp in det.keypoints.keypoints:
                        if kp.confidence >= 0.5:
                            cv2.circle(img_bgr, (int(kp.x), int(kp.y)), 3, (0, 0, 255), -1)

            # Render Overlay Info
            cv2.putText(img_bgr, f"Frame #{frame.frame_number} | Persons: {person_count}", (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)

            # Initialize VideoWriter on first frame
            if writer is None:
                h, w = img_bgr.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(output_video_path), fourcc, 25.0, (w, h))

            writer.write(img_bgr)
            processed_count += 1

            if processed_count % 20 == 0:
                logger.info("  Processed %d/%d frames (Active Persons: %d)",
                            processed_count, max_frames_to_process, person_count)

    finally:
        logger.info("[+] Stopping ReaderWorker and releasing resources...")
        worker.stop()
        if writer is not None:
            writer.release()
        detector.release()

    elapsed = time.time() - start_time
    fps = processed_count / elapsed if elapsed > 0 else 0

    logger.info("=" * 70)
    logger.info("SUCCESS: Simple detection test completed!")
    logger.info("  Total Frames Processed: %d", processed_count)
    logger.info("  Total Time Elapsed:     %.2f seconds", elapsed)
    logger.info("  Average Processing FPS: %.1f FPS", fps)
    logger.info("  Output Video Saved To:  %s", output_video_path)
    logger.info("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
