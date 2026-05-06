"""Agent 与 DAG 工厂。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from client.agents.screen_capture_agent import ScreenCaptureAgent
from client.core.context import TaskContext
from client.core.dag_factory import DAGFactory
from client.drivers.adb_driver import ADBDriver


@pytest.mark.asyncio
async def test_screen_capture_agent_mock() -> None:
    agent = ScreenCaptureAgent(name="sc", config={})
    drv = ADBDriver("emulator-5554", adb_path="adb")
    with patch.object(drv, "screenshot", new_callable=AsyncMock) as ms:
        ms.return_value = b"\x89PNG\r\n\x1a\n"
        ctx = TaskContext({"adb": drv})
        out = await agent.run(ctx)
    assert "screenshot_base64" in out


def test_dag_factory_parse() -> None:
    fac = DAGFactory()
    dag = fac.load_dag_from_dict(
        {
            "name": "t",
            "agents": [{"name": "a", "type": "DeviceInfoAgent", "depends_on": []}],
        }
    )
    assert dag.name == "t"
    assert "a" in dag.nodes
