"""从 YAML 构建 DAG 与 Agent 实例。"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Type

import yaml

from client.core.agent import BaseAgent
from client.core.dag import DAG, DAGNode
from client.core.exceptions import ConfigError, DAGError


class DAGFactory:
    """读取 DAG YAML，产出 DAG 与可执行 Agent 映射。"""

    def __init__(self, agents_module: str = "client.agents") -> None:
        self._agents_module = agents_module

    def load_dag_from_file(self, path: str | Path) -> DAG:
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"DAG 文件不存在: {path}")
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return self._parse_dag_dict(raw, source=str(path))

    def load_dag_from_dict(self, data: dict[str, Any]) -> DAG:
        return self._parse_dag_dict(data, source="<dict>")

    def _parse_dag_dict(self, raw: dict[str, Any], source: str) -> DAG:
        if not isinstance(raw, dict):
            raise DAGError(f"{source}: 根必须为 mapping")
        name = raw.get("name")
        if not name:
            raise DAGError(f"{source}: 缺少 name")
        executor = raw.get("executor", "AsyncExecutor")
        agents_raw = raw.get("agents")
        if not isinstance(agents_raw, list):
            raise DAGError(f"{source}: agents 必须为列表")
        nodes: dict[str, DAGNode] = {}
        for item in agents_raw:
            if not isinstance(item, dict):
                raise DAGError(f"{source}: agent 项必须为 mapping")
            n = item.get("name")
            if not n:
                raise DAGError(f"{source}: agent 缺少 name")
            atype = item.get("type")
            if not atype:
                raise DAGError(f"{source}: agent {n!r} 缺少 type")
            nodes[n] = DAGNode(
                name=n,
                agent_type=atype,
                depends_on=list(item.get("depends_on") or []),
                config=dict(item.get("config") or {}),
            )
        return DAG(name=str(name), executor_name=str(executor), nodes=nodes)

    def resolve_agent_class(self, agent_type: str) -> Type[BaseAgent]:
        """将 YAML 中的 type 解析为 BaseAgent 子类。"""
        if "." in agent_type:
            mod_name, _, cls_name = agent_type.rpartition(".")
            mod = importlib.import_module(mod_name)
        else:
            mod = importlib.import_module(self._agents_module)
            cls_name = agent_type
        cls = getattr(mod, cls_name, None)
        if cls is None or not isinstance(cls, type) or not issubclass(cls, BaseAgent):
            raise ConfigError(f"无法解析 Agent 类型: {agent_type!r}")
        return cls

    def build_agents(self, dag: DAG) -> dict[str, BaseAgent]:
        agents: dict[str, BaseAgent] = {}
        for name, node in dag.nodes.items():
            cls = self.resolve_agent_class(node.agent_type)
            agents[name] = cls(name=name, config=node.config)
        return agents
