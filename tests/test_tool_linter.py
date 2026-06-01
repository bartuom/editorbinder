from __future__ import annotations

import unittest

from unreal_utility_tool.tool_linter import has_warning_or_error, lint_summary, lint_tool_code


class ToolLinterTests(unittest.TestCase):
    def test_linter_flags_trace_without_hitresult_to_tuple(self) -> None:
        code = """
import unreal
raw = unreal.SystemLibrary.line_trace_single(world, start, end, trace_type, False, [], draw_type, False)
if raw[0]:
    hit = raw[1]
    point = hit.impact_point
"""

        issues = lint_tool_code(code)

        self.assertTrue(has_warning_or_error(code))
        self.assertTrue(any(issue.title == "Risky HitResult handling" for issue in issues))
        self.assertTrue(any(issue.title == "Direct HitResult property access" for issue in issues))
        self.assertTrue(any(issue.title == "Tuple-only trace result handling" for issue in issues))

    def test_linter_accepts_trace_with_tuple_helper(self) -> None:
        code = """
import unreal
def hit_tuple(hit_result):
    return hit_result.to_tuple()
def hit_location(hit_result):
    values = hit_tuple(hit_result)
    return values[5]
raw = unreal.SystemLibrary.line_trace_single(world, start, end, trace_type, False, [], draw_type, False)
hit = raw
point = hit_location(hit)
unreal.log(f"point={point}")
"""

        issues = lint_tool_code(code)

        self.assertFalse(any(issue.title == "Risky HitResult handling" for issue in issues))
        self.assertIn("Troubleshooting:", lint_summary(code))

    def test_linter_flags_movement_without_old_target_new_diagnostics(self) -> None:
        code = """
import unreal
with unreal.ScopedEditorTransaction("Move"):
    actor.set_actor_location(unreal.Vector(0, 0, 0), False, False)
unreal.log("done")
"""

        issues = lint_tool_code(code)

        self.assertTrue(any(issue.title == "Move verification missing" for issue in issues))


if __name__ == "__main__":
    unittest.main()
