from __future__ import annotations

import unittest

from unreal_utility_tool.validation import validate_python_code, validate_tool_code, validate_tool_fields


class ValidationTests(unittest.TestCase):
    def test_valid_python_code_passes(self) -> None:
        result = validate_python_code("print('ok')\n")

        self.assertTrue(result.ok)
        self.assertEqual(result.message, "")

    def test_invalid_python_code_returns_line_and_column(self) -> None:
        result = validate_python_code("def broken(:\n    pass\n")

        self.assertFalse(result.ok)
        self.assertIn("Syntax error at line 1", result.message)
        self.assertIn("column", result.message)

    def test_tool_fields_require_name_and_code(self) -> None:
        errors = validate_tool_fields("", "")

        self.assertEqual(errors, ["Name is required.", "Code is required."])

    def test_tool_code_with_param_placeholders_passes_using_defaults(self) -> None:
        result = validate_tool_code("# Param: amount | int | 3 | Amount\namount = {{amount}}\n")

        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
