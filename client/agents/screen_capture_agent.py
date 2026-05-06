"""截屏 Agent。"""

from __future__ import annotations

from typing import Any

from client.core.agent import BaseAgent
from client.core.context import TaskContext
from client.core.exceptions import ExecutionError
from client.drivers.adb_driver import ADBDriver


class ScreenCaptureAgent(BaseAgent):
    async def run(self, ctx: TaskContext) -> dict[str, Any]:
        driver = ctx.get("adb")
        if not isinstance(driver, ADBDriver):
            raise ExecutionError("ScreenCaptureAgent 需要 ctx['adb'] 为 ADBDriver")
        png = await driver.screenshot()
        fmt = str(self.config.get("format", "png"))
        quality = int(self.config.get("quality", 80))
        data: dict[str, Any] = {
            "format": fmt,
            "screenshot_base64": driver.screenshot_base64(png),
            "bytes_length": len(png),
            "quality": quality,
        }
        return data
