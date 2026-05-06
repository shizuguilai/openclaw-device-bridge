"""设备驱动基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseDriver(ABC):
    """所有设备驱动的抽象接口。"""

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id

    @abstractmethod
    async def screenshot(self) -> bytes:
        """截取屏幕 PNG 字节。"""

    @abstractmethod
    async def get_device_info(self) -> dict[str, Any]:
        """返回设备元信息 dict。"""
