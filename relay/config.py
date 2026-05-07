"""Relay 与 Web Console 配置加载。"""

from __future__ import annotations

import logging
import os
from typing import Any


_DEFAULT_WS_MAX = 16 * 1024 * 1024  # 截图 base64 JSON 易超过 websockets 默认 1MiB


def load_relay_config(path: str | None = None) -> dict[str, Any]:
    """
    从环境变量加载配置（可选 YAML 路径 ``path`` 预留）。

    环境变量：
    - ``RELAY_WS_HOST`` / ``RELAY_WS_PORT``：WebSocket 监听地址
    - ``RELAY_AUTH_TOKEN`` 或 ``BRIDGE_AUTH_TOKEN``：Bridge 与 Console 共享密钥
    - ``RELAY_CONSOLE_HOST`` / ``RELAY_CONSOLE_PORT``：Web Console
    - ``RELAY_CONSOLE_BIND``：``0.0.0.0`` 或 ``127.0.0.1``
    - ``RELAY_WS_MAX_MESSAGE_BYTES``：Bridge WebSocket 单帧上限（字节），默认 16MiB，避免大图截图触发 1009
    """
    _ = path
    token = os.environ.get("RELAY_AUTH_TOKEN") or os.environ.get("BRIDGE_AUTH_TOKEN") or "dev-change-me"
    max_ws = int(os.environ.get("RELAY_WS_MAX_MESSAGE_BYTES", str(_DEFAULT_WS_MAX)))
    return {
        "host": os.environ.get("RELAY_WS_HOST", "0.0.0.0"),
        "port": int(os.environ.get("RELAY_WS_PORT", "8091")),
        "auth_token": token,
        "max_ws_message_bytes": max_ws,
        "web_console": {
            "host": os.environ.get("RELAY_CONSOLE_BIND", "0.0.0.0"),
            "port": int(os.environ.get("RELAY_CONSOLE_PORT", "8092")),
            "auth_token": os.environ.get("RELAY_CONSOLE_TOKEN") or token,
        },
    }


def setup_logging(level: str | None = None) -> None:
    logging.basicConfig(
        level=getattr(logging, (level or os.environ.get("RELAY_LOG_LEVEL", "INFO")).upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
