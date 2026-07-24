"""
Analytics runner orchestrator.

Coordinates execution across the AI Integration Layer:
    FrameSource -> DetectorPort -> TrackerPort -> Pipeline.process()

The Runner manages the frame ingestion loop while keeping Pipeline,
Detector, and Tracker decoupled.

Example::

    runner = Runner(
        pipeline=pipeline,
        detector=detector,
        tracker=tracker,
    )

    runner.run(frame_source)
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from camera_analytics.core.frame_context import FrameContext
from camera_analytics.core.frame_source import FrameSource
from camera_analytics.core.pipeline import Pipeline
from camera_analytics.core.ports import DetectorPort, TrackerPort

logger = logging.getLogger(__name__)


class Runner:
    """Orchestrator for the execution loop.

    Connects a FrameSource to DetectorPort, TrackerPort, and Pipeline.
    Encapsulates the standard frame iteration:
        1. Fetch frame from FrameSource
        2. Execute DetectorPort.detect(frame)
        3. Execute TrackerPort.track(frame, detection_result)
        4. Dispatch to Pipeline.process(frame, tracking_result.results)

    Args:
        pipeline: Initialized Pipeline instance.
        detector: DetectorPort implementation.
        tracker: TrackerPort implementation.
    """

    def __init__(
        self,
        pipeline: Pipeline,
        detector: DetectorPort,
        tracker: TrackerPort,
    ) -> None:
        self._pipeline = pipeline
        self._detector = detector
        self._tracker = tracker
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Whether the runner loop is active."""
        return self._is_running

    def run(
        self,
        source: FrameSource,
        max_frames: Optional[int] = None,
    ) -> None:
        """Run the frame processing loop until source finishes or max_frames is reached.

        Starts the pipeline if not already running, iterates frames from source,
        runs detection and tracking, and passes results to pipeline.process().

        Args:
            source: The FrameSource instance providing video frames.
            max_frames: Optional frame limit (useful for testing live streams).
        """
        if not self._pipeline.is_running:
            self._pipeline.start()

        self._is_running = True
        logger.info(
            "Runner started processing source '%s' using detector '%s' and tracker '%s'",
            source.name,
            self._detector.name,
            self._tracker.name,
        )

        try:
            frame_count = 0
            for item in source:
                if not self._is_running:
                    break

                frame_count += 1

                # Extract image payload whether item is FramePacket or raw NDArray
                image = item.image if hasattr(item, "image") else item

                # 1. Detection
                det_result = self._detector.detect(image)

                # 2. Tracking
                trk_result = self._tracker.track(image, det_result)

                # 3. Pipeline Execution
                self._pipeline.process(image, trk_result.results)

                # Check max frames limit if specified
                if max_frames is not None and frame_count >= max_frames:
                    logger.info("Runner reached max_frames limit (%d)", max_frames)
                    break

        except Exception as exc:
            logger.exception("Error during execution loop: %s", exc)
            raise
        finally:
            self._is_running = False
            source.release()
            logger.info("Runner loop completed")

    def stop(self) -> None:
        """Signal the runner loop to stop after current frame."""
        self._is_running = False
        logger.info("Runner stop requested")
