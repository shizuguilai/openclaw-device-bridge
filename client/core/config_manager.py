"""Bridge Client 配置加载与管理。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from client.core.exceptions import ConfigError
from client.core.utils import expand_env_vars


class ConfigManager:
    """加载 ``bridge.yaml``，提供分段配置访问。"""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._config_path = Path(config_path) if config_path else None
        self._raw: dict[str, Any] = {}

    def load_bridge_config(self, path: str | Path | None = None) -> None:
        cfg_path = Path(path) if path else self._config_path
        if cfg_path is None:
            root = Path(__file__).resolve().parents[2]
            cfg_path = root / "client" / "config" / "bridge.yaml"
        if not cfg_path.is_file():
            raise ConfigError(f"找不到 Bridge 配置: {cfg_path}")
        self._config_path = cfg_path
        with cfg_path.open(encoding="utf-8") as f:
            self._raw = yaml.safe_load(f) or {}
        self._raw = expand_env_vars(self._raw)

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    @property
    def bridge_id(self) -> str:
        b = self._raw.get("bridge") or {}
        return str(b.get("id") or "bridge-default")

    @property
    def bridge_name(self) -> str:
        b = self._raw.get("bridge") or {}
        return str(b.get("name") or self.bridge_id)

    @property
    def relay_config(self) -> dict[str, Any]:
        r = self._raw.get("relay") or {}
        url = r.get("url")
        if not url:
            raise ConfigError("relay.url 未配置")
        token = r.get("auth_token")
        if not token:
            raise ConfigError("relay.auth_token 未配置")
        return {
            "relay_url": str(url),
            "auth_token": str(token),
            "bridge_id": self.bridge_id,
            "heartbeat_interval": int(r.get("heartbeat_interval", 30)),
            "reconnect_max_delay": float(r.get("reconnect_max_delay", 60)),
            "reconnect_base_delay": float(r.get("reconnect_base_delay", 1)),
        }

    @property
    def device_config(self) -> dict[str, Any]:
        d = self._raw.get("devices") or {}
        return {
            "adb_path": str(d.get("adb_path", "adb")),
            "poll_interval": float(d.get("poll_interval", 5)),
            "auto_discover": bool(d.get("auto_discover", True)),
            "allowed_devices": list(d.get("allowed_devices") or []),
        }

    @property
    def executor_config(self) -> dict[str, Any]:
        e = self._raw.get("executor") or {}
        return {
            "default": str(e.get("default", "AsyncExecutor")),
            "timeout": float(e.get("timeout", 30.0)),
            "max_concurrent_tasks": int(e.get("max_concurrent_tasks", 5)),
        }

    @property
    def logging_config(self) -> dict[str, Any]:
        return dict(self._raw.get("logging") or {})

    @property
    def security_config(self) -> dict[str, Any]:
        return dict(self._raw.get("security") or {})

    @property
    def config_dir(self) -> Path:
        if self._config_path is None:
            return Path(__file__).resolve().parents[1] / "config"
        return self._config_path.parent

    def agents_yaml_path(self) -> Path:
        return self.config_dir / "agents" / "agents.yaml"

    def dag_dir(self) -> Path:
        return self.config_dir / "dags"
