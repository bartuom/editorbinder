from __future__ import annotations

import unittest

from unreal_utility_tool.ui.windowing import (
    DEFAULT_MIN_WINDOW_HEIGHT,
    DEFAULT_MIN_WINDOW_WIDTH,
    clamp_geometry_to_screen,
    is_valid_geometry,
)


class WindowingRecoveryTests(unittest.TestCase):
    def test_clamps_positive_offscreen_coordinates(self) -> None:
        result = clamp_geometry_to_screen("500x400+5000+5000", screen_width=1920, screen_height=1080)
        self.assertEqual(result, "500x400+1420+680")

    def test_clamps_negative_offscreen_coordinates(self) -> None:
        result = clamp_geometry_to_screen("500x400-3000-2000", screen_width=1920, screen_height=1080)
        self.assertEqual(result, "500x400+0+0")

    def test_clamps_mixed_negative_and_positive_offscreen(self) -> None:
        result = clamp_geometry_to_screen("500x400-500+2500", screen_width=1920, screen_height=1080)
        self.assertEqual(result, "500x400+0+680")

    def test_clamps_with_explicit_plus_minus_signs(self) -> None:
        result = clamp_geometry_to_screen("500x400+-3000+-2000", screen_width=1920, screen_height=1080)
        self.assertEqual(result, "500x400+0+0")

    def test_preserves_valid_on_screen_geometry(self) -> None:
        result = clamp_geometry_to_screen("500x400+100+120", screen_width=1920, screen_height=1080)
        self.assertEqual(result, "500x400+100+120")

    def test_preserves_boundary_on_screen_geometry(self) -> None:
        top_left = clamp_geometry_to_screen("500x400+0+0", screen_width=1920, screen_height=1080)
        self.assertEqual(top_left, "500x400+0+0")

        bottom_right = clamp_geometry_to_screen("500x400+1420+680", screen_width=1920, screen_height=1080)
        self.assertEqual(bottom_right, "500x400+1420+680")

    def test_window_larger_than_screen_is_bounded_to_screen(self) -> None:
        result = clamp_geometry_to_screen("2560x1440+500+500", screen_width=1920, screen_height=1080)
        self.assertEqual(result, "1920x1080+0+0")

    def test_invalid_geometry_strings_return_none(self) -> None:
        invalid_inputs = [
            "",
            "   ",
            "not_a_geometry",
            "500x",
            "x400",
            "+100+100",
            "500x400",
            "500x400+",
            "abcxdef+10+10",
        ]
        for item in invalid_inputs:
            with self.subTest(geometry=item):
                self.assertIsNone(clamp_geometry_to_screen(item, screen_width=1920, screen_height=1080))

    def test_dimensions_below_minimums_return_none(self) -> None:
        below_minimums = [
            "0x0+100+100",
            "100x100+100+100",
            f"{DEFAULT_MIN_WINDOW_WIDTH - 1}x400+100+100",
            f"500x{DEFAULT_MIN_WINDOW_HEIGHT - 1}+100+100",
        ]
        for item in below_minimums:
            with self.subTest(geometry=item):
                self.assertIsNone(clamp_geometry_to_screen(item, screen_width=1920, screen_height=1080))

    def test_screen_smaller_than_minimums_returns_none(self) -> None:
        self.assertIsNone(clamp_geometry_to_screen("500x400+100+100", screen_width=300, screen_height=200))
        self.assertIsNone(clamp_geometry_to_screen("500x400+100+100", screen_width=-1920, screen_height=1080))
        self.assertIsNone(clamp_geometry_to_screen("500x400+100+100", screen_width=1920, screen_height=0))

    def test_custom_min_width_and_height(self) -> None:
        result = clamp_geometry_to_screen(
            "200x200+5000+5000",
            screen_width=1920,
            screen_height=1080,
            min_width=150,
            min_height=150,
        )
        self.assertEqual(result, "200x200+1720+880")

    def test_is_valid_geometry_handles_positive_and_negative(self) -> None:
        self.assertTrue(is_valid_geometry("500x400+100+200"))
        self.assertTrue(is_valid_geometry("500x400-3000-2000"))
        self.assertTrue(is_valid_geometry("500x400+-3000+-2000"))
        self.assertFalse(is_valid_geometry("invalid"))
        self.assertFalse(is_valid_geometry(""))


if __name__ == "__main__":
    unittest.main()
