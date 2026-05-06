"""Agent 基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from client.core.context import TaskContext


class BaseAgent(ABC):
    """所有业务 Agent 的抽象基类。"""

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}

    @abstractmethod
    async def run(self, ctx: TaskContext) -> Any:
        """执行本节点逻辑并写回 ctx（约定）。"""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
