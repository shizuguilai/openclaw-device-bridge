"""WebSocket 客户端：连接 Relay、心跳、指令回调。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import websockets

from shared.protocol import (
    build_auth_message,
    build_device_status_message,
    build_heartbeat_message,
    build_result_message,
    is_command,
    new_command_id,
)
from client.bridge.device_manager import DeviceManager
from client.bridge.heartbeat import ReconnectBackoff

logger = logging.getLogger(__name__)

CommandHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class RelayConnector:
    def __init__(self, config: dict[str, Any]) -> None:
        self.relay_url = str(config["relay_url"])
        self.auth_token = str(config["auth_token"])
        self.bridge_id = str(config["bridge_id"])
        self.heartbeat_interval = int(config.get("heartbeat_interval", 30))
        self.reconnect_max_delay = float(config.get("reconnect_max_delay", 60))
        self.reconnect_base_delay = float(config.get("reconnect_base_delay", 1))
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

    async def _consume_ws(self, ws: WebSocketClientProtocol) -> None:
        self._ws = ws
        try:
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
                logger.info("连接 Relay: %s", self.relay_url)
                async with websockets.connect(
                    self.relay_url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    backoff.reset()
                    await ws.send(
                        json.dumps(
                            build_auth_message(token=self.auth_token, bridge_id=self.bridge_id),
                            ensure_ascii=False,
                        )
                    )
                    await self._consume_ws(ws)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("Relay 连接断开: %s", e)
            if self._stop.is_set():
                break
            await backoff.sleep()

    def stop(self) -> None:
        self._stop.set()
