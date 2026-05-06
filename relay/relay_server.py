"""Bridge Relay：WebSocket Server + 对内 send_command API。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

from relay.session_manager import BridgeSession, SessionManager
from shared.protocol import (
    is_auth,
    is_device_status,
    is_heartbeat,
    is_result,
    new_command_id,
)

logger = logging.getLogger(__name__)


class _ConsoleEventBus:
    """每个 Web Console WS 独立队列，避免单队列多消费者抢读。"""

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[dict[str, Any]]] = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        if q in self._queues:
            self._queues.remove(q)

    def publish(self, msg: dict[str, Any]) -> None:
        for q in list(self._queues):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass


class BridgeRelayServer:
    """
    部署在远程 Linux：等待 Bridge Client WebSocket 连入；
    对内提供 ``send_command``，将 JSON 指令转发到指定 Bridge 并等待 ``result``。
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.host = str(config.get("host", "0.0.0.0"))
        self.port = int(config.get("port", 8091))
        self.auth_token = str(config["auth_token"])
        self._sessions = SessionManager(on_device_update=self._notify_console_listeners)
        self.console_events = _ConsoleEventBus()
        self._stop = asyncio.Event()

    async def _notify_console_listeners(self) -> None:
        self.console_events.publish({"type": "devices_updated"})

    async def _handle_bridge_connection(self, websocket: Any) -> None:
        bridge_id: str | None = None
        try:
            raw_first = await websocket.recv()
            if isinstance(raw_first, bytes):
                raw_first = raw_first.decode("utf-8")
            msg = json.loads(raw_first)
            if not is_auth(msg) or str(msg.get("token")) != self.auth_token:
                await websocket.close(code=4001, reason="unauthorized")
                return
            bridge_id = str(msg.get("bridge_id") or "bridge-unknown")
            sess = BridgeSession(bridge_id=bridge_id, websocket=websocket)
            self._sessions.register(sess)
            self.console_events.publish({"type": "bridge_online", "bridge_id": bridge_id})

            async for raw in websocket:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if is_result(data):
                    cid = str(data.get("id") or "")
                    self._sessions.resolve_pending(cid, data)
                    self._sessions.record_history(
                        {"kind": "result", "bridge_id": bridge_id, "command_id": cid, "status": data.get("status")}
                    )
                    self.console_events.publish({"type": "command_result", "payload": data})
                elif is_device_status(data):
                    devs = list(data.get("devices") or [])
                    self._sessions.update_devices(bridge_id, devs)
                    self.console_events.publish(
                        {"type": "device_status", "bridge_id": bridge_id, "devices": devs}
                    )
                elif is_heartbeat(data):
                    self._sessions.update_heartbeat(bridge_id)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Bridge 连接异常 %s: %s", bridge_id, e)
        finally:
            if bridge_id:
                await self._sessions.unregister(bridge_id)
                self.console_events.publish({"type": "bridge_offline", "bridge_id": bridge_id})

    async def start(self) -> None:
        """启动 WebSocket 服务（阻塞至 ``stop()``）。"""
        async with websockets.serve(
            self._handle_bridge_connection,
            self.host,
            self.port,
        ):
            logger.info("Relay WebSocket 监听 ws://%s:%s", self.host, self.port)
            await self._stop.wait()

    def stop(self) -> None:
        self._stop.set()

    def list_bridges(self) -> list[dict[str, Any]]:
        return self._sessions.list_bridges()

    def list_devices(self, bridge_id: str | None = None) -> list[dict[str, Any]]:
        return self._sessions.list_devices(bridge_id)

    def command_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._sessions.history()[:limit]

    async def send_command(self, bridge_id: str | None, command: dict[str, Any]) -> dict[str, Any]:
        bid = bridge_id or self._sessions.default_bridge_id()
        if not bid:
            raise RuntimeError("当前无已连接 Bridge，或存在多个 Bridge 需显式指定 bridge_id")
        cmd_id = str(command.get("id") or new_command_id())
        command = {**command, "id": cmd_id, "type": "command"}
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._sessions.register_pending(cmd_id, fut)
        timeout_s = float(command.get("timeout_ms", 30000)) / 1000.0
        self._sessions.record_history({"kind": "command_sent", "bridge_id": bid, "command": command})
        try:
            await self._sessions.send_to_bridge(bid, command)
            return await asyncio.wait_for(fut, timeout=timeout_s)
        except Exception as e:
            self._sessions.cancel_pending(cmd_id, e)
            raise
        finally:
            self._sessions.discard_pending(cmd_id)
