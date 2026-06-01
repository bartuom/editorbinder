from __future__ import annotations

import ast
from dataclasses import dataclass

from .params import ParamRenderError, render_tool_code


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    message: str = ""


def validate_python_code(code: str) -> ValidationResult:
    if not code.strip():
        return ValidationResult(False, "Code is required.")

    try:
        ast.parse(code)
    except SyntaxError as exc:
        line = exc.lineno or 1
        column = exc.offset or 1
        return ValidationResult(
            False,
            f"Syntax error at line {line}, column {column}: {exc.msg}.",
        )

    return ValidationResult(True)


def validate_tool_code(code: str) -> ValidationResult:
    if not code.strip():
        return ValidationResult(False, "Code is required.")

    try:
        rendered = render_tool_code(code, {})
    except ParamRenderError as exc:
        return ValidationResult(False, str(exc))

    return validate_python_code(rendered)


def validate_tool_fields(name: str, code: str) -> list[str]:
    errors: list[str] = []
    if not name.strip():
        errors.append("Name is required.")
    if not code.strip():
        errors.append("Code is required.")
    return errors
