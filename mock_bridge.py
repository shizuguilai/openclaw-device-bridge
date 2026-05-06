"""
Mock Bridge Client：模拟手机设备连接 Relay并响应指令。
用法：python mock_bridge.py [relay_url] [bridge_id]
"""

import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from shared.protocol import (
    build_auth_message,
    build_command_message,
    build_device_status_message,
    build_heartbeat_message,
    build_result_message,
    is_command,
    new_command_id,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("mock_bridge")


class MockDevice:
    """模拟一台手机设备。"""

    def __init__(self, device_id: str, model: str = "MockPhone-2026") -> None:
        self.device_id = device_id
        self.model = model
        self.screen_on = True

    def handle_action(self, action: str, params: dict) -> dict:
        if action == "screenshot":
            return {
                "status": "success",
                "data": {
                    "width": 1080,
                    "height": 2400,
                    "format": "png",
                    "size_bytes": 342880,
                    "note": "这是模拟截图，来自 MockDevice",
                },
            }
        elif action == "screen_and_act":
            return {
                "status": "success",
                "data": {
                    "screen_text": "桌面 | 应用列表 | 设置",
                    "acts_done": 0,
                    "note": "模拟 screen_and_act",
                },
            }
        elif action == "click":
            x, y = params.get("x", 540), params.get("y", 1200)
            return {"status": "success", "data": {"clicked": f"({x}, {y})"}}
        elif action == "input_text":
            return {"status": "success", "data": {"text": params.get("text", ""), "committed": True}}
        elif action == "device_info":
            return {
                "status": "success",
                "data": {
                    "device_id": self.device_id,
                    "model": self.model,
                    "android_version": "14",
                    "screen_on": self.screen_on,
                },
            }
        else:
            return {"status": "error", "data": {"message": f"Unknown action: {action}"}}


class MockBridge:
    """模拟 Bridge Client：连接 Relay、注册设备、响应指令。"""

    def __init__(self, relay_url: str, bridge_id: str, auth_token: str) -> None:
        self.relay_url = relay_url
        self.bridge_id = bridge_id
        self.auth_token = auth_token
        self.devices = [
            MockDevice(f"device-{i}", f"MockPhone-{i}") for i in range(1, 3)
        ]
        self.ws = None
        self._running = True

    async def run(self) -> None:
        import websockets

        logger.info("Bridge %s 正在连接 Relay: %s", self.bridge_id, self.relay_url)
        async with websockets.connect(self.relay_url, ping_interval=None) as ws:
            self.ws = ws
            # 1. 认证
            await ws.send(json.dumps(build_auth_message(token=self.auth_token, bridge_id=self.bridge_id)))
            auth_reply = await ws.recv()
            logger.info("认证响应: %s", auth_reply)

            # 2. 上报设备状态
            await ws.send(
                json.dumps(
                    build_device_status_message(
                        devices=[
                            {
                                "device_id": d.device_id,
                                "model": d.model,
                                "status": "online",
                                "note": f"模拟设备 {d.device_id}",
                            }
                            for d in self.devices
                        ],
                        bridge_id=self.bridge_id,
                    )
                )
            )
            logger.info("已上报 %d 台设备", len(self.devices))

            # 等待Relay处理设备列表
            await asyncio.sleep(0.5)

            # 3. 心跳 + 处理指令循环
            async def heartbeat():
                while self._running:
                    await asyncio.sleep(10)
                    try:
                        await ws.send(json.dumps(build_heartbeat_message(bridge_id=self.bridge_id)))
                    except Exception:
                        break

            async def listen():
                while self._running:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        continue
                    msg = json.loads(raw)
                    if is_command(msg):
                        await self._handle_command(msg)

            await asyncio.gather(heartbeat(), listen())

        logger.warning("WebSocket 连接断开")

    async def _handle_command(self, cmd: dict) -> None:
        device_id = cmd.get("device_id")
        action = cmd.get("action")
        params = cmd.get("params", {})
        command_id = cmd.get("id")

        device = next((d for d in self.devices if d.device_id == device_id), None)
        if not device:
            result = {"status": "error", "data": {"message": f"Device {device_id} not found"}}
        else:
            result = device.handle_action(action, params)

        import time

        result_msg = build_result_message(
            command_id=command_id,
            device_id=device_id,
            status=result["status"],
            data=result.get("data"),
            execution_time_ms=int(time.time() * 1000) - cmd.get("timestamp", 0),
        )
        logger.info("<- command: %s → result: %s", action, result["status"])
        await self.ws.send(json.dumps(result_msg))


async def main():
    relay_url = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8091"
    bridge_id = sys.argv[2] if len(sys.argv) > 2 else f"mock-bridge-{uuid.uuid4().hex[:8]}"
    auth_token = "dev-change-me"

    logger.info("启动 Mock Bridge: id=%s, relay=%s", bridge_id, relay_url)
    bridge = MockBridge(relay_url, bridge_id, auth_token)
    try:
        await bridge.run()
    except KeyboardInterrupt:
        logger.info("被Interrupt，退出")
    except Exception as e:
        logger.error("异常: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
