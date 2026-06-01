from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .compatibility_templates import (
    infer_tool_type,
    normalize_tool_type,
    requirements_for_tool_type,
    snippets_for_tool_type,
)

UNREAL_QUALITY_CONSTRAINTS = (
    "Hard rules:\n"
    "- Return exactly one EditorBinder tool block and nothing else.\n"
    "- Write plain Unreal Python that runs from one paste into Unreal Python Console.\n"
    "- Do not invent Unreal Python methods, helpers, properties, or magic EditorBinder APIs.\n"
    "- If an Unreal API detail is uncertain, use a simpler safe actor/component operation and log a warning.\n"
    "- Import unreal at the top of the code.\n"
    "- Keep parameter declarations as '# Param: name | type | default | Label'.\n"
    "- Supported parameter types: str, text, path, int, float, bool, enum.\n"
    "- Optional parameter metadata: min=, max=, step=, options=a,b,c.\n"
    "- Every declared parameter must be assigned from its placeholder near the top, for example: amount = {{amount}}.\n"
    "- Never assign a fixed literal instead of a declared parameter placeholder.\n"
    "- Use unreal.ScopedEditorTransaction for scene changes.\n"
    "- Handle empty selection, missing actors, missing components, and failed operations without crashing.\n"
    "- Log clear final counts with unreal.log(), for example changed/skipped/missed/failed.\n"
    "- Do not put marker strings inside Python code.\n"
    "- Do not include explanations outside the requested marker format.\n"
    "\n"
    "Reliable Unreal Python patterns:\n"
    "- Selected actors: editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem), then get_selected_level_actors().\n"
    "- Actor labels: actor.get_actor_label() and actor.set_actor_label().\n"
    "- Outliner folders: actor.set_folder_path().\n"
    "- Actor movement: read actor.get_actor_location(), then call actor.set_actor_location(new_location, False, False).\n"
    "- Actor rotation: use actor.get_actor_rotation() and actor.set_actor_rotation(new_rotation, False).\n"
    "- Actor scale: use actor.get_actor_scale3d() and actor.set_actor_scale3d(new_scale).\n"
    "- Duplicates should be created through editor actor subsystem duplication/spawn APIs only when you are confident they exist; otherwise create a clear paste-ready fallback.\n"
    "\n"
    "Quality check before final answer:\n"
    "- Check that the marker order is UUT_NAME, UUT_NOTES, UUT_CODE, UUT_END.\n"
    "- Check that Python syntax is valid after replacing {{param}} placeholders with their defaults.\n"
    "- Check that the code logs useful counts and does not silently do nothing.\n"
    "- Check that the tool name is short and searchable by likely user words.\n"
)


MARKER_FORMAT = (
    "<<<UUT_NAME>>>\n"
    "Short searchable tool name\n"
    "<<<UUT_NOTES>>>\n"
    "Short note about editable params and behavior, or None\n"
    "<<<UUT_CODE>>>\n"
    "```python\n"
    "# Param: amount | float | 100 | Amount | min=0 | max=1000 | step=10\n"
    "import unreal\n"
    "amount = {{amount}}\n"
    "# paste-ready code here\n"
    "```\n"
    "<<<UUT_END>>>"
)


@dataclass(frozen=True, slots=True)
class PromptExample:
    name: str
    notes: str
    code: str
    category: str = ""


CATEGORY_KEYWORDS = {
    "Transform": {
        "array",
        "align",
        "axis",
        "bounds",
        "duplicate",
        "grid",
        "ground",
        "location",
        "move",
        "offset",
        "pivot",
        "radial",
        "rotate",
        "rotation",
        "scale",
        "snap",
        "trace",
        "transform",
    },
    "Selection": {
        "actor",
        "asset",
        "filter",
        "find",
        "get",
        "material",
        "mesh",
        "select",
        "selection",
        "tag",
    },
    "Organization": {
        "folder",
        "label",
        "name",
        "outliner",
        "prefix",
        "rename",
        "suffix",
    },
    "Debug": {
        "debug",
        "draw",
        "inspect",
        "line",
        "log",
        "print",
        "report",
        "trace",
    },
}


def build_ai_prompt(
    example_code: str = "",
    tool_request: str = "",
    *,
    examples: Iterable[PromptExample] | None = None,
    tool_type: str = "",
) -> str:
    request = tool_request.strip() or "[DESCRIBE THE UNREAL TOOL HERE]"
    selected_tool_type = normalize_tool_type(tool_type or infer_tool_type(request))
    prompt_examples = list(examples or [])
    if not prompt_examples and example_code.strip():
        prompt_examples = [PromptExample(name="Existing EditorBinder Tool", notes="Style reference.", code=example_code)]

    return (
        "You are generating one high-quality Unreal Engine Python Console tool for EditorBinder.\n"
        "Think through the implementation privately, but output only the final marker block.\n\n"
        "USER TOOL REQUEST\n"
        f"{request}\n\n"
        "TOOL TYPE\n"
        f"{selected_tool_type}\n\n"
        "OUTPUT FORMAT - copy exactly, with your generated content replacing the descriptions:\n"
        f"{MARKER_FORMAT}\n\n"
        f"{_format_type_requirements(selected_tool_type)}\n\n"
        f"{_format_compatibility_snippets(selected_tool_type)}\n\n"
        f"{_format_prompt_examples(prompt_examples)}\n\n"
        "IMPLEMENTATION REQUIREMENTS\n"
        f"{UNREAL_QUALITY_CONSTRAINTS}"
    )


def build_generation_repair_prompt(
    tool_request: str,
    bad_response: str,
    diagnostics: Iterable[str],
    *,
    examples: Iterable[PromptExample] | None = None,
    tool_type: str = "",
) -> str:
    request = tool_request.strip() or "[DESCRIBE THE UNREAL TOOL HERE]"
    selected_tool_type = normalize_tool_type(tool_type or infer_tool_type(request))
    diagnostic_text = "\n".join(f"- {item}" for item in diagnostics if str(item).strip())
    if not diagnostic_text:
        diagnostic_text = "- Output did not validate."

    return (
        "Repair this EditorBinder Unreal Python tool response.\n"
        "Return only the marker format. Do not explain the fix.\n\n"
        "Original tool request:\n"
        f"{request}\n\n"
        "Tool type:\n"
        f"{selected_tool_type}\n\n"
        "Validation diagnostics:\n"
        f"{diagnostic_text}\n\n"
        "Bad response:\n"
        f"{bad_response.strip()}\n\n"
        f"{_format_type_requirements(selected_tool_type)}\n\n"
        f"{_format_compatibility_snippets(selected_tool_type)}\n\n"
        f"{_format_prompt_examples(list(examples or []))}\n\n"
        "Required marker format:\n"
        f"{MARKER_FORMAT}\n\n"
        "Implementation requirements:\n"
        f"{UNREAL_QUALITY_CONSTRAINTS}"
    )


def build_runtime_fix_prompt(
    tool_request: str,
    tool_name: str,
    tool_code: str,
    runtime_logs: str,
    diagnostics: Iterable[str] = (),
    *,
    tool_type: str = "",
) -> str:
    request = tool_request.strip() or "[ORIGINAL TOOL REQUEST WAS EMPTY]"
    selected_tool_type = normalize_tool_type(tool_type or infer_tool_type(f"{request}\n{tool_code}"))
    diagnostic_text = "\n".join(f"- {item}" for item in diagnostics if str(item).strip()) or "- No parser diagnostics."
    logs = runtime_logs.strip() or "[PASTE UNREAL OUTPUT LOG HERE]"
    return (
        "Fix this EditorBinder Unreal Python tool using the runtime logs.\n"
        "Return only one corrected EditorBinder marker block. Do not explain outside the markers.\n\n"
        "Original user request:\n"
        f"{request}\n\n"
        "Tool type:\n"
        f"{selected_tool_type}\n\n"
        "Current tool name:\n"
        f"{tool_name.strip() or 'Imported AI Tool'}\n\n"
        "Parser / static diagnostics:\n"
        f"{diagnostic_text}\n\n"
        "Runtime logs from Unreal:\n"
        f"{logs}\n\n"
        "Current tool code:\n"
        "```python\n"
        f"{tool_code.strip()}\n"
        "```\n\n"
        f"{_format_type_requirements(selected_tool_type)}\n\n"
        f"{_format_compatibility_snippets(selected_tool_type)}\n\n"
        "Required marker format:\n"
        f"{MARKER_FORMAT}\n\n"
        "Implementation requirements:\n"
        f"{UNREAL_QUALITY_CONSTRAINTS}"
    )


def build_fix_prompt(tool_name: str, tool_code: str, unreal_error: str = "") -> str:
    error = unreal_error.strip() or "[PASTE UNREAL PYTHON ERROR HERE]"
    return (
        "Fix this Unreal Engine Python Console tool.\n"
        "Return only the EditorBinder marker format.\n"
        "Keep the tool paste-ready for Unreal Python Console.\n\n"
        "Unreal Python error:\n"
        f"{error}\n\n"
        "Current tool name:\n"
        f"{tool_name.strip() or 'Imported Tool'}\n\n"
        "Current tool code:\n"
        "```python\n"
        f"{tool_code.strip()}\n"
        "```\n\n"
        "Return format:\n"
        "<<<UUT_NAME>>>\n"
        "Fixed user-facing tool name\n"
        "<<<UUT_NOTES>>>\n"
        "Short note about what changed, or None\n"
        "<<<UUT_CODE>>>\n"
        "```python\n"
        "# fixed paste-ready code here\n"
        "```\n"
        "<<<UUT_END>>>\n\n"
        "Constraints:\n"
        f"{UNREAL_QUALITY_CONSTRAINTS}"
    )


def select_prompt_examples(tool_request: str, tools: Iterable[Any], limit: int = 3) -> list[PromptExample]:
    request_tokens = _tokens(tool_request)
    if not request_tokens:
        return []

    scored: list[tuple[int, int, PromptExample]] = []
    for index, tool in enumerate(tools):
        example = _tool_to_prompt_example(tool)
        if not example.code.strip():
            continue
        score = _score_example(request_tokens, example)
        if score > 0:
            scored.append((score, -index, example))

    scored.sort(reverse=True)
    return [example for _score, _index, example in scored[: max(0, limit)]]


def _tool_to_prompt_example(tool: Any) -> PromptExample:
    return PromptExample(
        name=str(getattr(tool, "name", "") or "Untitled Tool"),
        notes=str(getattr(tool, "description", "") or ""),
        code=str(getattr(tool, "code", "") or ""),
        category=str(getattr(tool, "category", "") or ""),
    )


def _score_example(request_tokens: set[str], example: PromptExample) -> int:
    searchable = " ".join([example.name, example.notes, example.category, example.code[:1600]]).casefold()
    score = sum(4 for token in request_tokens if token in searchable)
    category = example.category.strip()
    if category in CATEGORY_KEYWORDS and request_tokens & CATEGORY_KEYWORDS[category]:
        score += 8
    if "param" in searchable and request_tokens & {"input", "parameter", "param", "slider", "option"}:
        score += 3
    return score


def _tokens(text: str) -> set[str]:
    normalized = "".join(char.casefold() if char.isalnum() else " " for char in text)
    return {part for part in normalized.split() if len(part) >= 3}


def _format_prompt_examples(examples: Iterable[PromptExample]) -> str:
    prompt_examples = list(examples)
    if not prompt_examples:
        return "Relevant examples: None."

    blocks: list[str] = ["Relevant existing EditorBinder examples:"]
    for index, example in enumerate(prompt_examples[:3], start=1):
        notes = example.notes.strip() or "None"
        category = f" [{example.category}]" if example.category.strip() else ""
        blocks.append(
            f"\nExample {index}: {example.name.strip() or 'Untitled'}{category}\n"
            f"Notes: {notes}\n"
            "```python\n"
            f"{_compact_code(example.code)}\n"
            "```"
        )
    return "\n".join(blocks)


def _format_type_requirements(tool_type: str) -> str:
    requirements = requirements_for_tool_type(tool_type)
    lines = [f"Tool-type requirements for {normalize_tool_type(tool_type)}:"]
    lines.extend(f"- {item}" for item in requirements)
    return "\n".join(lines)


def _format_compatibility_snippets(tool_type: str) -> str:
    snippets = snippets_for_tool_type(tool_type)
    return "Use these compatibility snippets/patterns when relevant:\n" + "\n\n".join(snippets)


def _compact_code(code: str, max_chars: int = 1800) -> str:
    stripped = code.strip()
    if len(stripped) <= max_chars:
        return stripped
    return f"{stripped[:max_chars].rstrip()}\n# ... example truncated ..."
