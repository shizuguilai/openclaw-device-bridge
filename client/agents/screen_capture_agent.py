"""截屏 Agent（Bridge 端压缩后再发往 Relay）。"""

from __future__ import annotations

import base64
import logging
from io import BytesIO
from typing import Any

from client.core.agent import BaseAgent
from client.core.context import TaskContext
from client.core.exceptions import ExecutionError
from client.drivers.adb_driver import ADBDriver

logger = logging.getLogger(__name__)

try:
    from PIL import Image

    _HAS_PIL = True
except ImportError:
    Image = None  # type: ignore[misc, assignment]
    _HAS_PIL = False


def _clamp_quality(q: int) -> int:
    return max(1, min(100, int(q)))


def _resize_if_needed(
    im: Any,
    max_width: int,
    max_height: int,
) -> Any:
    w, h = im.size
    if max_width <= 0 and max_height <= 0:
        return im
    scale = 1.0
    if max_width > 0:
        scale = min(scale, max_width / float(w))
    if max_height > 0:
        scale = min(scale, max_height / float(h))
    if scale >= 1.0:
        return im
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return im.resize((nw, nh), Image.Resampling.LANCZOS)


def _prepare_rgba_for_lossy(im: Any) -> Any:
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
        return bg
    if im.mode == "P":
        return im.convert("RGBA").convert("RGB")
    if im.mode != "RGB":
        return im.convert("RGB")
    return im


def encode_screenshot(png_bytes: bytes, config: dict[str, Any]) -> dict[str, Any]:
    """
    将 ADB 返回的 PNG 字节编码为可选 JPEG/WebP/PNG，支持按最大边缩放。
    失败时退回原始 PNG Base64。
    """
    fmt = str(config.get("format", "png")).lower().strip()
    quality = _clamp_quality(int(config.get("quality", 80)))
    max_width = int(config.get("max_width", 0))
    max_height = int(config.get("max_height", 0))

    if not _HAS_PIL:
        logger.warning("未安装 Pillow，截图将以原始 PNG 发送。请 pip install pillow")
        return {
            "format": "png",
            "mime_type": "image/png",
            "screenshot_base64": base64.b64encode(png_bytes).decode("ascii"),
            "bytes_length": len(png_bytes),
            "quality": quality,
            "pillow": False,
        }

    try:
        im = Image.open(BytesIO(png_bytes))
        im.load()
        im = _resize_if_needed(im, max_width, max_height)
        buf = BytesIO()
        if fmt in ("jpg", "jpeg"):
            rgb = _prepare_rgba_for_lossy(im)
            rgb.save(buf, format="JPEG", quality=quality, optimize=True)
            mime = "image/jpeg"
            out_fmt = "jpeg"
        elif fmt == "webp":
            rgb = _prepare_rgba_for_lossy(im)
            rgb.save(buf, format="WEBP", quality=quality, method=4)
            mime = "image/webp"
            out_fmt = "webp"
        else:
            im.save(buf, format="PNG", compress_level=png_level, optimize=True)
            mime = "image/png"
            out_fmt = "png"
        raw = buf.getvalue()
        w, h = im.size
        return {
            "format": out_fmt,
            "mime_type": mime,
            "screenshot_base64": base64.b64encode(raw).decode("ascii"),
            "bytes_length": len(raw),
            "width": w,
            "height": h,
            "quality": quality,
            "pillow": True,
        }
    except Exception as e:
        logger.warning("截图压缩失败，使用原始 PNG: %s", e, exc_info=True)
        return {
            "format": "png",
            "mime_type": "image/png",
            "screenshot_base64": base64.b64encode(png_bytes).decode("ascii"),
            "bytes_length": len(png_bytes),
            "quality": quality,
            "pillow": False,
            "encode_error": str(e),
        }


class ScreenCaptureAgent(BaseAgent):
    async def run(self, ctx: TaskContext) -> dict[str, Any]:
        driver = ctx.get("adb")
        if not isinstance(driver, ADBDriver):
            raise ExecutionError("ScreenCaptureAgent 需要 ctx['adb'] 为 ADBDriver")
        png = await driver.screenshot()
        out = encode_screenshot(png, self.config)
        out["source_bytes_length"] = len(png)
        return out
