from __future__ import annotations

import importlib.util
import unittest


@unittest.skipIf(importlib.util.find_spec("tkinter") is None, "tkinter is not installed")
class WindowingTests(unittest.TestCase):
    def test_dialog_geometry_stays_inside_right_hand_monitor_work_area(self) -> None:
        from unreal_utility_tool.tk_app import _compute_dialog_geometry

        width, height, x, y = _compute_dialog_geometry(
            parent_x=3700,
            parent_y=120,
            parent_width=420,
            parent_height=500,
            work_area=(1920, 0, 3840, 1040),
        )

        self.assertGreaterEqual(x, 1936)
        self.assertLessEqual(x + width, 3824)
        self.assertGreaterEqual(y, 16)
        self.assertLessEqual(y + height, 1024)

    def test_dialog_geometry_stays_inside_left_hand_monitor_work_area(self) -> None:
        from unreal_utility_tool.tk_app import _compute_dialog_geometry

        width, height, x, y = _compute_dialog_geometry(
            parent_x=-1200,
            parent_y=120,
            parent_width=420,
            parent_height=500,
            work_area=(-1920, 0, 0, 1040),
        )

        self.assertGreaterEqual(x, -1904)
        self.assertLessEqual(x + width, -16)
        self.assertGreaterEqual(y, 16)
        self.assertLessEqual(y + height, 1024)

    def test_dialog_geometry_clamps_above_work_area(self) -> None:
        from unreal_utility_tool.tk_app import _compute_dialog_geometry

        _width, _height, _x, y = _compute_dialog_geometry(
            parent_x=120,
            parent_y=-200,
            parent_width=420,
            parent_height=320,
            work_area=(0, 0, 1920, 1040),
        )

        self.assertEqual(y, 16)

    def test_dialog_geometry_without_work_area_uses_centered_position(self) -> None:
        from unreal_utility_tool.tk_app import _compute_dialog_geometry

        width, height, x, y = _compute_dialog_geometry(
            parent_x=100,
            parent_y=200,
            parent_width=500,
            parent_height=400,
            work_area=None,
        )

        self.assertEqual((width, height), (860, 640))
        self.assertEqual((x, y), (-80, 80))

    def test_source_icon_file_is_available(self) -> None:
        from unreal_utility_tool.tk_app import resolve_app_icon_path

        icon_path = resolve_app_icon_path()

        self.assertIsNotNone(icon_path)
        self.assertEqual(icon_path.name, "editorbinder.ico")
        self.assertGreater(icon_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
