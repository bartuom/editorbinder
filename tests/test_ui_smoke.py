from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory


def _walk_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk_widgets(child)


@unittest.skipIf(importlib.util.find_spec("tkinter") is None, "tkinter is not installed")
class UiSmokeTests(unittest.TestCase):
    def test_main_window_constructs_with_seed_data(self) -> None:
        import tkinter as tk

        from unreal_utility_tool.models import CATEGORY_CUSTOM, CATEGORY_TRANSFORM, Tool
        from unreal_utility_tool import __version__
        from unreal_utility_tool.params import parse_tool_params
        from unreal_utility_tool.settings import AppSettingsStore
        from unreal_utility_tool.storage import ToolLibraryStore
        from unreal_utility_tool.tool_importer import IMPORT_POLICY_SKIP
        from unreal_utility_tool.tk_app import (
            ACCENT,
            MUTED,
            ToolEditorDialog,
            UnrealNumericField,
            UnrealUtilityApp,
            _group_tool_params,
            _layout_spec_for_width,
            _step_numeric_value,
        )
        from unreal_utility_tool.theme import ACCENT_DARK, SUCCESS, WARNING
        import unreal_utility_tool.ui.main_window as main_window_module

        with TemporaryDirectory() as temp_dir:
            store = ToolLibraryStore(Path(temp_dir) / "tools.json")
            settings_store = AppSettingsStore(Path(temp_dir) / "settings.json")
            seed_path = Path(__file__).resolve().parents[1] / "data" / "tools.json"
            store.save_tools(ToolLibraryStore(seed_path).load_tools())
            try:
                root = tk.Tk()
            except tk.TclError as exc:
                self.skipTest(f"tkinter root window is unavailable on this runner: {exc}")
            root.withdraw()
            try:
                app = UnrealUtilityApp(root, store, settings_store=settings_store)

                self.assertEqual(app.root.title(), "EditorBinder")
                self.assertGreater(len(app.filtered_tools), 0)
                self.assertGreater(len(app.tool_rows), 0)
                self.assertEqual(app.current_tool_id, app.filtered_tools[0].id)
                self.assertEqual(app.expanded_tool_id, app.current_tool_id)
                self.assertEqual(app.status_var.get(), "Ready")
                self.assertEqual(app.library_button.cget("text"), "Library")
                self.assertTrue(hasattr(app, "outliner_table_header"))
                self.assertTrue(hasattr(app, "splitter"))
                self.assertFalse(app.header_frame.grid_info())
                self.assertFalse(app.outliner_filter_row.grid_info())
                self.assertFalse(app.outliner_table_header.grid_info())
                self.assertEqual(app.count_var.get(), f"{len(app.filtered_tools)} recommended tools")
                self.assertTrue(hasattr(app, "details_panel"))
                self.assertTrue(hasattr(app, "details_inner"))
                self.assertEqual(app.outliner_panel.grid_info()["row"], 0)
                self.assertFalse(app.splitter.grid_info())
                self.assertFalse(app.details_panel.grid_info())
                list_text = " ".join(
                    child.cget("text")
                    for child in _walk_widgets(app.list_inner)
                    if "text" in child.keys()
                )
                self.assertIn(app.filtered_tools[0].name, list_text)
                self.assertIn("Copy", list_text)
                self.assertIn(app.current_tool_id, app.param_values)
                self.assertGreater(len(app.param_input_widgets.get(app.current_tool_id, {})), 0)
                first_refs = app.tool_card_widgets[app.current_tool_id]
                self.assertEqual(first_refs["category_badge"].cget("text"), app.filtered_tools[0].category)
                self.assertEqual(first_refs["selected_marker"].cget("text"), "▾")
                self.assertTrue(root.bind("<Control-n>"))
                self.assertTrue(root.bind("<Control-f>"))
                self.assertTrue(root.bind("<Return>"))
                self.assertTrue(root.bind("<space>"))
                self.assertTrue(root.bind("<Delete>"))
                self.assertTrue(root.bind("<Up>"))
                self.assertTrue(root.bind("<Down>"))
                self.assertTrue(root.bind_all("<ButtonPress-1>"))
                self.assertTrue(root.bind_all("<B1-Motion>"))
                self.assertTrue(root.bind_all("<ButtonRelease-1>"))
                self.assertTrue(root.bind_all("<ButtonPress-3>"))
                self.assertTrue(root.bind_all("<B3-Motion>"))
                self.assertTrue(root.bind_all("<ButtonRelease-3>"))
                self.assertEqual(app.category_var.get(), "All")
                self.assertEqual(app.category_combo.cget("style"), "Dark.TCombobox")
                self.assertIn(CATEGORY_TRANSFORM, app.category_combo.cget("values"))
                app.category_var.set(CATEGORY_TRANSFORM)
                app._refresh_list()
                self.assertGreater(len(app.filtered_tools), 0)
                self.assertTrue(all(tool.category == CATEGORY_TRANSFORM for tool in app.filtered_tools))
                app.category_var.set("All")
                app._refresh_list()
                app._set_outliner_filter_tab(CATEGORY_TRANSFORM)
                self.assertEqual(app.category_var.get(), CATEGORY_TRANSFORM)
                app._set_outliner_filter_tab("All")
                self.assertEqual(app.category_var.get(), "All")

                for width, height, expected_mode, expected_add_text in [
                    (380, 320, "compact", "Add Tool"),
                    (420, 500, "compact", "Add Tool"),
                    (520, 700, "normal", "Add Tool"),
                ]:
                    root.geometry(f"{width}x{height}")
                    root.update_idletasks()
                    spec = _layout_spec_for_width(width)
                    app._apply_layout_spec(spec)
                    app._rebuild_tool_rows()

                    self.assertEqual(spec.mode, expected_mode)
                    self.assertEqual(app.add_button.cget("text"), expected_add_text)
                    self.assertEqual(int(app.header_frame.cget("padx")), spec.outer_pad_x)
                    self.assertEqual(int(app.search_entry.grid_info()["ipady"]), max(spec.search_ipady, 2))
                    self.assertEqual(app.list_canvas.grid_info()["sticky"], "nesw")
                    if len(app.tool_rows) > 1:
                        self.assertLessEqual(app.tool_rows[1].winfo_reqheight(), 72)

                app.always_top_var.set(True)
                app._toggle_always_top()
                self.assertEqual(bool(root.attributes("-topmost")), True)
                app.always_top_var.set(False)
                app._toggle_always_top()
                self.assertEqual(bool(root.attributes("-topmost")), False)
                self.assertFalse(app.splitter.grid_info())
                self.assertFalse(app.details_panel.grid_info())
                app._cancel_after("_tool_wrap_refresh_after_id")
                app._cancel_after("_list_resize_after_id")
                app._cancel_after("_list_canvas_width_after_id")
                app._last_layout_mode = app._layout_spec(root.winfo_width()).mode
                app._last_canvas_width = 20
                app._on_list_canvas_configure(SimpleNamespace(width=170))
                self.assertEqual(app._list_resize_after_id, "")
                self.assertNotEqual(app._list_canvas_width_after_id, "")
                self.assertNotEqual(app._tool_wrap_refresh_after_id, "")
                app._cancel_after("_list_canvas_width_after_id")
                app._cancel_after("_tool_wrap_refresh_after_id")
                app._on_root_configure(SimpleNamespace(widget=root, width=700))
                first_resize_job = app._root_resize_after_id
                app._on_root_configure(SimpleNamespace(widget=root, width=710))
                self.assertNotEqual(app._root_resize_after_id, "")
                self.assertNotEqual(app._root_resize_after_id, first_resize_job)
                app._cancel_after("_root_resize_after_id")
                opened_paths = []
                original_startfile = getattr(main_window_module.os, "startfile", None)
                try:
                    main_window_module.os.startfile = lambda path: opened_paths.append(Path(path))
                    app._open_data_folder()
                    app._open_license()
                    app._open_changelog()
                    app._open_settings_file()
                finally:
                    if original_startfile is None:
                        delattr(main_window_module.os, "startfile")
                    else:
                        main_window_module.os.startfile = original_startfile
                self.assertEqual(
                    opened_paths,
                    [
                        store.path.parent,
                        main_window_module.app_root() / "LICENSE.txt",
                        main_window_module.app_root() / "CHANGELOG.md",
                        settings_store.path,
                    ],
                )
                self.assertTrue(settings_store.path.exists())
                self.assertEqual(app.status_var.get(), "Opened settings file")
                self.assertIn("Created by Bartosz Rozmus", app._about_text())
                self.assertIn("not affiliated with, endorsed by, or sponsored by Epic Games", app._about_text())
                app._copy_app_info()
                app_info = root.clipboard_get()
                self.assertIn(f"EditorBinder {__version__}", app_info)
                self.assertIn("Author: Bartosz Rozmus", app_info)
                self.assertIn(str(store.path.parent), app_info)
                self.assertEqual(app.status_var.get(), "Copied app info")
                info_calls = []
                original_showinfo = main_window_module.messagebox.showinfo
                try:
                    main_window_module.messagebox.showinfo = (
                        lambda title, message, **kwargs: info_calls.append((title, message, kwargs))
                    )
                    app._show_app_info()
                finally:
                    main_window_module.messagebox.showinfo = original_showinfo
                self.assertEqual(info_calls[0][0], "EditorBinder")
                self.assertIn("Library:", info_calls[0][1])
                self.assertIn(str(store.path), info_calls[0][1])
                self.assertIn("Settings:", info_calls[0][1])
                self.assertIn(str(settings_store.path), info_calls[0][1])

                app._select_tool(app.filtered_tools[0].id)
                first_keyboard_id = app.current_tool_id
                self.assertEqual(first_keyboard_id, app.filtered_tools[0].id)
                self.assertEqual(app._select_next_tool_shortcut(SimpleNamespace(widget=root)), "break")
                self.assertEqual(app.current_tool_id, app.filtered_tools[1].id)
                self.assertEqual(app._select_previous_tool_shortcut(SimpleNamespace(widget=root)), "break")
                self.assertEqual(app.current_tool_id, first_keyboard_id)
                self.assertEqual(app._select_next_tool_shortcut(SimpleNamespace(widget=app.search_entry)), None)
                self.assertEqual(app.current_tool_id, first_keyboard_id)
                select_rebuild_count = 0
                original_rebuild = app._rebuild_tool_rows

                def counted_select_rebuild():
                    nonlocal select_rebuild_count
                    select_rebuild_count += 1
                    original_rebuild()

                app._rebuild_tool_rows = counted_select_rebuild
                try:
                    app._select_tool(app.filtered_tools[1].id)
                finally:
                    app._rebuild_tool_rows = original_rebuild
                self.assertEqual(select_rebuild_count, 0)
                self.assertEqual(app.current_tool_id, app.filtered_tools[1].id)
                app._select_tool(first_keyboard_id)
                first_row_before_toggle = app.tool_row_by_id[first_keyboard_id]
                toggle_rebuild_count = 0
                original_rebuild = app._rebuild_tool_rows

                def counted_toggle_rebuild():
                    nonlocal toggle_rebuild_count
                    toggle_rebuild_count += 1
                    original_rebuild()

                app._rebuild_tool_rows = counted_toggle_rebuild
                try:
                    self.assertEqual(app._toggle_selected_params_shortcut(SimpleNamespace(widget=root)), "break")
                    self.assertEqual(app.expanded_tool_id, first_keyboard_id)
                    self.assertEqual(app._toggle_selected_params_shortcut(SimpleNamespace(widget=root)), "break")
                    self.assertEqual(app.expanded_tool_id, first_keyboard_id)
                finally:
                    app._rebuild_tool_rows = original_rebuild
                self.assertEqual(toggle_rebuild_count, 0)
                self.assertIs(app.tool_row_by_id[first_keyboard_id], first_row_before_toggle)
                rebuild_count = 0

                def counted_rebuild():
                    nonlocal rebuild_count
                    rebuild_count += 1
                    original_rebuild()

                app._rebuild_tool_rows = counted_rebuild
                try:
                    self.assertEqual(app._copy_selected_shortcut(SimpleNamespace(widget=root)), "break")
                finally:
                    app._rebuild_tool_rows = original_rebuild
                self.assertEqual(rebuild_count, 0)
                self.assertIn("Copied:", app.status_var.get())
                self.assertEqual(app.copy_feedback_tool_id, first_keyboard_id)
                self.assertEqual(app.copy_button_by_tool_id[first_keyboard_id].cget("text"), "Copied")
                self.assertTrue(root.clipboard_get().strip())
                app._clear_copy_feedback(app._copy_feedback_token)
                self.assertEqual(app.copy_feedback_tool_id, "")
                self.assertEqual(app.copy_button_by_tool_id[first_keyboard_id].cget("text"), "Copy")
                self.assertEqual(app.copy_button_by_tool_id[first_keyboard_id].cget("bg"), SUCCESS)

                transform_tool_id = next(
                    tool.id for tool in app.filtered_tools if tool.name == "Transform Selected Actors"
                )
                app._select_tool(transform_tool_id)
                self.assertEqual(app.current_tool_id, transform_tool_id)
                self.assertEqual(app.expanded_tool_id, transform_tool_id)
                self.assertIn(transform_tool_id, app.param_values)
                self.assertIn("offset_x", app.param_values[transform_tool_id])
                self.assertEqual(app.param_values[transform_tool_id]["offset_x"].get(), "0")
                second_tool_id = app.filtered_tools[1].id
                app._select_tool(second_tool_id)
                self.assertEqual(app.current_tool_id, second_tool_id)
                self.assertEqual(app.expanded_tool_id, second_tool_id)
                app._toggle_favorite(second_tool_id)
                self.assertEqual(app.filtered_tools[0].id, second_tool_id)
                self.assertTrue(app.filtered_tools[0].id in app._favorite_ids())

                typed_tool = Tool.create(
                    name="Typed Params",
                    description="",
                    tags=[],
                    category=CATEGORY_CUSTOM,
                    code=(
                        "# Param: enabled | bool | False | Enabled\n"
                        "# Param: count | int | 2 | Count | min=1 | max=5 | step=2\n"
                        "# Param: scale | float | 0.5 | Scale | min=0.1 | max=1.0 | step=0.1\n"
                        "# Param: mode | enum | selected | Mode | options=selected,all\n"
                        "# Param: folder_path | path | Environment/Props | Folder Path\n"
                        "enabled = {{enabled}}\n"
                        "count = {{count}}\n"
                        "scale = {{scale}}\n"
                        "mode = {{mode}}\n"
                        "folder_path = {{folder_path}}\n"
                    ),
                )
                app.tools.append(typed_tool)
                app.current_tool_id = typed_tool.id
                app.expanded_tool_id = typed_tool.id
                app._refresh_list()
                app.category_var.set(CATEGORY_CUSTOM)
                app._refresh_list()
                self.assertIn(typed_tool.id, {tool.id for tool in app.filtered_tools})
                app.category_var.set("All")
                app._refresh_list()
                typed_params = parse_tool_params(typed_tool.code)
                typed_groups = _group_tool_params(typed_params)
                self.assertEqual([group.kind for group in typed_groups], ["single", "single", "single", "single", "single"])
                self.assertEqual(typed_groups[2].label, "Scale")
                vector_groups = _group_tool_params(parse_tool_params(
                    "# Param: offset_x | float | 0 | X Offset\n"
                    "# Param: offset_y | float | 0 | Y Offset\n"
                    "# Param: offset_z | float | 0 | Z Offset\n"
                ))
                self.assertEqual(len(vector_groups), 1)
                self.assertEqual(vector_groups[0].kind, "vector")
                self.assertEqual(vector_groups[0].label, "Location")
                range_groups = _group_tool_params(parse_tool_params(
                    "# Param: min_yaw | float | -15 | Min Yaw\n"
                    "# Param: max_yaw | float | 15 | Max Yaw\n"
                ))
                self.assertEqual(len(range_groups), 1)
                self.assertEqual(range_groups[0].kind, "range")
                self.assertEqual(range_groups[0].label, "Rotation")
                incomplete_groups = _group_tool_params(parse_tool_params(
                    "# Param: offset_x | float | 0 | X Offset\n"
                    "# Param: offset_y | float | 0 | Y Offset\n"
                ))
                self.assertEqual([group.kind for group in incomplete_groups], ["single", "single"])
                self.assertEqual(_step_numeric_value(typed_params[1], "2", 1), "4")
                self.assertEqual(_step_numeric_value(typed_params[1], "2", 1, 0.1), "3")
                self.assertEqual(_step_numeric_value(typed_params[2], "0.5", 1, 10), "1")
                self.assertEqual(_step_numeric_value(typed_params[2], "0,5", 1), "0.6")
                app._ensure_param_vars(typed_tool.id, typed_params)
                self.assertIsInstance(app.param_values[typed_tool.id]["enabled"], tk.BooleanVar)
                self.assertEqual(app.param_values[typed_tool.id]["enabled"].get(), False)
                app.param_values[typed_tool.id]["enabled"].set(True)
                app._step_numeric_param(typed_params[1], app.param_values[typed_tool.id]["count"], 1)
                app._step_numeric_param(typed_params[2], app.param_values[typed_tool.id]["scale"], 1)
                typed_values = app._get_param_values(typed_tool.id, typed_params)
                self.assertEqual(typed_values["enabled"], "true")
                self.assertEqual(typed_values["count"], "4")
                self.assertEqual(typed_values["scale"], "0.6")
                self.assertEqual(app.param_values[typed_tool.id]["mode"].get(), "selected")
                app.param_values[typed_tool.id]["mode"].set("all")
                self.assertEqual(app._get_param_values(typed_tool.id, typed_params)["mode"], "all")
                self.assertEqual(app.param_values[typed_tool.id]["folder_path"].get(), "Environment/Props")
                path_buttons = [
                    child
                    for child in app.param_input_widgets[typed_tool.id]["folder_path"][0].master.winfo_children()
                    if isinstance(child, tk.Button)
                ]
                self.assertEqual([button.cget("text") for button in path_buttons], ["Copy", "Clear"])
                app.param_values[typed_tool.id]["folder_path"].set("Gameplay/Blockout")
                app._persist_param_values(typed_tool.id, typed_params)
                self.assertEqual(
                    settings_store.load().param_values[typed_tool.id]["folder_path"],
                    "Gameplay/Blockout",
                )
                app.param_values[typed_tool.id]["scale"].set("0,7")
                self.assertTrue(app._validate_param_on_change(typed_tool.id, typed_params[2], save=True))
                self.assertIn("scale = 0.7", root.clipboard_get())
                self.assertEqual(app.copy_feedback_tool_id, typed_tool.id)
                scale_field = app.param_input_widgets[typed_tool.id]["scale"][1]
                self.assertIsInstance(scale_field, UnrealNumericField)
                app.param_values[typed_tool.id]["scale"].set("0,8")
                scale_field._on_key_release()
                self.assertIn("scale = 0.8", root.clipboard_get())
                app.param_values[typed_tool.id]["count"].set("abc")
                self.assertFalse(app._validate_tool_params(typed_tool.id, typed_params))
                self.assertIn("integer", app.param_error_vars[typed_tool.id]["count"].get())
                count_entry = app.param_input_widgets[typed_tool.id]["count"][0]
                self.assertEqual(count_entry.cget("highlightbackground"), WARNING)
                self.assertTrue(app.param_error_labels[typed_tool.id]["count"].grid_info())
                self.assertEqual(app._begin_list_drag_scroll(SimpleNamespace(widget=app.category_combo, y_root=100, num=3)), None)
                self.assertEqual(app._begin_list_drag_scroll(SimpleNamespace(widget=count_entry, y_root=100, num=1)), None)
                self.assertEqual(app._begin_list_drag_scroll(SimpleNamespace(widget=count_entry, y_root=100, num=3)), None)
                numeric_field = app.param_input_widgets[typed_tool.id]["count"][1]
                self.assertIsInstance(numeric_field, UnrealNumericField)
                self.assertEqual(numeric_field.reset_button.cget("text"), "↺")
                self.assertEqual(numeric_field._drag_delta_to_steps(3), 0)
                self.assertEqual(numeric_field._drag_delta_to_steps(12), 2)
                self.assertEqual(numeric_field._drag_delta_to_steps(-12), -2)
                app.param_values[typed_tool.id]["count"].set("4")
                self.assertIsNone(numeric_field._on_mousewheel(SimpleNamespace(delta=-120, state=0)))
                self.assertEqual(app.param_values[typed_tool.id]["count"].get(), "4")
                self.assertEqual(numeric_field._on_mousewheel(SimpleNamespace(delta=120, state=0x0004)), "break")
                self.assertEqual(app.param_values[typed_tool.id]["count"].get(), "5")
                inline_buttons = [
                    child
                    for child in _walk_widgets(app.list_inner)
                    if isinstance(child, tk.Button)
                ]
                self.assertGreater(len(inline_buttons), 0)
                self.assertEqual(app._begin_list_drag_scroll(SimpleNamespace(widget=inline_buttons[0], y_root=100, num=1)), "break")
                self.assertEqual(app._drag_list_scroll(SimpleNamespace(widget=inline_buttons[0], y_root=94, num=1)), "break")
                self.assertEqual(inline_buttons[0].cget("state"), tk.DISABLED)
                self.assertEqual(app._end_list_drag_scroll(SimpleNamespace(widget=inline_buttons[0], y_root=94, num=1)), "break")
                self.assertIsNone(app._scroll_drag_disabled_button)
                self.assertEqual(app._begin_list_drag_scroll(SimpleNamespace(widget=inline_buttons[0], y_root=100, num=3)), "break")
                self.assertEqual(app._end_list_drag_scroll(SimpleNamespace(widget=inline_buttons[0], y_root=100, num=3)), "break")
                self.assertEqual(app._on_global_mousewheel(SimpleNamespace(widget=inline_buttons[0], delta=-120, num=0)), "break")
                self.assertEqual(app._mousewheel_pixels(SimpleNamespace(delta=-120, num="??")), 144)
                self.assertEqual(app._on_global_mousewheel(SimpleNamespace(widget=inline_buttons[0], delta=-120, num="??")), "break")
                clicked: list[str] = []
                drag_test_button = tk.Button(app.list_inner, text="Drag Test", command=lambda: clicked.append("click"))
                drag_test_button.grid(row=999, column=0)
                app._bind_list_scroll_events(drag_test_button)
                self.assertEqual(
                    app._begin_list_button_drag_scroll(SimpleNamespace(widget=drag_test_button, y_root=100, num=1)),
                    "break",
                )
                self.assertEqual(
                    app._end_list_button_drag_scroll(SimpleNamespace(widget=drag_test_button, y_root=100, num=1), drag_test_button),
                    "break",
                )
                self.assertEqual(clicked, ["click"])
                clicked.clear()
                self.assertEqual(
                    app._begin_list_button_drag_scroll(SimpleNamespace(widget=drag_test_button, y_root=100, num=1)),
                    "break",
                )
                self.assertEqual(app._drag_list_scroll(SimpleNamespace(widget=drag_test_button, y_root=92, num=1)), "break")
                self.assertEqual(
                    app._end_list_button_drag_scroll(SimpleNamespace(widget=drag_test_button, y_root=92, num=1), drag_test_button),
                    "break",
                )
                self.assertEqual(clicked, [])
                app._set_scroll_overscroll_offset(80)
                self.assertEqual(app._scroll_overscroll_offset, 64.0)
                self.assertEqual(app.list_canvas.coords(app.list_window)[1], 64)
                app._set_scroll_overscroll_offset(-80)
                self.assertEqual(app._scroll_overscroll_offset, -64.0)
                self.assertEqual(app.list_canvas.coords(app.list_window)[1], -64)
                app._set_scroll_overscroll_offset(0)
                self.assertEqual(app._begin_list_drag_scroll(SimpleNamespace(widget=app.list_canvas, y_root=100, num=1)), "break")
                self.assertEqual(app._scroll_drag_active, True)
                self.assertEqual(app._drag_list_scroll(SimpleNamespace(widget=app.list_canvas, y_root=95, num=1)), "break")
                self.assertEqual(app._scroll_drag_started, True)
                self.assertEqual(app._end_list_drag_scroll(SimpleNamespace(widget=app.list_canvas, y_root=95, num=1)), "break")
                self.assertEqual(app._scroll_drag_active, False)
                app._cancel_scroll_overscroll_animation()
                app._set_scroll_overscroll_offset(0)
                app.param_values[typed_tool.id]["count"].set("4")
                self.assertTrue(app._validate_tool_params(typed_tool.id, typed_params))
                self.assertEqual(app.param_error_vars[typed_tool.id]["count"].get(), "")
                self.assertNotEqual(count_entry.cget("highlightbackground"), WARNING)
                self.assertFalse(app.param_error_labels[typed_tool.id]["count"].grid_info())
                app._reset_params(typed_tool.id)
                self.assertEqual(app.param_values[typed_tool.id]["mode"].get(), "selected")
                app._copy_fix_prompt(typed_tool.id)
                self.assertIn("Fix this Unreal Engine Python Console tool.", root.clipboard_get())
                app._remember_recent_tool(typed_tool.id)
                self.assertEqual(app._recent_ids()[0], typed_tool.id)
                self.assertGreaterEqual(app._param_label_wraplength(), 180)
                original_tool_id = app.current_tool_id
                inactive_tool_id = next(tool.id for tool in app.filtered_tools if tool.id != original_tool_id)
                inactive_row = app.tool_row_by_id[inactive_tool_id]
                self.assertEqual(
                    app._begin_list_row_drag_scroll(SimpleNamespace(widget=inactive_row, y_root=100, num=1), inactive_tool_id),
                    "break",
                )
                self.assertEqual(app._drag_list_scroll(SimpleNamespace(widget=inactive_row, y_root=92, num=1)), "break")
                self.assertEqual(
                    app._end_list_row_drag_scroll(SimpleNamespace(widget=inactive_row, y_root=92, num=1), inactive_tool_id),
                    "break",
                )
                self.assertEqual(app.current_tool_id, original_tool_id)
                self.assertEqual(
                    app._begin_list_row_drag_scroll(SimpleNamespace(widget=inactive_row, y_root=100, num=1), inactive_tool_id),
                    "break",
                )
                self.assertEqual(
                    app._end_list_row_drag_scroll(SimpleNamespace(widget=inactive_row, y_root=100, num=1), inactive_tool_id),
                    "break",
                )
                self.assertEqual(app.current_tool_id, inactive_tool_id)

                dialog = ToolEditorDialog(root)
                try:
                    self.assertEqual(dialog.mode, "paste")
                    dialog.window.update_idletasks()
                    self.assertGreaterEqual(dialog.window.winfo_rootx(), 0)
                    self.assertGreaterEqual(dialog.window.winfo_rooty(), 0)
                    self.assertLessEqual(
                        dialog.window.winfo_rootx() + dialog.window.winfo_width(),
                        root.winfo_screenwidth(),
                    )
                    self.assertLessEqual(
                        dialog.window.winfo_rooty() + dialog.window.winfo_height(),
                        root.winfo_screenheight(),
                    )
                    self.assertEqual(dialog.mode_buttons["paste"].cget("text"), "AI Flow")
                    self.assertEqual(dialog.mode_buttons["import"].cget("text"), "Import Files")
                    self.assertEqual(dialog.mode_buttons["manual"].cget("text"), "Manual")
                    self.assertEqual(dialog.mode_buttons["paste"].cget("bg"), ACCENT_DARK)
                    self.assertEqual(dialog.mode_buttons["import"].cget("fg"), MUTED)
                    self.assertIn("Describe the tool", dialog.parse_status_var.get())
                    self.assertIsNotNone(dialog.request_text)
                    self.assertIsNotNone(dialog.paste_and_save_button)
                    self.assertIsNotNone(dialog.save_ai_button)
                    self.assertEqual(dialog.paste_and_save_button.cget("state"), tk.DISABLED)
                    self.assertEqual(dialog.save_ai_button.cget("state"), tk.DISABLED)
                    dialog.request_text.insert("1.0", "Offset selected actors up by 100 cm.")
                    dialog._copy_ai_prompt_from_dialog()
                    self.assertIn("Offset selected actors up by 100 cm.", root.clipboard_get())
                    self.assertIn("<<<UUT_NAME>>>", root.clipboard_get())
                    self.assertIn("<<<UUT_CODE>>>", root.clipboard_get())
                    self.assertEqual(dialog.paste_and_save_button.cget("state"), tk.DISABLED)
                    dialog.ai_text.insert(
                        "1.0",
                        """<<<UUT_NAME>>>
Preview Tool
<<<UUT_NOTES>>>
None
<<<UUT_CODE>>>
import unreal
unreal.log("preview")
<<<UUT_END>>>
""",
                    )
                    dialog._refresh_ai_preview()
                    self.assertIn("Ready to save", dialog.parse_status_var.get())
                    self.assertEqual(dialog.parse_status_label.cget("fg"), SUCCESS)
                    self.assertEqual(dialog.save_ai_button.cget("state"), tk.NORMAL)
                    dialog.ai_text.delete("1.0", tk.END)
                    dialog._refresh_ai_preview()
                    root.clipboard_clear()
                    root.clipboard_append(
                        """<<<UUT_NAME>>>
Clipboard Tool
<<<UUT_NOTES>>>
None
<<<UUT_CODE>>>
import unreal
unreal.log("ok")
<<<UUT_END>>>
"""
                    )
                    dialog._refresh_paste_and_save_button()
                    self.assertEqual(dialog.paste_and_save_button.cget("state"), tk.NORMAL)
                    dialog._paste_and_save_from_clipboard()
                    self.assertIsNotNone(dialog.result)
                finally:
                    if dialog.window.winfo_exists():
                        dialog.window.destroy()

                dialog = ToolEditorDialog(root)
                try:
                    dialog._set_mode("import")
                    self.assertEqual(dialog.mode, "import")
                    self.assertEqual(dialog.mode_buttons["import"].cget("bg"), ACCENT_DARK)
                    self.assertEqual(dialog.mode_buttons["paste"].cget("fg"), MUTED)
                    self.assertIn("Choose files", dialog.import_status_var.get())
                    self.assertEqual(dialog.import_policy_var.get(), IMPORT_POLICY_SKIP)
                    self.assertIsNotNone(dialog.import_text)
                    self.assertIn(".zip", dialog.import_text.get("1.0", tk.END))
                finally:
                    if dialog.window.winfo_exists():
                        dialog.window.destroy()

                dialog = ToolEditorDialog(root, typed_tool)
                try:
                    self.assertEqual(dialog.mode, "manual")
                    self.assertEqual(dialog.mode_buttons, {})
                    self.assertIsNotNone(dialog.code_text)
                    self.assertEqual(dialog.category_var.get(), CATEGORY_CUSTOM)
                finally:
                    if dialog.window.winfo_exists():
                        dialog.window.destroy()

                delete_tool = Tool.create(name="Keyboard Delete", code="import unreal\nunreal.log('delete')")
                app.tools.append(delete_tool)
                app.current_tool_id = delete_tool.id
                app._refresh_list()
                original_askyesno = main_window_module.messagebox.askyesno
                try:
                    main_window_module.messagebox.askyesno = lambda *args, **kwargs: False
                    self.assertEqual(app._delete_selected_shortcut(SimpleNamespace(widget=root)), "break")
                    self.assertIsNotNone(app._tool_by_id(delete_tool.id))
                    main_window_module.messagebox.askyesno = lambda *args, **kwargs: True
                    self.assertEqual(app._delete_selected_shortcut(SimpleNamespace(widget=root)), "break")
                    self.assertIsNone(app._tool_by_id(delete_tool.id))
                finally:
                    main_window_module.messagebox.askyesno = original_askyesno
                app.tools = []
                app.current_tool_id = ""
                app.expanded_tool_id = ""
                app.search_var.set("")
                app.category_var.set("All")
                app._refresh_list()
                self.assertEqual(app.filtered_tools, [])
                empty_text = " ".join(
                    child.cget("text")
                    for child in app.tool_rows[0].winfo_children()
                    if "text" in child.keys()
                )
                self.assertIn("No tools yet", empty_text)
                self.assertIn("+ Add Tool", empty_text)
                app._close()
                self.assertTrue((Path(temp_dir) / "settings.json").exists())
            finally:
                try:
                    if root.winfo_exists():
                        root.destroy()
                except tk.TclError:
                    pass


if __name__ == "__main__":
    unittest.main()
