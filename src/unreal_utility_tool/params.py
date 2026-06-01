from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping


SUPPORTED_PARAM_TYPES = {"str", "string", "text", "path", "int", "float", "bool", "enum"}


@dataclass(frozen=True, slots=True)
class ToolParam:
    name: str
    kind: str
    default: str
    label: str
    min_value: str = ""
    max_value: str = ""
    step: str = ""
    options: list[str] = field(default_factory=list)


class ParamRenderError(ValueError):
    pass


def parse_tool_params(code: str) -> list[ToolParam]:
    params: list[ToolParam] = []
    seen: set[str] = set()

    for line in code.splitlines():
        match = re.match(r"^\s*#\s*Param\s*:\s*(.+?)\s*$", line, flags=re.IGNORECASE)
        if not match:
            continue

        parts = [part.strip() for part in match.group(1).split("|")]
        if len(parts) < 3:
            continue

        name = parts[0]
        kind = parts[1].casefold()
        default = parts[2]
        label = parts[3] if len(parts) >= 4 and parts[3] else _label_from_name(name)
        metadata = _parse_metadata_parts(parts[4:])

        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            continue
        if kind not in SUPPORTED_PARAM_TYPES:
            continue
        if name in seen:
            continue

        params.append(
            ToolParam(
                name=name,
                kind="str" if kind == "string" else kind,
                default=default,
                label=label,
                min_value=metadata.get("min", ""),
                max_value=metadata.get("max", ""),
                step=metadata.get("step", ""),
                options=_split_options(metadata.get("options", "")),
            )
        )
        seen.add(name)

    return params


def render_tool_code(code: str, values: Mapping[str, str]) -> str:
    params = {param.name: param for param in parse_tool_params(code)}

    def replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        if name not in params:
            raise ParamRenderError(f"Unknown parameter: {name}")
        raw_value = values.get(name, params[name].default)
        return _format_value(raw_value, params[name])

    rendered = re.sub(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", replace, code)
    return _rewrite_first_param_assignments(rendered, params, values)


def validate_param_value(param: ToolParam, raw_value: str) -> None:
    _format_value(raw_value, param)


def _rewrite_first_param_assignments(
    code: str,
    params: Mapping[str, ToolParam],
    values: Mapping[str, str],
) -> str:
    if not params:
        return code

    seen: set[str] = set()
    lines: list[str] = []
    assignment_pattern = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*?)(\s*(?:#.*)?)$")

    for line in code.splitlines(keepends=True):
        newline = ""
        body = line
        if body.endswith("\r\n"):
            body = body[:-2]
            newline = "\r\n"
        elif body.endswith("\n"):
            body = body[:-1]
            newline = "\n"

        match = assignment_pattern.match(body)
        if not match:
            lines.append(line)
            continue

        name = match.group(2)
        if name not in params or name in seen:
            lines.append(line)
            continue

        raw_value = values.get(name, params[name].default)
        replacement = _format_value(raw_value, params[name])
        lines.append(f"{match.group(1)}{name}{match.group(3)}{replacement}{match.group(5)}{newline}")
        seen.add(name)

    return "".join(lines)


def _format_value(raw_value: str, param: ToolParam) -> str:
    value = str(raw_value).strip()
    if param.kind in {"str", "text", "path"}:
        return repr(value)
    if param.kind == "enum":
        if param.options and value not in param.options:
            raise ParamRenderError(f"{param.label} must be one of: {', '.join(param.options)}.")
        return repr(value)
    if param.kind == "int":
        try:
            number = int(value)
        except ValueError as exc:
            raise ParamRenderError(f"{param.label} must be an integer.") from exc
        _validate_numeric_range(float(number), param)
        return str(number)
    if param.kind == "float":
        try:
            number = _parse_float_text(value)
        except ValueError as exc:
            raise ParamRenderError(f"{param.label} must be a number.") from exc
        _validate_numeric_range(number, param)
        return repr(number)
    if param.kind == "bool":
        normalized = value.casefold()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return "True"
        if normalized in {"false", "0", "no", "n", "off"}:
            return "False"
        raise ParamRenderError(f"{param.label} must be true or false.")

    raise ParamRenderError(f"Unsupported parameter type: {param.kind}")


def _label_from_name(name: str) -> str:
    return name.replace("_", " ").strip().title()


def _parse_metadata_parts(parts: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().casefold()
        if key in {"min", "max", "step", "options"}:
            metadata[key] = value.strip()
    return metadata


def _split_options(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]


def _validate_numeric_range(value: float, param: ToolParam) -> None:
    if param.min_value:
        try:
            min_value = _parse_float_text(param.min_value)
        except ValueError:
            min_value = None
        if min_value is not None and value < min_value:
            raise ParamRenderError(f"{param.label} must be at least {param.min_value}.")
    if param.max_value:
        try:
            max_value = _parse_float_text(param.max_value)
        except ValueError:
            max_value = None
        if max_value is not None and value > max_value:
            raise ParamRenderError(f"{param.label} must be at most {param.max_value}.")


def _parse_float_text(value: str) -> float:
    return float(str(value).strip().replace(",", "."))
