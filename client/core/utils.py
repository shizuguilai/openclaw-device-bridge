"""通用工具函数。"""

from __future__ import annotations

import os
import re
from typing import Any


_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def expand_env_vars(value: Any) -> Any:
    """递归展开字符串中的 ``${VAR}`` 为环境变量。"""
    if isinstance(value, str):

        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            return os.environ.get(key, "")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [expand_env_vars(v) for v in value]
    if isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    return value


def deep_get(d: dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
