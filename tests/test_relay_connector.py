"""RelayConnector 配置与退避。"""
from __future__ import annotations

import pytest

from client.bridge.heartbeat import ReconnectBackoff
from client.bridge.relay_connector import RelayConnector


def test_relay_connector_config() -> None:
    c = RelayConnector(
        {
            "relay_url": "ws://127.0.0.1:8091",
            "auth_token": "abc",
            "bridge_id": "b1",
        }
    )
    assert c.bridge_id == "b1"
    assert c.heartbeat_interval == 30


@pytest.mark.asyncio
async def test_reconnect_backoff_monotonic_attempt() -> None:
    b = ReconnectBackoff(0.01, 0.05)
    await b.sleep()
    assert b._attempt == 1
