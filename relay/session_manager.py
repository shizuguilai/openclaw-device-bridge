"""Bridge Client WebSocket 会话与待响应指令。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass
class BridgeSession:
    bridge_id: str
    websocket: Any
    last_heartbeat: float = field(default_factory=lambda: time.time())
    devices: list[dict[str, Any]] = field(default_factory=list)


class SessionManager:
    """管理多个 Bridge 连接、设备缓存、指令-结果配对。"""

    def __init__(
        self,
        *,
        on_device_update: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._sessions: dict[str, BridgeSession] = {}
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._send_locks: dict[str, asyncio.Lock] = {}
        self._history: deque[dict[str, Any]] = deque(maxlen=500)
        self._on_device_update = on_device_update

    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def record_history(self, entry: dict[str, Any]) -> None:
        self._history.appendleft(entry)

    def register(self, session: BridgeSession) -> None:
        self._sessions[session.bridge_id] = session
        self._send_locks.setdefault(session.bridge_id, asyncio.Lock())
        logger.info("Bridge 上线: %s", session.bridge_id)

    async def unregister(self, bridge_id: str) -> None:
        self._sessions.pop(bridge_id, None)
        self._send_locks.pop(bridge_id, None)
        logger.info("Bridge 下线: %s", bridge_id)
        if self._on_device_update:
            await self._on_device_update()

    def get_session(self, bridge_id: str) -> BridgeSession | None:
        return self._sessions.get(bridge_id)

    def list_bridge_ids(self) -> list[str]:
        return list(self._sessions.keys())

    def default_bridge_id(self) -> str | None:
        if len(self._sessions) == 1:
            return next(iter(self._sessions))
        return None

    def update_devices(self, bridge_id: str, devices: list[dict[str, Any]]) -> None:
        s = self._sessions.get(bridge_id)
        if s:
            s.devices = list(devices)

    def update_heartbeat(self, bridge_id: str) -> None:
        s = self._sessions.get(bridge_id)
        if s:
            s.last_heartbeat = time.time()

    def list_devices(self, bridge_id: str | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for bid, sess in self._sessions.items():
            if bridge_id and bid != bridge_id:
                continue
            for d in sess.devices:
                row = dict(d)
                row.setdefault("bridge_id", bid)
                out.append(row)
        return out

    def list_bridges(self) -> list[dict[str, Any]]:
        now = time.time()
        return [
            {
                "bridge_id": bid,
                "online": True,
                "last_heartbeat_age_sec": round(now - s.last_heartbeat, 2),
                "device_count": len(s.devices),
            }
            for bid, s in self._sessions.items()
        ]

    def register_pending(self, command_id: str, fut: asyncio.Future[dict[str, Any]]) -> None:
        self._pending[command_id] = fut

    def resolve_pending(self, command_id: str, result: dict[str, Any]) -> bool:
        fut = self._pending.pop(command_id, None)
        if fut is None or fut.done():
            return False
        fut.set_result(result)
        return True

    def cancel_pending(self, command_id: str, err: Exception) -> None:
        fut = self._pending.pop(command_id, None)
        if fut and not fut.done():
            fut.set_exception(err)

    def discard_pending(self, command_id: str) -> None:
        self._pending.pop(command_id, None)

    async def send_to_bridge(self, bridge_id: str, payload: dict[str, Any]) -> None:
        sess = self._sessions.get(bridge_id)
        if sess is None:
            raise RuntimeError(f"Bridge 未连接: {bridge_id}")
        lock = self._send_locks.setdefault(bridge_id, asyncio.Lock())
        raw = json.dumps(payload, ensure_ascii=False)
        async with lock:
            await sess.websocket.send(raw)
