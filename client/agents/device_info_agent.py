"""设备信息采集 Agent。"""

from __future__ import annotations

from typing import Any

from client.core.agent import BaseAgent
from client.core.context import TaskContext
from client.core.exceptions import ExecutionError
from client.drivers.adb_driver import ADBDriver


class DeviceInfoAgent(BaseAgent):
    async def run(self, ctx: TaskContext) -> dict[str, Any]:
        driver = ctx.get("adb")
        if not isinstance(driver, ADBDriver):
            raise ExecutionError("DeviceInfoAgent 需要 ctx['adb'] 为 ADBDriver")
        info = await driver.get_device_info()
        return {"device_info": info}
