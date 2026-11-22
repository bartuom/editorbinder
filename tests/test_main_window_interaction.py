from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


@unittest.skipIf(importlib.util.find_spec("tkinter") is None, "tkinter is not installed")
class MainWindowInteractionTests(unittest.TestCase):
    def setUp(self) -> None:
        import tkinter as tk

        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"tkinter root window is unavailable on this runner: {exc}")
        self.root.withdraw()

    def tearDown(self) -> None:
        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass
        if hasattr(self, "app") and self.app is not None:
            for attr in (
                "_root_resize_after_id",
                "_list_resize_after_id",
                "_tool_wrap_refresh_after_id",
                "_details_sync_after_id",
                "_scroll_overscroll_after_id",
                "_filter_refresh_after_id",
                "_list_canvas_width_after_id",
                "_copy_feedback_after_id",
            ):
                after_id = getattr(self.app, attr, "")
                if after_id:
                    try:
                        self.root.after_cancel(after_id)
                    except Exception:
                        pass
                    setattr(self.app, attr, "")
        try:
            self.root.destroy()
        except Exception:
            pass

    def _create_app(self, temp_dir: str):
        from unreal_utility_tool.settings import AppSettingsStore
        from unreal_utility_tool.storage import ToolLibraryStore
        from unreal_utility_tool.ui.main_window import UnrealUtilityApp

        store = ToolLibraryStore(Path(temp_dir) / "tools.json")
        settings_store = AppSettingsStore(Path(temp_dir) / "settings.json")
        seed_path = Path(__file__).resolve().parents[1] / "data" / "tools.json"
        store.save_tools(ToolLibraryStore(seed_path).load_tools())
        self.app = UnrealUtilityApp(self.root, store, settings_store=settings_store)
        return self.app


    def _create_app_with_saved_geometry(self, temp_dir: str, geometry: str):
        from unreal_utility_tool.settings import AppSettingsStore
        from unreal_utility_tool.storage import ToolLibraryStore
        from unreal_utility_tool.ui.main_window import UnrealUtilityApp

        root = Path(temp_dir)
        store = ToolLibraryStore(root / "tools.json")
        settings_path = root / "settings.json"
        settings_path.write_text(json.dumps({"geometry": geometry}), encoding="utf-8")
        settings_store = AppSettingsStore(settings_path)
        seed_path = Path(__file__).resolve().parents[1] / "data" / "tools.json"
        store.save_tools(ToolLibraryStore(seed_path).load_tools())
        self.app = UnrealUtilityApp(self.root, store, settings_store=settings_store)
        return self.app

    def test_startup_recovers_saved_geometry_to_current_monitor_work_area(self) -> None:
        screen_width = int(self.root.winfo_screenwidth())
        screen_height = int(self.root.winfo_screenheight())
        work_area = (0, 0, screen_width, screen_height)
        expected = f"500x400+{max(0, screen_width - 500)}+{max(0, screen_height - 400)}"
        with TemporaryDirectory() as temp_dir:
            with patch(
                "unreal_utility_tool.ui.main_window._monitor_work_area_for_widget",
                return_value=work_area,
            ):
                app = self._create_app_with_saved_geometry(temp_dir, "500x400+5000+5000")

            self.assertEqual(app.root.geometry(), expected)

    def test_compact_tool_row_button_exempt_from_keyboard_control_focus(self) -> None:
        import tkinter as tk

        with TemporaryDirectory() as temp_dir:
            app = self._create_app(temp_dir)
            self.assertGreaterEqual(len(app.filtered_tools), 2)

            tool1 = app.filtered_tools[1]
            card_btn = app.tool_card_widgets[tool1.id]["card"]
            self.assertIsInstance(card_btn, tk.Button)

            # Compact card button is recognized and exempt from keyboard control focus
            self.assertTrue(app._is_tool_row_card_button(card_btn))
            self.assertFalse(app._is_keyboard_control_focus(card_btn))

            # Form inputs like search_entry are still treated as keyboard control focus
            self.assertFalse(app._is_tool_row_card_button(app.search_entry))
            self.assertTrue(app._is_keyboard_control_focus(app.search_entry))

            generic_entry = tk.Entry(self.root)
            self.assertTrue(app._is_keyboard_control_focus(generic_entry))

    def test_keyboard_navigation_shortcuts_on_compact_tool_row_button(self) -> None:
        import tkinter as tk

        with TemporaryDirectory() as temp_dir:
            app = self._create_app(temp_dir)
            self.assertGreaterEqual(len(app.filtered_tools), 3)

            tool0 = app.filtered_tools[0]
            tool1 = app.filtered_tools[1]
            tool2 = app.filtered_tools[2]

            self.assertEqual(app.current_tool_id, tool0.id)
            tool1_btn = app.tool_card_widgets[tool1.id]["card"]

            # Clicking the compact button selects it and focuses it
            tool1_btn.invoke()
            self.assertEqual(app.current_tool_id, tool1.id)

            # 1. <Down> shortcut from compact tool row button moves selection down to tool 2
            ev_down = tk.Event()
            ev_down.widget = tool1_btn
            res_down = app._select_next_tool_shortcut(ev_down)
            self.assertEqual(res_down, "break")
            self.assertEqual(app.current_tool_id, tool2.id)

            # 2. <Up> shortcut moves selection back up to tool 1
            ev_up = tk.Event()
            ev_up.widget = app.root
            res_up = app._select_previous_tool_shortcut(ev_up)
            self.assertEqual(res_up, "break")
            self.assertEqual(app.current_tool_id, tool1.id)

            # 3. <Return> shortcut copies the tool
            copied: list[str] = []
            with patch.object(app, "_copy_code", side_effect=lambda tid: copied.append(tid)):
                ev_return = tk.Event()
                ev_return.widget = tool1_btn
                res_return = app._copy_selected_shortcut(ev_return)
                self.assertEqual(res_return, "break")
                self.assertEqual(copied, [tool1.id])

            # 4. <space> shortcut focuses/toggles parameters
            with patch.object(app, "_focus_selected_param") as mock_focus:
                ev_space = tk.Event()
                ev_space.widget = tool1_btn
                res_space = app._toggle_selected_params_shortcut(ev_space)
                self.assertEqual(res_space, "break")
                self.assertTrue(mock_focus.called)

            # 5. <Delete> shortcut invokes tool deletion
            deleted: list[str] = []
            with patch.object(app, "_delete_tool", side_effect=lambda tid: deleted.append(tid)):
                ev_del = tk.Event()
                ev_del.widget = tool1_btn
                res_del = app._delete_selected_shortcut(ev_del)
                self.assertEqual(res_del, "break")
                self.assertEqual(deleted, [tool1.id])

    def test_form_entry_focus_blocks_outliner_shortcuts(self) -> None:
        import tkinter as tk

        with TemporaryDirectory() as temp_dir:
            app = self._create_app(temp_dir)
            ev = tk.Event()
            ev.widget = app.search_entry

            # When focus is in search entry, list navigation and activation shortcuts must be blocked (return None)
            self.assertIsNone(app._select_next_tool_shortcut(ev))
            self.assertIsNone(app._select_previous_tool_shortcut(ev))
            self.assertIsNone(app._copy_selected_shortcut(ev))
            self.assertIsNone(app._delete_selected_shortcut(ev))
            self.assertIsNone(app._toggle_selected_params_shortcut(ev))

    def test_numeric_field_click_and_drag_selection_without_scrubbing(self) -> None:
        import tkinter as tk
        from unreal_utility_tool.params import ToolParam
        from unreal_utility_tool.ui.main_window import UnrealNumericField

        self.root.deiconify()
        self.root.update_idletasks()
        self.root.update()

        param = ToolParam(name="width", kind="int", default="100", label="Width")
        var = tk.StringVar(value="100")
        validated: list[bool] = []
        field = UnrealNumericField(
            self.root,
            param=param,
            variable=var,
            on_validate=lambda save=False: validated.append(save),
        )
        field.pack()
        self.root.update()

        # Normal click on entry does not scrub
        field.entry.event_generate("<Button-1>", x=10, y=10)
        field.entry.event_generate("<ButtonRelease-1>", x=10, y=10)
        self.root.update()
        self.assertEqual(var.get(), "100")
        self.assertEqual(len(validated), 0)

        # Normal horizontal drag on entry (>4px) selects text and does NOT scrub
        field.entry.event_generate("<Button-1>", x=5, y=10)
        field.entry.event_generate("<B1-Motion>", x=45, y=10)
        field.entry.event_generate("<ButtonRelease-1>", x=45, y=10)
        self.root.update()
        self.assertEqual(var.get(), "100")
        self.assertTrue(field.entry.selection_present())
        self.assertEqual(len(validated), 0)

    def test_numeric_field_modifier_gated_scrubbing(self) -> None:
        import tkinter as tk
        from unreal_utility_tool.params import ToolParam
        from unreal_utility_tool.ui.main_window import UnrealNumericField

        self.root.deiconify()
        self.root.update_idletasks()
        self.root.update()

        param = ToolParam(name="count", kind="int", default="50", label="Count")
        var = tk.StringVar(value="50")
        validated: list[bool] = []
        field = UnrealNumericField(
            self.root,
            param=param,
            variable=var,
            on_validate=lambda save=False: validated.append(save),
        )
        field.pack()
        self.root.update()

        # Alt drag scrubs value and prevents text selection
        field.entry.selection_clear()
        field.entry.event_generate("<Button-1>", x=10, y=10, state=0x20000)
        field.entry.event_generate("<B1-Motion>", x=46, y=10, state=0x20000 | 0x0100)
        field.entry.event_generate("<ButtonRelease-1>", x=46, y=10, state=0x20000)
        self.root.update()

        alt_drag_val = int(var.get())
        self.assertGreater(alt_drag_val, 50)
        self.assertFalse(field.entry.selection_present())
        self.assertGreaterEqual(len(validated), 1)

        # Ctrl drag also scrubs value
        field.entry.selection_clear()
        val_before_ctrl = int(var.get())
        field.entry.event_generate("<Button-1>", x=10, y=10, state=0x0004)
        field.entry.event_generate("<B1-Motion>", x=46, y=10, state=0x0004 | 0x0100)
        field.entry.event_generate("<ButtonRelease-1>", x=46, y=10, state=0x0004)
        self.root.update()

        ctrl_drag_val = int(var.get())
        self.assertGreater(ctrl_drag_val, val_before_ctrl)
        self.assertFalse(field.entry.selection_present())

    def test_numeric_field_axis_indicator_and_bound_widget_scrub_without_modifier(self) -> None:
        import tkinter as tk
        from unreal_utility_tool.params import ToolParam
        from unreal_utility_tool.ui.main_window import UnrealNumericField

        self.root.deiconify()
        self.root.update_idletasks()
        self.root.update()

        param = ToolParam(name="coord_x", kind="int", default="0", label="X")
        var = tk.StringVar(value="0")
        field = UnrealNumericField(
            self.root,
            param=param,
            variable=var,
            on_validate=lambda save=False: None,
            axis_color="#ff4444",
        )
        external_label = tk.Label(self.root, text="X:")
        external_label.pack()
        field.bind_scrub_widget(external_label)
        field.pack()
        self.root.update()

        # Drag on axis indicator directly scrubs without modifier keys
        self.assertIsNotNone(field.axis_indicator)
        field.axis_indicator.event_generate("<Button-1>", x=1, y=10)
        field.axis_indicator.event_generate("<B1-Motion>", x=40, y=10)
        field.axis_indicator.event_generate("<ButtonRelease-1>", x=40, y=10)
        self.root.update()
        self.assertGreater(int(var.get()), 0)

        # Drag on bound external label directly scrubs without modifier keys
        val_before = int(var.get())
        external_label.event_generate("<Button-1>", x=2, y=10)
        external_label.event_generate("<B1-Motion>", x=42, y=10)
        external_label.event_generate("<ButtonRelease-1>", x=42, y=10)
        self.root.update()
        self.assertGreater(int(var.get()), val_before)

    def test_close_cancels_copy_feedback_and_scroll_animation_callbacks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = self._create_app(temp_dir)
            tool = app.filtered_tools[0]
            app._show_copy_feedback(tool.id, tool.name)
            copy_after_id = app._copy_feedback_after_id
            scroll_after_id = app.root.after(60000, lambda: None)
            app._scroll_overscroll_after_id = scroll_after_id
            cancelled: list[str] = []
            original_after_cancel = app.root.after_cancel

            def record_after_cancel(after_id: str) -> None:
                cancelled.append(after_id)
                original_after_cancel(after_id)

            app.root.after_cancel = record_after_cancel
            app._close()

            self.assertIn(copy_after_id, cancelled)
            self.assertIn(scroll_after_id, cancelled)
            self.assertEqual(app._copy_feedback_after_id, "")
            self.assertEqual(app._scroll_overscroll_after_id, "")


if __name__ == "__main__":
    unittest.main()
