"""
Bridge ↔ Relay WebSocket 消息协议（JSON dict，无 Protobuf）。

与 README「3.2 通信协议设计」一致。
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any


def token_fingerprint(token: str) -> str:
    """
    日志用 token 指纹（不明文、不泄露口令长度）：比对客户端与 Relay 配置的密钥是否一致。
    取 SHA256 固定长度前缀；两边日志中的 fingerprint 应完全相同。
    """
    if not token:
        return "empty"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"sha256_16={digest}"

MSG_COMMAND = "command"
MSG_RESULT = "result"
MSG_DEVICE_STATUS = "device_status"
MSG_HEARTBEAT = "heartbeat"
MSG_AUTH = "auth"


def _now_ms() -> int:
    return int(time.time() * 1000)


def new_command_id() -> str:
    return f"cmd-{uuid.uuid4().hex}"


def build_command_message(
    *,
    command_id: str,
    device_id: str,
    action: str,
    params: dict[str, Any] | None = None,
    timeout_ms: int = 5000,
    dag_name: str | None = None,
) -> dict[str, Any]:
    return {
        "type": MSG_COMMAND,
        "id": command_id,
        "timestamp": _now_ms(),
        "device_id": device_id,
        "action": action,
        "params": params or {},
        "timeout_ms": timeout_ms,
        "dag_name": dag_name,
    }


def build_result_message(
    *,
    command_id: str,
    device_id: str,
    status: str,
    data: dict[str, Any] | None = None,
    execution_time_ms: int = 0,
    logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "type": MSG_RESULT,
        "id": command_id,
        "timestamp": _now_ms(),
        "device_id": device_id,
        "status": status,
        "data": data or {},
        "execution_time_ms": execution_time_ms,
        "logs": logs or [],
    }


def build_device_status_message(*, devices: list[dict[str, Any]], bridge_id: str | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "type": MSG_DEVICE_STATUS,
        "timestamp": _now_ms(),
        "devices": devices,
    }
    if bridge_id is not None:
        msg["bridge_id"] = bridge_id
    return msg


def build_heartbeat_message(*, bridge_id: str) -> dict[str, Any]:
    return {
        "type": MSG_HEARTBEAT,
        "timestamp": _now_ms(),
        "bridge_id": bridge_id,
    }


def build_auth_message(*, token: str, bridge_id: str) -> dict[str, Any]:
    return {
        "type": MSG_AUTH,
        "token": token,
        "bridge_id": bridge_id,
        "timestamp": _now_ms(),
    }


def is_command(msg: dict[str, Any]) -> bool:
    return msg.get("type") == MSG_COMMAND


def is_result(msg: dict[str, Any]) -> bool:
    return msg.get("type") == MSG_RESULT


def is_device_status(msg: dict[str, Any]) -> bool:
    return msg.get("type") == MSG_DEVICE_STATUS


def is_heartbeat(msg: dict[str, Any]) -> bool:
    return msg.get("type") == MSG_HEARTBEAT


def is_auth(msg: dict[str, Any]) -> bool:
    return msg.get("type") == MSG_AUTH
