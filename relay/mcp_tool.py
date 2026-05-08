"""
对内 MCP / Tool 风格 API：直接持有 ``BridgeRelayServer`` 时由 OpenClaw 进程内调用。

若仅通过 HTTP 暴露能力，可使用 ``skill/tool.py`` 访问 Web Console 的 ``/api/*``。
"""

from __future__ import annotations

from typing import Any

from relay.relay_server import BridgeRelayServer
from shared.protocol import build_command_message, new_command_id


class RelayMcpTool:
    """封装常用设备指令为异步方法。"""

    def __init__(self, relay: BridgeRelayServer) -> None:
        self._relay = relay

    async def device_list(self, bridge_id: str | None = None) -> list[dict[str, Any]]:
        return self._relay.list_devices(bridge_id)

    async def device_screenshot(
        self,
        device_id: str,
        bridge_id: str | None = None,
        *,
        image_format: str = "png",
        quality: int = 80,
        max_width: int = 0,
        max_height: int = 0,
    ) -> dict[str, Any]:
        cmd = build_command_message(
            command_id=new_command_id(),
            device_id=device_id,
            action="screenshot",
            params={
                "format": image_format,
                "quality": quality,
                "max_width": max_width,
                "max_height": max_height,
            },
        )
        return await self._relay.send_command(bridge_id, cmd)

    async def device_tap(self, device_id: str, x: int, y: int, bridge_id: str | None = None) -> dict[str, Any]:
        cmd = build_command_message(
            command_id=new_command_id(),
            device_id=device_id,
            action="tap",
            params={"x": x, "y": y},
        )
        return await self._relay.send_command(bridge_id, cmd)

    async def device_swipe(
        self,
        device_id: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        bridge_id: str | None = None,
        duration_ms: int = 300,
    ) -> dict[str, Any]:
        cmd = build_command_message(
            command_id=new_command_id(),
            device_id=device_id,
            action="swipe",
            params={"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration_ms": duration_ms},
        )
        return await self._relay.send_command(bridge_id, cmd)

    async def device_input(self, device_id: str, text: str, bridge_id: str | None = None) -> dict[str, Any]:
        cmd = build_command_message(
            command_id=new_command_id(),
            device_id=device_id,
            action="input_text",
            params={"text": text},
        )
        return await self._relay.send_command(bridge_id, cmd)

    async def device_launch_app(
        self,
        device_id: str,
        package: str,
        activity: str | None = None,
        bridge_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"package": package}
        if activity:
            params["activity"] = activity
        cmd = build_command_message(
            command_id=new_command_id(),
            device_id=device_id,
            action="launch_app",
            params=params,
        )
        return await self._relay.send_command(bridge_id, cmd)

    async def device_ui_dump(self, device_id: str, bridge_id: str | None = None) -> dict[str, Any]:
        cmd = build_command_message(
            command_id=new_command_id(),
            device_id=device_id,
            action="dump_ui",
            params={},
        )
        return await self._relay.send_command(bridge_id, cmd)

    async def device_run_dag(
        self,
        device_id: str,
        dag_name: str,
        bridge_id: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cmd = build_command_message(
            command_id=new_command_id(),
            device_id=device_id,
            action=dag_name,
            params=extra_params or {},
            dag_name=dag_name,
        )
        return await self._relay.send_command(bridge_id, cmd)
