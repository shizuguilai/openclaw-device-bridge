"""
任务上下文：纯 dict 语义，无 Protobuf。

Agent / Executor 通过键读写共享数据；约定可使用点分层键，如 ``screen_capture`` 节点输出存
``outputs.screen_capture``。
"""

from __future__ import annotations

import copy
from typing import Any


class TaskContext:
    """基于嵌套 dict 的可变上下文，支持浅拷贝快照。"""

    __slots__ = ("_root",)

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._root: dict[str, Any] = copy.deepcopy(initial) if initial else {}

    def get(self, key: str, default: Any = None) -> Any:
        cur: Any = self._root
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, key: str, value: Any) -> None:
        parts = key.split(".")
        cur = self._root
        for p in parts[:-1]:
            nxt = cur.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[p] = nxt
            cur = nxt
        cur[parts[-1]] = value

    def merge(self, other: dict[str, Any]) -> None:
        """浅合并到根 dict（顶层键）。"""
        self._root.update(other)

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._root)

    def branch(self) -> TaskContext:
        """返回独立深拷贝，用于子任务隔离。"""
        return TaskContext(self._root)
