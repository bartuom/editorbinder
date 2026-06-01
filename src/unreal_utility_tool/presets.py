from __future__ import annotations

from pathlib import Path

from .models import Tool

PRESET_CREATED_AT = "2026-05-26T00:00:00+00:00"
PRESET_PACKS_DIR = Path(__file__).with_name("preset_packs")
PRESET_SCRIPT_SEPARATOR = "# ---"
REQUIRED_PRESET_METADATA = {
    "id",
    "name",
    "description",
    "tags",
    "created_at",
    "updated_at",
    "category",
}


def default_presets() -> list[Tool]:
    """Load bundled product presets from pack folders."""

    return [_load_preset_script(path) for path in _preset_script_paths()]


def _preset_script_paths() -> list[Path]:
    return sorted(PRESET_PACKS_DIR.glob("*/*.py"), key=_preset_script_sort_key)


def _preset_script_sort_key(path: Path) -> tuple[int, str]:
    order = 999_999
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == PRESET_SCRIPT_SEPARATOR:
                break
            if stripped.casefold().startswith("# order:"):
                order = int(stripped.split(":", 1)[1].strip())
                break
    except (OSError, ValueError):
        pass
    return (order, path.relative_to(PRESET_PACKS_DIR).as_posix())


def _load_preset_script(path: Path) -> Tool:
    raw_text = path.read_text(encoding="utf-8")
    header_lines, code = _split_preset_script(raw_text, path)
    metadata = _parse_preset_metadata(header_lines, path)
    metadata["code"] = code
    return Tool.from_dict(metadata)


def _split_preset_script(raw_text: str, path: Path) -> tuple[list[str], str]:
    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    for index, line in enumerate(lines):
        if line.strip() == PRESET_SCRIPT_SEPARATOR:
            code = "\n".join(lines[index + 1:]).strip("\n")
            if not code.strip():
                raise ValueError(f"Preset script has no code body: {path}")
            return lines[:index], code + "\n"
    raise ValueError(f"Preset script missing separator '{PRESET_SCRIPT_SEPARATOR}': {path}")


def _parse_preset_metadata(header_lines: list[str], path: Path) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for line in header_lines:
        stripped = line.strip()
        if not stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped[1:].split(":", 1)
        key = key.strip().casefold()
        value = value.strip()
        if key in {"tags", "workflows", "roles"}:
            metadata[key] = [item.strip() for item in value.split(",") if item.strip()]
        elif key in REQUIRED_PRESET_METADATA or key == "visibility":
            metadata[key] = value

    missing = sorted(REQUIRED_PRESET_METADATA - set(metadata))
    if missing:
        raise ValueError(f"Preset script missing metadata {', '.join(missing)}: {path}")
    return metadata
