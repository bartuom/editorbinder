from __future__ import annotations

import json
import re

from .models import Tool


def write_tools_export(path: str, tools: list[Tool]) -> None:
    payload = {
        "version": 1,
        "tools": [tool.to_dict() for tool in tools],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return cleaned or "tool"
