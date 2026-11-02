"""
URL Sanitization and Redaction Utilities.

Provides secure masking of credentials (usernames and passwords) in RTSP, HTTP,
and other streaming/network URLs before logging or emitting telemetry.
"""

from __future__ import annotations

import urllib.parse
from typing import Optional


def redact_rtsp_url(url: Optional[str]) -> str:
    """Strips credentials from an RTSP URL for safe logging and telemetry.

    Args:
        url: Raw RTSP or stream connection URL.

    Returns:
        Redacted URL preserving scheme, host, port, and path, or '<unparseable>' on invalid input.
    """
    if not url or not isinstance(url, str):
        return "<unparseable>"
    try:
        parsed = urllib.parse.urlsplit(url)
        if not parsed.scheme or not parsed.netloc:
            return "<unparseable>"
        host_port = parsed.hostname or ""
        if not host_port:
            return "<unparseable>"
        if parsed.port:
            host_port = f"{host_port}:{parsed.port}"
        path = parsed.path
        if parsed.username is not None or parsed.password is not None:
            return f"{parsed.scheme}://<redacted>@{host_port}{path}"
        return f"{parsed.scheme}://{host_port}{path}"
    except Exception:
        return "<unparseable>"


# Alias for backward compatibility
_redact_rtsp = redact_rtsp_url

