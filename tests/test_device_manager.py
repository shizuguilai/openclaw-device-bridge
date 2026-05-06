"""设备管理器 mock adb devices。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from client.bridge.device_manager import DeviceManager


class _Proc:
    def __init__(self, out: bytes) -> None:
        self._out = out

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._out, b""


@pytest.mark.asyncio
async def test_device_manager_list_empty() -> None:
    dm = DeviceManager({"adb_path": "adb", "poll_interval": 0.01, "auto_discover": True})
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as m:
        m.return_value = _Proc(b"List of devices attached\n\n")
        await dm._refresh_devices()
    assert dm.list_devices() == []
