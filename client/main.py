"""Bridge Client 启动入口。"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client.bridge.device_manager import DeviceManager
from client.bridge.relay_connector import RelayConnector
from client.bridge.task_router import TaskRouter
from client.core.config_manager import ConfigManager
from client.core.logger import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    config_manager = ConfigManager()
    config_manager.load_bridge_config()
    setup_logging(config_manager)

    device_manager = DeviceManager(config_manager.device_config)
    task_router = TaskRouter(config_manager, device_manager)
    relay_connector = RelayConnector(config_manager.relay_config)

    async def handle_command(cmd: dict) -> dict:
        return await task_router.route(cmd, device_manager)

    relay_connector.on_command(handle_command)

    await device_manager.start_discovery()
    try:
        await asyncio.gather(
            relay_connector.connect(),
            relay_connector.heartbeat_loop(),
            relay_connector.status_report_loop(device_manager),
            device_manager.monitor_loop(),
        )
    finally:
        relay_connector.stop()
        await device_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
