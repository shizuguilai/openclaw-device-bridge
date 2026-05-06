"""Shared modules for Relay and Bridge Client."""

from shared.protocol import (
    MSG_AUTH,
    MSG_COMMAND,
    MSG_DEVICE_STATUS,
    MSG_HEARTBEAT,
    MSG_RESULT,
    build_auth_message,
    build_command_message,
    build_device_status_message,
    build_heartbeat_message,
    build_result_message,
    new_command_id,
)

__all__ = [
    "MSG_AUTH",
    "MSG_COMMAND",
    "MSG_DEVICE_STATUS",
    "MSG_HEARTBEAT",
    "MSG_RESULT",
    "build_auth_message",
    "build_command_message",
    "build_device_status_message",
    "build_heartbeat_message",
    "build_result_message",
    "new_command_id",
]
