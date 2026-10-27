"""
Unit tests for WebcamSource and SourceFactory extensions.
"""

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from camera_analytics.ingestion.sources.factory import create_video_source
from camera_analytics.ingestion.sources.webcam_source import WebcamSource


class TestWebcamSource(unittest.TestCase):
    """Test suite for USB/UVC Webcam video ingestion source."""

    def test_factory_creates_webcam_source(self):
        source1 = create_video_source("webcam://0")
        self.assertIsInstance(source1, WebcamSource)
        self.assertEqual(source1._device_index, 0)

        source2 = create_video_source("webcam:2")
        self.assertIsInstance(source2, WebcamSource)
        self.assertEqual(source2._device_index, 2)

        source3 = create_video_source("1")
        self.assertIsInstance(source3, WebcamSource)
        self.assertEqual(source3._device_index, 1)

    @patch("cv2.VideoCapture")
    def test_webcam_open_and_read_packet(self, mock_cv_capture):
        # Setup mock OpenCV capture
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap_instance.read.return_value = (True, dummy_frame)
        mock_cv_capture.return_value = mock_cap_instance

        source = WebcamSource("webcam://0", params={"width": 640, "height": 480})
        opened = source.open()
        self.assertTrue(opened)
        self.assertTrue(source.is_open)

        packet = source.read_packet()
        self.assertIsNotNone(packet)
        self.assertEqual(packet.packet_index, 1)
        self.assertFalse(packet.is_eof)
        self.assertEqual(packet.payload.shape, (480, 640, 3))
        self.assertEqual(packet.metadata.get("source_type"), "webcam")

        source.close()
        self.assertFalse(source.is_open)
        mock_cap_instance.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
