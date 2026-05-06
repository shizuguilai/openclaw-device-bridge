"""ADB 设备发现、状态与互斥锁。"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from client.drivers.adb_driver import ADBDriver

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    device_id: str
    model: str = ""
    status: str = "online"
    battery: int | str = ""
    screen_size: str = ""
    android_version: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "model": self.model,
            "status": self.status,
            "battery": self.battery,
            "screen_size": self.screen_size,
            "android_version": self.android_version,
            **self.extra,
        }


class DeviceManager:
    def __init__(self, config: dict) -> None:
        self.adb_path = str(config.get("adb_path", "adb"))
        self.poll_interval = float(config.get("poll_interval", 5))
        self.auto_discover = bool(config.get("auto_discover", True))
        self.allowed_devices: list[str] = list(config.get("allowed_devices") or [])
        self._devices: dict[str, DeviceInfo] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._running = False

    async def start_discovery(self) -> None:
        self._running = True
        logger.info("DeviceManager 发现循环已启用")

    async def stop(self) -> None:
        self._running = False

    async def monitor_loop(self) -> None:
        while self._running:
            try:
                await self._refresh_devices()
            except Exception:
                logger.exception("设备刷新失败")
            await asyncio.sleep(self.poll_interval)

    async def _adb_list_devices(self) -> list[str]:
        proc = await asyncio.create_subprocess_exec(
            self.adb_path,
            "devices",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        text = out.decode("utf-8", errors="replace")
        ids: list[str] = []
        for line in text.splitlines()[1:]:
            line = line.strip()
            if not line or "\t" not in line:
                continue
            dev_id, state = line.split("\t", 1)
            if state != "device":
                continue
            if self.allowed_devices and dev_id not in self.allowed_devices:
                continue
            ids.append(dev_id)
        return ids

    async def _refresh_devices(self) -> None:
        if not self.auto_discover:
            return
        found = await self._adb_list_devices()
        seen = set(found)
        for did in found:
            if did not in self._locks:
                self._locks[did] = asyncio.Lock()
            driver = ADBDriver(did, self.adb_path)
            try:
                info = await driver.get_device_info()
                self._devices[did] = DeviceInfo(
                    device_id=did,
                    model=str(info.get("model") or ""),
                    status="online",
                    battery=info.get("battery", ""),
                    screen_size=str(info.get("screen_size") or ""),
                    android_version=str(info.get("android_version") or ""),
                )
            except Exception as e:
                logger.warning("无法读取设备 %s 信息: %s", did, e)
                self._devices[did] = DeviceInfo(device_id=did, status="busy", model="unknown")
        for removed in list(self._devices.keys()):
            if removed not in seen:
                del self._devices[removed]
                self._locks.pop(removed, None)

    def get_device(self, device_id: str) -> DeviceInfo:
        if device_id not in self._devices:
            raise KeyError(device_id)
        return self._devices[device_id]

    def list_devices(self) -> list[DeviceInfo]:
        return list(self._devices.values())

    def list_device_dicts(self) -> list[dict]:
        return [d.to_dict() for d in self._devices.values()]

    @asynccontextmanager
    async def acquire_device(self, device_id: str) -> AsyncIterator[None]:
        if device_id not in self._locks:
            self._locks[device_id] = asyncio.Lock()
        async with self._locks[device_id]:
            yield
