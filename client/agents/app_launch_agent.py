"""启动应用 Agent。"""

from __future__ import annotations

from typing import Any

from client.core.agent import BaseAgent
from client.core.context import TaskContext
from client.core.exceptions import ExecutionError
from client.drivers.adb_driver import ADBDriver


class AppLaunchAgent(BaseAgent):
    async def run(self, ctx: TaskContext) -> dict[str, Any]:
        driver = ctx.get("adb")
        if not isinstance(driver, ADBDriver):
            raise ExecutionError("AppLaunchAgent 需要 ctx['adb'] 为 ADBDriver")
        cmd = ctx.get("command") or {}
        params = (cmd.get("params") or {}) if isinstance(cmd, dict) else {}
        package = params.get("package") or self.config.get("package")
        activity = params.get("activity") or self.config.get("activity")
        if not package:
            raise ExecutionError("缺少 package")
        await driver.launch_app(str(package), str(activity) if activity else None)
        return {"action_result": "launched", "package": package, "activity": activity}
