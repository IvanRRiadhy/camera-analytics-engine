"""
Session Manager Component.

Thread-safe lifecycle manager for Camera Sessions.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from camera_analytics.orchestration.session import CameraSession, ConnectionContext
from camera_analytics.orchestration.states import CameraSessionState

logger = logging.getLogger(__name__)


class SessionManagerError(KeyError):
    """Raised when session lookup or transition fails."""


class SessionManager:
    """Manager responsible for creating, tracking, and executing state transitions on CameraSessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, CameraSession] = {}
        self._lock = threading.RLock()

    def create_session(self, camera_id: str, rtsp_uri: str = "") -> CameraSession:
        """Create and register a new CameraSession in CREATED state.

        Args:
            camera_id: Camera identifier string.
            rtsp_uri: Stream URI.

        Returns:
            Created CameraSession instance.
        """
        with self._lock:
            conn = ConnectionContext(rtsp_uri=rtsp_uri)
            session = CameraSession(camera_id=camera_id, state=CameraSessionState.CREATED, connection=conn)
            self._sessions[session.session_id] = session
            logger.info("SessionManager: Created session '%s' for camera '%s'", session.session_id, camera_id)
            return session

    def get_session(self, session_id: str) -> Optional[CameraSession]:
        """Retrieve a session by session_id."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_required_session(self, session_id: str) -> CameraSession:
        """Retrieve a session or raise SessionManagerError."""
        with self._lock:
            if session_id not in self._sessions:
                raise SessionManagerError(f"SessionManager: Session '{session_id}' not found.")
            return self._sessions[session_id]

    def activate_session(self, session_id: str) -> CameraSession:
        """Transition session to CONNECTING -> READY."""
        with self._lock:
            sess = self.get_required_session(session_id)
            updated_conn = sess.connection.with_update(is_alive=True)
            new_sess = sess.with_state(CameraSessionState.READY, connection=updated_conn)
            self._sessions[session_id] = new_sess
            logger.info("SessionManager: Activated session '%s' -> READY", session_id)
            return new_sess

    def start_session(self, session_id: str) -> CameraSession:
        """Transition session to RUNNING."""
        with self._lock:
            sess = self.get_required_session(session_id)
            new_sess = sess.with_state(CameraSessionState.RUNNING)
            self._sessions[session_id] = new_sess
            logger.info("SessionManager: Started session '%s' -> RUNNING", session_id)
            return new_sess

    def suspend_session(self, session_id: str) -> CameraSession:
        """Transition session to PAUSED."""
        with self._lock:
            sess = self.get_required_session(session_id)
            new_sess = sess.with_state(CameraSessionState.PAUSED)
            self._sessions[session_id] = new_sess
            logger.info("SessionManager: Suspended session '%s' -> PAUSED", session_id)
            return new_sess

    def resume_session(self, session_id: str) -> CameraSession:
        """Transition session back to RUNNING."""
        with self._lock:
            sess = self.get_required_session(session_id)
            new_sess = sess.with_state(CameraSessionState.RUNNING)
            self._sessions[session_id] = new_sess
            logger.info("SessionManager: Resumed session '%s' -> RUNNING", session_id)
            return new_sess

    def stop_session(self, session_id: str) -> CameraSession:
        """Transition session to STOPPED."""
        with self._lock:
            sess = self.get_required_session(session_id)
            updated_conn = sess.connection.with_update(is_alive=False)
            new_sess = sess.with_state(CameraSessionState.STOPPED, connection=updated_conn)
            self._sessions[session_id] = new_sess
            logger.info("SessionManager: Stopped session '%s' -> STOPPED", session_id)
            return new_sess

    def mark_failed(self, session_id: str, error_message: str) -> CameraSession:
        """Transition session to FAILED with an error message."""
        with self._lock:
            sess = self.get_required_session(session_id)
            updated_conn = sess.connection.with_update(is_alive=False)
            new_sess = sess.with_state(CameraSessionState.FAILED, error_message=error_message, connection=updated_conn)
            self._sessions[session_id] = new_sess
            logger.error("SessionManager: Session '%s' FAILED: %s", session_id, error_message)
            return new_sess

    def destroy_session(self, session_id: str) -> bool:
        """Remove a session from management."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info("SessionManager: Destroyed session '%s'", session_id)
                return True
            return False

    def list_sessions(self) -> list[CameraSession]:
        """List snapshot of all sessions."""
        with self._lock:
            return list(self._sessions.values())

    def clear(self) -> None:
        """Clear all registered sessions."""
        with self._lock:
            self._sessions.clear()
