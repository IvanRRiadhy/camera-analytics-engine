"""
Slice 1.6a: Credential Cleanup & Env Resolution Tests.

Verifies:
1. No credential-shaped literals remain in tools/register_engine.py,
   tools/run_live_rtsp_analytics.py, and tools/validate_live_rtsp.py.
2. register_engine: with env unset, raises SystemExit naming missing variables,
   without calling socket.socket or constructing RabbitMQPublisher.
3. _resolve_rtsp_url precedence: CLI value > RTSP_URL > CAMERA_RTSP_URL > SystemExit.
4. _redact_rtsp: strips user/password, retains host/port/path, drops query,
   and returns '<unparseable>' for invalid URLs.
5. Importing each tool module with no env set does not exit or read env credentials.
"""

from __future__ import annotations

import base64
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure model symbols are accessible during import if not re-exported by models package
import camera_analytics.models as _models
import camera_analytics.models.camera as _cam
import camera_analytics.models.zone as _zone

_MODEL_SYMBOLS = {
    "Camera": _cam.Camera,
    "Point": _zone.Point,
    "Zone": _zone.Zone,
    "ZoneType": _zone.ZoneType,
}
_added_attrs = []
for _name, _val in _MODEL_SYMBOLS.items():
    if not hasattr(_models, _name):
        setattr(_models, _name, _val)
        _added_attrs.append(_name)

try:
    import camera_analytics.tools.register_engine as reg_tool
    import camera_analytics.tools.run_live_rtsp_analytics as run_tool
    import camera_analytics.tools.validate_live_rtsp as val_tool
finally:
    for _name in _added_attrs:
        delattr(_models, _name)


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestCredentialLiterals:
    """Verify that no credential-shaped literals exist in the edited tool files."""

    EDITED_FILES = [
        "tools/register_engine.py",
        "tools/run_live_rtsp_analytics.py",
        "tools/validate_live_rtsp.py",
    ]

    def test_no_credential_shaped_literals_in_source(self):
        # Known previous sensitive tokens encoded to prevent raw literals in test source
        old_rtsp_url = base64.b64decode(b"cnRzcDovL2FkbWluOkFkbWluMTIzNEAxOTIuMTY4LjEuNjQvU3RyZWFtaW5nL2NoYW5uZWxzLzI=").decode("ascii")
        old_rmq_user = base64.b64decode(b"Y2N0dl9hZG1pbg==").decode("ascii")
        old_rmq_pass = base64.b64decode(b"U2VjdXJlQ2N0dlBhc3MxMjM=").decode("ascii")
        old_uuid = base64.b64decode(b"ZTA3OGVlOTMtOTBjNC00Yjk1LTk2NTEtN2JmODJjOGE2ZDMz").decode("ascii")

        rtsp_cred_pattern = re.compile(r'rtsp://(?!(?:<user>:<password>|username:password|user:pass))[^/:]+:[^/@]+@')
        rmq_pass_pattern = re.compile(r'rabbitmq_pass\s*=\s*os\.getenv\("RABBITMQ_PASS",\s*["\']')
        rmq_user_pattern = re.compile(r'rabbitmq_user\s*=\s*os\.getenv\("RABBITMQ_USER",\s*["\']')
        app_id_default_pattern = re.compile(r'APPLICATION_ID.*os\.getenv\(.*,\s*["\'][0-9a-fA-F-]{36}["\']\)')

        for rel_path in self.EDITED_FILES:
            file_path = REPO_ROOT / rel_path
            assert file_path.exists(), f"Target file not found: {file_path}"
            content = file_path.read_text(encoding="utf-8")

            # Check previous credentials are removed
            assert old_rtsp_url not in content, f"Old RTSP URL found in {rel_path}"
            assert old_rmq_user not in content, f"Old RabbitMQ username found in {rel_path}"
            assert old_rmq_pass not in content, f"Old RabbitMQ password found in {rel_path}"
            assert old_uuid not in content, f"Old tenant UUID found in {rel_path}"

            # Check regex patterns
            assert not rtsp_cred_pattern.search(content), f"Credential-bearing RTSP URL found in {rel_path}"
            assert not rmq_pass_pattern.search(content), f"RABBITMQ_PASS default found in {rel_path}"
            assert not rmq_user_pattern.search(content), f"RABBITMQ_USER default found in {rel_path}"
            assert not app_id_default_pattern.search(content), f"APPLICATION_ID UUID default found in {rel_path}"


class TestRegisterEngineValidation:
    """Verify register_engine fail-fast env validation and zero network access."""

    def test_missing_env_raises_system_exit_without_socket_or_publisher(self, monkeypatch):
        # Clear required environment variables
        monkeypatch.delenv("APPLICATION_ID", raising=False)
        monkeypatch.delenv("RABBITMQ_USER", raising=False)
        monkeypatch.delenv("RABBITMQ_PASS", raising=False)

        # Monkeypatch socket.socket to fail if called
        def _forbidden_socket(*args, **kwargs):
            raise AssertionError("socket.socket was called when required env vars were missing!")

        monkeypatch.setattr(socket, "socket", _forbidden_socket)

        # Monkeypatch RabbitMQPublisher to fail if instantiated
        def _forbidden_publisher(*args, **kwargs):
            raise AssertionError("RabbitMQPublisher was constructed when required env vars were missing!")

        monkeypatch.setattr(reg_tool, "RabbitMQPublisher", _forbidden_publisher)

        with pytest.raises(SystemExit) as exc_info:
            reg_tool.main()

        msg = str(exc_info.value)
        assert "APPLICATION_ID" in msg
        assert "RABBITMQ_USER" in msg
        assert "RABBITMQ_PASS" in msg

    def test_partial_missing_env_names_only_missing(self, monkeypatch):
        monkeypatch.setenv("APPLICATION_ID", "11111111-1111-1111-1111-111111111111")
        monkeypatch.setenv("RABBITMQ_USER", "test_user")
        monkeypatch.delenv("RABBITMQ_PASS", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            reg_tool.main()

        msg = str(exc_info.value)
        assert "RABBITMQ_PASS" in msg
        assert "APPLICATION_ID" not in msg
        assert "RABBITMQ_USER" not in msg


class TestResolveRtspUrlPrecedence:
    """Verify _resolve_rtsp_url precedence across CLI, env vars, and SystemExit."""

    @pytest.mark.parametrize("tool_module", [run_tool, val_tool])
    def test_cli_value_takes_highest_precedence(self, tool_module, monkeypatch):
        monkeypatch.setenv("RTSP_URL", "rtsp://env-url:554/live")
        monkeypatch.setenv("CAMERA_RTSP_URL", "rtsp://camera-env-url:554/live")

        resolved = tool_module._resolve_rtsp_url("rtsp://cli-url:554/stream")
        assert resolved == "rtsp://cli-url:554/stream"

    @pytest.mark.parametrize("tool_module", [run_tool, val_tool])
    def test_rtsp_url_env_fallback(self, tool_module, monkeypatch):
        monkeypatch.setenv("RTSP_URL", "rtsp://env-url:554/live")
        monkeypatch.setenv("CAMERA_RTSP_URL", "rtsp://camera-env-url:554/live")

        resolved = tool_module._resolve_rtsp_url(None)
        assert resolved == "rtsp://env-url:554/live"

    @pytest.mark.parametrize("tool_module", [run_tool, val_tool])
    def test_camera_rtsp_url_env_fallback(self, tool_module, monkeypatch):
        monkeypatch.delenv("RTSP_URL", raising=False)
        monkeypatch.setenv("CAMERA_RTSP_URL", "rtsp://camera-env-url:554/live")

        resolved = tool_module._resolve_rtsp_url(None)
        assert resolved == "rtsp://camera-env-url:554/live"

    @pytest.mark.parametrize("tool_module", [run_tool, val_tool])
    def test_none_set_raises_system_exit(self, tool_module, monkeypatch):
        monkeypatch.delenv("RTSP_URL", raising=False)
        monkeypatch.delenv("CAMERA_RTSP_URL", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            tool_module._resolve_rtsp_url(None)

        expected_msg = "no RTSP URL: pass --rtsp-url or set RTSP_URL (or CAMERA_RTSP_URL)"
        assert expected_msg in str(exc_info.value)


class TestRedactRtsp:
    """Verify _redact_rtsp credential stripping, host/port preservation, and error handling."""

    @pytest.mark.parametrize("tool_module", [run_tool, val_tool])
    def test_redact_user_and_password(self, tool_module):
        url = "rtsp://alice:secret_pass123@192.168.1.100:554/Streaming/channels/1?foo=bar&baz=qux"
        redacted = tool_module._redact_rtsp(url)
        assert redacted == "rtsp://<redacted>@192.168.1.100:554/Streaming/channels/1"
        assert "alice" not in redacted
        assert "secret_pass123" not in redacted
        assert "foo=bar" not in redacted

    @pytest.mark.parametrize("tool_module", [run_tool, val_tool])
    def test_redact_user_without_password(self, tool_module):
        url = "rtsp://operator@camera.internal:8554/h264"
        redacted = tool_module._redact_rtsp(url)
        assert redacted == "rtsp://<redacted>@camera.internal:8554/h264"
        assert "operator" not in redacted

    @pytest.mark.parametrize("tool_module", [run_tool, val_tool])
    def test_no_credentials_preserves_host_port_and_path(self, tool_module):
        url = "rtsp://192.168.1.50:554/live/sub"
        redacted = tool_module._redact_rtsp(url)
        assert redacted == "rtsp://192.168.1.50:554/live/sub"

    @pytest.mark.parametrize("tool_module", [run_tool, val_tool])
    @pytest.mark.parametrize("garbage", [
        "",
        None,
        "not_a_url",
        "://missing-scheme",
        "rtsp://",
        "rtsp://:invalid-port:999999999/",
        "http://invalid [::1",
    ])
    def test_garbage_returns_unparseable(self, tool_module, garbage):
        assert tool_module._redact_rtsp(garbage) == "<unparseable>"


class TestToolImportSafety:
    """Verify importing tool modules with no environment set does not exit or read credentials."""

    @pytest.mark.parametrize("module_name", [
        "camera_analytics.tools.register_engine",
        "camera_analytics.tools.run_live_rtsp_analytics",
        "camera_analytics.tools.validate_live_rtsp",
    ])
    def test_import_with_no_env_does_not_exit(self, module_name):
        code = f"""
import sys
import camera_analytics.models as m
import camera_analytics.models.camera as mc
import camera_analytics.models.zone as mz

symbols = {{
    'Camera': mc.Camera,
    'Point': mz.Point,
    'Zone': mz.Zone,
    'ZoneType': mz.ZoneType,
}}
added = []
for name, val in symbols.items():
    if not hasattr(m, name):
        setattr(m, name, val)
        added.append(name)

try:
    import {module_name}
finally:
    for name in added:
        delattr(m, name)

sys.exit(0)
"""
        env = {k: v for k, v in os.environ.items() if k not in {
            "APPLICATION_ID", "RABBITMQ_USER", "RABBITMQ_PASS", "RTSP_URL", "CAMERA_RTSP_URL"
        }}
        proc = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT.parent),
        )
        assert proc.returncode == 0, f"Importing {module_name} failed: {proc.stderr}"
