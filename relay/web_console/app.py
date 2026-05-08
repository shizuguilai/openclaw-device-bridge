"""FastAPI：HTTP API + WebSocket 推送 + 静态资源。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from relay.relay_server import BridgeRelayServer
from relay.web_console.auth import verify_console_token

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent / "static"


class WebConsole:
    """
    Web 控制台：设备列表、下发指令、DAG、历史；WebSocket 订阅 Relay 事件总线。
    """

    def __init__(self, relay_server: BridgeRelayServer, config: dict[str, Any]) -> None:
        self.relay = relay_server
        self.host = str(config.get("host", "0.0.0.0"))
        self.port = int(config.get("port", 8092))
        self.auth_token = str(config.get("auth_token", ""))
        self._app = self._build_app()

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="OpenClaw Device Bridge Console", version="1.0.0")
        auth = verify_console_token(self.auth_token)

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(_STATIC_DIR / "index.html")

        @app.get("/api/bridges", dependencies=[Depends(auth)])
        async def api_bridges() -> dict[str, Any]:
            return {"bridges": self.relay.list_bridges()}

        @app.get("/api/devices", dependencies=[Depends(auth)])
        async def api_devices(bridge_id: str | None = None) -> dict[str, Any]:
            return {"devices": self.relay.list_devices(bridge_id)}

        @app.get("/api/devices/{device_id}", dependencies=[Depends(auth)])
        async def api_device_detail(device_id: str) -> dict[str, Any]:
            for d in self.relay.list_devices():
                if d.get("device_id") == device_id:
                    return {"device": d}
            raise HTTPException(status_code=404, detail="not found")

        @app.post("/api/command", dependencies=[Depends(auth)])
        async def api_command(body: dict[str, Any]) -> dict[str, Any]:
            bridge_id = body.get("bridge_id")
            cmd = {k: v for k, v in body.items() if k != "bridge_id" and v is not None}
            result = await self.relay.send_command(bridge_id, cmd)
            return {"result": result}

        @app.get("/api/screenshot/{device_id}", dependencies=[Depends(auth)])
        async def api_screenshot(
            device_id: str,
            bridge_id: str | None = None,
            image_format: str = Query("png", alias="format", description="png | jpeg | webp"),
            quality: int = Query(80, ge=1, le=100),
            max_width: int = Query(0, ge=0, description=">0 时按宽边缩放"),
            max_height: int = Query(0, ge=0, description=">0 时按高边缩放"),
        ) -> dict[str, Any]:
            cmd = {
                "type": "command",
                "device_id": device_id,
                "action": "screenshot",
                "params": {
                    "format": image_format,
                    "quality": quality,
                    "max_width": max_width,
                    "max_height": max_height,
                },
                "timeout_ms": 30000,
            }
            return {"result": await self.relay.send_command(bridge_id, cmd)}

        @app.post("/api/dag/run", dependencies=[Depends(auth)])
        async def api_dag_run(body: dict[str, Any]) -> dict[str, Any]:
            device_id = body["device_id"]
            dag_name = body["dag_name"]
            bridge_id = body.get("bridge_id")
            cmd = {
                "type": "command",
                "device_id": device_id,
                "action": dag_name,
                "dag_name": dag_name,
                "params": body.get("params") or {},
                "timeout_ms": int(body.get("timeout_ms", 120000)),
            }
            return {"result": await self.relay.send_command(bridge_id, cmd)}

        @app.get("/api/history", dependencies=[Depends(auth)])
        async def api_history(limit: int = 50) -> dict[str, Any]:
            return {"history": self.relay.command_history(limit)}

        @app.websocket("/ws/console")
        async def ws_console(ws: WebSocket) -> None:
            await ws.accept()
            try:
                first = await ws.receive_text()
                payload = json.loads(first)
                if payload.get("token") != self.auth_token:
                    await ws.close(code=4401)
                    return
            except Exception:
                await ws.close(code=4400)
                return
            q = self.relay.console_events.subscribe()
            try:
                while True:
                    msg = await q.get()
                    await ws.send_text(json.dumps(msg, ensure_ascii=False))
            except WebSocketDisconnect:
                pass
            finally:
                self.relay.console_events.unsubscribe(q)

        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
        return app

    @property
    def app(self) -> FastAPI:
        return self._app

    async def start(self) -> None:
        cfg = uvicorn.Config(self._app, host=self.host, port=self.port, log_level="info")
        server = uvicorn.Server(cfg)
        logger.info("Web Console 监听 http://%s:%s", self.host, self.port)
        await server.serve()
