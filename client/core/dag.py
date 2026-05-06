"""DAG 定义与拓扑校验。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from client.core.exceptions import DAGError


@dataclass
class DAGNode:
    name: str
    agent_type: str
    depends_on: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class DAG:
    name: str
    executor_name: str
    nodes: dict[str, DAGNode]

    def layers(self) -> list[list[str]]:
        """按依赖拓扑分层；同层可并行执行。"""
        remaining = set(self.nodes.keys())
        assigned: set[str] = set()
        out: list[list[str]] = []
        while remaining:
            layer: list[str] = []
            for name in sorted(remaining):
                node = self.nodes[name]
                deps = set(node.depends_on)
                if not deps.issubset(assigned):
                    continue
                if not deps.issubset(self.nodes.keys()):
                    missing = deps - self.nodes.keys()
                    raise DAGError(f"节点 {name!r} 依赖未知节点: {missing}")
                layer.append(name)
            if not layer:
                raise DAGError(f"DAG {self.name!r} 存在环或无法解析的依赖")
            out.append(layer)
            for n in layer:
                remaining.remove(n)
                assigned.add(n)
        return out
