"""根据上游解析结果执行占位 ADB 动作（DAG 末端示例）。"""

from __future__ import annotations

from typing import Any

from client.core.agent import BaseAgent
from client.core.context import TaskContext
from client.core.exceptions import ExecutionError
from client.drivers.adb_driver import ADBDriver


class ADBActionAgent(BaseAgent):
    """
    示例：若 ``command.params`` 含 tap 坐标则点击，否则仅返回 ok。

    真实场景可由 TaskRouter 直接走 direct 路径；本 Agent 用于 DAG 流水线演示。
    """

    async def run(self, ctx: TaskContext) -> dict[str, Any]:
        driver = ctx.get("adb")
        if not isinstance(driver, ADBDriver):
            raise ExecutionError("ADBActionAgent 需要 ctx['adb'] 为 ADBDriver")
        cmd = ctx.get("command") or {}
        params = (cmd.get("params") or {}) if isinstance(cmd, dict) else {}
        if "x" in params and "y" in params:
            await driver.tap(int(params["x"]), int(params["y"]))
            return {"action_result": "tap_ok", "x": params["x"], "y": params["y"]}
        return {"action_result": "noop", "reason": "no tap params on context.command"}
