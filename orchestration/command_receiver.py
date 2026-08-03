"""
Engine Command Receiver Component.

Listens for incoming remote control command messages (`EngineCommandMessage`) targeted at this engine instance
over the message broker (`cctv.engine.commands.{instance_id}`), delegating execution to PipelineCoordinator or ServiceRuntime.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class EngineCommandReceiver:
    """Receiver listening for remote control command messages and executing pipeline/runtime operations."""

    def __init__(
        self,
        instance_id: str,
        comm_manager: Any,
        pipeline_coordinator: Optional[Any] = None,
        service_runtime: Optional[Any] = None,
    ) -> None:
        self.instance_id = instance_id
        self.comm_manager = comm_manager
        self.pipeline_coordinator = pipeline_coordinator
        self.service_runtime = service_runtime
        self._custom_handlers: Dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register_command_handler(self, command_type: str, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        """Register a custom handler function for a specific command_type."""
        self._custom_handlers[command_type.upper()] = handler

    def handle_command_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming command payload and return execution result dictionary.

        Args:
            payload: Dict containing command_id, target_instance_id, command_type, camera_id, payload_json.

        Returns:
            Dict containing command_id, target_instance_id, status ('SUCCESS' / 'FAILED' / 'INVALID_COMMAND'), message, executed_at_utc.
        """
        cmd_id = payload.get("command_id", f"cmd_{int(time.time())}")
        target_id = payload.get("target_instance_id", "")
        cmd_type = str(payload.get("command_type", "")).upper()
        camera_id = payload.get("camera_id", "")
        raw_payload = payload.get("payload_json", "{}")

        if target_id and target_id != self.instance_id and target_id != "*":
            logger.debug("Ignoring command '%s' targeted for instance '%s' (current: '%s')", cmd_id, target_id, self.instance_id)
            return {
                "command_id": cmd_id,
                "target_instance_id": self.instance_id,
                "status": "SKIPPED",
                "message": f"Command targeted for {target_id}",
                "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        logger.info("Executing EngineCommandMessage '%s' of type '%s' for camera '%s'", cmd_id, cmd_type, camera_id)

        try:
            extra_config = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
        except Exception:
            extra_config = {}

        if cmd_type in self._custom_handlers:
            try:
                result = self._custom_handlers[cmd_type](payload)
                return {
                    "command_id": cmd_id,
                    "target_instance_id": self.instance_id,
                    "status": "SUCCESS",
                    "message": result.get("message", "Custom command handler executed successfully"),
                    "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            except Exception as exc:
                logger.error("Error executing custom handler for command '%s': %s", cmd_id, exc)
                return {
                    "command_id": cmd_id,
                    "target_instance_id": self.instance_id,
                    "status": "FAILED",
                    "message": f"Execution error: {exc}",
                    "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

        if cmd_type == "START_PIPELINE":
            if self.pipeline_coordinator and hasattr(self.pipeline_coordinator, "start_pipeline"):
                try:
                    self.pipeline_coordinator.start_pipeline(camera_id, extra_config)
                    msg = f"Pipeline for camera '{camera_id}' started successfully"
                except Exception as exc:
                    return {
                        "command_id": cmd_id,
                        "target_instance_id": self.instance_id,
                        "status": "FAILED",
                        "message": f"Failed to start pipeline: {exc}",
                        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
            else:
                msg = f"Command START_PIPELINE acknowledged for camera '{camera_id}'"

        elif cmd_type == "STOP_PIPELINE":
            if self.pipeline_coordinator and hasattr(self.pipeline_coordinator, "stop_pipeline"):
                try:
                    self.pipeline_coordinator.stop_pipeline(camera_id)
                    msg = f"Pipeline for camera '{camera_id}' stopped successfully"
                except Exception as exc:
                    return {
                        "command_id": cmd_id,
                        "target_instance_id": self.instance_id,
                        "status": "FAILED",
                        "message": f"Failed to stop pipeline: {exc}",
                        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
            else:
                msg = f"Command STOP_PIPELINE acknowledged for camera '{camera_id}'"

        elif cmd_type == "RESTART_SERVICE":
            msg = "Service runtime restart command acknowledged"

        elif cmd_type == "UPDATE_CONFIG":
            msg = f"Configuration update acknowledged for camera '{camera_id}'"

        else:
            return {
                "command_id": cmd_id,
                "target_instance_id": self.instance_id,
                "status": "INVALID_COMMAND",
                "message": f"Unsupported command type: {cmd_type}",
                "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        result_payload = {
            "command_id": cmd_id,
            "target_instance_id": self.instance_id,
            "status": "SUCCESS",
            "message": msg,
            "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if hasattr(self.comm_manager, "publish_raw"):
            try:
                self.comm_manager.publish_raw("cctv.engine.command_results", f"engine.results.{cmd_id}", result_payload)
            except Exception:
                pass

        return result_payload
