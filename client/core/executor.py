"""异步 DAG 执行器。"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from client.core.agent import BaseAgent
from client.core.context import TaskContext
from client.core.dag import DAG
from client.core.exceptions import ExecutionError


class AsyncExecutor:
    """按拓扑层并行执行 Agent。"""

    def __init__(self, timeout: float | None = None) -> None:
        self.timeout = timeout

    async def run(self, dag: DAG, agents: dict[str, BaseAgent], ctx: TaskContext) -> TaskContext:
        layers = dag.layers()
        for layer in layers:
            async def _run_one(name: str) -> tuple[str, Any, float]:
                t0 = time.perf_counter()
                agent = agents[name]
                try:
                    if self.timeout is not None:
                        result = await asyncio.wait_for(agent.run(ctx), timeout=self.timeout)
                    else:
                        result = await agent.run(ctx)
                except Exception as e:
                    elapsed_ms = int((time.perf_counter() - t0) * 1000)
                    raise ExecutionError(f"Agent {name!r} 失败 ({elapsed_ms}ms): {e}") from e
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                return name, result, float(elapsed_ms)

            tasks = [_run_one(n) for n in layer]
            results = await asyncio.gather(*tasks)
            for name, result, elapsed_ms in results:
                ctx.set(f"outputs.{name}", result)
                ctx.set(f"meta.{name}.execution_time_ms", elapsed_ms)
        return ctx
