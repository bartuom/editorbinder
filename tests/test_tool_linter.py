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

    def test_linter_detects_destroy_and_component_mutations(self) -> None:
        samples = [
            "actor.destroy_actor()\nunreal.log('done')",
            "mesh.set_material(0, material)\nunreal.log('done')",
            "component.set_collision_profile_name('BlockAll')\nunreal.log('done')",
            "actor.attach_to_actor(parent)\nunreal.log('done')",
        ]
        for code in samples:
            with self.subTest(code=code):
                issues = lint_tool_code(code)
                self.assertTrue(any(issue.title == "Missing editor transaction" for issue in issues))

    def test_comments_and_strings_do_not_trigger_or_suppress_transaction_warning(self) -> None:
        code = "# unreal.ScopedEditorTransaction('comment only')\nmessage = 'actor.destroy_actor()'\nactor.destroy_actor()\nunreal.log('done')"
        issues = lint_tool_code(code)
        self.assertTrue(any(issue.title == "Missing editor transaction" for issue in issues))

    def test_comments_and_strings_do_not_suppress_final_log_warning(self) -> None:
        code = "# unreal.log('comment only')\nmessage = 'unreal.log(\"not executable\")'\nactor.set_actor_label('renamed')"
        issues = lint_tool_code(code)
        self.assertTrue(any(issue.title == "No final log" for issue in issues))

    def test_hit_result_property_detection_ignores_unrelated_actor_location(self) -> None:
        code = "raw = unreal.SystemLibrary.line_trace_single(world, start, end, trace_type, False, [], draw_type, False)\nactor_location = actor.get_actor_location()\nunreal.log(str(actor_location))"
        issues = lint_tool_code(code)
        self.assertFalse(any(issue.title == "Direct HitResult property access" for issue in issues))

    def test_unreal_log_is_required_not_an_arbitrary_logger(self) -> None:
        issues = lint_tool_code("logger.log('done')")
        self.assertTrue(any(issue.title == "No final log" for issue in issues))

    def test_unrelated_transaction_method_does_not_suppress_warning(self) -> None:
        code = "transaction.ScopedEditorTransaction('not Unreal')\nactor.destroy_actor()\nunreal.log('done')"
        issues = lint_tool_code(code)
        self.assertTrue(any(issue.title == "Missing editor transaction" for issue in issues))


if __name__ == "__main__":
    unittest.main()
