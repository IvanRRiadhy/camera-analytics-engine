"""
Slice 1.6b: PluginContext rtsp_url default verification.

Verifies:
1. PluginContext(pipeline_id="p", camera_id="c").rtsp_url == ""
2. plugins/framework/context.py contains no credential-shaped literals.
"""

from __future__ import annotations

import re
from pathlib import Path

from camera_analytics.plugins.framework.context import PluginContext

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_plugin_context_rtsp_url_default():
    ctx = PluginContext(pipeline_id="p", camera_id="c")
    assert ctx.rtsp_url == ""


def test_context_file_no_credential_shaped_literals():
    context_file = REPO_ROOT / "plugins" / "framework" / "context.py"
    assert context_file.exists(), f"File not found: {context_file}"
    content = context_file.read_text(encoding="utf-8")

    # Generic credential patterns
    rtsp_cred_pattern = re.compile(r'rtsp://(?!(?:<user>:<password>|username:password|user:pass))[^/:]+:[^/@]+@')
    assert not rtsp_cred_pattern.search(content), "Credential-bearing RTSP URL found in context.py"

    cred_assignment_pattern = re.compile(r'(?i)\b(?:password|passwd|pwd)\s*=\s*["\'](?!test|mock|none|\[redacted\]|dummy)[^"\']+["\']')
    assert not cred_assignment_pattern.search(content), "Password assignment found in context.py"
