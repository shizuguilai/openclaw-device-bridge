"""
OpenClaw Device Control — 通过 Web Console HTTP API 调用 Relay。

部署：将本目录复制到 OpenClaw skills 路径，并配置环境变量。
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_BASE = os.environ.get("OPENCLAW_RELAY_CONSOLE_URL", "http://127.0.0.1:8092").rstrip("/")
_TOKEN = os.environ.get(
    "OPENCLAW_RELAY_CONSOLE_TOKEN",
    os.environ.get("RELAY_CONSOLE_TOKEN", os.environ.get("RELAY_AUTH_TOKEN", "dev-change-me")),
)


def _headers() -> dict[str, str]:
    return {"X-Console-Token": _TOKEN, "Content-Type": "application/json"}


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{_BASE}{path}", json=body, headers=_headers())
        r.raise_for_status()
        return r.json()


def _get(path: str) -> dict[str, Any]:
    with httpx.Client(timeout=60.0) as client:
        r = client.get(f"{_BASE}{path}", headers=_headers())
        r.raise_for_status()
        return r.json()


def device_list(bridge_id: str | None = None) -> dict[str, Any]:
    q = f"?bridge_id={bridge_id}" if bridge_id else ""
    return _get(f"/api/devices{q}")


def device_screenshot(device_id: str, bridge_id: str | None = None) -> dict[str, Any]:
    q = f"?bridge_id={bridge_id}" if bridge_id else ""
    return _get(f"/api/screenshot/{device_id}{q}")


def device_tap(device_id: str, x: int, y: int, bridge_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"device_id": device_id, "action": "tap", "params": {"x": x, "y": y}}
    if bridge_id:
        body["bridge_id"] = bridge_id
    return _post("/api/command", body)


def device_swipe(
    device_id: str,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    bridge_id: str | None = None,
    duration_ms: int = 300,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "device_id": device_id,
        "action": "swipe",
        "params": {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration_ms": duration_ms},
    }
    if bridge_id:
        body["bridge_id"] = bridge_id
    return _post("/api/command", body)


def device_input(device_id: str, text: str, bridge_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"device_id": device_id, "action": "input_text", "params": {"text": text}}
    if bridge_id:
        body["bridge_id"] = bridge_id
    return _post("/api/command", body)


def device_launch_app(
    device_id: str,
    package: str,
    activity: str | None = None,
    bridge_id: str | None = None,
) -> dict[str, Any]:
    p: dict[str, Any] = {"package": package}
    if activity:
        p["activity"] = activity
    body: dict[str, Any] = {"device_id": device_id, "action": "launch_app", "params": p}
    if bridge_id:
        body["bridge_id"] = bridge_id
    return _post("/api/command", body)


def device_ui_dump(device_id: str, bridge_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"device_id": device_id, "action": "dump_ui", "params": {}}
    if bridge_id:
        body["bridge_id"] = bridge_id
    return _post("/api/command", body)


def device_run_dag(
    device_id: str,
    dag_name: str,
    bridge_id: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "device_id": device_id,
        "dag_name": dag_name,
        "params": extra_params or {},
    }
    if bridge_id:
        body["bridge_id"] = bridge_id
    return _post("/api/dag/run", body)
