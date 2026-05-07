"""WebSocket 客户端：连接 Relay、心跳、指令回调。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Dict

import websockets
from websockets.exceptions import ConnectionClosed

from shared.protocol import (
    build_auth_message,
    build_device_status_message,
    build_heartbeat_message,
    build_result_message,
    is_command,
    new_command_id,
    token_fingerprint,
)
from client.bridge.device_manager import DeviceManager
from client.bridge.heartbeat import ReconnectBackoff

logger = logging.getLogger(__name__)

CommandHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class RelayConnector:
    def __init__(self, config: dict[str, Any]) -> None:
        self.relay_url = str(config["relay_url"])
        self.auth_token = str(config["auth_token"])
        self.bridge_id = str(config["bridge_id"])
        self.heartbeat_interval = int(config.get("heartbeat_interval", 30))
        self.reconnect_max_delay = float(config.get("reconnect_max_delay", 60))
        self.reconnect_base_delay = float(config.get("reconnect_base_delay", 1))
        self.max_ws_message_bytes = int(config.get("max_ws_message_bytes", 16 * 1024 * 1024))
        self._handler: CommandHandler | None = None
        self._ws: Any | None = None
        self._stop = asyncio.Event()
        self._send_lock = asyncio.Lock()

    def on_command(self, callback: CommandHandler) -> None:
        self._handler = callback

    async def send_result(self, result: dict[str, Any]) -> None:
        if self._ws is None:
            return
        payload = json.dumps(result, ensure_ascii=False)
        async with self._send_lock:
            await self._ws.send(payload)

    async def send_device_status(self, devices: list[dict[str, Any]]) -> None:
        if self._ws is None:
            return
        msg = build_device_status_message(devices=devices, bridge_id=self.bridge_id)
        async with self._send_lock:
            await self._ws.send(json.dumps(msg, ensure_ascii=False))

    async def heartbeat_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(self.heartbeat_interval)
            if self._ws is None:
                continue
            try:
                hb = build_heartbeat_message(bridge_id=self.bridge_id)
                async with self._send_lock:
                    await self._ws.send(json.dumps(hb, ensure_ascii=False))
            except Exception:
                logger.debug("心跳发送失败", exc_info=True)

    async def status_report_loop(self, device_manager: DeviceManager) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(max(2.0, self.heartbeat_interval / 2))
            try:
                devices = device_manager.list_device_dicts()
                await self.send_device_status(devices)
            except Exception:
                logger.debug("状态上报失败", exc_info=True)

    async def _handle_command_message(self, msg: dict[str, Any]) -> None:
        if self._handler is None:
            return
        cmd_id = str(msg.get("id") or new_command_id())
        device_id = str(msg.get("device_id") or "")
        t0 = time.perf_counter()
        try:
            out = await self._handler(msg)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            out.setdefault("id", cmd_id)
            out.setdefault("execution_time_ms", elapsed_ms)
            await self.send_result(out)
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            err = build_result_message(
                command_id=cmd_id,
                device_id=device_id,
                status="error",
                data={"error": str(e)},
                execution_time_ms=elapsed_ms,
            )
            await self.send_result(err)

    async def _consume_ws(self, ws: Any) -> None:
        self._ws = ws
        try:
            logger.info(
                "Relay WebSocket 已就绪，等待下行指令 bridge_id=%s token_fp=%s",
                self.bridge_id,
                token_fingerprint(self.auth_token),
            )
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if is_command(msg):
                    await self._handle_command_message(msg)
        finally:
            self._ws = None

    async def connect(self) -> None:
        """断线自动重连；与 ``heartbeat_loop`` / ``status_report_loop`` 并行运行。"""
        backoff = ReconnectBackoff(self.reconnect_base_delay, self.reconnect_max_delay)
        while not self._stop.is_set():
            try:
                logger.info(
                    "连接 Relay: url=%s bridge_id=%s token_fp=%s max_ws_message_bytes=%s "
                    "(与 Relay 日志中 relay_token_fp 一致则表示 token 配置一致)",
                    self.relay_url,
                    self.bridge_id,
                    token_fingerprint(self.auth_token),
                    self.max_ws_message_bytes,
                )
                async with websockets.connect(
                    self.relay_url,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=self.max_ws_message_bytes,
                ) as ws:
                    backoff.reset()
                    await ws.send(
                        json.dumps(
                            build_auth_message(token=self.auth_token, bridge_id=self.bridge_id),
                            ensure_ascii=False,
                        )
                    )
                    logger.info(
                        "已发送 auth 首包，等待 Relay 确认… bridge_id=%s token_fp=%s",
                        self.bridge_id,
                        token_fingerprint(self.auth_token),
                    )
                    await self._consume_ws(ws)
                    logger.info("Relay WebSocket 读循环结束 bridge_id=%s", self.bridge_id)
            except asyncio.CancelledError:
                raise
            except ConnectionClosed as e:
                rcvd = e.rcvd
                code = rcvd.code if rcvd is not None else None
                reason = (rcvd.reason if rcvd is not None else "") or ""
                if code == 4001:
                    logger.error(
                        "Relay 关闭连接：鉴权失败 (code=4001) reason=%r bridge_id=%s "
                        "client_token_fp=%s — 请核对本机 BRIDGE_AUTH_TOKEN / bridge.yaml "
                        "与服务器 RELAY_AUTH_TOKEN 是否完全一致（勿多空格、引号或 YAML 未展开 ${VAR}）",
                        reason,
                        self.bridge_id,
                        token_fingerprint(self.auth_token),
                    )
                elif code == 1009:
                    logger.error(
                        "Relay 关闭连接：单帧过大 (code=1009) bridge_id=%s — 多为截图等结果的 JSON "
                        "超过 Relay/WebSocket 限制。请在服务器增大 RELAY_WS_MAX_MESSAGE_BYTES，"
                        "或在 bridge.yaml 设置 relay.max_ws_message_bytes（默认 16MiB），并保持两端一致",
                        self.bridge_id,
                    )
                else:
                    logger.warning(
                        "Relay WebSocket 已关闭: code=%s reason=%r bridge_id=%s token_fp=%s",
                        code,
                        reason,
                        self.bridge_id,
                        token_fingerprint(self.auth_token),
                    )
            except Exception as e:
                logger.warning(
                    "Relay 连接异常: %s bridge_id=%s token_fp=%s",
                    e,
                    self.bridge_id,
                    token_fingerprint(self.auth_token),
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )
            if self._stop.is_set():
                break
            await backoff.sleep()

    def stop(self) -> None:
        self._stop.set()
