from __future__ import annotations

import unittest

from unreal_utility_tool.theme import (
    ACCENT_DARK,
    DANGER,
    DANGER_HOVER,
    PANEL_BG_ALT,
    SUCCESS,
    TEXT,
    contrast_ratio,
    relative_luminance,
)


class ThemeContrastTests(unittest.TestCase):
    def test_relative_luminance_extremes(self) -> None:
        self.assertAlmostEqual(relative_luminance("#000000"), 0.0, places=4)
        self.assertAlmostEqual(relative_luminance("#ffffff"), 1.0, places=4)
        self.assertAlmostEqual(relative_luminance("#000"), 0.0, places=4)
        self.assertAlmostEqual(relative_luminance("#fff"), 1.0, places=4)

    def test_contrast_ratio_extremes(self) -> None:
        self.assertAlmostEqual(contrast_ratio("#ffffff", "#000000"), 21.0, places=1)
        self.assertAlmostEqual(contrast_ratio("#000000", "#ffffff"), 21.0, places=1)
        self.assertAlmostEqual(contrast_ratio("#123456", "#123456"), 1.0, places=4)

    def test_danger_button_contrast_meets_wcag_aa(self) -> None:
        ratio = contrast_ratio(DANGER, TEXT)
        self.assertGreaterEqual(
            ratio,
            4.5,
            f"DANGER button background ({DANGER}) with TEXT ({TEXT}) has contrast {ratio:.2f}:1, expected >= 4.5:1",
        )

    def test_danger_hover_button_contrast_meets_wcag_aa(self) -> None:
        ratio = contrast_ratio(DANGER_HOVER, TEXT)
        self.assertGreaterEqual(
            ratio,
            4.5,
            f"DANGER_HOVER button background ({DANGER_HOVER}) with TEXT ({TEXT}) has contrast {ratio:.2f}:1, expected >= 4.5:1",
        )

    def test_primary_and_secondary_button_contrast_meets_wcag_aa(self) -> None:
        primary_ratio = contrast_ratio(ACCENT_DARK, TEXT)
        self.assertGreaterEqual(primary_ratio, 4.5)

        secondary_ratio = contrast_ratio(PANEL_BG_ALT, TEXT)
        self.assertGreaterEqual(secondary_ratio, 4.5)

        success_ratio = contrast_ratio(SUCCESS, "#101510")
        self.assertGreaterEqual(success_ratio, 4.5)


if __name__ == "__main__":
    unittest.main()
