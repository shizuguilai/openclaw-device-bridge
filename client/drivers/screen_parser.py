"""从 UI Automator XML 解析可点击节点（轻量实现）。"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any


def parse_ui_hierarchy(xml_text: str, *, max_elements: int = 50) -> list[dict[str, Any]]:
    """
    解析 accessibility / uiautomator dump XML，返回扁平元素列表。

    每个元素包含: tag, text, resource_id, bounds, clickable
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    out: list[dict[str, Any]] = []

    def bounds_to_tuple(b: str) -> tuple[int, int, int, int] | None:
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b.strip())
        if not m:
            return None
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))

    for el in root.iter():
        if len(out) >= max_elements:
            break
        attrib = el.attrib
        bounds = attrib.get("bounds") or ""
        bt = bounds_to_tuple(bounds)
        item = {
            "tag": el.tag,
            "text": attrib.get("text") or "",
            "resource_id": attrib.get("resource-id") or "",
            "bounds": bounds,
            "clickable": attrib.get("clickable", "false").lower() == "true",
        }
        if bt:
            cx = (bt[0] + bt[2]) // 2
            cy = (bt[1] + bt[3]) // 2
            item["center"] = {"x": cx, "y": cy}
        out.append(item)
    return out
