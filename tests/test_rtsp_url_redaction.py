"""
Tests for RTSP URL redaction across logging and telemetry.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from camera_analytics.bootstrap.providers.standalone_provider import StandaloneConfigurationProvider
from camera_analytics.sources.rtsp_source import RTSPSource
from camera_analytics.utils.url_sanitizer import redact_rtsp_url, _redact_rtsp


def test_url_sanitizer_redaction():
    raw_user = "alice_test"
    raw_pass = "secret_pass_999"
    url = f"rtsp://{raw_user}:{raw_pass}@192.168.1.100:554/live/stream?param=1"
    redacted = redact_rtsp_url(url)
    assert raw_user not in redacted
    assert raw_pass not in redacted
    assert redacted == "rtsp://<redacted>@192.168.1.100:554/live/stream"
    assert _redact_rtsp(url) == redacted


def test_rtsp_source_logs_and_metadata_redact_credentials(caplog):
    raw_user = "cctv_operator"
    raw_pass = "topsecret_pwd_777"
    url = f"rtsp://{raw_user}:{raw_pass}@192.168.1.250:554/h264"

    source = RTSPSource(rtsp_url=url, reconnect_delay=0.1)

    # 1. Verify metadata telemetry
    meta = source.metadata
    assert raw_user not in meta.source_uri
    assert raw_pass not in meta.source_uri
    assert meta.source_uri == "rtsp://<redacted>@192.168.1.250:554/h264"

    # 2. Verify logging on open failure / synthetic fallback
    with patch.object(source, "_connect_stream", return_value=False), \
         patch("threading.Thread") as mock_thread, \
         caplog.at_level(logging.INFO):
        source.open()

    # 3. Verify logging on release
    with caplog.at_level(logging.INFO):
        source.release()

    for record in caplog.records:
        msg = record.getMessage()
        assert raw_user not in msg, f"Found username in log: {msg}"
        assert raw_pass not in msg, f"Found password in log: {msg}"

    all_logs = " ".join(r.getMessage() for r in caplog.records)
    assert "<redacted>" in all_logs


def test_standalone_provider_warning_redacts_credentials(caplog):
    raw_user = "admin_user"
    raw_pass = "super_secret_444"
    conflicting_source = f"rtsp://{raw_user}:{raw_pass}@192.168.1.111:554/ch1"
    conflicting_rtsp = f"rtsp://{raw_user}:{raw_pass}@192.168.1.222:554/ch2"

    provider = StandaloneConfigurationProvider.__new__(StandaloneConfigurationProvider)
    raw_data = {
        "cameras": [
            {
                "camera_id": "cam_conflict",
                "source": conflicting_source,
                "rtsp_url": conflicting_rtsp,
            }
        ]
    }

    with caplog.at_level(logging.WARNING):
        _ = provider.parse_dict(raw_data, expand=False)

    for record in caplog.records:
        msg = record.getMessage()
        assert raw_user not in msg, f"Found username in log: {msg}"
        assert raw_pass not in msg, f"Found password in log: {msg}"

    warning_msgs = [r.getMessage() for r in caplog.records if "conflicting values" in r.getMessage()]
    assert len(warning_msgs) == 1
    assert "rtsp://<redacted>@192.168.1.111:554/ch1" in warning_msgs[0]
    assert "rtsp://<redacted>@192.168.1.222:554/ch2" in warning_msgs[0]

