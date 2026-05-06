"""UI 解析 Agent（依赖截屏或独立 dump）。"""

from __future__ import annotations

from typing import Any

from client.core.agent import BaseAgent
from client.core.context import TaskContext
from client.core.exceptions import ExecutionError
from client.drivers.adb_driver import ADBDriver
from client.drivers.screen_parser import parse_ui_hierarchy


class UIParseAgent(BaseAgent):
    async def run(self, ctx: TaskContext) -> dict[str, Any]:
        driver = ctx.get("adb")
        if not isinstance(driver, ADBDriver):
            raise ExecutionError("UIParseAgent 需要 ctx['adb'] 为 ADBDriver")
        mode = str(self.config.get("parse_mode", "accessibility_tree"))
        max_elements = int(self.config.get("max_elements", 50))
        xml_text = await driver.dump_ui()
        elements = parse_ui_hierarchy(xml_text, max_elements=max_elements)
        return {
            "parse_mode": mode,
            "ui_elements": elements,
            "raw_xml_length": len(xml_text),
        }
