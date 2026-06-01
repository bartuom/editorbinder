from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .ai_parser import parse_ai_tool_response, split_marker_tool_blocks
from .models import Tool
from .validation import validate_tool_fields

PACK_JSON_NAME = "editorbinder-pack.json"
SUPPORTED_IMPORT_SUFFIXES = {".json", ".py", ".txt", ".zip"}
IGNORED_IMPORT_FILENAMES = {"bundle-manifest.json", "release.json"}
IMPORT_POLICY_COPY = "copy"
IMPORT_POLICY_SKIP = "skip"
IMPORT_POLICY_REPLACE = "replace"
IMPORT_POLICIES = {IMPORT_POLICY_COPY, IMPORT_POLICY_SKIP, IMPORT_POLICY_REPLACE}


@dataclass(frozen=True, slots=True)
class ToolImportBatch:
    tools: list[Tool]
    policy: str = IMPORT_POLICY_SKIP


@dataclass(frozen=True, slots=True)
class ImportResolution:
    tools: list[Tool]
    added_count: int
    replaced_count: int
    skipped_count: int
    renamed_count: int
    last_tool_id: str = ""


def import_tools_from_paths(paths: Iterable[str | Path]) -> tuple[list[Tool], list[str]]:
    tools: list[Tool] = []
    errors: list[str] = []

    for path in _collect_import_files(paths):
        try:
            tools.extend(_import_tools_from_file(path))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, zipfile.BadZipFile) as exc:
            errors.append(f"{path.name}: {exc}")

    return tools, errors


def _collect_import_files(paths: Iterable[str | Path]) -> list[Path]:
    collected: list[Path] = []
    seen: set[Path] = set()

    for raw_path in paths:
        path = Path(raw_path).expanduser()
        candidates = _candidate_import_files(path)

        for candidate in candidates:
            if not _is_supported_import_file(candidate):
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                collected.append(resolved)
                seen.add(resolved)

    return collected


def _candidate_import_files(path: Path) -> list[Path]:
    if not path.is_dir():
        return [path]

    root_pack = path / PACK_JSON_NAME
    if root_pack.is_file():
        return [root_pack]

    return sorted(child for child in path.rglob("*") if _is_supported_import_file(child))


def _is_supported_import_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name.casefold() in IGNORED_IMPORT_FILENAMES:
        return False
    return path.suffix.casefold() in SUPPORTED_IMPORT_SUFFIXES


def _import_tools_from_file(path: Path) -> list[Tool]:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        return _import_tools_from_json(path)
    if suffix == ".zip":
        return _import_tools_from_zip(path)
    return import_tools_from_text(path.read_text(encoding="utf-8-sig"), fallback_name=_fallback_name(path))


def _import_tools_from_json(path: Path) -> list[Tool]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return _import_tools_from_payload(payload, path)


def _import_tools_from_zip(path: Path) -> list[Tool]:
    with zipfile.ZipFile(path) as archive:
        payload_name = _zip_pack_payload_name(archive)
        if not payload_name:
            raise ValueError(f"ZIP does not contain {PACK_JSON_NAME}")
        payload = json.loads(archive.read(payload_name).decode("utf-8-sig"))
    return _import_tools_from_payload(payload, path)


def _zip_pack_payload_name(archive: zipfile.ZipFile) -> str:
    names = [name for name in archive.namelist() if not name.endswith("/")]
    if PACK_JSON_NAME in names:
        return PACK_JSON_NAME
    matches = sorted(name for name in names if name.replace("\\", "/").endswith(f"/{PACK_JSON_NAME}"))
    return matches[0] if matches else ""


def _import_tools_from_payload(payload: Any, path: Path) -> list[Tool]:
    raw_tools = _extract_raw_json_tools(payload)
    tools = [_tool_from_json(raw_tool, path, index) for index, raw_tool in enumerate(raw_tools, start=1)]
    if not tools:
        raise ValueError("no importable tools found")
    return tools


def _extract_raw_json_tools(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("tools"), list):
            return payload["tools"]
        return [payload]
    if isinstance(payload, list):
        return payload
    raise ValueError("JSON must contain a tool object, a tools array, or an array of tools")


def _tool_from_json(raw: dict[str, Any], path: Path, index: int) -> Tool:
    if not isinstance(raw, dict):
        raise ValueError(f"tool #{index} is not a JSON object")

    name = str(raw.get("name") or raw.get("title") or _fallback_name(path))
    description = str(
        raw.get("description")
        or raw.get("notes")
        or raw.get("parameters")
        or raw.get("parameters / notes")
        or raw.get("parameters/notes")
        or ""
    )
    tags = raw.get("tags") or []
    category = str(raw.get("category") or "")
    workflows = raw.get("workflows")
    roles = raw.get("roles")
    visibility = raw.get("visibility")
    code = str(raw.get("code") or raw.get("script") or raw.get("script_code") or raw.get("python") or "")

    errors = validate_tool_fields(name, code)
    if errors:
        raise ValueError(f"tool #{index}: {', '.join(errors)}")

    tool = Tool.create(
        name=name,
        description=description,
        tags=tags,
        code=code,
        category=category,
        workflows=workflows,
        roles=roles,
        visibility=str(visibility or ""),
    )
    raw_id = str(raw.get("id") or "").strip()
    if not raw_id:
        return tool

    return Tool(
        id=raw_id,
        name=tool.name,
        description=tool.description,
        tags=tool.tags,
        code=tool.code,
        created_at=str(raw.get("created_at") or tool.created_at),
        updated_at=str(raw.get("updated_at") or tool.updated_at),
        category=tool.category,
        workflows=tool.workflows,
        roles=tool.roles,
        visibility=tool.visibility,
    )


def import_tools_from_text(text: str, fallback_name: str = "Imported Tool") -> list[Tool]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("no importable tools found")

    tools: list[Tool] = []
    blocks = split_marker_tool_blocks(cleaned)
    for index, block in enumerate(blocks, start=1):
        parsed = parse_ai_tool_response(block)
        name = parsed.name or (fallback_name if len(blocks) == 1 else f"{fallback_name} {index}")
        notes = "" if parsed.notes.casefold() == "none" else parsed.notes
        code = parsed.code or block

        errors = validate_tool_fields(name, code)
        if errors:
            raise ValueError(f"tool #{index}: {', '.join(errors)}")

        tools.append(Tool.create(name=name, description=notes, tags=[], code=code))

    if not tools:
        raise ValueError("no importable tools found")
    return tools


def apply_import_policy(
    existing_tools: list[Tool],
    imported_tools: list[Tool],
    policy: str,
) -> ImportResolution:
    if policy not in IMPORT_POLICIES:
        raise ValueError(f"Unknown import policy: {policy}")

    result = list(existing_tools)
    existing_index_by_id = {
        _normalize_id(tool.id): index
        for index, tool in enumerate(result)
        if _normalize_id(tool.id)
    }
    existing_index_by_name = {_normalize_name(tool.name): index for index, tool in enumerate(result)}
    used_ids = set(existing_index_by_id)
    used_names = {_normalize_name(tool.name) for tool in result}
    processed_import_ids: set[str] = set()
    processed_import_names: set[str] = set()
    added_count = 0
    replaced_count = 0
    skipped_count = 0
    renamed_count = 0
    last_tool_id = ""

    for imported_tool in imported_tools:
        id_key = _normalize_id(imported_tool.id)
        name_key = _normalize_name(imported_tool.name)
        if not name_key:
            skipped_count += 1
            continue

        duplicate_id_in_import = bool(id_key and id_key in processed_import_ids)
        duplicate_name_in_import = name_key in processed_import_names
        duplicate_in_import = duplicate_id_in_import or duplicate_name_in_import
        existing_index = None
        if id_key and id_key in existing_index_by_id:
            existing_index = existing_index_by_id[id_key]
        elif name_key in existing_index_by_name:
            existing_index = existing_index_by_name[name_key]
        duplicate_existing = existing_index is not None

        if policy == IMPORT_POLICY_SKIP and (duplicate_existing or duplicate_in_import):
            skipped_count += 1
            if id_key:
                processed_import_ids.add(id_key)
            processed_import_names.add(name_key)
            continue

        if policy == IMPORT_POLICY_REPLACE:
            if duplicate_in_import:
                skipped_count += 1
                if id_key:
                    processed_import_ids.add(id_key)
                processed_import_names.add(name_key)
                continue
            if duplicate_existing:
                index = existing_index
                existing_tool = result[index]
                updated = existing_tool.with_updates(
                    name=imported_tool.name,
                    description=imported_tool.description,
                    tags=imported_tool.tags,
                    code=imported_tool.code,
                    category=imported_tool.category,
                    workflows=imported_tool.workflows,
                    roles=imported_tool.roles,
                    visibility=imported_tool.visibility,
                )
                result[index] = updated
                existing_index_by_id[_normalize_id(updated.id)] = index
                existing_index_by_name[_normalize_name(updated.name)] = index
                used_ids.add(_normalize_id(updated.id))
                used_names.add(_normalize_name(updated.name))
                replaced_count += 1
                last_tool_id = updated.id
            else:
                result.append(imported_tool)
                if id_key:
                    existing_index_by_id[id_key] = len(result) - 1
                    used_ids.add(id_key)
                existing_index_by_name[name_key] = len(result) - 1
                used_names.add(name_key)
                added_count += 1
                last_tool_id = imported_tool.id
            if id_key:
                processed_import_ids.add(id_key)
            processed_import_names.add(name_key)
            continue

        tool_to_add = imported_tool
        if duplicate_existing or duplicate_in_import or (id_key and id_key in used_ids) or name_key in used_names:
            copied_name = _unique_copy_name(imported_tool.name, used_names)
            tool_to_add = Tool.create(
                name=copied_name,
                description=imported_tool.description,
                tags=imported_tool.tags,
                code=imported_tool.code,
                category=imported_tool.category,
                workflows=imported_tool.workflows,
                roles=imported_tool.roles,
                visibility=imported_tool.visibility,
            )
            name_key = _normalize_name(copied_name)
            renamed_count += 1
            id_key = _normalize_id(tool_to_add.id)

        result.append(tool_to_add)
        if id_key:
            existing_index_by_id[id_key] = len(result) - 1
            used_ids.add(id_key)
        existing_index_by_name[name_key] = len(result) - 1
        used_names.add(name_key)
        original_id_key = _normalize_id(imported_tool.id)
        if original_id_key:
            processed_import_ids.add(original_id_key)
        processed_import_names.add(_normalize_name(imported_tool.name))
        added_count += 1
        last_tool_id = tool_to_add.id

    return ImportResolution(
        tools=result,
        added_count=added_count,
        replaced_count=replaced_count,
        skipped_count=skipped_count,
        renamed_count=renamed_count,
        last_tool_id=last_tool_id,
    )


def _fallback_name(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip().title() or "Imported Tool"


def _normalize_name(name: str) -> str:
    return " ".join(name.casefold().strip().split())


def _normalize_id(tool_id: str) -> str:
    return str(tool_id or "").strip()


def _unique_copy_name(name: str, used_names: set[str]) -> str:
    base_name = name.strip() or "Imported Tool"
    candidate = f"{base_name} Copy"
    suffix = 2
    while _normalize_name(candidate) in used_names:
        candidate = f"{base_name} Copy {suffix}"
        suffix += 1
    return candidate
