from __future__ import annotations

import re
from dataclasses import dataclass


SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"


@dataclass(frozen=True, slots=True)
class ToolLintIssue:
    severity: str
    title: str
    message: str


def lint_tool_code(code: str) -> tuple[ToolLintIssue, ...]:
    issues: list[ToolLintIssue] = []
    text = code or ""
    lowered = text.casefold()

    uses_trace = "line_trace_" in lowered or "hitresult" in lowered or "hit_result" in lowered
    uses_hit_tuple = ".to_tuple()" in lowered or "def hit_tuple" in lowered

    if uses_trace and not uses_hit_tuple:
        issues.append(
            ToolLintIssue(
                SEVERITY_WARNING,
                "Risky HitResult handling",
                "Trace code should read HitResult through to_tuple(); direct properties can be protected in Unreal Python.",
            )
        )

    direct_hit_properties = _direct_hit_property_patterns(text)
    if direct_hit_properties and not uses_hit_tuple:
        issues.append(
            ToolLintIssue(
                SEVERITY_WARNING,
                "Direct HitResult property access",
                f"Found direct access to {', '.join(direct_hit_properties)} without a to_tuple fallback.",
            )
        )

    if uses_trace and re.search(r"\braw(?:_hit)?\s*\[\s*0\s*\]", text) and "isinstance" not in lowered:
        issues.append(
            ToolLintIssue(
                SEVERITY_WARNING,
                "Tuple-only trace result handling",
                "line_trace_single may return HitResult directly in some Unreal versions; guard raw[0] with isinstance(raw, (list, tuple)).",
            )
        )

    if uses_trace and "debug_log" not in lowered:
        issues.append(
            ToolLintIssue(
                SEVERITY_INFO,
                "Needs runtime diagnostics",
                "Trace tools should include debug_log and log raw trace type, blocking hit, hit point, target, and new location.",
            )
        )

    if "set_actor_location" in lowered and not all(token in lowered for token in ("old", "target", "new")):
        issues.append(
            ToolLintIssue(
                SEVERITY_INFO,
                "Move verification missing",
                "Movement tools should log old, target, and new locations in diagnostic mode.",
            )
        )

    if "scopededitortransaction" not in lowered and _looks_mutating(lowered):
        issues.append(
            ToolLintIssue(
                SEVERITY_WARNING,
                "Missing editor transaction",
                "Scene-changing tools should use unreal.ScopedEditorTransaction.",
            )
        )

    if "unreal.log(" not in lowered and "unreal.log_warning(" not in lowered:
        issues.append(
            ToolLintIssue(
                SEVERITY_INFO,
                "No final log",
                "Tools should finish with a useful unreal.log() count summary.",
            )
        )

    return tuple(issues)


def lint_summary(code: str) -> str:
    issues = lint_tool_code(code)
    if not issues:
        return "Troubleshooting: no known risky Unreal Python patterns detected."
    details = "\n".join(f"[{issue.severity.upper()}] {issue.title}: {issue.message}" for issue in issues)
    return f"Troubleshooting:\n{details}"


def has_warning_or_error(code: str) -> bool:
    return any(issue.severity in {SEVERITY_WARNING, SEVERITY_ERROR} for issue in lint_tool_code(code))


def _direct_hit_property_patterns(code: str) -> list[str]:
    found: list[str] = []
    patterns = {
        ".impact_point": r"\.\s*impact_point\b",
        ".location": r"\.\s*location\b",
        ".blocking_hit": r"\.\s*blocking_hit\b",
        ".b_blocking_hit": r"\.\s*b_blocking_hit\b",
    }
    for label, pattern in patterns.items():
        if re.search(pattern, code):
            found.append(label)
    return found


def _looks_mutating(lowered_code: str) -> bool:
    mutators = (
        "set_actor_location",
        "set_actor_rotation",
        "set_actor_scale3d",
        "set_actor_label",
        "set_folder_path",
        "set_editor_property",
        "duplicate_actor",
        "spawn_actor",
    )
    return any(mutator in lowered_code for mutator in mutators)
