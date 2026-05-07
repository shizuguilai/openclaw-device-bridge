"""
诊断日志「包」：启动时打印一份可读摘要，便于核对 URL / token 指纹 / 端口。

启用方式（客户端或 Relay 任一进程）::

    export OPENCLAW_DIAG=1          # Linux / macOS
    # Windows PowerShell:
    $env:OPENCLAW_DIAG = "1"

等价别名：DEVICE_BRIDGE_DIAG=1（历史兼容）。
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from shared.protocol import token_fingerprint

_TRUE = frozenset({"1", "true", "yes", "on"})


def diag_enabled() -> bool:
    for key in ("OPENCLAW_DIAG", "DEVICE_BRIDGE_DIAG"):
        if os.environ.get(key, "").strip().lower() in _TRUE:
            return True
    return False


def apply_verbose_logging_if_diag() -> None:
    """将根与子 logger 调到 DEBUG（需在各自 setup_logging 之后调用）。"""
    if not diag_enabled():
        return
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for name in (
        "client",
        "client.bridge",
        "client.core",
        "client.drivers",
        "client.agents",
        "relay",
        "relay.web_console",
        "websockets",
        "uvicorn",
    ):
        logging.getLogger(name).setLevel(logging.DEBUG)
    logging.getLogger(__name__).debug("OPENCLAW_DIAG：已开启 DEBUG（含 websockets/uvicorn）")


def log_bridge_client_banner(logger: logging.Logger, relay_cfg: dict[str, Any]) -> None:
    if not diag_enabled():
        return
    tok = str(relay_cfg.get("auth_token") or "")
    fp = token_fingerprint(tok)
    lines = (
        "",
        "======== OpenClaw Bridge · 诊断包 ========",
        f"  Python          : {sys.version.split()[0]}",
        f"  解释器          : {sys.executable}",
        f"  relay.url       : {relay_cfg.get('relay_url')}",
        f"  bridge_id       : {relay_cfg.get('bridge_id')}",
        f"  token_fp        : {fp}",
        f"  max_ws_bytes    : {relay_cfg.get('max_ws_message_bytes')}",
        "  说明 token_fp 须与 Relay 启动日志里「Bridge 鉴权 token 指纹」一致；",
        "  若为 empty：多为 bridge.yaml 使用 ${BRIDGE_AUTH_TOKEN} 但未在该终端设置变量。",
        "========================================",
        "",
    )
    for line in lines:
        logger.info(line)


def log_relay_banner(logger: logging.Logger, config: dict[str, Any]) -> None:
    if not diag_enabled():
        return
    tok = str(config.get("auth_token") or "")
    fp = token_fingerprint(tok)
    wc = dict(config.get("web_console") or {})
    lines = (
        "",
        "======== OpenClaw Relay · 诊断包 ========",
        f"  Python          : {sys.version.split()[0]}",
        f"  WebSocket 监听  : {config.get('host')}:{config.get('port')}",
        f"  Bridge token_fp : {fp}",
        f"  Web Console     : {wc.get('host')}:{wc.get('port')}",
        f"  max_ws_bytes    : {config.get('max_ws_message_bytes')}",
        "  Bridge 客户端日志中的 token_fp 须与本行一致。",
        "=======================================",
        "",
    )
    for line in lines:
        logger.info(line)
