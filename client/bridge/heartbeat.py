"""断线重连指数退避。"""

from __future__ import annotations

import asyncio
import random


class ReconnectBackoff:
    """指数退避 + 抖动，上限 ``max_delay``。"""

    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0) -> None:
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._attempt = 0

    def reset(self) -> None:
        self._attempt = 0

    async def sleep(self) -> None:
        delay = min(self.max_delay, self.base_delay * (2**self._attempt))
        self._attempt += 1
        jitter = delay * 0.1 * random.random()
        await asyncio.sleep(delay + jitter)
