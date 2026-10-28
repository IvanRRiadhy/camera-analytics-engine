import logging
import socket
from unittest.mock import MagicMock, patch

import cv2
import pytest

from camera_analytics.bootstrap.providers.standalone_provider import StandaloneConfigurationProvider
from camera_analytics.ingestion.sources.rtsp_source import RTSPSource


def test_rtsp_source_default_and_custom_timeouts(tmp_path):
    src_default = RTSPSource("rtsp://192.168.1.204:8080/h264_ulaw.sdp")
    assert src_default._open_timeout_sec == 5.0
    assert src_default._read_timeout_sec == 5.0
    assert src_default._tcp_precheck_timeout_sec == 2.0

    cfg_file = tmp_path / "test_rtsp_timeouts.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_rtsp_custom",
                "source": "rtsp://192.168.1.204:8080/h264_ulaw.sdp",
                "open_timeout_sec": 3.5,
                "read_timeout_sec": 4.5
            },
            {
                "camera_id": "cam_rtsp_default",
                "source": "rtsp://192.168.1.204:8080/h264_ulaw.sdp"
            }
        ]
    }""", encoding="utf-8")

    snapshot = StandaloneConfigurationProvider(config_file_path=str(cfg_file)).load()
    p_custom = snapshot.pipelines[0].app.source.params
    p_default = snapshot.pipelines[1].app.source.params
    assert p_custom["open_timeout_sec"] == 3.5
    assert p_custom["read_timeout_sec"] == 4.5
    assert p_default["open_timeout_sec"] == 5.0
    assert p_default["read_timeout_sec"] == 5.0

    src_custom = RTSPSource("rtsp://192.168.1.204:8080/h264_ulaw.sdp", params=p_custom)
    assert src_custom._open_timeout_sec == 3.5
    assert src_custom._read_timeout_sec == 4.5


def test_rtsp_source_tcp_precheck_failure_skips_videocapture(caplog):
    src = RTSPSource("rtsp://192.168.1.204:8080/h264_ulaw.sdp")
    with patch("socket.create_connection", side_effect=socket.timeout("timed out")) as mock_sock, \
         patch("cv2.VideoCapture") as mock_cap, \
         caplog.at_level(logging.WARNING):
        ok = src.open()

    assert ok is False
    mock_sock.assert_called_once_with(("192.168.1.204", 8080), timeout=2.0)
    mock_cap.assert_not_called()
    assert any("TCP pre-check failed" in r.message for r in caplog.records)


def test_rtsp_source_tcp_precheck_success_passes_timeout_props():
    src = RTSPSource(
        "rtsp://192.168.1.204:8080/h264_ulaw.sdp",
        params={"open_timeout_sec": 5.0, "read_timeout_sec": 5.0},
    )
    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = True
    fake_sock_ctx = MagicMock()

    with patch("socket.create_connection", return_value=fake_sock_ctx) as mock_sock, \
         patch("cv2.VideoCapture", return_value=fake_cap) as mock_cap:
        ok = src.open()

    assert ok is True
    mock_sock.assert_called_once_with(("192.168.1.204", 8080), timeout=2.0)
    mock_cap.assert_called_once_with(
        "rtsp://192.168.1.204:8080/h264_ulaw.sdp",
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            5000,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            5000,
        ],
    )

