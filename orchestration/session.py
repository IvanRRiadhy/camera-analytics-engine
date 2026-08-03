"""
Camera Session and Connection Context Domain Models.

Defines immutable `ConnectionContext` and `CameraSession` dataclasses for managing
camera lifecycle, reconnect metrics, and heartbeat status.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.orchestration.states import CameraSessionState


@dataclass(frozen=True, slots=True)
class ConnectionContext:
    """Placeholder context for RTSP connection metrics, heartbeat, and auto-reconnect stats.

    Attributes:
        rtsp_uri: RTSP or stream resource URI.
        connect_timeout_sec: Timeout threshold for stream connection attempts.
        reconnect_attempts: Counter of reconnection attempts.
        max_reconnect_attempts: Maximum allowed retries before flagging FAILED.
        last_heartbeat_timestamp: UTC timestamp of last received frame/heartbeat.
        is_alive: Current connection health status.
        connection_metadata: Arbitrary transport-specific connection params.
    """

    rtsp_uri: str = ""
    connect_timeout_sec: float = 10.0
    reconnect_attempts: int = 0
    max_reconnect_attempts: int = 5
    last_heartbeat_timestamp: float = field(default_factory=time.time)
    is_alive: bool = False
    connection_metadata: dict[str, Any] = field(default_factory=dict)

    def with_update(
        self,
        reconnect_attempts: Optional[int] = None,
        last_heartbeat: Optional[float] = None,
        is_alive: Optional[bool] = None,
    ) -> ConnectionContext:
        """Return a new updated immutable ConnectionContext instance."""
        return ConnectionContext(
            rtsp_uri=self.rtsp_uri,
            connect_timeout_sec=self.connect_timeout_sec,
            reconnect_attempts=self.reconnect_attempts if reconnect_attempts is None else reconnect_attempts,
            max_reconnect_attempts=self.max_reconnect_attempts,
            last_heartbeat_timestamp=self.last_heartbeat_timestamp if last_heartbeat is None else last_heartbeat,
            is_alive=self.is_alive if is_alive is None else is_alive,
            connection_metadata=dict(self.connection_metadata),
        )


@dataclass(frozen=True, slots=True)
class CameraSession:
    """Immutable Camera Session domain entity.

    Attributes:
        session_id: Unique string identifier for this session.
        camera_id: Target camera identifier string.
        state: Current CameraSessionState.
        connection: ConnectionContext placeholder for stream metrics and heartbeats.
        created_at: Epoch timestamp of session creation.
        updated_at: Epoch timestamp of last state transition.
        error_message: Optional error description string.
    """

    camera_id: str
    session_id: str = field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:8]}")
    state: CameraSessionState = CameraSessionState.CREATED
    connection: ConnectionContext = field(default_factory=ConnectionContext)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None

    def with_state(
        self,
        new_state: CameraSessionState,
        error_message: Optional[str] = None,
        connection: Optional[ConnectionContext] = None,
    ) -> CameraSession:
        """Construct a new immutable CameraSession instance with updated state."""
        return CameraSession(
            session_id=self.session_id,
            camera_id=self.camera_id,
            state=new_state,
            connection=self.connection if connection is None else connection,
            created_at=self.created_at,
            updated_at=time.time(),
            error_message=error_message,
        )
