from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppSettings:
    geometry: str = ""
    always_top: bool = False
    favorite_ids: list[str] | None = None
    recent_ids: list[str] | None = None
    param_values: dict[str, dict[str, str]] = field(default_factory=dict)
    details_panel_width: int = 360
    details_panel_height: int = 520
    collapsed_detail_sections: list[str] | None = field(default_factory=lambda: ["Source", "Tool"])
    outliner_column_widths: dict[str, int] = field(default_factory=dict)
    ai_provider: str = "Custom OpenAI-Compatible"
    ai_base_url: str = ""
    ai_model: str = ""
    ai_api_key_env: str = "EDITORBINDER_API_KEY"
    ai_timeout_seconds: int = 45
    ai_temperature: float = 0.2
    ai_max_tokens: int = 3000

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppSettings":
        return cls(
            geometry=str(raw.get("geometry") or ""),
            always_top=bool(raw.get("always_top", False)),
            favorite_ids=_string_list(raw.get("favorite_ids")),
            recent_ids=_string_list(raw.get("recent_ids")),
            param_values=_param_values(raw.get("param_values")),
            details_panel_width=_positive_int(raw.get("details_panel_width"), default=360),
            details_panel_height=_positive_int(raw.get("details_panel_height"), default=520),
            collapsed_detail_sections=_string_list(raw.get("collapsed_detail_sections"), default=["Source", "Tool"]),
            outliner_column_widths=_positive_int_map(raw.get("outliner_column_widths")),
            ai_provider=str(raw.get("ai_provider") or "Custom OpenAI-Compatible"),
            ai_base_url=str(raw.get("ai_base_url") or ""),
            ai_model=str(raw.get("ai_model") or ""),
            ai_api_key_env=_env_name(raw.get("ai_api_key_env"), default="EDITORBINDER_API_KEY"),
            ai_timeout_seconds=_positive_int(raw.get("ai_timeout_seconds"), default=45),
            ai_temperature=_bounded_float(raw.get("ai_temperature"), default=0.2, minimum=0.0, maximum=2.0),
            ai_max_tokens=_positive_int(raw.get("ai_max_tokens"), default=3000),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "geometry": self.geometry,
            "always_top": self.always_top,
            "favorite_ids": list(self.favorite_ids or []),
            "recent_ids": list(self.recent_ids or []),
            "param_values": {
                str(tool_id): {str(name): str(value) for name, value in values.items()}
                for tool_id, values in (self.param_values or {}).items()
                if isinstance(values, dict)
            },
            "details_panel_width": int(self.details_panel_width or 360),
            "details_panel_height": int(self.details_panel_height or 520),
            "collapsed_detail_sections": list(self.collapsed_detail_sections or []),
            "outliner_column_widths": dict(self.outliner_column_widths or {}),
            "ai_provider": str(self.ai_provider or "Custom OpenAI-Compatible"),
            "ai_base_url": str(self.ai_base_url or ""),
            "ai_model": str(self.ai_model or ""),
            "ai_api_key_env": _env_name(self.ai_api_key_env, default="EDITORBINDER_API_KEY"),
            "ai_timeout_seconds": int(self.ai_timeout_seconds or 45),
            "ai_temperature": float(self.ai_temperature if self.ai_temperature is not None else 0.2),
            "ai_max_tokens": int(self.ai_max_tokens or 3000),
        }


class AppSettingsStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings()
        if not isinstance(payload, dict):
            return AppSettings()
        return AppSettings.from_dict(payload)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        temp_path.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
        temp_path.replace(self.path)


def resolve_default_settings_path() -> Path:
    from .storage import resolve_app_data_dir

    return resolve_app_data_dir() / "settings.json"


def _string_list(value: Any, default: list[str] | None = None) -> list[str]:
    if not isinstance(value, list):
        return list(default or [])
    return [str(item) for item in value if str(item).strip()]


def _param_values(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for raw_tool_id, raw_values in value.items():
        if not isinstance(raw_values, dict):
            continue
        tool_id = str(raw_tool_id).strip()
        if not tool_id:
            continue
        result[tool_id] = {
            str(name): str(raw_value)
            for name, raw_value in raw_values.items()
            if str(name).strip()
        }
    return result


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _positive_int_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            continue
        try:
            number = int(raw_value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            result[key] = number
    return result


def _env_name(value: Any, *, default: str) -> str:
    name = str(value or "").strip()
    if not name:
        return default
    return "".join(char for char in name if char.isalnum() or char == "_") or default


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number < minimum or number > maximum:
        return default
    return number
