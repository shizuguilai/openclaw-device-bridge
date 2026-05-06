"""Relay 会话与 history。"""

import asyncio

import pytest

from relay.relay_server import BridgeRelayServer
from relay.session_manager import SessionManager
from shared.protocol import build_result_message


@pytest.mark.asyncio
async def test_session_manager_pending_resolve() -> None:
    sm = SessionManager()
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    sm.register_pending("c1", fut)
    ok = sm.resolve_pending(
        "c1",
        build_result_message(command_id="c1", device_id="d1", status="success", data={}),
    )
    assert ok is True
    assert fut.done()
    assert fut.result()["status"] == "success"


def test_relay_command_history() -> None:
    cfg = {"host": "127.0.0.1", "port": 0, "auth_token": "t"}
    relay = BridgeRelayServer(cfg)
    relay._sessions.record_history({"kind": "test"})
    assert relay.command_history(10)[0]["kind"] == "test"


def test_list_bridges_empty() -> None:
    cfg = {"host": "127.0.0.1", "port": 0, "auth_token": "t"}
    relay = BridgeRelayServer(cfg)
    assert relay.list_bridges() == []
