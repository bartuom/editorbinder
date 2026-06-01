from __future__ import annotations

import re
from dataclasses import dataclass

from .validation import validate_tool_code


@dataclass(frozen=True, slots=True)
class ParsedAiTool:
    name: str
    notes: str
    code: str
    diagnostics: tuple[str, ...] = ()


FIELD_ALIASES = {
    "name": "name",
    "tool name": "name",
    "title": "name",
    "parameters": "notes",
    "params": "notes",
    "notes": "notes",
    "parameters / notes": "notes",
    "parameters/notes": "notes",
    "description": "notes",
}

MARKER_NAME = "<<<UUT_NAME>>>"
MARKER_NOTES = "<<<UUT_NOTES>>>"
MARKER_CODE = "<<<UUT_CODE>>>"
MARKER_END = "<<<UUT_END>>>"
MARKERS = (MARKER_NAME, MARKER_NOTES, MARKER_CODE, MARKER_END)
MARKER_PATTERN = re.compile(r"^\s*<<<(UUT_NAME|UUT_NOTES|UUT_CODE|UUT_END)>>>\s*$", re.IGNORECASE)
MARKER_NORMALIZATION = {
    "UUT_NAME": MARKER_NAME,
    "UUT_NOTES": MARKER_NOTES,
    "UUT_CODE": MARKER_CODE,
    "UUT_END": MARKER_END,
}


def parse_ai_tool_response(text: str) -> ParsedAiTool:
    cleaned = text.strip()
    if not cleaned:
        return _with_diagnostics("", "", "")

    marker_result = _parse_marker_format(cleaned)
    if marker_result is not None:
        return marker_result

    code = _clean_code_block(_extract_code(cleaned))
    metadata_text = cleaned.replace(code, "", 1).strip() if code else cleaned
    fields = _extract_fields(metadata_text)

    name = (
        fields.get("name")
        or _extract_name_from_comments(code)
        or _extract_name_from_comments(cleaned)
        or _extract_heading(cleaned)
    )
    notes = fields.get("notes", "")

    if not code:
        code = _clean_code_block(_strip_metadata_lines(cleaned))

    return _with_diagnostics(name.strip(), notes.strip(), code.strip())


def split_marker_tool_blocks(text: str) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    lines = cleaned.splitlines()
    start_lines = [
        index
        for index, line in enumerate(lines)
        if (match := MARKER_PATTERN.match(line)) and MARKER_NORMALIZATION[match.group(1).upper()] == MARKER_NAME
    ]
    if len(start_lines) <= 1:
        return [cleaned]

    blocks: list[str] = []
    for block_index, start_line in enumerate(start_lines):
        end_line = start_lines[block_index + 1] if block_index + 1 < len(start_lines) else len(lines)
        block = "\n".join(lines[start_line:end_line]).strip()
        if block:
            blocks.append(block)
    return blocks


def _parse_marker_format(text: str) -> ParsedAiTool | None:
    lines = text.splitlines()
    marker_positions = _marker_positions(lines)
    code_positions = [position for position in marker_positions if position[1] == MARKER_CODE]
    if not code_positions:
        return None

    code_line_index = code_positions[0][0]
    code_end_index = next(
        (line_index for line_index, marker in marker_positions if marker == MARKER_END and line_index > code_line_index),
        len(lines),
    )
    code = _clean_code_block("\n".join(lines[code_line_index + 1 : code_end_index]))

    return _with_diagnostics(
        name=_extract_marker_section(lines, marker_positions, MARKER_NAME),
        notes=_extract_marker_section(lines, marker_positions, MARKER_NOTES),
        code=code,
    )


def _marker_positions(lines: list[str]) -> list[tuple[int, str]]:
    positions: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = MARKER_PATTERN.match(line)
        if match:
            positions.append((index, MARKER_NORMALIZATION[match.group(1).upper()]))
    return positions


def _extract_marker_section(
    lines: list[str],
    marker_positions: list[tuple[int, str]],
    marker_name: str,
) -> str:
    marker_index = next((index for index, marker in marker_positions if marker == marker_name), None)
    if marker_index is None:
        return ""
    next_marker_index = next((index for index, _marker in marker_positions if index > marker_index), len(lines))
    return "\n".join(lines[marker_index + 1 : next_marker_index]).strip()


def _extract_code(text: str) -> str:
    fence_match = re.search(r"```[ \t]*(?:python|py)?[ \t]*\r?\n?(.*?)\r?\n?```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    code_label_match = re.search(
        r"(?im)^\s*(?:code|script code|python code)\s*:\s*$\s*(.*)",
        text,
        flags=re.DOTALL,
    )
    if code_label_match:
        return code_label_match.group(1).strip()

    first_code_line = _find_first_code_line(text)
    if first_code_line >= 0:
        return "\n".join(text.splitlines()[first_code_line:]).strip()

    return ""


def _clean_code_block(text: str) -> str:
    code = _strip_code_fence(text.strip())
    code = _strip_leading_language_label(code)
    return code.strip()


def _strip_code_fence(text: str) -> str:
    fence_match = re.fullmatch(
        r"```[ \t]*(?:python|py)?[ \t]*\r?\n?(.*?)\r?\n?```",
        text.strip(),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fence_match:
        return fence_match.group(1).strip()
    return text


def _strip_leading_language_label(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    if lines[0].strip().casefold() in {"python", "py"}:
        return "\n".join(lines[1:]).strip()
    return text


def _extract_fields(text: str) -> dict[str, str]:
    lines = text.splitlines()
    fields: dict[str, list[str]] = {}
    current_key = ""

    for line in lines:
        match = re.match(r"^\s*(?:[-*]\s*)?([A-Za-z][A-Za-z /_-]{1,40})\s*:\s*(.*)$", line)
        if match:
            raw_key = match.group(1).strip().casefold()
            if raw_key in {"code", "script code", "python code"}:
                current_key = ""
                continue
            key = FIELD_ALIASES.get(raw_key)
            if key:
                current_key = key
                fields.setdefault(current_key, [])
                if match.group(2).strip():
                    fields[current_key].append(match.group(2).strip())
                continue

        if current_key and line.strip():
            fields[current_key].append(line.strip())

    return {key: "\n".join(value).strip() for key, value in fields.items()}


def _extract_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("# "):
            continue
        heading = stripped[2:].strip()
        if re.match(r"^(param|parameter)\s*:", heading, flags=re.IGNORECASE):
            continue
        return heading
    return ""


def _extract_name_from_comments(code: str) -> str:
    for line in code.splitlines()[:8]:
        match = re.match(r"^\s*#\s*(?:tool|name|title)\s*:\s*(.+?)\s*$", line, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _find_first_code_line(text: str) -> int:
    code_prefixes = (
        "#",
        "import ",
        "from ",
        "def ",
        "class ",
        "if ",
        "for ",
        "while ",
        "try:",
        "with ",
        "unreal.",
    )
    for index, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith(code_prefixes):
            return index
    return -1


def _strip_metadata_lines(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        if re.match(
            r"^\s*(?:name|tool name|title|parameters|params|notes|description|code|script code|python code)\s*:",
            line,
            re.I,
        ):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _with_diagnostics(name: str, notes: str, code: str) -> ParsedAiTool:
    diagnostics: list[str] = [
        "found name" if name.strip() else "missing name",
        "found notes" if notes.strip() else "missing notes",
        "found code" if code.strip() else "missing code",
    ]
    if code.strip():
        syntax = validate_tool_code(code)
        diagnostics.append("code syntax ok" if syntax.ok else f"code syntax error: {syntax.message}")
    return ParsedAiTool(name=name, notes=notes, code=code, diagnostics=tuple(diagnostics))
