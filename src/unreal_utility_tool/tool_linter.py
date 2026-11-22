from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass


SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

_MUTATING_CALLS = {
    "set_actor_location",
    "set_actor_rotation",
    "set_actor_scale3d",
    "set_actor_relative_location",
    "set_actor_relative_rotation",
    "set_actor_relative_scale3d",
    "set_actor_relative_transform",
    "set_actor_label",
    "set_folder_path",
    "set_editor_property",
    "duplicate_actor",
    "spawn_actor",
    "destroy_actor",
    "attach_to_actor",
    "detach_from_actor",
    "destroy_component",
    "register_component",
    "unregister_component",
    "set_material",
    "set_collision_profile_name",
    "set_collision_enabled",
    "set_actor_enable_collision",
    "set_mobility",
    "set_static_mesh",
    "set_actor_transform",
    "set_actor_hidden_in_game",
    "add_actor_world_offset",
    "add_actor_local_offset",
    "add_actor_world_rotation",
    "add_actor_local_rotation",
    "add_actor_world_transform",
    "add_actor_local_transform",
}
_HIT_RESULT_VARIABLES = {"hit", "hit_result", "hitresult", "raw_hit", "trace_result", "result"}
_HIT_RESULT_PROPERTIES = {"impact_point", "location", "blocking_hit", "b_blocking_hit"}


@dataclass(frozen=True, slots=True)
class ToolLintIssue:
    severity: str
    title: str
    message: str


def lint_tool_code(code: str) -> tuple[ToolLintIssue, ...]:
    issues: list[ToolLintIssue] = []
    text = code or ""
    tree = _parse_source(text)
    analysis_text = _source_without_comments_and_strings(text)
    called_names = _called_names(tree) if tree is not None else set()
    identifier_names = _identifier_names(tree) if tree is not None else set()
    function_names = _function_names(tree) if tree is not None else set()

    if tree is None:
        lowered = analysis_text.casefold()
        uses_trace = "line_trace_" in lowered or "hitresult" in lowered or "hit_result" in lowered
        uses_hit_tuple = bool(re.search(r"\.\s*to_tuple\s*\(|\bdef\s+hit_tuple\b", lowered))
        has_debug_log = "debug_log" in lowered
        has_move_call = "set_actor_location" in lowered
        has_final_log = bool(re.search(r"\bunreal\s*\.\s*log(?:_warning|_error)?\s*\(", lowered))
        has_transaction = "scopededitortransaction" in lowered
        looks_mutating = any(name in lowered for name in _MUTATING_CALLS)
        identifiers = set(re.findall(r"\b[A-Za-z_]\w*\b", lowered))
    else:
        uses_trace = any(name.startswith("line_trace_") for name in called_names) or bool(
            {"hitresult", "hit_result"} & identifier_names
        )
        uses_hit_tuple = "to_tuple" in called_names or "hit_tuple" in function_names
        has_debug_log = "debug_log" in called_names or "debug_log" in function_names
        has_move_call = "set_actor_location" in called_names
        has_final_log = _has_unreal_log(tree)
        has_transaction = _has_editor_transaction(tree)
        looks_mutating = bool(_MUTATING_CALLS & called_names)
        identifiers = identifier_names

    if uses_trace and not uses_hit_tuple:
        issues.append(
            ToolLintIssue(
                SEVERITY_WARNING,
                "Risky HitResult handling",
                "Trace code should read HitResult through to_tuple(); direct properties can be protected in Unreal Python.",
            )
        )

    direct_hit_properties = _direct_hit_property_patterns(tree, analysis_text)
    if direct_hit_properties and not uses_hit_tuple:
        issues.append(
            ToolLintIssue(
                SEVERITY_WARNING,
                "Direct HitResult property access",
                f"Found direct access to {', '.join(direct_hit_properties)} without a to_tuple fallback.",
            )
        )

    if uses_trace and re.search(r"\braw(?:_hit)?\s*\[\s*0\s*\]", analysis_text) and "isinstance" not in identifiers:
        issues.append(
            ToolLintIssue(
                SEVERITY_WARNING,
                "Tuple-only trace result handling",
                "line_trace_single may return HitResult directly in some Unreal versions; guard raw[0] with isinstance(raw, (list, tuple)).",
            )
        )

    if uses_trace and not has_debug_log:
        issues.append(
            ToolLintIssue(
                SEVERITY_INFO,
                "Needs runtime diagnostics",
                "Trace tools should include debug_log and log raw trace type, blocking hit, hit point, target, and new location.",
            )
        )

    if has_move_call and not {"old", "target", "new"}.issubset(identifiers):
        issues.append(
            ToolLintIssue(
                SEVERITY_INFO,
                "Move verification missing",
                "Movement tools should log old, target, and new locations in diagnostic mode.",
            )
        )

    if not has_transaction and looks_mutating:
        issues.append(
            ToolLintIssue(
                SEVERITY_WARNING,
                "Missing editor transaction",
                "Scene-changing tools should use unreal.ScopedEditorTransaction.",
            )
        )

    if not has_final_log:
        issues.append(
            ToolLintIssue(
                SEVERITY_INFO,
                "No final log",
                "Tools should finish with a useful unreal.log() count summary.",
            )
        )

    return tuple(issues)


def _parse_source(code: str) -> ast.AST | None:
    try:
        return ast.parse(code)
    except (SyntaxError, ValueError, TypeError):
        return None


def _source_without_comments_and_strings(code: str) -> str:
    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        return " ".join(
            token.string
            for token in tokens
            if token.type not in {
                tokenize.COMMENT,
                tokenize.STRING,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENDMARKER,
            }
        )
    except (tokenize.TokenError, IndentationError):
        return code


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            names.add(node.func.attr.casefold())
        elif isinstance(node.func, ast.Name):
            names.add(node.func.id.casefold())
    return names


def _identifier_names(tree: ast.AST) -> set[str]:
    return {node.id.casefold() for node in ast.walk(tree) if isinstance(node, ast.Name)}


def _function_names(tree: ast.AST) -> set[str]:
    return {
        node.name.casefold()
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _has_unreal_log(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr.casefold() not in {"log", "log_warning", "log_error"}:
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id.casefold() == "unreal":
            return True
    return False


def _has_editor_transaction(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id.casefold() == "scopededitortransaction":
            return True
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr.casefold() == "scopededitortransaction"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id.casefold() == "unreal"
        ):
            return True
    return False


def _direct_hit_property_patterns(tree: ast.AST | None, code: str) -> list[str]:
    if tree is None:
        patterns = {
            ".impact_point": r"\.\s*impact_point\b",
            ".location": r"\.\s*location\b",
            ".blocking_hit": r"\.\s*blocking_hit\b",
            ".b_blocking_hit": r"\.\s*b_blocking_hit\b",
        }
        return [label for label, pattern in patterns.items() if re.search(pattern, code)]

    found = {
        f".{node.attr.casefold()}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr.casefold() in _HIT_RESULT_PROPERTIES
        and isinstance(node.value, ast.Name)
        and node.value.id.casefold() in _HIT_RESULT_VARIABLES
    }
    return sorted(found)


def lint_summary(code: str) -> str:
    issues = lint_tool_code(code)
    if not issues:
        return "Troubleshooting: no known risky Unreal Python patterns detected."
    details = "\n".join(f"[{issue.severity.upper()}] {issue.title}: {issue.message}" for issue in issues)
    return f"Troubleshooting:\n{details}"


def has_warning_or_error(code: str) -> bool:
    return any(issue.severity in {SEVERITY_WARNING, SEVERITY_ERROR} for issue in lint_tool_code(code))
