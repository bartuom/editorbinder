from __future__ import annotations

import unittest

from unreal_utility_tool.ui.editor_dialog import _parse_float


class EditorDialogValidationTests(unittest.TestCase):
    def test_temperature_parser_clamps_to_provider_range(self) -> None:
        self.assertEqual(_parse_float("-5", default=0.2), 0.0)
        self.assertEqual(_parse_float("100", default=0.2), 2.0)
        self.assertEqual(_parse_float("1.25", default=0.2), 1.25)
        self.assertEqual(_parse_float("1,5", default=0.2), 1.5)

    def test_temperature_parser_rejects_non_finite_and_invalid_values(self) -> None:
        for value in ("nan", "inf", "-inf", "not a number", ""):
            with self.subTest(value=value):
                self.assertEqual(_parse_float(value, default=0.2), 0.2)


if __name__ == "__main__":
    unittest.main()
