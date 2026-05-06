"""ADB 驱动：截图、UI dump、触控、Shell 等。"""

from __future__ import annotations

import asyncio
import base64
import re
from typing import Any

from client.core.exceptions import DriverError
from client.drivers.base_driver import BaseDriver


class ADBDriver(BaseDriver):
    """封装常用异步 adb 子进程调用。"""

    def __init__(self, device_id: str, adb_path: str = "adb") -> None:
        super().__init__(device_id)
        self.adb_path = adb_path

    async def _exec(self, *args: str, timeout: float = 60.0) -> tuple[bytes, bytes, int]:
        cmd = (self.adb_path, "-s", self.device_id, *args)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise DriverError(f"ADB 超时: {' '.join(cmd)}") from None
        code = proc.returncode or 0
        return out, err, code

    async def screenshot(self) -> bytes:
        out, err, code = await self._exec("exec-out", "screencap", "-p", timeout=30.0)
        if code != 0 or not out:
            raise DriverError(f"截图失败: {err.decode(errors='replace')}")
        return out

    async def dump_ui(self) -> str:
        remote = "/sdcard/ocdb_window_dump.xml"
        _, err1, c1 = await self._exec("shell", "uiautomator", "dump", remote, timeout=30.0)
        if c1 != 0:
            raise DriverError(f"uiautomator dump 失败: {err1.decode(errors='replace')}")
        out, err2, c2 = await self._exec("exec-out", "cat", remote, timeout=30.0)
        if c2 != 0:
            raise DriverError(f"读取 UI dump 失败: {err2.decode(errors='replace')}")
        return out.decode("utf-8", errors="replace")

    async def tap(self, x: int, y: int) -> None:
        _, err, code = await self._exec("shell", "input", "tap", str(x), str(y), timeout=15.0)
        if code != 0:
            raise DriverError(err.decode(errors="replace"))

    async def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        _, err, code = await self._exec(
            "shell",
            "input",
            "swipe",
            str(x1),
            str(y1),
            str(x2),
            str(y2),
            str(duration_ms),
            timeout=20.0,
        )
        if code != 0:
            raise DriverError(err.decode(errors="replace"))

    async def input_text(self, text: str) -> None:
        # 空格转 %s 等简化处理
        escaped = text.replace(" ", "%s").replace("&", "\\&")
        _, err, code = await self._exec("shell", "input", "text", escaped, timeout=15.0)
        if code != 0:
            raise DriverError(err.decode(errors="replace"))

    async def key_event(self, keycode: int) -> None:
        _, err, code = await self._exec("shell", "input", "keyevent", str(keycode), timeout=10.0)
        if code != 0:
            raise DriverError(err.decode(errors="replace"))

    async def launch_app(self, package: str, activity: str | None = None) -> None:
        if activity:
            comp = f"{package}/{activity}"
            args = ("shell", "am", "start", "-n", comp)
        else:
            args = ("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        _, err, code = await self._exec(*args, timeout=30.0)
        if code != 0:
            raise DriverError(err.decode(errors="replace"))

    async def shell(self, command: str) -> str:
        out, err, code = await self._exec("shell", "sh", "-c", command, timeout=60.0)
        if code != 0:
            raise DriverError(err.decode(errors="replace") or out.decode(errors="replace"))
        return out.decode("utf-8", errors="replace")

    async def get_device_info(self) -> dict[str, Any]:
        props = await self.shell("getprop ro.product.model && getprop ro.build.version.release && wm size")
        lines = [ln.strip() for ln in props.splitlines() if ln.strip()]
        model = lines[0] if len(lines) > 0 else "unknown"
        android_ver = lines[1] if len(lines) > 1 else "unknown"
        size = lines[2] if len(lines) > 2 else ""
        m = re.search(r"(\d+)\s*x\s*(\d+)", size)
        screen = f"{m.group(1)}x{m.group(2)}" if m else ""
        battery = ""
        try:
            binfo = await self.shell("dumpsys battery")
            bm = re.search(r"level:\s*(\d+)", binfo)
            if bm:
                battery = int(bm.group(1))
        except DriverError:
            battery = ""
        return {
            "device_id": self.device_id,
            "model": model,
            "android_version": android_ver,
            "screen_size": screen,
            "battery": battery,
        }

    def screenshot_base64(self, png_bytes: bytes) -> str:
        return base64.b64encode(png_bytes).decode("ascii")
