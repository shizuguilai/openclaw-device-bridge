"""将远程 command 路由到 ADB / 单 Agent / DAG。"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from shared.protocol import build_result_message
from client.bridge.device_manager import DeviceManager
from client.core.config_manager import ConfigManager
from client.core.context import TaskContext
from client.core.dag_factory import DAGFactory
from client.core.exceptions import DeviceNotFoundError, ExecutionError, SecurityError
from client.core.executor import AsyncExecutor
from client.core.logger import audit_log
from client.drivers.adb_driver import ADBDriver

logger = logging.getLogger(__name__)


class TaskRouter:
    ROUTE_TABLE: dict[str, str] = {
        "tap": "direct",
        "swipe": "direct",
        "input_text": "direct",
        "key_event": "direct",
        "launch_app": "direct",
        "shell": "direct",
        "screenshot": "agent:ScreenCaptureAgent",
        "dump_ui": "agent:UIParseAgent",
        "device_info": "agent:DeviceInfoAgent",
        "screen_and_act": "dag:screen_and_act",
        "device_check": "dag:device_check",
        "app_automation": "dag:app_automation",
        "natural_language": "dag:nl_to_actions",
    }

    def __init__(self, config_manager: ConfigManager, device_manager: DeviceManager) -> None:
        self._cfg = config_manager
        self._dm = device_manager
        self._factory = DAGFactory()
        self._security = config_manager.security_config
        self._executor = AsyncExecutor(timeout=float(config_manager.executor_config.get("timeout", 30.0)))

    def _check_action_allowed(self, action: str) -> None:
        allowed = list(self._security.get("allowed_actions") or [])
        if not allowed:
            return
        if action not in allowed:
            raise SecurityError(f"操作 {action!r} 不在白名单内")

    def _check_blocked_package(self, package: str | None) -> None:
        if not package:
            return
        blocked = list(self._security.get("blocked_packages") or [])
        if package in blocked:
            raise SecurityError(f"包名 {package!r} 已被禁止")

    def _resolve_device_id(self, command: dict[str, Any]) -> str:
        did = str(command.get("device_id") or "")
        if did == "*":
            devices = self._dm.list_devices()
            if not devices:
                raise DeviceNotFoundError("没有可用设备")
            return devices[0].device_id
        if not did:
            raise DeviceNotFoundError("缺少 device_id")
        if did not in {d.device_id for d in self._dm.list_devices()}:
            raise DeviceNotFoundError(f"未知设备: {did}")
        return did

    async def _run_direct(self, driver: ADBDriver, command: dict[str, Any]) -> dict[str, Any]:
        action = str(command.get("action") or "")
        params = command.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        if action == "tap":
            await driver.tap(int(params["x"]), int(params["y"]))
            return {"action_result": "ok"}
        if action == "swipe":
            await driver.swipe(
                int(params["x1"]),
                int(params["y1"]),
                int(params["x2"]),
                int(params["y2"]),
                int(params.get("duration_ms", 300)),
            )
            return {"action_result": "ok"}
        if action == "input_text":
            await driver.input_text(str(params.get("text", "")))
            return {"action_result": "ok"}
        if action == "key_event":
            await driver.key_event(int(params["keycode"]))
            return {"action_result": "ok"}
        if action == "launch_app":
            pkg = str(params.get("package", ""))
            act = params.get("activity")
            self._check_blocked_package(pkg)
            await driver.launch_app(pkg, str(act) if act else None)
            return {"action_result": "ok", "package": pkg}
        if action == "shell":
            max_t = float(self._security.get("max_shell_timeout", 10))
            out = await asyncio.wait_for(
                driver.shell(str(params.get("command", ""))),
                timeout=max_t,
            )
            return {"shell_output": out}
        raise ExecutionError(f"未知 direct 动作: {action}")

    async def _run_single_agent(
        self,
        agent_type: str,
        ctx: TaskContext,
        config: dict[str, Any] | None = None,
    ) -> Any:
        cfg = dict(config or {})
        dag = self._factory.load_dag_from_dict(
            {
                "name": "_single",
                "agents": [{"name": "only", "type": agent_type, "depends_on": [], "config": cfg}],
            }
        )
        agents = self._factory.build_agents(dag)
        only = agents["only"]
        return await only.run(ctx)

    async def _run_dag(self, dag_name: str, ctx: TaskContext) -> TaskContext:
        path = self._cfg.dag_dir() / f"{dag_name}.yaml"
        if not path.is_file():
            raise ExecutionError(f"DAG 文件不存在: {path}")
        dag = self._factory.load_dag_from_file(path)
        agents = self._factory.build_agents(dag)
        return await self._executor.run(dag, agents, ctx)

    async def route(self, command: dict[str, Any], device_manager: DeviceManager) -> dict[str, Any]:
        """供 RelayConnector 调用，返回完整 result 消息 dict。"""
        _ = device_manager
        cmd_id = str(command.get("id") or "")
        t0 = time.perf_counter()
        action = str(command.get("action") or "")
        device_id = ""
        try:
            self._check_action_allowed(action)
            device_id = self._resolve_device_id(command)
            adb_path = self._cfg.device_config.get("adb_path", "adb")
            driver = ADBDriver(device_id, str(adb_path))
            audit_log(
                f"command action={action} device={device_id}",
                extra={"action": action, "device_id": device_id, "command_id": cmd_id},
            )
            async with self._dm.acquire_device(device_id):
                route = self.ROUTE_TABLE.get(action, "")
                if route == "direct":
                    data = await self._run_direct(driver, command)
                elif route.startswith("agent:"):
                    agent_type = route.split(":", 1)[1]
                    ctx = TaskContext({"device_id": device_id, "command": command, "adb": driver})
                    raw_params = command.get("params")
                    cmd_params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
                    if agent_type == "ScreenCaptureAgent":
                        agent_cfg = {**self._cfg.screenshot_config, **cmd_params}
                    else:
                        agent_cfg = cmd_params
                    data = await self._run_single_agent(agent_type, ctx, agent_cfg)
                elif route.startswith("dag:") or command.get("dag_name"):
                    if command.get("dag_name"):
                        dag_name = str(command["dag_name"])
                    elif route.startswith("dag:"):
                        dag_name = route.split(":", 1)[1]
                    else:
                        dag_name = action
                    ctx = TaskContext({"device_id": device_id, "command": command, "adb": driver})
                    final_ctx = await self._run_dag(dag_name, ctx)
                    data = {"outputs": final_ctx.as_dict().get("outputs", {}), "ctx": final_ctx.as_dict()}
                else:
                    raise ExecutionError(f"无法路由动作: {action!r}")
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.exception("指令执行失败")
            return build_result_message(
                command_id=cmd_id,
                device_id=device_id or "*",
                status="error",
                data={"error": str(e)},
                execution_time_ms=elapsed_ms,
            )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if isinstance(data, dict) and "screenshot_base64" in data:
            wrapped = dict(data)
        else:
            wrapped = {"action_result": "ok", "payload": data}
        return build_result_message(
            command_id=cmd_id,
            device_id=device_id,
            status="success",
            data=wrapped if isinstance(wrapped, dict) else {"result": wrapped},
            execution_time_ms=elapsed_ms,
        )
