from __future__ import annotations

import unittest

from unreal_utility_tool.models import CATEGORY_DEBUG, CATEGORY_TRANSFORM, Tool
from unreal_utility_tool.prompts import (
    PromptExample,
    build_ai_prompt,
    build_fix_prompt,
    build_generation_repair_prompt,
    build_runtime_fix_prompt,
    select_prompt_examples,
)


class PromptTests(unittest.TestCase):
    def test_prompt_contains_compact_contract_examples_and_constraints(self) -> None:
        prompt = build_ai_prompt(
            "import unreal\nunreal.log('x')",
            "Offset selected actors up by 100 cm.",
            examples=[PromptExample("Offset Example", "None", "import unreal\nunreal.log('x')", CATEGORY_TRANSFORM)],
        )

        self.assertIn("OUTPUT FORMAT - copy exactly", prompt)
        self.assertTrue(prompt.startswith("You are generating one high-quality Unreal Engine Python Console tool"))
        self.assertIn("Offset selected actors up by 100 cm.", prompt)
        self.assertIn("Think through the implementation privately", prompt)
        self.assertIn("<<<UUT_NAME>>>", prompt)
        self.assertIn("<<<UUT_NOTES>>>", prompt)
        self.assertIn("<<<UUT_CODE>>>", prompt)
        self.assertIn("<<<UUT_END>>>", prompt)
        self.assertIn("# Param: amount | float | 100 | Amount", prompt)
        self.assertIn("{{amount}}", prompt)
        self.assertIn("Supported parameter types: str, text, path, int, float, bool, enum.", prompt)
        self.assertIn("options=a,b,c", prompt)
        self.assertIn("Do not put marker strings inside Python code.", prompt)
        self.assertIn("Offset Example", prompt)
        self.assertIn("Write plain Unreal Python that runs from one paste into Unreal Python Console.", prompt)
        self.assertIn("Use unreal.ScopedEditorTransaction for scene changes.", prompt)
        self.assertIn("Actor movement: read actor.get_actor_location()", prompt)
        self.assertIn("actor.get_actor_label()", prompt)
        self.assertNotIn("actor.get_components_by_class()", prompt)

    def test_trace_prompt_contains_hitresult_tuple_compatibility(self) -> None:
        prompt = build_ai_prompt(tool_request="Snap selected actors to ground with line trace.", tool_type="Line Trace / HitResult")

        self.assertIn("hit_result.to_tuple()", prompt)
        self.assertIn('"impact_point": 5', prompt)
        self.assertIn('"location": 4', prompt)
        self.assertIn("raw_type=", prompt)
        self.assertIn("debug_log | bool | False", prompt)

    def test_transform_prompt_contains_move_diagnostics(self) -> None:
        prompt = build_ai_prompt(tool_request="Move selected actors upward.", tool_type="Transform / Move Actors")

        self.assertIn("old=", prompt)
        self.assertIn("target=", prompt)
        self.assertIn("new=", prompt)
        self.assertIn("move_actor_to_location", prompt)

    def test_prompt_uses_placeholder_when_request_is_empty(self) -> None:
        prompt = build_ai_prompt()

        self.assertIn("[DESCRIBE THE UNREAL TOOL HERE]", prompt)
        self.assertIn("Relevant examples: None.", prompt)

    def test_select_prompt_examples_returns_relevant_limited_presets(self) -> None:
        tools = [
            Tool.create(
                name="Debug Trace",
                description="Draw line traces.",
                tags=[],
                category=CATEGORY_DEBUG,
                code="import unreal\nunreal.log('trace')",
            ),
            Tool.create(
                name="Grid Array",
                description="Duplicate actors in a grid.",
                tags=[],
                category=CATEGORY_TRANSFORM,
                code="import unreal\nunreal.log('grid')",
            ),
            Tool.create(
                name="Radial Array",
                description="Duplicate actors around a circle.",
                tags=[],
                category=CATEGORY_TRANSFORM,
                code="import unreal\nunreal.log('radial')",
            ),
            Tool.create(
                name="Move Up",
                description="Offset actors.",
                tags=[],
                category=CATEGORY_TRANSFORM,
                code="import unreal\nunreal.log('move')",
            ),
        ]

        examples = select_prompt_examples("make radial array actor duplicates", tools, limit=2)

        self.assertEqual(len(examples), 2)
        self.assertEqual(examples[0].name, "Radial Array")
        self.assertTrue(all(example.code.startswith("import unreal") for example in examples))

    def test_generation_repair_prompt_contains_diagnostics(self) -> None:
        prompt = build_generation_repair_prompt(
            "Create snap tool",
            "bad python",
            ["Name is required.", "Syntax error at line 2"],
        )

        self.assertIn("Repair this EditorBinder Unreal Python tool response.", prompt)
        self.assertIn("Create snap tool", prompt)
        self.assertIn("Name is required.", prompt)
        self.assertIn("bad python", prompt)
        self.assertIn("<<<UUT_CODE>>>", prompt)

    def test_runtime_fix_prompt_contains_logs_code_and_compatibility(self) -> None:
        prompt = build_runtime_fix_prompt(
            "Snap actors down",
            "Snap Tool",
            "raw = unreal.SystemLibrary.line_trace_single(...)\nhit = raw.location",
            "Property 'Location' is protected and cannot be read",
            ["warning: Direct HitResult property access"],
            tool_type="Line Trace / HitResult",
        )

        self.assertIn("Runtime logs from Unreal:", prompt)
        self.assertIn("Property 'Location' is protected", prompt)
        self.assertIn("raw.location", prompt)
        self.assertIn("hit_result.to_tuple()", prompt)
        self.assertIn("warning: Direct HitResult property access", prompt)

    def test_fix_prompt_contains_error_tool_and_unreal_constraints(self) -> None:
        prompt = build_fix_prompt(
            "Broken Tool",
            "import unreal\nactor.is_pending_kill()",
            "AttributeError: 'Actor' object has no attribute 'is_pending_kill'",
        )

        self.assertIn("Fix this Unreal Engine Python Console tool.", prompt)
        self.assertIn("Return only the EditorBinder marker format.", prompt)
        self.assertIn("AttributeError", prompt)
        self.assertIn("Broken Tool", prompt)
        self.assertIn("actor.is_pending_kill()", prompt)
        self.assertIn("<<<UUT_NAME>>>", prompt)
        self.assertIn("<<<UUT_CODE>>>", prompt)
        self.assertIn("Use unreal.ScopedEditorTransaction for scene changes.", prompt)

    def test_fix_prompt_uses_error_placeholder_when_empty(self) -> None:
        prompt = build_fix_prompt("Tool", "import unreal", "")

        self.assertIn("[PASTE UNREAL PYTHON ERROR HERE]", prompt)


if __name__ == "__main__":
    unittest.main()
