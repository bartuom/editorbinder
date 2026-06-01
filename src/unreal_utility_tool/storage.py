from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import Tool

RELEASE_SEED_FILENAME = "tools.json"
WORKING_LIBRARY_FILENAME = "user_tools.json"


@dataclass(frozen=True, slots=True)
class BackupInfo:
    path: Path
    filename: str
    modified_at: str
    tool_count: int
    error: str = ""


@dataclass(frozen=True, slots=True)
class RestoreResult:
    restored_tools: list[Tool]
    safety_backup_path: Path | None


@dataclass(frozen=True, slots=True)
class BundledPresetRefreshResult:
    refreshed_tools: list[Tool]
    added_count: int
    updated_count: int
    unchanged_count: int


class ToolLibraryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.last_load_error = ""

    def load_tools(self) -> list[Tool]:
        self.last_load_error = ""
        if not self.path.exists():
            return []

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            raw_tools = self._extract_tool_payload(payload)
            return [Tool.from_dict(raw_tool) for raw_tool in raw_tools]
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            backup_path = self._backup_corrupt_file()
            self.last_load_error = f"Could not load tool library: {exc}. Backup: {backup_path}"
            return []

    def save_tools(self, tools: list[Tool]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._backup_existing_file()
        payload = {
            "version": 1,
            "tools": [tool.to_dict() for tool in tools],
        }
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def create_timestamped_backup(self) -> Path:
        if not self.path.exists():
            return self.path
        backup_path = self._unique_backup_path("backup")
        shutil.copy2(self.path, backup_path)
        return backup_path

    def list_backups(self) -> list[BackupInfo]:
        candidates = self._backup_candidates()
        backups: list[BackupInfo] = []
        for path in candidates:
            try:
                tools = self._load_tools_from_path(path)
                tool_count = len(tools)
                error = ""
            except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
                tool_count = 0
                error = str(exc)
            backups.append(
                BackupInfo(
                    path=path,
                    filename=path.name,
                    modified_at=self._format_mtime(path),
                    tool_count=tool_count,
                    error=error,
                )
            )
        return sorted(backups, key=lambda backup: backup.path.stat().st_mtime, reverse=True)

    def restore_backup(self, backup_path: str | Path) -> RestoreResult:
        source_path = Path(backup_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Backup does not exist: {source_path}")
        if source_path.resolve() not in {path.resolve() for path in self._backup_candidates()}:
            raise ValueError("Selected file is not a known backup for this library.")

        restored_tools = self._load_tools_from_path(source_path)
        safety_backup_path = self.create_timestamped_backup() if self.path.exists() else None
        self.save_tools(restored_tools)
        return RestoreResult(restored_tools=restored_tools, safety_backup_path=safety_backup_path)

    def _extract_tool_payload(self, payload: object) -> list[dict]:
        if isinstance(payload, dict):
            raw_tools = payload.get("tools", [])
        elif isinstance(payload, list):
            raw_tools = payload
        else:
            raise ValueError("Tool library must be a JSON object or list.")

        if not isinstance(raw_tools, list):
            raise ValueError("Tool library 'tools' field must be a list.")
        return raw_tools

    def _load_tools_from_path(self, path: Path) -> list[Tool]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_tools = self._extract_tool_payload(payload)
        return [Tool.from_dict(raw_tool) for raw_tool in raw_tools]

    def _backup_corrupt_file(self) -> Path:
        if not self.path.exists():
            return self.path

        backup_path = self._unique_backup_path("corrupt")
        self.path.replace(backup_path)
        return backup_path

    def _backup_existing_file(self) -> None:
        if not self.path.exists():
            return
        backup_path = self.path.with_name(f"{self.path.stem}.backup{self.path.suffix}")
        shutil.copy2(self.path, backup_path)

    def _unique_backup_path(self, kind: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = self.path.with_name(f"{self.path.stem}.{kind}-{timestamp}{self.path.suffix}.bak")
        index = 1
        while backup_path.exists():
            backup_path = self.path.with_name(
                f"{self.path.stem}.{kind}-{timestamp}-{index}{self.path.suffix}.bak"
            )
            index += 1
        return backup_path

    def _backup_candidates(self) -> list[Path]:
        if not self.path.parent.exists():
            return []
        names: set[Path] = set()
        rolling_backup = self.path.with_name(f"{self.path.stem}.backup{self.path.suffix}")
        if rolling_backup.exists():
            names.add(rolling_backup)
        for path in self.path.parent.glob(f"{self.path.stem}.backup-*{self.path.suffix}.bak"):
            if path.is_file():
                names.add(path)
        for path in self.path.parent.glob(f"{self.path.stem}.corrupt-*{self.path.suffix}.bak"):
            if path.is_file():
                names.add(path)
        return sorted(names)

    def _format_mtime(self, path: Path) -> str:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            return "unknown"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).absolute().parent
    return project_root()


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass)
    return app_root()


def app_file_path(filename: str) -> Path:
    app_path = app_root() / filename
    if app_path.exists():
        return app_path
    return resource_root() / filename


def is_portable_mode() -> bool:
    value = os.environ.get("UNREAL_UTILITY_TOOL_PORTABLE", "").strip().casefold()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    return any((app_root() / marker).exists() for marker in ("portable.flag", "portable.txt"))


def resolve_app_data_dir() -> Path:
    if getattr(sys, "frozen", False) and not is_portable_mode():
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "EditorBinder"
    return app_root() / "data"


def resolve_default_storage_path() -> Path:
    filename = RELEASE_SEED_FILENAME
    if not getattr(sys, "frozen", False) or is_portable_mode():
        filename = WORKING_LIBRARY_FILENAME
    return resolve_app_data_dir() / filename


def resolve_release_seed_path() -> Path:
    resource_seed = resource_root() / "data" / RELEASE_SEED_FILENAME
    if resource_seed.exists():
        return resource_seed
    return app_root() / "data" / RELEASE_SEED_FILENAME


def ensure_default_storage_seeded(path: str | Path | None = None) -> Path:
    storage_path = Path(path) if path is not None else resolve_default_storage_path()
    if storage_path.exists():
        _merge_missing_release_seed_tools(storage_path)
        return storage_path

    tools = _load_release_seed_tools(storage_path)
    if not tools:
        from .presets import default_presets

        tools = default_presets()

    ToolLibraryStore(storage_path).save_tools(tools)
    return storage_path


def refresh_bundled_presets(
    path: str | Path,
    bundled_tools: list[Tool] | None = None,
) -> BundledPresetRefreshResult:
    storage_path = Path(path)
    store = ToolLibraryStore(storage_path)
    existing_tools = store.load_tools()
    source_tools = list(bundled_tools) if bundled_tools is not None else _load_bundled_preset_tools(storage_path)
    source_by_id = {tool.id: tool for tool in source_tools}
    seen_source_ids: set[str] = set()
    refreshed_tools: list[Tool] = []
    added_count = 0
    updated_count = 0
    unchanged_count = 0

    for tool in existing_tools:
        replacement = source_by_id.get(tool.id)
        if replacement is None:
            refreshed_tools.append(tool)
            continue

        seen_source_ids.add(tool.id)
        if tool.to_dict() == replacement.to_dict():
            unchanged_count += 1
        else:
            updated_count += 1
        refreshed_tools.append(replacement)

    for tool in source_tools:
        if tool.id not in seen_source_ids:
            refreshed_tools.append(tool)
            added_count += 1

    if added_count or updated_count:
        store.save_tools(refreshed_tools)

    return BundledPresetRefreshResult(
        refreshed_tools=refreshed_tools,
        added_count=added_count,
        updated_count=updated_count,
        unchanged_count=unchanged_count,
    )


def _merge_missing_release_seed_tools(storage_path: Path) -> None:
    seed_tools = _load_release_seed_tools(storage_path)
    if not seed_tools:
        return

    store = ToolLibraryStore(storage_path)
    existing_tools = store.load_tools()
    existing_ids = {tool.id for tool in existing_tools}
    missing_tools = [tool for tool in seed_tools if tool.id not in existing_ids]
    if missing_tools:
        store.save_tools(existing_tools + missing_tools)


def _load_bundled_preset_tools(storage_path: Path) -> list[Tool]:
    try:
        from .presets import default_presets

        return default_presets()
    except Exception:
        return _load_release_seed_tools(storage_path)


def _load_release_seed_tools(storage_path: Path) -> list[Tool]:
    seed_path = resolve_release_seed_path()
    try:
        if not seed_path.exists() or seed_path.resolve() == storage_path.resolve():
            return []
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        raw_tools = ToolLibraryStore(seed_path)._extract_tool_payload(payload)
        return [Tool.from_dict(raw_tool) for raw_tool in raw_tools]
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return []
