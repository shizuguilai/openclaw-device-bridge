"""日志初始化：主日志、按设备分文件、审计。"""

from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from client.core.config_manager import ConfigManager


def setup_logging(config_manager: ConfigManager | None = None, overrides: dict[str, Any] | None = None) -> None:
    """
    根据 ``bridge.yaml`` 的 logging 段配置根与常用子 logger。

    扩展能力：设备维度日志目录、审计日志文件（由业务侧 ``bridge.audit`` logger 写入）。
    """
    cfg: dict[str, Any] = dict(overrides or {})
    if config_manager is not None:
        cfg = {**config_manager.logging_config, **cfg}

    level_name = str(cfg.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = cfg.get(
        "format",
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s",
    )
    formatter = logging.Formatter(str(fmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    file_cfg = cfg.get("file") or {}
    if file_cfg.get("enabled", True):
        log_path = Path(str(file_cfg.get("path", "logs/bridge.log")))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        when = str(file_cfg.get("when", "H"))
        interval = int(file_cfg.get("interval", 1))
        backup = int(file_cfg.get("backup_count", 72))
        fh = TimedRotatingFileHandler(
            log_path,
            when=when,
            interval=interval,
            backupCount=backup,
            encoding="utf-8",
        )
        fh.setFormatter(formatter)
        root.addHandler(fh)

    console_cfg = cfg.get("console") or {}
    if console_cfg.get("enabled", True):
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        root.addHandler(ch)

    device_cfg = cfg.get("device_log") or {}
    if device_cfg.get("enabled", True):
        ddir = Path(str(device_cfg.get("dir", "logs/devices")))
        ddir.mkdir(parents=True, exist_ok=True)
        # 占位：具体设备 handler 由 DeviceManager 在发现设备时挂载
        logging.getLogger("bridge.device").setLevel(level)

    audit_cfg = cfg.get("audit_log") or {}
    if audit_cfg.get("enabled", True):
        ap = Path(str(audit_cfg.get("path", "logs/audit/operations.log")))
        ap.parent.mkdir(parents=True, exist_ok=True)
        ah = logging.FileHandler(ap, encoding="utf-8")
        ah.setFormatter(formatter)
        audit = logging.getLogger("bridge.audit")
        audit.handlers.clear()
        audit.addHandler(ah)
        audit.setLevel(logging.INFO)
        audit.propagate = False


def get_device_file_logger(device_id: str, log_dir: str | Path = "logs/devices") -> logging.Logger:
    """为单设备返回写入独立文件的 logger。"""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in device_id)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(f"bridge.device.{safe}")
    if not log.handlers:
        fh = logging.FileHandler(Path(log_dir) / f"{safe}.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        log.addHandler(fh)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


def audit_log(message: str, *, extra: dict[str, Any] | None = None) -> None:
    logging.getLogger("bridge.audit").info(message, extra=extra or {})
