"""ADB 驱动（mock 子进程）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from client.drivers.adb_driver import ADBDriver


@pytest.mark.asyncio
async def test_adb_screenshot() -> None:
    driver = ADBDriver("emulator-5554", adb_path="adb")
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"\x89PNG\r\n\x1a\n", b""))
    proc.returncode = 0
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as m:
        m.return_value = proc
        png = await driver.screenshot()
        assert png.startswith(b"\x89PNG")
