"""Relay Server + Web Console 统一入口。"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from relay.config import load_relay_config, setup_logging
from relay.relay_server import BridgeRelayServer
from relay.web_console.app import WebConsole
from shared.diagnostics import apply_verbose_logging_if_diag, log_relay_banner

logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_relay_config()
    setup_logging()
    apply_verbose_logging_if_diag()
    log_relay_banner(logger, config)
    relay = BridgeRelayServer(config)
    wc_cfg = dict(config.get("web_console") or {})
    wc_cfg.setdefault("auth_token", config["auth_token"])
    web_console = WebConsole(relay, wc_cfg)
    await asyncio.gather(
        relay.start(),
        web_console.start(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
