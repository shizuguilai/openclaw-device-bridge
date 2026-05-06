"""Console 登录：Header ``X-Console-Token`` 或 ``Authorization: Bearer``。"""

from __future__ import annotations

from fastapi import Header, HTTPException

MISSING = object()


def verify_console_token(expected_token: str):
    """返回依赖函数 ``dep``，校验请求 token。"""

    async def dep(
        x_console_token: str | None = Header(default=None, alias="X-Console-Token"),
        authorization: str | None = Header(default=None),
    ) -> None:
        token: str | None = x_console_token
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        if not token or token != expected_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

    return dep
