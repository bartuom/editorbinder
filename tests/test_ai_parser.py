from __future__ import annotations

import unittest

from unreal_utility_tool.ai_parser import parse_ai_tool_response


class AiParserTests(unittest.TestCase):
    def test_parses_marker_format_response(self) -> None:
        parsed = parse_ai_tool_response(
            """some ignored intro
<<<UUT_NAME>>>
Randomize Mars Rocks
<<<UUT_NOTES>>>
min_scale and max_scale control the random range.
<<<UUT_CODE>>>
```python
# Param: min_scale | float | 1.0 | Min Scale
import unreal
min_scale = {{min_scale}}
```
<<<UUT_END>>>
ignored outro
"""
        )

        self.assertEqual(parsed.name, "Randomize Mars Rocks")
        self.assertEqual(parsed.notes, "min_scale and max_scale control the random range.")
        self.assertEqual(
            parsed.code,
            "# Param: min_scale | float | 1.0 | Min Scale\nimport unreal\nmin_scale = {{min_scale}}",
        )
        self.assertIn("found name", parsed.diagnostics)
        self.assertIn("found notes", parsed.diagnostics)
        self.assertIn("found code", parsed.diagnostics)
        self.assertIn("code syntax ok", parsed.diagnostics)

    def test_parses_marker_format_with_whitespace_around_markers_and_fence(self) -> None:
        parsed = parse_ai_tool_response(
            """AI intro that should be ignored.
   <<<UUT_NAME>>>
Offset Actors
  <<<UUT_NOTES>>>   
None
   <<<UUT_CODE>>>   
``` python
import unreal
unreal.log("ok")
```
   <<<UUT_END>>>   
Ignored outro.
"""
        )

        self.assertEqual(parsed.name, "Offset Actors")
        self.assertEqual(parsed.notes, "None")
        self.assertEqual(parsed.code, 'import unreal\nunreal.log("ok")')

    def test_parses_marker_format_without_end_marker(self) -> None:
        parsed = parse_ai_tool_response(
            """<<<UUT_NAME>>>
Offset Actors
<<<UUT_NOTES>>>
None
<<<UUT_CODE>>>
import unreal
unreal.log("ok")
"""
        )

        self.assertEqual(parsed.name, "Offset Actors")
        self.assertEqual(parsed.notes, "None")
        self.assertEqual(parsed.code, 'import unreal\nunreal.log("ok")')

    def test_ignores_text_after_end_marker(self) -> None:
        parsed = parse_ai_tool_response(
            """<<<UUT_NAME>>>
Offset Actors
<<<UUT_NOTES>>>
None
<<<UUT_CODE>>>
import unreal
unreal.log("ok")
<<<UUT_END>>>
This should not be imported as code.
import broken outro
"""
        )

        self.assertEqual(parsed.code, 'import unreal\nunreal.log("ok")')

    def test_marker_text_inside_python_string_does_not_end_code(self) -> None:
        parsed = parse_ai_tool_response(
            """<<<UUT_NAME>>>
Marker String Tool
<<<UUT_NOTES>>>
None
<<<UUT_CODE>>>
import unreal
message = "<<<UUT_END>>>"
unreal.log(message)
<<<UUT_END>>>
"""
        )

        self.assertEqual(
            parsed.code,
            'import unreal\nmessage = "<<<UUT_END>>>"\nunreal.log(message)',
        )
        self.assertIn("code syntax ok", parsed.diagnostics)

    def test_parses_structured_ai_response_with_fenced_code(self) -> None:
        parsed = parse_ai_tool_response(
            """Name: Select lights
Parameters / Notes: Change min_intensity if needed.
Code:
```python
import unreal
unreal.log("ok")
```
"""
        )

        self.assertEqual(parsed.name, "Select lights")
        self.assertEqual(parsed.notes, "Change min_intensity if needed.")
        self.assertEqual(parsed.code, 'import unreal\nunreal.log("ok")')

    def test_parses_structured_ai_response_with_python_label_but_no_fence(self) -> None:
        parsed = parse_ai_tool_response(
            """Name: Select lights
Parameters / Notes: None
Code:
python
import unreal
unreal.log("ok")
"""
        )

        self.assertEqual(parsed.name, "Select lights")
        self.assertEqual(parsed.notes, "None")
        self.assertEqual(parsed.code, 'import unreal\nunreal.log("ok")')

    def test_parses_plain_code_with_comment_name(self) -> None:
        parsed = parse_ai_tool_response(
            """# Tool: Print selected actors
import unreal
unreal.log("ok")
"""
        )

        self.assertEqual(parsed.name, "Print selected actors")
        self.assertEqual(parsed.code, '# Tool: Print selected actors\nimport unreal\nunreal.log("ok")')

    def test_parses_code_after_metadata_without_fence(self) -> None:
        parsed = parse_ai_tool_response(
            """Name: Rename actors
Notes: prefix = "SM_"
Code:
import unreal
prefix = "SM_"
unreal.log(prefix)
"""
        )

        self.assertEqual(parsed.name, "Rename actors")
        self.assertEqual(parsed.notes, 'prefix = "SM_"')
        self.assertTrue(parsed.code.startswith("import unreal"))

    def test_does_not_use_param_header_as_tool_name(self) -> None:
        parsed = parse_ai_tool_response(
            """# Param: use_selected_only | bool | True | Use Selected Actors Only
# Param: start_index | int | 1 | Start Index
import unreal
use_selected_only = True
"""
        )

        self.assertEqual(parsed.name, "")
        self.assertTrue(parsed.code.startswith("# Param: use_selected_only"))
        self.assertIn("missing name", parsed.diagnostics)

    def test_reports_syntax_error_in_diagnostics(self) -> None:
        parsed = parse_ai_tool_response(
            """Name: Broken
Code:
import unreal
if True
    unreal.log("broken")
"""
        )

        self.assertEqual(parsed.name, "Broken")
        self.assertTrue(any(item.startswith("code syntax error:") for item in parsed.diagnostics))


if __name__ == "__main__":
    unittest.main()
