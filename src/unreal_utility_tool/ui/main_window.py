from __future__ import annotations

import os
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk

from .. import __version__
from ..exporter import safe_filename as _safe_filename, write_tools_export as _write_tools_export
from ..models import (
    CATEGORY_CUSTOM,
    CATEGORY_DEBUG,
    CATEGORY_ORGANIZATION,
    CATEGORY_SELECTION,
    CATEGORY_TRANSFORM,
    Tool,
    WORKFLOWS,
    ROLES,
    VISIBILITY_PRIMARY,
    VISIBILITY_SECONDARY,
    VISIBILITY_HIDDEN,
    category_options,
)
from ..params import ParamRenderError, ToolParam, parse_tool_params, render_tool_code, validate_param_value
from ..prompts import build_fix_prompt
from ..settings import AppSettingsStore, resolve_default_settings_path
from ..storage import ToolLibraryStore, app_file_path, app_root, refresh_bundled_presets
from ..theme import (
    ACCENT,
    ACCENT_DARK,
    ACCENT_HOVER,
    BG,
    BORDER,
    BORDER_DARK,
    CODE_FONT,
    CODE_BG,
    DANGER,
    DOCK_BG,
    HEADER_BG,
    INPUT_BG,
    MUTED,
    PANEL,
    PANEL_ALT,
    PANEL_TITLE_FONT,
    ROW_BG,
    ROW_BG_ALT,
    ROW_HOVER,
    SELECTION_BLUE,
    SMALL_FONT,
    SUBTLE,
    SUCCESS,
    SUCCESS_HOVER,
    TEXT,
    UI_FONT,
    UI_FONT_BOLD,
    WARNING,
    X_AXIS,
    Y_AXIS,
    Z_AXIS,
    configure_ttk_style,
    make_dark_entry,
    make_button,
    make_search_shell,
    make_static_icon,
    make_tab,
    make_toolbar_button,
)
from ..tool_importer import ToolImportBatch, apply_import_policy
from .editor_dialog import ToolEditorDialog
from .fix_prompt_dialog import FixPromptDialog
from .layout import LayoutSpec, _layout_spec_for_width
from .restore_dialog import RestoreBackupDialog
from .windowing import is_valid_geometry, set_app_icon, set_initial_window_size


@dataclass(frozen=True, slots=True)
class ParamRenderGroup:
    kind: str
    label: str
    params: tuple[ToolParam, ...]


DETAIL_NUMERIC_WIDTH = 180
DETAIL_VECTOR_NUMERIC_WIDTH = 110
DETAIL_RANGE_NUMERIC_WIDTH = 160


class UnrealNumericField(tk.Frame):
    drag_threshold_px = 4
    drag_pixels_per_step = 6

    def __init__(
        self,
        parent: tk.Widget,
        *,
        param: ToolParam,
        variable: tk.Variable,
        on_validate,
        axis_color: str | None = None,
        width_px: int | None = None,
    ) -> None:
        parent_bg = str(parent.cget("bg")) if hasattr(parent, "cget") else PANEL
        super().__init__(parent, bg=parent_bg)
        self.param = param
        self.variable = variable
        self.on_validate = on_validate
        self.axis_color = axis_color
        self._drag_start_x = 0
        self._last_drag_steps = 0
        self._dragging = False
        self._value_before_edit = str(variable.get())
        self._cursor_before_drag = ""
        if width_px is not None:
            self.configure(width=width_px, height=24)
            self.grid_propagate(False)

        if axis_color:
            tk.Frame(self, bg=axis_color, width=3).grid(row=0, column=0, sticky="ns")
            entry_column = 1
        else:
            entry_column = 0
        self.columnconfigure(entry_column, weight=1)
        self.entry = make_dark_entry(self, variable, width=10)
        self.entry.grid(row=0, column=entry_column, sticky="ew", ipady=2)
        self.reset_button = tk.Button(
            self,
            text="↺",
            command=self.reset_to_default,
            bg=parent_bg,
            fg=MUTED,
            activebackground=ROW_HOVER,
            activeforeground=TEXT,
            disabledforeground=SUBTLE,
            relief="flat",
            bd=0,
            highlightthickness=0,
            width=2,
            padx=1,
            pady=1,
            font=("Segoe UI Symbol", 9),
            cursor="hand2",
        )
        self.reset_button.grid(row=0, column=entry_column + 1, sticky="ns", padx=(3, 0))

        self.entry.bind("<FocusIn>", self._begin_edit)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Return>", self._commit)
        self.entry.bind("<Escape>", self._cancel_edit)
        self.entry.bind("<FocusOut>", self._commit)
        self.entry.bind("<MouseWheel>", self._on_mousewheel)
        self.entry.bind("<ButtonPress-1>", self._begin_drag)
        self.entry.bind("<B1-Motion>", self._drag)
        self.entry.bind("<ButtonRelease-1>", self._end_drag)
        self.refresh_reset_visibility()

    def apply_step(self, direction: int, multiplier: float = 1.0) -> None:
        self.variable.set(_step_numeric_value(self.param, str(self.variable.get()), direction, multiplier))
        self.refresh_reset_visibility()

    def reset_to_default(self) -> None:
        self.variable.set(self.param.default)
        self.refresh_reset_visibility()
        self.on_validate(save=True)

    def refresh_reset_visibility(self) -> None:
        changed = str(self.variable.get()).strip() != str(self.param.default).strip()
        if changed:
            self.reset_button.grid()
        else:
            self.reset_button.grid_remove()

    def _begin_edit(self, _event: tk.Event | None = None) -> None:
        self._value_before_edit = str(self.variable.get())

    def _on_key_release(self, _event: tk.Event | None = None) -> None:
        self.refresh_reset_visibility()
        self.on_validate(save=True)

    def _commit(self, _event: tk.Event | None = None) -> str:
        self.refresh_reset_visibility()
        self.on_validate(save=True)
        return "break"

    def _cancel_edit(self, _event: tk.Event | None = None) -> str:
        self.variable.set(self._value_before_edit)
        self.refresh_reset_visibility()
        self.on_validate(save=False)
        return "break"

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        if not _event_has_ctrl(event):
            return None
        try:
            delta = int(getattr(event, "delta", 0) or 0)
        except (TypeError, ValueError):
            delta = 0
        direction = 1 if delta > 0 else -1
        self.apply_step(direction, _numeric_multiplier_from_event(self.param, event))
        self.on_validate(save=True)
        return "break"

    def _begin_drag(self, event: tk.Event) -> None:
        self._drag_start_x = int(getattr(event, "x_root", 0))
        self._last_drag_steps = 0
        self._dragging = False
        self._value_before_edit = str(self.variable.get())

    def _drag(self, event: tk.Event) -> str | None:
        delta = int(getattr(event, "x_root", 0)) - self._drag_start_x
        if not self._dragging and abs(delta) < self.drag_threshold_px:
            return None
        if not self._dragging:
            self._dragging = True
            self._cursor_before_drag = str(self.winfo_toplevel().cget("cursor") or "")
            self.winfo_toplevel().configure(cursor="sb_h_double_arrow")
        steps = self._drag_delta_to_steps(delta)
        step_delta = steps - self._last_drag_steps
        if step_delta:
            direction = 1 if step_delta > 0 else -1
            multiplier = _numeric_multiplier_from_event(self.param, event)
            for _ in range(abs(step_delta)):
                self.apply_step(direction, multiplier)
            self.on_validate(save=True)
            self._last_drag_steps = steps
        return "break"

    def _end_drag(self, _event: tk.Event | None = None) -> str | None:
        if self._dragging:
            try:
                self.winfo_toplevel().configure(cursor=self._cursor_before_drag)
            except tk.TclError:
                pass
            self._dragging = False
            self._cursor_before_drag = ""
            return "break"
        return None

    def _drag_delta_to_steps(self, delta: int) -> int:
        if abs(delta) < self.drag_threshold_px:
            return 0
        if delta > 0:
            return max(1, delta // self.drag_pixels_per_step)
        return min(-1, -((-delta) // self.drag_pixels_per_step))


class UnrealUtilityApp:
    def __init__(
        self,
        root: tk.Tk,
        store: ToolLibraryStore,
        settings_store: AppSettingsStore | None = None,
    ) -> None:
        self.root = root
        self.store = store
        self.settings_store = settings_store or AppSettingsStore(resolve_default_settings_path())
        self.settings = self.settings_store.load()
        self._normalize_detail_section_state()
        self.tools = self.store.load_tools()
        self.filtered_tools: list[Tool] = []
        self.current_tool_id = ""
        self.tool_rows: list[tk.Widget] = []
        self.tool_row_by_id: dict[str, tk.Widget] = {}
        self.tool_card_widgets: dict[str, dict[str, object]] = {}
        self.copy_button_by_tool_id: dict[str, tk.Widget] = {}
        self.param_values: dict[str, dict[str, tk.Variable]] = {}
        self.param_error_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.param_error_labels: dict[str, dict[str, tk.Label]] = {}
        self.param_input_widgets: dict[str, dict[str, list[tk.Widget]]] = {}
        self.expanded_tool_id = ""
        self.copy_feedback_tool_id = ""
        self._copy_feedback_token = 0
        self._scroll_drag_active = False
        self._scroll_drag_started = False
        self._scroll_drag_start_y = 0
        self._scroll_drag_last_y = 0
        self._scroll_drag_button = 0
        self._scroll_drag_previous_cursor = ""
        self._scroll_drag_pressed_button: tk.Button | None = None
        self._scroll_drag_disabled_button: tk.Button | None = None
        self._scroll_drag_disabled_button_state = tk.NORMAL
        self._pending_row_click_tool_id = ""
        self._scroll_overscroll_offset = 0.0
        self._scroll_overscroll_after_id = ""
        self._filter_refresh_after_id = ""
        self._root_resize_after_id = ""
        self._list_resize_after_id = ""
        self._list_canvas_width_after_id = ""
        self._tool_wrap_refresh_after_id = ""
        self._details_sync_after_id = ""
        self._pending_root_width = 0
        self._pending_list_canvas_width = 0

        self.search_var = tk.StringVar()
        self.workflow_var = tk.StringVar(value="All")
        self.role_var = tk.StringVar(value="All")
        self.category_var = tk.StringVar(value="All")
        self.visibility_filter_var = tk.StringVar(value=SHOW_RECOMMENDED)
        self.details_search_var = tk.StringVar(value="")
        self.details_category_var = tk.StringVar(value="All")
        self.status_var = tk.StringVar(value="Ready")
        self.count_var = tk.StringVar(value="")
        self.active_filter_summary_var = tk.StringVar(value=SHOW_RECOMMENDED)
        self.always_top_var = tk.BooleanVar(value=self.settings.always_top)
        self._search_trace_registered = False
        self._details_search_trace_registered = False
        self._detail_section_bodies: dict[str, tk.Widget] = {}
        self._split_drag_active = False
        self._split_drag_start_y = 0
        self._split_drag_start_height = int(self.settings.details_panel_height or 520)
        self._last_layout_mode: str | None = None
        self._last_details_label_width = 0
        self._last_canvas_width = 0
        self._last_list_window_width = 0

        self._set_app_icon()
        self.root.title("EditorBinder")
        self.root.minsize(380, 320)
        self._set_saved_or_initial_window_size()
        self.root.configure(bg=BG)
        self.root.option_add("*Font", UI_FONT)
        self.root.attributes("-topmost", bool(self.always_top_var.get()))
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self._configure_ttk()
        self._build_ui()
        self._bind_keyboard_shortcuts()
        self._bind_scroll_drag()
        self._refresh_list()
        self.root.bind("<Configure>", self._on_root_configure)

        if self.store.last_load_error:
            messagebox.showwarning("Library Load Problem", self.store.last_load_error, parent=self.root)

    def _set_app_icon(self) -> None:
        self._app_icon = set_app_icon(self.root)

    def _set_saved_or_initial_window_size(self) -> None:
        if self._is_valid_geometry(self.settings.geometry):
            self.root.geometry(self.settings.geometry)
            return
        self._set_initial_window_size()

    def _is_valid_geometry(self, geometry: str) -> bool:
        return is_valid_geometry(geometry)

    def _set_initial_window_size(self) -> None:
        set_initial_window_size(self.root)

    def _configure_ttk(self) -> None:
        configure_ttk_style()

    def _normalize_detail_section_state(self) -> None:
        collapsed = set(self.settings.collapsed_detail_sections or [])
        collapsed.discard("Parameters")
        collapsed.add("Source")
        collapsed.add("Tool")
        self.settings.collapsed_detail_sections = sorted(collapsed)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self.header_frame = tk.Frame(self.root, bg=BG, padx=0, pady=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_remove()
        self.header_frame.columnconfigure(2, weight=1)

        self.outliner_tab = make_tab(self.header_frame, "Outliner", active=True, close=True, icon="outliner")
        self.outliner_tab.grid(row=0, column=0, sticky="w")
        self.details_tab = make_tab(self.header_frame, "Details", active=False, close=False, icon="details")
        self.details_tab.grid(row=0, column=1, sticky="w")
        self._bind_tab_click(self.outliner_tab, self._focus_outliner_tab)
        self._bind_tab_click(self.details_tab, self._focus_details_tab)

        self.body_frame = tk.Frame(self.root, bg=DOCK_BG, padx=2, pady=2)
        self.body_frame.grid(row=1, column=0, sticky="nsew")
        self.body_frame.columnconfigure(0, weight=1, minsize=260)
        self.body_frame.rowconfigure(0, weight=1, minsize=240)
        self.body_frame.rowconfigure(1, weight=0, minsize=5)
        self.body_frame.rowconfigure(2, weight=0, minsize=max(220, int(self.settings.details_panel_height)))

        self.outliner_panel = tk.Frame(self.body_frame, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        self.outliner_panel.grid(row=0, column=0, sticky="nsew", pady=(0, 2))
        self.outliner_panel.rowconfigure(2, weight=1)
        self.outliner_panel.columnconfigure(0, weight=1)

        self.outliner_toolbar = tk.Frame(self.outliner_panel, bg=PANEL, padx=8, pady=8)
        self.outliner_toolbar.grid(row=0, column=0, sticky="ew")
        self.outliner_toolbar.columnconfigure(0, weight=1)
        self.search_shell = make_search_shell(self.outliner_toolbar)
        self.search_shell.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        for child in self.search_shell.grid_slaves(row=0, column=0):
            child.grid_remove()
        self.search_shell.columnconfigure(0, weight=1)
        self.search_shell.columnconfigure(1, weight=0)
        self.search_entry = make_dark_entry(self.search_shell, self.search_var)
        self.search_entry.configure(relief="flat", bd=0)
        self.search_entry.grid(row=0, column=0, sticky="ew", ipady=3, padx=(8, 8))
        self.search_entry.insert(0, "")
        self.search_placeholder = tk.Label(
            self.search_shell,
            text="Search tool",
            bg=self.search_entry.cget("background"),
            fg=SUBTLE,
            font=UI_FONT,
            anchor="w",
            cursor="xterm",
        )
        self.search_placeholder.bind("<Button-1>", lambda _event: self.search_entry.focus_set())
        self.search_entry.bind("<FocusIn>", lambda _event: self._update_search_placeholder())
        self.search_entry.bind("<FocusOut>", lambda _event: self._update_search_placeholder())
        self._update_search_placeholder()
        if not self._search_trace_registered:
            self.search_var.trace_add(
                "write",
                lambda *_: (self._schedule_filter_refresh(), self._update_search_placeholder()),
            )
            self._search_trace_registered = True

        self.add_button = make_toolbar_button(self.outliner_toolbar, "Add Tool", self._add_tool)
        self.add_button.configure(fg=TEXT, font=UI_FONT_BOLD)
        self.add_button.grid(row=0, column=1, padx=(0, 5))
        self.filter_button = make_toolbar_button(self.outliner_toolbar, "Filters", self._toggle_filter_panel)
        self.filter_button.grid(row=0, column=2, padx=(0, 5))

        self.active_filter_summary_label = tk.Label(
            self.outliner_toolbar,
            textvariable=self.active_filter_summary_var,
            bg=PANEL,
            fg=SUBTLE,
            font=SMALL_FONT,
            anchor="w",
        )
        self.active_filter_summary_label.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))

        self.filter_panel = tk.Frame(self.outliner_toolbar, bg=PANEL_ALT, padx=8, pady=8)
        self.filter_panel.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        self.filter_panel.columnconfigure(1, weight=1)
        self.filter_panel.grid_remove()

        tk.Label(self.filter_panel, text="Workflow", bg=PANEL_ALT, fg=SUBTLE, font=SMALL_FONT).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6)
        )
        self.workflow_combo = ttk.Combobox(
            self.filter_panel,
            textvariable=self.workflow_var,
            values=["All"],
            state="readonly",
            font=UI_FONT,
            width=22,
            style="Dark.TCombobox",
        )
        self.workflow_combo.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self.workflow_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_list())

        tk.Label(self.filter_panel, text="Role", bg=PANEL_ALT, fg=SUBTLE, font=SMALL_FONT).grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 6)
        )
        self.role_combo = ttk.Combobox(
            self.filter_panel,
            textvariable=self.role_var,
            values=["All"],
            state="readonly",
            font=UI_FONT,
            width=22,
            style="Dark.TCombobox",
        )
        self.role_combo.grid(row=1, column=1, sticky="ew", pady=(0, 6))
        self.role_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_list())

        tk.Label(self.filter_panel, text="Category", bg=PANEL_ALT, fg=SUBTLE, font=SMALL_FONT).grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 6)
        )
        self.category_combo = ttk.Combobox(
            self.filter_panel,
            textvariable=self.category_var,
            values=["All", *category_options(self.tools)],
            state="readonly",
            font=UI_FONT,
            width=22,
            style="Dark.TCombobox",
        )
        self.category_combo.grid(row=2, column=1, sticky="ew", pady=(0, 6))
        self.category_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_list())

        tk.Label(self.filter_panel, text="Show", bg=PANEL_ALT, fg=SUBTLE, font=SMALL_FONT).grid(
            row=3, column=0, sticky="w", padx=(0, 8), pady=(0, 8)
        )
        self.visibility_combo = ttk.Combobox(
            self.filter_panel,
            textvariable=self.visibility_filter_var,
            values=SHOW_FILTERS,
            state="readonly",
            font=UI_FONT,
            width=22,
            style="Dark.TCombobox",
        )
        self.visibility_combo.grid(row=3, column=1, sticky="ew", pady=(0, 8))
        self.visibility_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_list())

        make_toolbar_button(self.filter_panel, "Reset Filters", self._reset_filters).grid(
            row=4, column=0, sticky="ew", padx=(0, 6)
        )
        self.library_button = make_toolbar_button(self.filter_panel, "Library", self._show_library_menu)
        self.library_button.grid(row=4, column=1, sticky="ew")

        self.outliner_filter_row = tk.Frame(self.outliner_panel, bg=PANEL, padx=5, pady=0)
        self.outliner_filter_row.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        for index, label in enumerate(["General", "Transform", "Selection", "All"]):
            button = make_toolbar_button(
                self.outliner_filter_row,
                label,
                lambda selected=label: self._set_outliner_filter_tab(selected),
            )
            button.configure(padx=8, pady=2, bg=HEADER_BG if label != "All" else ACCENT_DARK)
            button.grid(row=0, column=index, padx=(0, 4))
        self.outliner_filter_row.grid_remove()

        self.outliner_table_header = tk.Frame(self.outliner_panel, bg=HEADER_BG, highlightthickness=1, highlightbackground=BORDER)
        self.outliner_table_header.grid(row=2, column=0, sticky="ew")
        self.outliner_table_header.grid_remove()
        self.outliner_table_header.columnconfigure(0, weight=1)
        self.outliner_table_header.columnconfigure(1, weight=0, minsize=1)
        self.outliner_table_header.columnconfigure(2, weight=0, minsize=140)
        self.outliner_table_header.columnconfigure(3, weight=0, minsize=1)
        self.outliner_table_header.columnconfigure(4, weight=2)
        for column, label in [(0, "Item Label"), (2, "Category"), (4, "ID Name")]:
            tk.Label(
                self.outliner_table_header,
                text=label,
                bg=HEADER_BG,
                fg=TEXT,
                font=UI_FONT,
                anchor="w",
                padx=6,
                pady=4,
            ).grid(row=0, column=column, sticky="ew")
        for column in (1, 3):
            tk.Frame(self.outliner_table_header, bg=BORDER_DARK, width=1).grid(row=0, column=column, sticky="ns")

        self.list_shell = tk.Frame(self.outliner_panel, bg=PANEL, padx=0, pady=0)
        self.list_shell.grid(row=2, column=0, sticky="nsew")
        self.list_shell.rowconfigure(0, weight=1)
        self.list_shell.columnconfigure(0, weight=1)

        self.list_canvas = tk.Canvas(self.list_shell, bg=PANEL, highlightthickness=0, bd=0)
        self.list_canvas.grid(row=0, column=0, sticky="nsew")
        self.list_inner = tk.Frame(self.list_canvas, bg=PANEL)
        self.list_window = self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_inner.bind("<Configure>", self._on_list_inner_configure)
        self.list_canvas.bind("<Configure>", self._on_list_canvas_configure)

        list_scroll = ttk.Scrollbar(
            self.list_shell,
            orient="vertical",
            command=self.list_canvas.yview,
            style="Dark.Vertical.TScrollbar",
        )
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.list_canvas.configure(yscrollcommand=list_scroll.set)
        self._bind_list_scroll_events(self.list_shell)

        self.outliner_footer = tk.Frame(self.outliner_panel, bg=HEADER_BG, padx=6, pady=4)
        self.outliner_footer.grid(row=3, column=0, sticky="ew")
        self.outliner_footer.columnconfigure(0, weight=1)
        self.outliner_count_label = tk.Label(
            self.outliner_footer,
            textvariable=self.count_var,
            bg=HEADER_BG,
            fg=TEXT,
            font=SMALL_FONT,
            anchor="w",
        )
        self.outliner_count_label.grid(row=0, column=0, sticky="ew")

        self.splitter = tk.Frame(self.body_frame, bg=BORDER, height=5, cursor="sb_v_double_arrow")
        self.splitter.grid(row=1, column=0, sticky="ew")
        self.splitter.grid_remove()
        self.splitter.bind("<ButtonPress-1>", self._begin_split_drag)
        self.splitter.bind("<B1-Motion>", self._drag_split)
        self.splitter.bind("<ButtonRelease-1>", self._end_split_drag)

        self.details_panel = tk.Frame(self.body_frame, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        self.details_panel.grid(row=2, column=0, sticky="nsew")
        self.details_panel.grid_remove()
        self.details_panel.grid_propagate(False)
        self.details_panel.configure(height=max(220, int(self.settings.details_panel_height)))
        self.details_panel.bind("<Configure>", lambda _event: self._schedule_details_label_sync(), add="+")
        self.details_panel.rowconfigure(1, weight=1)
        self.details_panel.columnconfigure(0, weight=1)

        self.details_header = tk.Frame(self.details_panel, bg=HEADER_BG, padx=7, pady=3)
        self.details_header.grid(row=0, column=0, sticky="ew")
        self.details_header.columnconfigure(0, weight=1)
        title_shell = tk.Frame(self.details_header, bg=HEADER_BG)
        title_shell.grid(row=0, column=0, sticky="w")
        make_static_icon(title_shell, "details", size=14, bg=HEADER_BG, fg=TEXT).grid(row=0, column=0, padx=(0, 5))
        tk.Label(title_shell, text="Details", bg=HEADER_BG, fg=TEXT, font=PANEL_TITLE_FONT).grid(
            row=0,
            column=1,
            sticky="w",
        )

        self.details_canvas = tk.Canvas(self.details_panel, bg=PANEL, highlightthickness=0, bd=0)
        self.details_canvas.grid(row=1, column=0, sticky="nsew")
        self.details_inner = tk.Frame(self.details_canvas, bg=PANEL)
        self.details_inner.columnconfigure(0, weight=1)
        self.details_window = self.details_canvas.create_window((0, 0), window=self.details_inner, anchor="nw")
        self.details_inner.bind("<Configure>", self._on_details_inner_configure)
        self.details_canvas.bind("<Configure>", self._on_details_canvas_configure)
        details_scroll = ttk.Scrollbar(
            self.details_panel,
            orient="vertical",
            command=self.details_canvas.yview,
            style="Dark.Vertical.TScrollbar",
        )
        details_scroll.grid(row=1, column=1, sticky="ns")
        self.details_canvas.configure(yscrollcommand=details_scroll.set)

        self.footer_frame = tk.Frame(self.root, bg=HEADER_BG, padx=10, pady=4)
        self.footer_frame.grid(row=2, column=0, sticky="ew")
        self.footer_frame.columnconfigure(0, weight=1)

        self.status_label = tk.Label(
            self.footer_frame,
            textvariable=self.status_var,
            anchor="w",
            bg=HEADER_BG,
            fg=SUBTLE,
            font=SMALL_FONT,
            width=1,
        )
        self.status_label.grid(row=0, column=0, sticky="ew")
        self.always_top_check = tk.Checkbutton(
            self.footer_frame,
            text="Always Top",
            variable=self.always_top_var,
            command=self._toggle_always_top,
            bg=HEADER_BG,
            fg=MUTED,
            activebackground=HEADER_BG,
            activeforeground=TEXT,
            selectcolor=INPUT_BG,
            font=SMALL_FONT,
            relief="flat",
            cursor="hand2",
        )
        self.always_top_check.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self._apply_layout_spec(self._layout_spec())

    def _bind_keyboard_shortcuts(self) -> None:
        self.root.bind("<Control-f>", self._focus_search_shortcut, add="+")
        self.root.bind("<Control-F>", self._focus_search_shortcut, add="+")
        self.root.bind("<Control-n>", self._add_tool_shortcut, add="+")
        self.root.bind("<Control-N>", self._add_tool_shortcut, add="+")
        self.root.bind("<Return>", self._copy_selected_shortcut, add="+")
        self.root.bind("<space>", self._toggle_selected_params_shortcut, add="+")
        self.root.bind("<Delete>", self._delete_selected_shortcut, add="+")
        self.root.bind("<Up>", self._select_previous_tool_shortcut, add="+")
        self.root.bind("<Down>", self._select_next_tool_shortcut, add="+")

    def _bind_tab_click(self, widget: tk.Widget, command) -> None:
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda _event: command(), add="+")
        for child in widget.winfo_children():
            self._bind_tab_click(child, command)

    def _focus_outliner_tab(self) -> None:
        self.search_entry.focus_set()

    def _focus_details_tab(self) -> None:
        self._focus_selected_param()

    def _bind_scroll_drag(self) -> None:
        for button in (1, 2, 3):
            self.root.bind_all(f"<ButtonPress-{button}>", self._begin_list_drag_scroll, add="+")
            self.root.bind_all(f"<B{button}-Motion>", self._drag_list_scroll, add="+")
            self.root.bind_all(f"<ButtonRelease-{button}>", self._end_list_drag_scroll, add="+")
        self.root.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_global_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._on_global_mousewheel, add="+")

    def _layout_spec(self, width: int | None = None) -> LayoutSpec:
        if width is None:
            width = self.root.winfo_width()
        if width <= 1:
            width = 420
        return _layout_spec_for_width(width)

    def _apply_layout_spec(self, spec: LayoutSpec) -> None:
        self._last_layout_mode = spec.mode
        compact = spec.mode == "compact"

        self.header_frame.configure(padx=spec.outer_pad_x)
        self.header_frame.grid_remove()
        self.library_button.configure(padx=spec.header_button_padx, pady=spec.header_button_pady)
        self.add_button.configure(
            padx=spec.header_button_padx,
            pady=spec.header_button_pady,
        )

        self.search_entry.grid_configure(ipady=max(spec.search_ipady, 2), padx=6 if compact else 8)
        self.filter_button.configure(
            text="Filters",
            padx=spec.header_button_padx,
            pady=spec.header_button_pady,
        )
        for combo in (self.workflow_combo, self.role_combo, self.category_combo, self.visibility_combo):
            combo.configure(width=20 if compact else 28)
        self.footer_frame.configure(padx=spec.outer_pad_x, pady=max(3, spec.footer_pady - 1))
        self.status_label.configure(wraplength=max(120, self.root.winfo_width() - (spec.outer_pad_x * 2) - 180))
        self.always_top_check.configure(text="Top" if compact else "Always Top")

        self.body_frame.columnconfigure(0, weight=1, minsize=260)
        self.body_frame.columnconfigure(1, weight=0, minsize=0)
        self.body_frame.columnconfigure(2, weight=0, minsize=0)

        self.body_frame.rowconfigure(0, weight=1, minsize=220)
        self.body_frame.rowconfigure(1, weight=0, minsize=0)
        self.body_frame.rowconfigure(2, weight=0, minsize=0)
        self.outliner_panel.grid_configure(row=0, column=0, sticky="nsew", padx=0, pady=(0, 2))
        self.splitter.grid_remove()
        self.details_panel.grid_remove()

    def _on_root_configure(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        self._pending_root_width = self._event_int(event, "width", self.root.winfo_width())
        self._schedule_root_resize()

    def _schedule_root_resize(self) -> None:
        self._cancel_after("_root_resize_after_id")
        self._root_resize_after_id = self.root.after(48, self._flush_root_resize)

    def _flush_root_resize(self) -> None:
        self._root_resize_after_id = ""
        width = self._pending_root_width or self.root.winfo_width()
        spec = self._layout_spec(width)
        mode_changed = spec.mode != self._last_layout_mode
        if mode_changed:
            self._apply_layout_spec(spec)
            if self.tool_rows:
                self._schedule_tool_rows_rebuild()
        else:
            self._update_resize_dependent_widgets(spec, width)
            self._schedule_tool_wrap_refresh()
        self._schedule_details_label_sync()

    def _update_resize_dependent_widgets(self, spec: LayoutSpec, width: int | None = None) -> None:
        width = width or self.root.winfo_width()
        try:
            self.status_label.configure(wraplength=max(120, width - (spec.outer_pad_x * 2) - 180))
        except tk.TclError:
            pass

    def _schedule_tool_rows_rebuild(self) -> None:
        self._cancel_after("_list_resize_after_id")
        self._list_resize_after_id = self.root.after(90, self._flush_tool_rows_rebuild)

    def _flush_tool_rows_rebuild(self) -> None:
        self._list_resize_after_id = ""
        self._rebuild_tool_rows()

    def _schedule_tool_wrap_refresh(self) -> None:
        self._cancel_after("_tool_wrap_refresh_after_id")
        self._tool_wrap_refresh_after_id = self.root.after(120, self._refresh_tool_wraplengths)

    def _refresh_tool_wraplengths(self) -> None:
        self._tool_wrap_refresh_after_id = ""
        title_wrap = self._card_title_wraplength(self._layout_spec())
        meta_wrap = self._tool_meta_wraplength()
        error_wrap = self._param_label_wraplength()
        for refs in self.tool_card_widgets.values():
            title = refs.get("title")
            meta = refs.get("meta")
            if isinstance(title, tk.Label):
                try:
                    title.configure(wraplength=title_wrap)
                except tk.TclError:
                    pass
            if isinstance(meta, tk.Label):
                try:
                    meta.configure(wraplength=meta_wrap)
                except tk.TclError:
                    pass
        for labels in self.param_error_labels.values():
            for label in labels.values():
                try:
                    label.configure(wraplength=error_wrap)
                except tk.TclError:
                    pass
        self._refresh_list_scrollregion()

    def _schedule_details_label_sync(self) -> None:
        if not hasattr(self, "details_panel") or not self.details_panel.winfo_ismapped():
            return
        self._cancel_after("_details_sync_after_id")
        self._details_sync_after_id = self.root.after(80, self._flush_details_label_sync)

    def _flush_details_label_sync(self) -> None:
        self._details_sync_after_id = ""
        self._sync_details_label_width()

    def _cancel_after(self, attr_name: str) -> None:
        after_id = getattr(self, attr_name, "")
        if not after_id:
            return
        try:
            self.root.after_cancel(after_id)
        except tk.TclError:
            pass
        setattr(self, attr_name, "")

    def _sync_details_label_width(self) -> None:
        details_label_width = self._details_label_minsize()
        if abs(details_label_width - self._last_details_label_width) >= 24:
            self._last_details_label_width = details_label_width
            self.root.after_idle(self._render_details)

    def _selected_tool(self) -> Tool | None:
        return next((tool for tool in self.tools if tool.id == self.current_tool_id), None)

    def _tool_by_id(self, tool_id: str) -> Tool | None:
        return next((tool for tool in self.tools if tool.id == tool_id), None)

    def _is_keyboard_control_focus(self, widget: tk.Widget | None = None) -> bool:
        focus_widget = widget or self.root.focus_get()
        if focus_widget is None:
            return False
        return isinstance(
            focus_widget,
            (
                tk.Entry,
                tk.Text,
                tk.Button,
                tk.Checkbutton,
                tk.Radiobutton,
                tk.Listbox,
                tk.Scrollbar,
                ttk.Button,
                ttk.Combobox,
                ttk.Scrollbar,
                tk.Spinbox,
            ),
        )

    def _is_widget_inside(self, widget: tk.Widget | None, ancestor: tk.Widget) -> bool:
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    @staticmethod
    def _event_int(event: tk.Event, name: str, default: int = 0) -> int:
        try:
            return int(getattr(event, name, default) or default)
        except (TypeError, ValueError):
            return default

    def _is_scroll_drag_blocked_widget(self, widget: tk.Widget) -> bool:
        return isinstance(
            widget,
            (
                tk.Entry,
                tk.Text,
                tk.Checkbutton,
                tk.Radiobutton,
                tk.Listbox,
                tk.Scrollbar,
                tk.Spinbox,
                ttk.Combobox,
                ttk.Scrollbar,
            ),
        )

    def _is_list_mousewheel_blocked_widget(self, widget: tk.Widget) -> bool:
        return isinstance(
            widget,
            (
                tk.Text,
                tk.Listbox,
                tk.Scrollbar,
                ttk.Combobox,
                ttk.Scrollbar,
            ),
        )

    def _bind_list_scroll_events(self, widget: tk.Widget) -> None:
        if not self._is_scroll_drag_blocked_widget(widget):
            widget.bind("<MouseWheel>", self._on_list_mousewheel, add="+")
            widget.bind("<Button-4>", self._on_list_mousewheel, add="+")
            widget.bind("<Button-5>", self._on_list_mousewheel, add="+")
        if isinstance(widget, tk.Button):
            widget.bind("<ButtonPress-1>", self._begin_list_button_drag_scroll)
            widget.bind("<B1-Motion>", self._drag_list_scroll)
            widget.bind("<ButtonRelease-1>", lambda event, button=widget: self._end_list_button_drag_scroll(event, button))
        for child in widget.winfo_children():
            self._bind_list_scroll_events(child)

    def _can_start_list_drag_scroll(self, event: tk.Event) -> bool:
        widget = getattr(event, "widget", None)
        if not isinstance(widget, tk.Widget):
            return False
        if not self._is_widget_inside(widget, self.list_shell):
            return False
        if isinstance(widget, (tk.Scrollbar, ttk.Scrollbar)):
            return False
        if self._is_scroll_drag_blocked_widget(widget):
            return False
        return True

    def _begin_list_drag_scroll(self, event: tk.Event) -> str | None:
        if not self._can_start_list_drag_scroll(event):
            return None
        y_root = self._event_int(event, "y_root")
        self._cancel_scroll_overscroll_animation()
        self._scroll_drag_active = True
        self._scroll_drag_started = False
        self._scroll_drag_start_y = y_root
        self._scroll_drag_last_y = y_root
        self._scroll_drag_button = self._event_int(event, "num")
        widget = getattr(event, "widget", None)
        self._scroll_drag_pressed_button = widget if isinstance(widget, tk.Button) else None
        return "break"

    def _begin_list_row_drag_scroll(self, event: tk.Event, tool_id: str) -> str | None:
        result = self._begin_list_drag_scroll(event)
        if result == "break":
            self._pending_row_click_tool_id = tool_id
        return result

    def _begin_list_button_drag_scroll(self, event: tk.Event) -> str:
        self._begin_list_drag_scroll(event)
        return "break"

    def _drag_list_scroll(self, event: tk.Event) -> str | None:
        if not self._scroll_drag_active:
            return None

        y_root = self._event_int(event, "y_root", self._scroll_drag_last_y)
        delta_y = y_root - self._scroll_drag_last_y
        if not self._scroll_drag_started:
            if abs(y_root - self._scroll_drag_start_y) < 4:
                return "break"
            self._scroll_drag_started = True
            self._scroll_drag_previous_cursor = str(self.root.cget("cursor") or "")
            self.root.configure(cursor="sb_v_double_arrow")
            self._suppress_pressed_button_click_for_scroll_drag()

        if delta_y:
            self._scroll_list_by_pixels(int(-delta_y * 1.15))
            self._scroll_drag_last_y = y_root
        return "break"

    def _end_list_drag_scroll(self, _event: tk.Event | None = None) -> str | None:
        if not self._scroll_drag_active:
            return None
        was_active = self._scroll_drag_active
        self._scroll_drag_active = False
        self._scroll_drag_started = False
        self._scroll_drag_start_y = 0
        self._scroll_drag_last_y = 0
        self._scroll_drag_button = 0
        self._scroll_drag_pressed_button = None
        try:
            self.root.configure(cursor=self._scroll_drag_previous_cursor)
        except tk.TclError:
            pass
        self._scroll_drag_previous_cursor = ""
        self._animate_scroll_overscroll_return()
        self._restore_scroll_drag_button_after_release()
        return "break" if was_active else None

    def _end_list_row_drag_scroll(self, event: tk.Event, tool_id: str) -> str | None:
        should_select = (
            self._scroll_drag_active
            and not self._scroll_drag_started
            and self._pending_row_click_tool_id == tool_id
        )
        self._pending_row_click_tool_id = ""
        result = self._end_list_drag_scroll(event)
        if should_select:
            self._select_tool(tool_id)
        return result

    def _end_list_button_drag_scroll(self, event: tk.Event, button: tk.Button) -> str:
        should_invoke = self._scroll_drag_active and not self._scroll_drag_started
        self._end_list_drag_scroll(event)
        if should_invoke:
            try:
                button.invoke()
            except tk.TclError:
                pass
        return "break"

    def _suppress_pressed_button_click_for_scroll_drag(self) -> None:
        button = self._scroll_drag_pressed_button
        if button is None or self._scroll_drag_disabled_button is not None:
            return
        try:
            self._scroll_drag_disabled_button_state = str(button.cget("state") or tk.NORMAL)
            if self._scroll_drag_disabled_button_state != tk.DISABLED:
                button.configure(state=tk.DISABLED)
                self._scroll_drag_disabled_button = button
        except tk.TclError:
            self._scroll_drag_disabled_button = None
            self._scroll_drag_disabled_button_state = tk.NORMAL

    def _restore_scroll_drag_button_after_release(self) -> None:
        button = self._scroll_drag_disabled_button
        previous_state = self._scroll_drag_disabled_button_state
        self._scroll_drag_disabled_button = None
        self._scroll_drag_disabled_button_state = tk.NORMAL
        if button is None:
            return

        def restore() -> None:
            try:
                button.configure(state=previous_state)
            except tk.TclError:
                pass

        try:
            self.root.after_idle(restore)
        except tk.TclError:
            restore()

    def _scroll_list_by_pixels(self, pixels: int) -> None:
        if pixels == 0:
            return

        content_height = self._list_content_height()
        canvas_height = max(self.list_canvas.winfo_height(), 1)
        max_top = max(content_height - canvas_height, 0)

        if self._scroll_overscroll_offset:
            easing_to_origin = (
                (self._scroll_overscroll_offset > 0 and pixels > 0)
                or (self._scroll_overscroll_offset < 0 and pixels < 0)
            )
            if easing_to_origin:
                next_offset = self._scroll_overscroll_offset - (pixels * 0.55)
                if self._scroll_overscroll_offset > 0:
                    self._set_scroll_overscroll_offset(max(0.0, next_offset))
                else:
                    self._set_scroll_overscroll_offset(min(0.0, next_offset))
                if self._scroll_overscroll_offset:
                    return

        if max_top <= 0:
            self._set_scroll_overscroll_offset(self._scroll_overscroll_offset - (pixels * 0.35))
            return

        current_top = self.list_canvas.canvasy(0)
        target_top = current_top + pixels
        if target_top < 0:
            self.list_canvas.yview_moveto(0)
            self._set_scroll_overscroll_offset(self._scroll_overscroll_offset + ((0 - target_top) * 0.35))
            return
        if target_top > max_top:
            self.list_canvas.yview_moveto(max_top / content_height)
            self._set_scroll_overscroll_offset(self._scroll_overscroll_offset - ((target_top - max_top) * 0.35))
            return

        self._set_scroll_overscroll_offset(0)
        self.list_canvas.yview_moveto(target_top / content_height)

    def _mousewheel_pixels(self, event: tk.Event) -> int:
        button_number = self._event_int(event, "num")
        if button_number == 4:
            return -84
        if button_number == 5:
            return 84

        delta = self._event_int(event, "delta")
        if delta == 0:
            return 0
        pixels = int(-delta * 1.2)
        if pixels == 0:
            pixels = -1 if delta > 0 else 1
        if abs(pixels) < 24:
            pixels = 24 if pixels > 0 else -24
        return pixels

    def _scroll_canvas_by_pixels(self, canvas: tk.Canvas, pixels: int) -> None:
        if pixels == 0:
            return
        try:
            scroll_region = canvas.bbox("all")
        except tk.TclError:
            return
        if not scroll_region:
            return

        content_height = max(scroll_region[3] - scroll_region[1], 1)
        canvas_height = max(canvas.winfo_height(), 1)
        max_top = max(content_height - canvas_height, 0)
        if max_top <= 0:
            canvas.yview_moveto(0)
            return
        current_top = canvas.canvasy(0)
        target_top = max(0, min(max_top, current_top + pixels))
        canvas.yview_moveto(target_top / content_height)

    def _on_global_mousewheel(self, event: tk.Event) -> str | None:
        widget = self._pointer_widget_for_event(event)
        if not isinstance(widget, tk.Widget):
            return None
        if hasattr(self, "outliner_panel") and self._is_widget_inside(widget, self.outliner_panel):
            if self._is_list_mousewheel_blocked_widget(widget):
                return None
            return self._on_list_mousewheel(event)
        if hasattr(self, "details_panel") and self._is_widget_inside(widget, self.details_panel):
            if isinstance(widget, (tk.Text, ttk.Combobox)):
                return None
            return self._on_details_mousewheel(event)
        return None

    def _pointer_widget_for_event(self, event: tk.Event) -> tk.Widget | None:
        x_root = getattr(event, "x_root", None)
        y_root = getattr(event, "y_root", None)
        if x_root is not None and y_root is not None:
            try:
                pointed = self.root.winfo_containing(int(x_root), int(y_root))
                if isinstance(pointed, tk.Widget):
                    return pointed
            except (tk.TclError, TypeError, ValueError):
                pass
        widget = getattr(event, "widget", None)
        return widget if isinstance(widget, tk.Widget) else None

    def _on_details_mousewheel(self, event: tk.Event) -> str:
        self._scroll_canvas_by_pixels(self.details_canvas, self._mousewheel_pixels(event))
        return "break"

    def _list_content_height(self) -> int:
        try:
            return max(self.list_inner.winfo_reqheight(), self.list_inner.winfo_height(), 1)
        except tk.TclError:
            return 1

    def _set_scroll_overscroll_offset(self, offset: float) -> None:
        clamped_offset = max(-64.0, min(64.0, float(offset)))
        self._scroll_overscroll_offset = clamped_offset
        try:
            self.list_canvas.coords(self.list_window, 0, int(round(clamped_offset)))
        except tk.TclError:
            pass

    def _cancel_scroll_overscroll_animation(self) -> None:
        if not self._scroll_overscroll_after_id:
            return
        try:
            self.root.after_cancel(self._scroll_overscroll_after_id)
        except tk.TclError:
            pass
        self._scroll_overscroll_after_id = ""

    def _animate_scroll_overscroll_return(self) -> None:
        self._scroll_overscroll_after_id = ""
        if abs(self._scroll_overscroll_offset) < 0.75:
            self._set_scroll_overscroll_offset(0)
            return

        self._set_scroll_overscroll_offset(self._scroll_overscroll_offset * 0.62)
        try:
            self._scroll_overscroll_after_id = self.root.after(16, self._animate_scroll_overscroll_return)
        except tk.TclError:
            self._scroll_overscroll_after_id = ""

    def _focus_search_shortcut(self, _event: tk.Event | None = None) -> str:
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, tk.END)
        return "break"

    def _add_tool_shortcut(self, _event: tk.Event | None = None) -> str:
        self._add_tool()
        return "break"

    def _copy_selected_shortcut(self, event: tk.Event | None = None) -> str | None:
        if event is not None and self._is_keyboard_control_focus(event.widget):
            return None
        if not self.current_tool_id:
            return "break"
        self._copy_code(self.current_tool_id)
        return "break"

    def _toggle_selected_params_shortcut(self, event: tk.Event | None = None) -> str | None:
        if event is not None and self._is_keyboard_control_focus(event.widget):
            return None
        if not self.current_tool_id:
            return "break"
        self._focus_selected_param()
        return "break"

    def _delete_selected_shortcut(self, event: tk.Event | None = None) -> str | None:
        if event is not None and self._is_keyboard_control_focus(event.widget):
            return None
        if not self.current_tool_id:
            return "break"
        self._delete_tool(self.current_tool_id)
        return "break"

    def _select_previous_tool_shortcut(self, event: tk.Event | None = None) -> str | None:
        if event is not None and self._is_keyboard_control_focus(event.widget):
            return None
        self._move_keyboard_selection(-1)
        return "break"

    def _select_next_tool_shortcut(self, event: tk.Event | None = None) -> str | None:
        if event is not None and self._is_keyboard_control_focus(event.widget):
            return None
        self._move_keyboard_selection(1)
        return "break"

    def _move_keyboard_selection(self, direction: int) -> None:
        if not self.filtered_tools:
            self.status_var.set("No tools to select.")
            return

        current_index = next(
            (index for index, tool in enumerate(self.filtered_tools) if tool.id == self.current_tool_id),
            None,
        )
        if current_index is None:
            next_index = 0 if direction >= 0 else len(self.filtered_tools) - 1
        else:
            next_index = max(0, min(len(self.filtered_tools) - 1, current_index + direction))

        selected_tool = self.filtered_tools[next_index]
        self._select_tool(selected_tool.id)
        self.root.after_idle(lambda tool_id=selected_tool.id: self._scroll_tool_into_view(tool_id))

    def _toggle_always_top(self) -> None:
        self.root.attributes("-topmost", bool(self.always_top_var.get()))
        self.settings.always_top = bool(self.always_top_var.get())
        self._save_settings()

    def _close(self) -> None:
        for attr_name in (
            "_filter_refresh_after_id",
            "_root_resize_after_id",
            "_list_resize_after_id",
            "_list_canvas_width_after_id",
            "_tool_wrap_refresh_after_id",
            "_details_sync_after_id",
        ):
            self._cancel_after(attr_name)
        self.settings.geometry = self.root.geometry()
        self.settings.always_top = bool(self.always_top_var.get())
        if hasattr(self, "details_panel"):
            try:
                self.settings.details_panel_width = max(260, int(self.details_panel.winfo_width()))
                self.settings.details_panel_height = max(220, int(self.details_panel.winfo_height()))
            except tk.TclError:
                pass
        self._persist_all_current_param_values()
        self._save_settings()
        self.root.destroy()

    def _save_settings(self) -> None:
        self.settings_store.save(self.settings)

    def _schedule_filter_refresh(self) -> None:
        self._cancel_after("_filter_refresh_after_id")
        self._filter_refresh_after_id = self.root.after(120, self._flush_filter_refresh)

    def _flush_filter_refresh(self) -> None:
        self._filter_refresh_after_id = ""
        self._refresh_list()

    def _toggle_filter_panel(self) -> None:
        if self.filter_panel.winfo_ismapped():
            self.filter_panel.grid_remove()
        else:
            self.filter_panel.grid()
        self._refresh_list_scrollregion()

    def _update_search_placeholder(self) -> None:
        if not hasattr(self, "search_placeholder"):
            return
        if self.search_var.get().strip() or self.root.focus_get() == self.search_entry:
            self.search_placeholder.place_forget()
            return
        self.search_placeholder.place(in_=self.search_entry, x=8, y=0, relheight=1, relwidth=1)

    def _reset_filters(self) -> None:
        self.workflow_var.set("All")
        self.role_var.set("All")
        self.category_var.set("All")
        self.visibility_filter_var.set(SHOW_RECOMMENDED)
        self._refresh_list()

    def _active_filter_summary(self) -> str:
        parts: list[str] = []
        workflow = self._selected_workflow_filter()
        role = self._selected_role_filter()
        category = self._selected_category_filter()
        show = self.visibility_filter_var.get().strip() or SHOW_RECOMMENDED
        if workflow:
            parts.append(workflow)
        if role:
            parts.append(role)
        if category:
            parts.append(category)
        parts.append(show)
        return " | ".join(parts)

    def _update_filter_summary(self) -> None:
        self.active_filter_summary_var.set(self._active_filter_summary())

    def _refresh_list(self) -> None:
        self._refresh_workflow_filter_options()
        query = self.search_var.get()
        category = self._selected_category_filter()
        workflow = self._selected_workflow_filter()
        role = self._selected_role_filter()
        self._update_filter_summary()

        self.filtered_tools = self._sort_tools_for_display(
            [
                tool
                for tool in self.tools
                if self._tool_matches_visibility_filter(tool) and tool.matches(query, category, workflow, role)
            ]
        )
        visible_ids = {tool.id for tool in self.filtered_tools}
        if self.current_tool_id and self.current_tool_id not in visible_ids:
            self.current_tool_id = ""
        if not self.current_tool_id and self.filtered_tools:
            self.current_tool_id = self.filtered_tools[0].id
        self.expanded_tool_id = self.current_tool_id
        self.count_var.set(self._filtered_count_text(len(self.filtered_tools)))
        self._rebuild_tool_rows()
        self._render_details()

    def _selected_category_filter(self) -> str | None:
        value = self.category_var.get().strip()
        return value if value and value != "All" and value in self._category_filter_values() else None

    def _selected_workflow_filter(self) -> str | None:
        value = self.workflow_var.get().strip()
        return value if value and value != "All" else None

    def _selected_role_filter(self) -> str | None:
        value = self.role_var.get().strip()
        return value if value and value != "All" else None

    def _tool_matches_visibility_filter(self, tool: Tool) -> bool:
        mode = self.visibility_filter_var.get().strip()
        if mode == SHOW_HIDDEN_LEGACY:
            return tool.visibility == VISIBILITY_HIDDEN
        if mode == SHOW_ALL_WORKFLOW_TOOLS:
            return tool.visibility in {VISIBILITY_PRIMARY, VISIBILITY_SECONDARY}
        return tool.visibility == VISIBILITY_PRIMARY

    def _filtered_count_text(self, count: int) -> str:
        mode = self.visibility_filter_var.get().strip()
        if mode == SHOW_HIDDEN_LEGACY:
            return f"{count} hidden / legacy tools"
        if mode == SHOW_ALL_WORKFLOW_TOOLS:
            return f"{count} workflow tools"
        return f"{count} recommended tools"

    def _refresh_workflow_filter_options(self) -> None:
        workflow_values = self._workflow_filter_values()
        role_values = self._role_filter_values()
        category_values = self._category_filter_values()
        if hasattr(self, "workflow_combo"):
            self.workflow_combo.configure(values=workflow_values)
        if hasattr(self, "role_combo"):
            self.role_combo.configure(values=role_values)
        if hasattr(self, "category_combo"):
            self.category_combo.configure(values=["All", *category_values])
        if self.workflow_var.get() not in workflow_values:
            self.workflow_var.set("All")
        if self.role_var.get() not in role_values:
            self.role_var.set("All")
        if self.category_var.get() not in ["All", *category_values]:
            self.category_var.set("All")

    def _workflow_filter_values(self) -> list[str]:
        tools = [tool for tool in self.tools if self._tool_matches_visibility_filter(tool)]
        visible_workflows = {workflow for tool in tools for workflow in tool.workflows}
        ordered = [workflow for workflow in WORKFLOWS if workflow in visible_workflows]
        extras = sorted(workflow for workflow in visible_workflows if workflow not in WORKFLOWS)
        return ["All", *ordered, *extras]

    def _role_filter_values(self) -> list[str]:
        tools = [tool for tool in self.tools if self._tool_matches_visibility_filter(tool)]
        visible_roles = {role for tool in tools for role in tool.roles}
        ordered = [role for role in ROLES if role in visible_roles]
        extras = sorted(role for role in visible_roles if role not in ROLES)
        return ["All", *ordered, *extras]

    def _category_filter_values(self) -> list[str]:
        tools = [tool for tool in self.tools if self._tool_matches_visibility_filter(tool)]
        return category_options(tools)

    def _rebuild_tool_rows(self) -> None:
        for row in self.tool_rows:
            row.destroy()
        self.tool_rows = []
        self.tool_row_by_id = {}
        self.tool_card_widgets = {}
        self.copy_button_by_tool_id = {}
        self.param_input_widgets = {}
        self.param_error_labels = {}
        spec = self._layout_spec()

        if not self.filtered_tools:
            empty = tk.Frame(self.list_inner, bg=PANEL, padx=10, pady=10)
            empty.grid(row=0, column=0, sticky="ew")
            library_empty = not self.tools
            title_text = "No tools yet" if library_empty else "No tools found"
            body_text = (
                "Add your first Unreal Python tool."
                if library_empty
                else self._empty_filter_message()
            )
            tk.Label(
                empty,
                text=title_text,
                bg=PANEL,
                fg=TEXT,
                font=PANEL_TITLE_FONT,
            ).grid(row=0, column=0, sticky="w")
            tk.Label(
                empty,
                text=body_text,
                bg=PANEL,
                fg=MUTED,
                font=UI_FONT,
            ).grid(row=1, column=0, sticky="w", pady=(6, 0))
            if library_empty:
                make_button(
                    empty,
                    "+ Add Tool",
                    self._add_tool,
                    variant="success",
                    padx=14,
                    pady=7,
                    font=UI_FONT_BOLD,
                ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(14, 0))
                empty.columnconfigure(0, weight=1)
            self.tool_rows.append(empty)
            return

        for index, tool in enumerate(self.filtered_tools):
            row = self._create_tool_card(self.list_inner, tool, index)
            row_gap = 10 if tool.id == self.current_tool_id else 2
            row.grid(row=index, column=0, sticky="ew", pady=(0, row_gap))
            self.list_inner.columnconfigure(0, weight=1)
            self.tool_rows.append(row)
            self.tool_row_by_id[tool.id] = row

    def _empty_filter_message(self) -> str:
        workflow = self._selected_workflow_filter()
        if workflow:
            return "No tools in this workflow yet."
        return "No tools found. Change filters or search."

    def _replace_visible_tool_rows(self, tool_ids: list[str]) -> None:
        self._update_visible_tool_rows(tool_ids)

    def _replace_tool_rows(self, tool_ids: list[str]) -> bool:
        replaced = False
        for tool_id in dict.fromkeys(tool_id for tool_id in tool_ids if tool_id):
            replaced = self._replace_tool_row(tool_id) or replaced
        if replaced:
            self._refresh_list_scrollregion()
        return replaced

    def _replace_tool_row(self, tool_id: str) -> bool:
        tool = next((visible_tool for visible_tool in self.filtered_tools if visible_tool.id == tool_id), None)
        if tool is None:
            return False
        try:
            index = self.filtered_tools.index(tool)
        except ValueError:
            return False

        old_row = self.tool_row_by_id.get(tool_id)
        if old_row is not None:
            try:
                old_row.destroy()
            except tk.TclError:
                pass
        self._clear_tool_widget_refs(tool_id)

        row = self._create_tool_card(self.list_inner, tool, index)
        row_gap = 10 if tool.id == self.current_tool_id else 2
        row.grid(row=index, column=0, sticky="ew", pady=(0, row_gap))
        self.list_inner.columnconfigure(0, weight=1)
        while len(self.tool_rows) <= index:
            self.tool_rows.append(row)
        self.tool_rows[index] = row
        self.tool_row_by_id[tool.id] = row
        return True

    def _update_visible_tool_rows(self, tool_ids: list[str]) -> None:
        seen: set[str] = set()
        for tool_id in tool_ids:
            if not tool_id or tool_id in seen:
                continue
            seen.add(tool_id)
            self._update_visible_tool_row(tool_id)

    def _update_visible_tool_row(self, tool_id: str) -> None:
        tool = next((visible_tool for visible_tool in self.filtered_tools if visible_tool.id == tool_id), None)
        if tool is None:
            return

        refs = self.tool_card_widgets.get(tool_id)
        if not refs:
            return
        border = refs.get("border")
        title = refs.get("title")
        meta = refs.get("meta")
        meta_frame = refs.get("meta_frame")
        workflow_badge = refs.get("workflow_badge")
        category_badge = refs.get("category_badge")
        visibility_badge = refs.get("visibility_badge")
        favorite = refs.get("favorite")
        card = refs.get("card")
        header = refs.get("header")
        title_frame = refs.get("title_frame")
        selected_marker = refs.get("selected_marker")
        accent = refs.get("accent")
        if not isinstance(border, tk.Frame):
            return

        selected = tool.id == self.current_tool_id
        row_bg = PANEL_ALT if selected else str(refs.get("row_bg") or ROW_BG)
        try:
            border.configure(bg=SELECTION_BLUE if selected else BORDER_DARK)
            for widget in (card, header, title_frame, meta_frame):
                if isinstance(widget, tk.Frame):
                    widget.configure(bg=row_bg)
            if isinstance(title, tk.Label):
                title.configure(text=tool.name, bg=row_bg, fg=TEXT, font=UI_FONT_BOLD if selected else UI_FONT)
            if isinstance(selected_marker, tk.Label):
                selected_marker.configure(text="▾" if selected else "", bg=row_bg, fg=SELECTION_BLUE)
            if isinstance(meta, tk.Label):
                meta.configure(text=tool.description, bg=row_bg, fg=MUTED, wraplength=self._tool_meta_wraplength())
            if isinstance(workflow_badge, tk.Label):
                workflow = _primary_workflow(tool)
                workflow_badge.configure(text=workflow, bg=_workflow_color(workflow), fg=TEXT)
            if isinstance(category_badge, tk.Label):
                category_badge.configure(
                    text=tool.category,
                    bg=_category_color(tool.category),
                    fg=_category_text_color(tool.category),
                )
            if isinstance(visibility_badge, tk.Label):
                visibility_badge.configure(
                    text=_visibility_badge_text(tool),
                    bg=_visibility_color(tool.visibility),
                    fg=TEXT,
                )
                if tool.visibility == VISIBILITY_PRIMARY:
                    visibility_badge.grid_remove()
                else:
                    visibility_badge.grid(row=0, column=2, sticky="nw", padx=(0, 6))
            if isinstance(favorite, tk.Label):
                favorite.configure(text="★" if tool.id in self._favorite_ids() else "", bg=row_bg)
            if isinstance(accent, tk.Frame):
                accent.configure(bg=_category_color(tool.category))
        except tk.TclError:
            return
        self.root.after_idle(self._refresh_list_scrollregion)

    def _clear_tool_widget_refs(self, tool_id: str) -> None:
        self.tool_row_by_id.pop(tool_id, None)
        self.tool_card_widgets.pop(tool_id, None)
        self.copy_button_by_tool_id.pop(tool_id, None)
        self.param_input_widgets.pop(tool_id, None)
        self.param_error_labels.pop(tool_id, None)

    def _create_collapsed_tool_row(self, parent: tk.Widget, tool: Tool, index: int = 0) -> tk.Frame:
        base_bg = ROW_BG_ALT if index % 2 else ROW_BG
        row = tk.Frame(parent, bg=BORDER_DARK, padx=0, pady=0)
        row.columnconfigure(1, weight=1)
        accent = tk.Frame(row, bg=_category_color(tool.category), width=2)
        accent.grid(row=0, column=0, sticky="ns", padx=(0, 1))
        button = tk.Button(
            row,
            text=_collapsed_tool_text(tool, tool.id in self._favorite_ids()),
            command=lambda tool_id=tool.id: self._select_tool(tool_id),
            bg=base_bg,
            fg=TEXT,
            activebackground=ROW_HOVER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            anchor="w",
            justify="left",
            padx=12,
            pady=7,
            font=UI_FONT,
            cursor="hand2",
        )
        button.grid(row=0, column=1, sticky="ew")
        button.bind("<Double-Button-1>", lambda _event, tool_id=tool.id: self._copy_code(tool_id))
        button.bind("<Button-3>", lambda _event, tool_id=tool.id: self._show_tool_menu(tool_id))
        button.bind("<Enter>", lambda _event, tool_id=tool.id: self._set_tool_row_hover(tool_id, True))
        button.bind("<Leave>", lambda _event, tool_id=tool.id: self._set_tool_row_hover(tool_id, False))

        for widget in (row, accent):
            widget.bind("<ButtonPress-1>", lambda event, tool_id=tool.id: self._begin_list_row_drag_scroll(event, tool_id))
            widget.bind("<B1-Motion>", self._drag_list_scroll)
            widget.bind("<ButtonRelease-1>", lambda event, tool_id=tool.id: self._end_list_row_drag_scroll(event, tool_id))
            widget.bind("<Double-Button-1>", lambda _event, tool_id=tool.id: self._copy_code(tool_id))
            widget.bind("<Button-3>", lambda _event, tool_id=tool.id: self._show_tool_menu(tool_id))
            widget.bind("<Enter>", lambda _event, tool_id=tool.id: self._set_tool_row_hover(tool_id, True))
            widget.bind("<Leave>", lambda _event, tool_id=tool.id: self._set_tool_row_hover(tool_id, False))

        self.tool_card_widgets[tool.id] = {
            "border": row,
            "title": button,
            "card": button,
            "accent": accent,
            "row_bg": base_bg,
            "compact": True,
        }
        self._bind_list_scroll_events(row)
        return row

    def _create_tool_card(self, parent: tk.Widget, tool: Tool, index: int = 0) -> tk.Frame:
        selected = tool.id == self.current_tool_id
        if not selected:
            return self._create_collapsed_tool_row(parent, tool, index)

        border_color = ACCENT_DARK if selected else BORDER_DARK
        card_border = tk.Frame(parent, bg=border_color, padx=1, pady=1)
        card_border.rowconfigure(0, weight=1)
        card_border.columnconfigure(0, weight=1)
        base_bg = ROW_BG_ALT if index % 2 else ROW_BG
        row_bg = PANEL_ALT if selected else base_bg
        card = tk.Frame(card_border, bg=row_bg, padx=0, pady=0, cursor="hand2")
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)

        header = tk.Frame(card, bg=row_bg, padx=14 if selected else 12, pady=10 if selected else 8, cursor="hand2")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, weight=0)

        accent = tk.Frame(header, bg=_category_color(tool.category), width=2)
        accent.grid(row=0, column=0, rowspan=3 if selected else 2, sticky="ns", padx=(0, 10))

        title_frame = tk.Frame(header, bg=row_bg, cursor="hand2")
        title_frame.grid(row=0, column=1, sticky="ew")
        title_frame.columnconfigure(1, weight=1)

        selected_marker = tk.Label(
            title_frame,
            text="▾" if selected else "",
            bg=row_bg,
            fg=ACCENT,
            font=UI_FONT_BOLD,
            width=2,
            anchor="w",
            cursor="hand2",
        )
        selected_marker.grid(row=0, column=0, sticky="w")

        title = tk.Label(
            title_frame,
            text=tool.name,
            bg=row_bg,
            fg=TEXT,
            font=UI_FONT_BOLD if selected else UI_FONT,
            anchor="w",
            justify="left",
            cursor="hand2",
            wraplength=self._tool_meta_wraplength(),
        )
        title.grid(row=0, column=1, sticky="ew")
        meta_frame = tk.Frame(header, bg=row_bg)
        meta_frame.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(2, 0))
        meta_frame.columnconfigure(3, weight=1)
        workflow = _primary_workflow(tool)
        workflow_badge = tk.Label(
            meta_frame,
            text=workflow,
            bg=_workflow_color(workflow),
            fg=TEXT,
            font=SMALL_FONT,
            anchor="w",
            padx=7,
            pady=2,
            cursor="hand2",
        )
        workflow_badge.grid(row=0, column=0, sticky="nw", padx=(0, 6))
        category_badge = tk.Label(
            meta_frame,
            text=tool.category,
            bg=_category_color(tool.category),
            fg=_category_text_color(tool.category),
            font=SMALL_FONT,
            anchor="w",
            padx=7,
            pady=2,
            cursor="hand2",
        )
        category_badge.grid(row=0, column=1, sticky="nw", padx=(0, 6))
        visibility_badge = tk.Label(
            meta_frame,
            text=_visibility_badge_text(tool),
            bg=_visibility_color(tool.visibility),
            fg=TEXT,
            font=SMALL_FONT,
            anchor="w",
            padx=7,
            pady=2,
            cursor="hand2",
        )
        if tool.visibility != VISIBILITY_PRIMARY:
            visibility_badge.grid(row=0, column=2, sticky="nw", padx=(0, 6))
        else:
            visibility_badge.grid_remove()
        meta = tk.Label(
            meta_frame,
            text=tool.description,
            bg=row_bg,
            fg=MUTED,
            font=SMALL_FONT,
            anchor="w",
            justify="left",
            cursor="hand2",
            wraplength=self._tool_meta_wraplength(),
        )
        meta.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))

        actions = None
        if selected:
            actions = tk.Frame(header, bg=row_bg)
            actions.grid(row=2, column=1, sticky="w", pady=(9, 0))
            copy_feedback_active = tool.id == self.copy_feedback_tool_id
            copy_button = make_button(
                actions,
                "Copied" if copy_feedback_active else "Copy",
                lambda tool_id=tool.id: self._copy_code(tool_id),
                variant="success",
                padx=22,
                pady=7,
                font=UI_FONT_BOLD,
            )
            copy_button.grid(row=0, column=0, padx=(0, 7))
            self.copy_button_by_tool_id[tool.id] = copy_button
            if parse_tool_params(tool.code):
                make_toolbar_button(actions, "Reset Params", lambda tool_id=tool.id: self._reset_params(tool_id)).grid(
                    row=0,
                    column=1,
                    padx=(0, 5),
                )
                menu_column = 2
            else:
                menu_column = 1
            make_toolbar_button(actions, "More", lambda tool_id=tool.id: self._show_tool_menu(tool_id)).grid(
                row=0,
                column=menu_column,
            )

        favorite = tk.Label(
            title_frame,
            text="★" if tool.id in self._favorite_ids() else "",
            bg=row_bg,
            fg=WARNING,
            font=("Segoe UI Symbol", 8),
            width=2,
            anchor="e",
            cursor="hand2",
        )
        favorite.grid(row=0, column=2, sticky="ne", padx=(4, 0))

        if selected:
            params = parse_tool_params(tool.code)
            if params:
                params_shell = tk.Frame(card, bg=PANEL, padx=8, pady=8, highlightthickness=1, highlightbackground=BORDER_DARK)
                params_shell.grid(row=1, column=0, sticky="ew", pady=(0, 8), padx=(0, 0))
                params_shell.columnconfigure(0, weight=1)
                self._ensure_param_vars(tool.id, params)
                for group_index, group in enumerate(_group_tool_params(params)):
                    self._render_param_group(params_shell, group_index, tool.id, group)
            else:
                tk.Label(
                    card,
                    text="No editable parameters. Use Copy to copy this tool.",
                    bg=PANEL,
                    fg=MUTED,
                    font=UI_FONT,
                    anchor="w",
                    padx=12,
                    pady=8,
                ).grid(row=1, column=0, sticky="ew")

        self.tool_card_widgets[tool.id] = {
            "border": card_border,
            "title": title,
            "selected_marker": selected_marker,
            "meta": meta,
            "meta_frame": meta_frame,
            "workflow_badge": workflow_badge,
            "category_badge": category_badge,
            "visibility_badge": visibility_badge,
            "favorite": favorite,
            "card": card,
            "header": header,
            "title_frame": title_frame,
            "actions": actions,
            "accent": accent,
            "row_bg": base_bg,
        }

        row_widgets = [
            card_border,
            card,
            header,
            title_frame,
            selected_marker,
            title,
            meta_frame,
            meta,
            workflow_badge,
            category_badge,
            visibility_badge,
            favorite,
            accent,
        ]
        for widget in row_widgets:
            widget.bind("<ButtonPress-1>", lambda event, tool_id=tool.id: self._begin_list_row_drag_scroll(event, tool_id))
            widget.bind("<B1-Motion>", self._drag_list_scroll)
            widget.bind("<ButtonRelease-1>", lambda event, tool_id=tool.id: self._end_list_row_drag_scroll(event, tool_id))
            widget.bind("<Double-Button-1>", lambda _event, tool_id=tool.id: self._copy_code(tool_id))
            widget.bind("<Button-3>", lambda _event, tool_id=tool.id: self._show_tool_menu(tool_id))
            widget.bind("<Enter>", lambda _event, tool_id=tool.id: self._set_tool_row_hover(tool_id, True))
            widget.bind("<Leave>", lambda _event, tool_id=tool.id: self._set_tool_row_hover(tool_id, False))
        self._bind_list_scroll_events(card_border)
        return card_border

    def _set_tool_row_hover(self, tool_id: str, active: bool) -> None:
        if tool_id == self.current_tool_id:
            return
        refs = self.tool_card_widgets.get(tool_id)
        if not refs:
            return
        color = ROW_HOVER if active else str(refs.get("row_bg") or ROW_BG)
        for key in ("card", "header", "title_frame", "meta_frame", "selected_marker", "title", "meta", "favorite"):
            widget = refs.get(key)
            if isinstance(widget, (tk.Frame, tk.Label)):
                try:
                    widget.configure(bg=color)
                except tk.TclError:
                    pass
            elif isinstance(widget, tk.Button):
                try:
                    widget.configure(bg=color, activebackground=ROW_HOVER)
                except tk.TclError:
                    pass
        accent = refs.get("accent")
        if isinstance(accent, tk.Frame):
            try:
                tool = self._tool_by_id(tool_id)
                accent.configure(bg=_category_color(tool.category) if tool else color)
            except tk.TclError:
                pass

    def _render_details(self) -> None:
        # The app now keeps parameters inline with the selected tool row.
        # The old Details dock remains only as an internal compatibility surface.
        if not hasattr(self, "details_inner") or not self.details_panel.winfo_ismapped():
            return
        if not hasattr(self, "details_inner"):
            return
        for child in self.details_inner.winfo_children():
            child.destroy()
        self.copy_button_by_tool_id = {}
        self.param_input_widgets = {}
        self.param_error_labels = {}

        tool = self._selected_tool()
        if tool is None:
            empty = tk.Frame(self.details_inner, bg=PANEL, padx=12, pady=12)
            empty.grid(row=0, column=0, sticky="ew")
            tk.Label(empty, text="No Selection", bg=PANEL, fg=TEXT, font=PANEL_TITLE_FONT).grid(row=0, column=0, sticky="w")
            tk.Label(
                empty,
                text="Select a tool in the Outliner to edit its Unreal-style details.",
                bg=PANEL,
                fg=MUTED,
                font=UI_FONT,
                wraplength=320,
                justify="left",
            ).grid(row=1, column=0, sticky="ew", pady=(6, 0))
            self.root.after_idle(self._refresh_details_scrollregion)
            return

        row_index = 0
        self._render_details_selection_header(self.details_inner, row_index, tool)
        row_index += 1
        self._render_details_search_tabs(self.details_inner, row_index)
        row_index += 1
        self._render_parameters_section(self.details_inner, row_index, tool)
        row_index += 1
        self._render_tool_details_section(self.details_inner, row_index, tool)
        row_index += 1
        self._render_source_section(self.details_inner, row_index, tool)
        self.root.after_idle(self._refresh_details_scrollregion)

    def _render_details_selection_header(self, parent: tk.Widget, row_index: int, tool: Tool) -> None:
        header = tk.Frame(parent, bg=PANEL, padx=8, pady=6, highlightthickness=1, highlightbackground=BORDER_DARK)
        header.grid(row=row_index, column=0, sticky="ew", pady=(0, 4))
        header.columnconfigure(1, weight=1)
        make_static_icon(header, "tool", size=15, bg=PANEL, fg=TEXT).grid(row=0, column=0, sticky="w", padx=(0, 7))
        tk.Label(header, text=tool.name, bg=PANEL, fg=TEXT, font=PANEL_TITLE_FONT, anchor="w").grid(
            row=0,
            column=1,
            sticky="ew",
        )
        actions = tk.Frame(header, bg=PANEL)
        actions.grid(row=0, column=2, sticky="e", padx=(8, 0))
        copy_feedback_active = tool.id == self.copy_feedback_tool_id
        copy_button = make_toolbar_button(
            actions,
            "Copied" if copy_feedback_active else "Copy",
            lambda tool_id=tool.id: self._copy_code(tool_id),
            variant="success",
        )
        copy_button.grid(row=0, column=0, padx=(0, 5))
        self.copy_button_by_tool_id[tool.id] = copy_button
        if parse_tool_params(tool.code):
            make_toolbar_button(actions, "Reset Params", lambda tool_id=tool.id: self._reset_params(tool_id)).grid(
                row=0,
                column=1,
                padx=(0, 5),
            )
        make_toolbar_button(actions, "Edit", lambda tool_id=tool.id: self._edit_tool(tool_id)).grid(
            row=0,
            column=2,
            padx=(0, 5),
        )
        make_toolbar_button(actions, "More", lambda tool_id=tool.id: self._show_tool_menu(tool_id)).grid(row=0, column=3)

    def _render_details_search_tabs(self, parent: tk.Widget, row_index: int) -> None:
        panel = tk.Frame(parent, bg=PANEL, padx=7, pady=4)
        panel.grid(row=row_index, column=0, sticky="ew", pady=(0, 3))
        panel.columnconfigure(0, weight=1)
        search_shell = make_search_shell(panel)
        search_shell.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        search_entry = make_dark_entry(search_shell, self.details_search_var)
        self.details_search_entry = search_entry
        search_entry.configure(relief="flat", bd=0)
        search_entry.grid(row=0, column=1, sticky="ew", ipady=2, padx=(4, 5))
        if not self._details_search_trace_registered:
            self.details_search_var.trace_add("write", lambda *_: self._rerender_details_preserving_search_focus())
            self._details_search_trace_registered = True
        favorite_text = "Favorited" if self.current_tool_id in self._favorite_ids() else "Favorite"
        make_toolbar_button(
            panel,
            favorite_text,
            lambda tool_id=self.current_tool_id: self._toggle_favorite(tool_id),
        ).grid(row=0, column=1, padx=(0, 0))

        tabs = tk.Frame(panel, bg=PANEL)
        tabs.grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))
        for index, label in enumerate(["General", "Transform", "Selection", "All"]):
            active = self.details_category_var.get() == label
            button = make_toolbar_button(tabs, label, lambda selected=label: self._set_details_category_tab(selected))
            button.configure(
                bg=ACCENT if active else HEADER_BG,
                activebackground=ACCENT_HOVER if active else ROW_HOVER,
                padx=11,
                pady=3,
            )
            button.grid(row=0, column=index, padx=(0, 5))

    def _render_tool_details_section(self, parent: tk.Widget, row_index: int, tool: Tool) -> None:
        section = self._create_details_section(parent, "Tool", row_index)
        row = 0
        if tool.description:
            self._create_readonly_property(section, row, "Notes", tool.description)
            row += 1
        self._create_readonly_property(section, row, "Workflow", ", ".join(tool.workflows) or "None")
        row += 1
        self._create_readonly_property(section, row, "Roles", ", ".join(tool.roles) or "None")
        row += 1
        self._create_readonly_property(section, row, "Visibility", tool.visibility)
        row += 1
        self._create_readonly_property(section, row, "Category", tool.category)
        row += 1
        self._create_readonly_property(section, row, "Tags", ", ".join(tool.tags) or "None")


    def _render_parameters_section(self, parent: tk.Widget, row_index: int, tool: Tool) -> None:
        section = self._create_details_section(parent, "Parameters", row_index, collapsible=False)
        params = parse_tool_params(tool.code)
        if not params:
            tk.Label(section, text="This tool has no editable parameters.", bg=PANEL, fg=MUTED, font=UI_FONT).grid(
                row=0,
                column=0,
                sticky="ew",
                padx=8,
                pady=8,
            )
            return
        self._ensure_param_vars(tool.id, params)
        rendered_index = 0
        for group in _group_tool_params(params):
            if not self._details_group_matches_filters(group):
                continue
            self._render_param_group(section, rendered_index, tool.id, group)
            rendered_index += 1
        if rendered_index == 0:
            tk.Label(section, text="No matching properties.", bg=PANEL, fg=MUTED, font=UI_FONT).grid(
                row=0,
                column=0,
                sticky="ew",
                padx=7,
                pady=7,
            )

    def _details_group_matches_filters(self, group: ParamRenderGroup) -> bool:
        query = self.details_search_var.get().strip().casefold()
        category = self.details_category_var.get().strip()
        if query:
            haystack = " ".join([group.label, *[param.name for param in group.params], *[param.label for param in group.params]]).casefold()
            if query not in haystack:
                return False
        if category in {"", "All"}:
            return True
        transform_labels = {"location", "rotation", "scale", "yaw", "offset"}
        if category == "Transform":
            return group.label.casefold() in transform_labels or any(
                token in param.name.casefold()
                for param in group.params
                for token in ("offset", "yaw", "scale", "location", "rotation")
            )
        if category == "Selection":
            return any("selected" in param.name.casefold() or "selection" in param.label.casefold() for param in group.params)
        if category == "General":
            return not any(
                token in param.name.casefold()
                for param in group.params
                for token in ("offset", "yaw", "scale", "location", "rotation", "selected", "selection")
            )
        return True

    def _render_source_section(self, parent: tk.Widget, row_index: int, tool: Tool) -> None:
        section = self._create_details_section(parent, "Source", row_index)
        code_shell = tk.Frame(section, bg=BORDER, padx=1, pady=1)
        code_shell.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        code_shell.columnconfigure(0, weight=1)
        text = tk.Text(
            code_shell,
            height=8,
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=ACCENT_DARK,
            selectforeground=TEXT,
            borderwidth=0,
            font=CODE_FONT,
            padx=8,
            pady=8,
            relief="flat",
            wrap="none",
        )
        text.grid(row=0, column=0, sticky="nsew")
        text.insert("1.0", tool.code)
        text.configure(state=tk.DISABLED)
        y_scroll = ttk.Scrollbar(code_shell, orient="vertical", command=text.yview, style="Dark.Vertical.TScrollbar")
        y_scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=y_scroll.set)

    def _create_details_section(
        self,
        parent: tk.Widget,
        title: str,
        row_index: int,
        *,
        collapsible: bool = True,
    ) -> tk.Frame:
        shell = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        shell.grid(row=row_index, column=0, sticky="ew", padx=0, pady=(0, 6))
        shell.columnconfigure(0, weight=1)
        cursor = "hand2" if collapsible else ""
        header = tk.Frame(shell, bg=HEADER_BG, padx=6, pady=4, cursor=cursor)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        collapsed = collapsible and self._is_detail_section_collapsed(title)
        tk.Label(
            header,
            text="▸" if collapsed else ("▾" if collapsible else ""),
            bg=HEADER_BG,
            fg=MUTED,
            font=("Segoe UI Symbol", 8),
            width=2,
            cursor=cursor,
        ).grid(row=0, column=0, sticky="w")
        tk.Label(header, text=title, bg=HEADER_BG, fg=TEXT, font=PANEL_TITLE_FONT, anchor="w", cursor=cursor).grid(
            row=0,
            column=1,
            sticky="ew",
        )
        if collapsible:
            header.bind("<Button-1>", lambda _event, section=title: self._toggle_detail_section(section))
            for child in header.winfo_children():
                child.bind("<Button-1>", lambda _event, section=title: self._toggle_detail_section(section))
        body = tk.Frame(shell, bg=PANEL)
        body.grid(row=1, column=0, sticky="ew")
        body.columnconfigure(0, weight=1)
        if collapsed:
            body.grid_remove()
        self._detail_section_bodies[title] = body
        return body

    def _is_detail_section_collapsed(self, section: str) -> bool:
        if section == "Parameters":
            return False
        return section in set(self.settings.collapsed_detail_sections or [])

    def _toggle_detail_section(self, section: str) -> None:
        if section == "Parameters":
            return
        collapsed = set(self.settings.collapsed_detail_sections or [])
        if section in collapsed:
            collapsed.remove(section)
        else:
            collapsed.add(section)
        self.settings.collapsed_detail_sections = sorted(collapsed)
        self._save_settings()
        self._render_details()

    def _details_label_minsize(self) -> int:
        width = 0
        try:
            if self.details_panel.winfo_ismapped():
                width = int(self.details_panel.winfo_width())
        except tk.TclError:
            width = 0
        if width <= 1:
            width = self._content_width()
        return max(130, min(220, int(width * 0.28)))

    def _create_readonly_property(self, parent: tk.Widget, row_index: int, label: str, value: str) -> None:
        row = tk.Frame(parent, bg=ROW_BG if row_index % 2 == 0 else ROW_BG_ALT, padx=0, pady=0, height=28)
        row.grid(row=row_index, column=0, sticky="ew")
        row.grid_propagate(False)
        row.columnconfigure(0, weight=0, minsize=self._details_label_minsize())
        row.columnconfigure(1, weight=1)
        row_bg = row.cget("bg")
        tk.Label(row, text=label, bg=row_bg, fg=MUTED, font=UI_FONT, anchor="w", padx=8).grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        tk.Label(row, text=value, bg=row_bg, fg=TEXT, font=UI_FONT, anchor="w", justify="left", padx=8).grid(
            row=0,
            column=1,
            sticky="nsew",
        )

    def _render_param_group(self, parent: tk.Widget, row_index: int, tool_id: str, group: ParamRenderGroup) -> None:
        row_bg = ROW_BG if row_index % 2 == 0 else ROW_BG_ALT
        row = tk.Frame(parent, bg=row_bg, padx=0, pady=0, highlightthickness=0)
        row.grid(row=row_index, column=0, sticky="ew", pady=(0, 3))
        two_column = self._params_use_two_column()
        if two_column:
            row.columnconfigure(0, weight=0, minsize=self._details_label_minsize())
            row.columnconfigure(1, weight=1)
            label_row = 0
            label_column = 0
            control_row = 0
            control_column = 1
            label_pad = (10, 7)
            control_pad = (10, 6)
        else:
            row.columnconfigure(0, weight=1)
            label_row = 0
            label_column = 0
            control_row = 1
            control_column = 0
            label_pad = (10, 6)
            control_pad = (10, 8)
        row.bind("<Enter>", lambda _event, widget=row: widget.configure(bg=ROW_HOVER))
        row.bind("<Leave>", lambda _event, widget=row, bg=row_bg: widget.configure(bg=bg))
        label_shell = tk.Frame(row, bg=row_bg, padx=label_pad[0], pady=label_pad[1])
        label_shell.grid(row=label_row, column=label_column, sticky="nsew")
        label_shell.columnconfigure(0, weight=1)
        tk.Label(label_shell, text=group.label, bg=row_bg, fg=TEXT, font=UI_FONT_BOLD, anchor="w").grid(
            row=0,
            column=0,
            sticky="ew",
        )
        control_shell = tk.Frame(row, bg=row_bg, padx=control_pad[0], pady=control_pad[1])
        control_shell.grid(row=control_row, column=control_column, sticky="nsew")
        control_shell.columnconfigure(0, weight=1)

        if group.kind == "vector":
            self._render_vector_group(control_shell, tool_id, group.params)
            return
        if group.kind == "range":
            self._render_range_group(control_shell, tool_id, group.params)
            return
        self._render_single_param(control_shell, tool_id, group.params[0])

    def _render_vector_group(self, parent: tk.Widget, tool_id: str, params: tuple[ToolParam, ...]) -> None:
        parent_bg = str(parent.cget("bg"))
        axis_colors = {"X": X_AXIS, "Y": Y_AXIS, "Z": Z_AXIS}
        slot_width = self._vector_param_slot_width()
        numeric_width = self._vector_numeric_width(slot_width)
        for index, param in enumerate(params):
            parent.columnconfigure(index, weight=0, minsize=slot_width)
            shell = tk.Frame(parent, bg=parent_bg)
            shell.grid(row=0, column=index, sticky="w", padx=(0 if index == 0 else 8, 0))
            shell.columnconfigure(1, weight=0)
            axis = param.name.rsplit("_", 1)[-1].upper()
            tk.Label(
                shell,
                text=axis,
                bg=PANEL_ALT,
                fg=axis_colors.get(axis, MUTED),
                font=UI_FONT_BOLD,
                width=2,
            ).grid(
                row=0,
                column=0,
                sticky="ns",
                padx=(0, 4),
            )
            control = self._create_numeric_control(
                shell,
                tool_id,
                param,
                axis_color=None,
                width_px=numeric_width,
            )
            control.grid(row=0, column=1, sticky="w")
            self._attach_param_error_label(shell, tool_id, param.name, row=1, column=1)
            self._validate_param_on_change(tool_id, param, save=False)

    def _render_range_group(self, parent: tk.Widget, tool_id: str, params: tuple[ToolParam, ...]) -> None:
        parent_bg = str(parent.cget("bg"))
        slot_width = self._range_param_slot_width()
        numeric_width = self._range_numeric_width(slot_width)
        for index, param in enumerate(params):
            parent.columnconfigure(index, weight=0, minsize=slot_width)
            shell = tk.Frame(parent, bg=parent_bg)
            shell.grid(row=0, column=index, sticky="w", padx=(0 if index == 0 else 8, 0))
            shell.columnconfigure(1, weight=0)
            label = "Min" if param.name.startswith("min_") else "Max"
            tk.Label(shell, text=label, bg=parent_bg, fg=SUBTLE, font=SMALL_FONT, width=4, anchor="w").grid(
                row=0,
                column=0,
                padx=(0, 3),
            )
            control = self._create_numeric_control(shell, tool_id, param, width_px=numeric_width)
            control.grid(row=0, column=1, sticky="w")
            self._attach_param_error_label(shell, tool_id, param.name, row=1, column=1)
            self._validate_param_on_change(tool_id, param, save=False)

    def _render_single_param(self, parent: tk.Widget, tool_id: str, param: ToolParam) -> None:
        if _is_numeric_param(param):
            control = self._create_numeric_control(parent, tool_id, param)
        else:
            control = self._create_param_control(parent, tool_id, param)
        sticky = "w" if param.kind == "bool" else "ew"
        control.grid(row=0, column=0, sticky=sticky)
        self._attach_param_error_label(parent, tool_id, param.name, row=1, column=0)
        self._validate_param_on_change(tool_id, param, save=False)

    def _attach_param_error_label(self, parent: tk.Widget, tool_id: str, param_name: str, *, row: int, column: int) -> None:
        error_var = self._param_error_var(tool_id, param_name)
        parent_bg = str(parent.cget("bg")) if hasattr(parent, "cget") else PANEL
        error_label = tk.Label(
            parent,
            textvariable=error_var,
            bg=parent_bg,
            fg=WARNING,
            font=SMALL_FONT,
            anchor="w",
            justify="left",
            wraplength=self._param_label_wraplength(),
        )
        error_label.grid(row=row, column=column, sticky="ew", pady=(3, 0))
        self.param_error_labels.setdefault(tool_id, {})[param_name] = error_label

    def _param_controls_available_width(self) -> int:
        width = self._content_width()
        if self._params_use_two_column():
            width -= self._details_label_minsize() + 28
        else:
            width -= 24
        return max(260, width)

    def _params_use_two_column(self) -> bool:
        return self._layout_spec().param_two_column and self._content_width() >= 640

    def _vector_param_slot_width(self) -> int:
        return max(96, min(150, int((self._param_controls_available_width() - 16) / 3)))

    def _vector_numeric_width(self, slot_width: int) -> int:
        return max(72, min(DETAIL_VECTOR_NUMERIC_WIDTH, slot_width - 30))

    def _range_param_slot_width(self) -> int:
        return max(132, min(222, int((self._param_controls_available_width() - 8) / 2)))

    def _range_numeric_width(self, slot_width: int) -> int:
        return max(90, min(DETAIL_RANGE_NUMERIC_WIDTH, slot_width - 45))

    def _single_numeric_width(self) -> int:
        return max(120, min(DETAIL_NUMERIC_WIDTH, self._param_controls_available_width()))

    def _focus_selected_param(self) -> bool:
        widgets_by_param = self.param_input_widgets.get(self.current_tool_id, {})
        for widgets in widgets_by_param.values():
            for widget in widgets:
                if not isinstance(widget, (tk.Entry, ttk.Combobox, tk.Checkbutton)):
                    continue
                try:
                    widget.focus_set()
                    if isinstance(widget, tk.Entry):
                        widget.selection_range(0, tk.END)
                    return True
                except tk.TclError:
                    continue
        self.list_canvas.focus_set()
        return False

    def _toggle_details_focus(self) -> None:
        if not self.details_panel.winfo_ismapped():
            self._focus_selected_param()
            return
        focus_widget = self.root.focus_get()
        if self._is_widget_inside(focus_widget, self.details_panel):
            self.list_canvas.focus_set()
            return
        for widget in self.details_inner.winfo_children():
            target = _first_focusable_descendant(widget)
            if target is not None:
                target.focus_set()
                return
        self.details_canvas.focus_set()

    def _set_details_category_tab(self, label: str) -> None:
        self.details_category_var.set(label)
        self._render_details()

    def _rerender_details_preserving_search_focus(self) -> None:
        cursor_index = None
        focus_widget = self.root.focus_get()
        search_entry = getattr(self, "details_search_entry", None)
        if search_entry is not None and focus_widget is search_entry:
            try:
                cursor_index = search_entry.index(tk.INSERT)
            except tk.TclError:
                cursor_index = None
        self._render_details()
        if cursor_index is not None:
            replacement = getattr(self, "details_search_entry", None)
            if replacement is not None:
                try:
                    replacement.focus_set()
                    replacement.icursor(min(cursor_index, len(self.details_search_var.get())))
                except tk.TclError:
                    pass

    def _set_outliner_filter_tab(self, label: str) -> None:
        if label == "All":
            self.category_var.set("All")
        elif label in self._category_filter_values():
            self.category_var.set(label)
        else:
            self.category_var.set("All")
        self._refresh_list()

    def _begin_split_drag(self, event: tk.Event) -> str:
        self._split_drag_active = True
        self._split_drag_start_y = int(getattr(event, "y_root", 0))
        self._split_drag_start_height = max(220, int(self.details_panel.winfo_height()))
        return "break"

    def _drag_split(self, event: tk.Event) -> str:
        if not self._split_drag_active:
            return "break"
        y_root = int(getattr(event, "y_root", self._split_drag_start_y))
        delta = y_root - self._split_drag_start_y
        max_height = max(220, self.root.winfo_height() - 230)
        new_height = max(220, min(max_height, self._split_drag_start_height - delta))
        self.settings.details_panel_height = new_height
        self.details_panel.configure(height=new_height)
        self.body_frame.rowconfigure(2, minsize=new_height)
        return "break"

    def _end_split_drag(self, _event: tk.Event | None = None) -> str:
        if self._split_drag_active:
            self._split_drag_active = False
            self._save_settings()
        return "break"

    def _display_tool_name(self, tool: Tool) -> str:
        return f"★ {tool.name}" if tool.id in self._favorite_ids() else tool.name

    def _favorite_ids(self) -> list[str]:
        return list(self.settings.favorite_ids or [])

    def _recent_ids(self) -> list[str]:
        return list(self.settings.recent_ids or [])

    def _sort_tools_for_display(self, tools: list[Tool]) -> list[Tool]:
        original_index = {tool.id: index for index, tool in enumerate(self.tools)}
        favorite_rank = {tool_id: index for index, tool_id in enumerate(self._favorite_ids())}
        recent_rank = {tool_id: index for index, tool_id in enumerate(self._recent_ids())}
        return sorted(
            tools,
            key=lambda tool: (
                0 if tool.id in favorite_rank else 1,
                favorite_rank.get(tool.id, 9999),
                recent_rank.get(tool.id, 9999),
                original_index.get(tool.id, 9999),
            ),
        )

    def _content_width(self) -> int:
        width = self.list_canvas.winfo_width() if hasattr(self, "list_canvas") else self.root.winfo_width()
        if width <= 1:
            width = self.root.winfo_width()
        if width <= 1:
            width = 420
        return width

    def _card_title_wraplength(self, spec: LayoutSpec) -> int:
        width = self._content_width()
        return max(120, min(520, width - spec.card_title_reserved_width))

    def _tool_meta_wraplength(self) -> int:
        return max(180, min(560, self._content_width() - 190))

    def _param_label_wraplength(self) -> int:
        width = self._content_width()
        spec = self._layout_spec()
        return max(140, min(520, width - spec.param_label_wrap_extra))

    def _create_param_row(
        self,
        parent: tk.Widget,
        row_index: int,
        tool_id: str,
        param: ToolParam,
        spec: LayoutSpec,
    ) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.grid(row=row_index, column=0, sticky="ew", pady=(0, spec.param_gap))

        if spec.param_two_column:
            row.columnconfigure(0, weight=0, minsize=170)
            row.columnconfigure(1, weight=1, minsize=spec.param_entry_minsize)
            label_row = 0
            control_row = 0
            label_column = 0
            control_column = 1
            error_columnspan = 1
            label_sticky = "nw"
            control_pady = (0, 0)
            error_pady = (3, 0)
        else:
            row.columnconfigure(0, weight=1, minsize=spec.param_entry_minsize)
            label_row = 0
            control_row = 1
            label_column = 0
            control_column = 0
            error_columnspan = 1
            label_sticky = "ew"
            control_pady = (0, 0)
            error_pady = (2, 0)

        tk.Label(
            row,
            text=param.label,
            bg=PANEL,
            fg=MUTED,
            font=SMALL_FONT,
            anchor="w",
            justify="left",
            wraplength=self._param_label_wraplength(),
        ).grid(row=label_row, column=label_column, sticky=label_sticky, padx=(0, 10 if spec.param_two_column else 0), pady=(0, 2))

        control = self._create_param_control(row, tool_id, param)
        control.grid(row=control_row, column=control_column, sticky="ew", pady=control_pady)

        error_var = self._param_error_var(tool_id, param.name)
        error_label = tk.Label(
            row,
            textvariable=error_var,
            bg=PANEL,
            fg=WARNING,
            font=SMALL_FONT,
            anchor="w",
            justify="left",
            wraplength=self._param_label_wraplength(),
        )
        error_row = 1 if spec.param_two_column else 2
        error_col = 1 if spec.param_two_column else 0
        error_label.grid(row=error_row, column=error_col, columnspan=error_columnspan, sticky="ew", pady=error_pady)
        self.param_error_labels.setdefault(tool_id, {})[param.name] = error_label

        self._validate_param_on_change(tool_id, param, save=False)

    def _select_tool(self, tool_id: str) -> None:
        tool = self._tool_by_id(tool_id)
        if tool is None:
            return
        previous_current_tool_id = self.current_tool_id
        if self.current_tool_id == tool_id:
            return
        self.current_tool_id = tool_id
        self.expanded_tool_id = tool_id
        if not self._replace_tool_rows([previous_current_tool_id, tool_id]):
            self._rebuild_tool_rows()
        self._render_details()
        self.root.after_idle(lambda: self.details_canvas.yview_moveto(0))
        self.root.after_idle(lambda selected_tool_id=tool_id: self._scroll_tool_into_view(selected_tool_id))

    def _toggle_params(self, tool_id: str) -> None:
        tool = self._tool_by_id(tool_id)
        if tool is None:
            return
        self.current_tool_id = tool_id
        self.expanded_tool_id = ""
        self._update_visible_tool_rows([tool_id])
        self._render_details()
        self._toggle_details_focus()

    def _show_tool_menu(self, tool_id: str) -> None:
        if self.current_tool_id != tool_id:
            previous_tool_id = self.current_tool_id
            self.current_tool_id = tool_id
            self.expanded_tool_id = tool_id
            if not self._replace_tool_rows([previous_tool_id, tool_id]):
                self._rebuild_tool_rows()
            self._render_details()
        favorite_label = "Remove Favorite" if tool_id in self._favorite_ids() else "Add Favorite"
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=PANEL,
            fg=TEXT,
            activebackground=ACCENT_DARK,
            activeforeground=TEXT,
            borderwidth=0,
            relief="flat",
            font=UI_FONT,
        )
        menu.add_command(label=favorite_label, command=lambda: self._toggle_favorite(tool_id))
        menu.add_separator()
        menu.add_command(label="Edit", command=lambda: self._edit_tool(tool_id))
        menu.add_command(label="Duplicate", command=lambda: self._duplicate_tool(tool_id))
        menu.add_command(label="Export Tool", command=lambda: self._export_tool(tool_id))
        menu.add_command(label="Reset Parameters", command=lambda: self._reset_params(tool_id))
        menu.add_command(label="Copy Fix Prompt", command=lambda: self._show_fix_prompt_dialog(tool_id))
        menu.add_separator()
        menu.add_command(label="Delete", command=lambda: self._delete_tool(tool_id))
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def _save_and_refresh(self) -> None:
        self.store.save_tools(self.tools)
        self._refresh_list()

    def _refresh_bundled_presets(self) -> None:
        try:
            result = refresh_bundled_presets(self.store.path)
        except Exception as exc:
            messagebox.showerror("Refresh Bundled Presets", f"Could not refresh bundled presets:\n\n{exc}", parent=self.root)
            self.status_var.set("Bundled preset refresh failed.")
            return

        self.tools = result.refreshed_tools
        if self.current_tool_id and self._tool_by_id(self.current_tool_id) is None:
            self.current_tool_id = self.tools[0].id if self.tools else ""
        self._refresh_list()

        if result.added_count or result.updated_count:
            self.status_var.set(
                f"Refreshed bundled presets: {result.added_count} added, {result.updated_count} updated."
            )
        else:
            self.status_var.set("Bundled presets already up to date.")

    def _show_library_menu(self) -> None:
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=PANEL,
            fg=TEXT,
            activebackground=ACCENT_DARK,
            activeforeground=TEXT,
            borderwidth=0,
            relief="flat",
            font=UI_FONT,
        )
        library_menu = tk.Menu(
            menu,
            tearoff=0,
            bg=PANEL,
            fg=TEXT,
            activebackground=ACCENT_DARK,
            activeforeground=TEXT,
            borderwidth=0,
            relief="flat",
            font=UI_FONT,
        )
        library_menu.add_command(label="Refresh Bundled Presets", command=self._refresh_bundled_presets)
        library_menu.add_separator()
        library_menu.add_command(label="Export All Tools", command=self._export_all_tools)
        library_menu.add_command(label="Backup Library", command=self._backup_library)
        library_menu.add_command(label="Restore Backup", command=self._restore_backup)
        library_menu.add_separator()
        library_menu.add_command(label="Open Data Folder", command=self._open_data_folder)

        settings_menu = tk.Menu(
            menu,
            tearoff=0,
            bg=PANEL,
            fg=TEXT,
            activebackground=ACCENT_DARK,
            activeforeground=TEXT,
            borderwidth=0,
            relief="flat",
            font=UI_FONT,
        )
        settings_menu.add_checkbutton(
            label="Always on top",
            variable=self.always_top_var,
            command=self._toggle_always_top,
            selectcolor=CODE_BG,
        )
        settings_menu.add_command(label="Open Settings File", command=self._open_settings_file)

        menu.add_command(label="About EditorBinder", command=self._show_about_dialog)
        menu.add_command(label="Open Data Folder", command=self._open_data_folder)
        menu.add_command(label="Open License", command=self._open_license)
        menu.add_command(label="Open Changelog", command=self._open_changelog)
        menu.add_separator()
        menu.add_cascade(label="Library", menu=library_menu)
        menu.add_cascade(label="Settings", menu=settings_menu)
        menu.add_separator()
        menu.add_command(label="App Info", command=self._show_app_info)
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def _toggle_favorite(self, tool_id: str) -> None:
        favorites = self._favorite_ids()
        if tool_id in favorites:
            favorites = [existing_id for existing_id in favorites if existing_id != tool_id]
            status = "Removed favorite"
        else:
            favorites.insert(0, tool_id)
            status = "Added favorite"
        self.settings.favorite_ids = favorites
        self._save_settings()
        self._refresh_list()
        tool = self._tool_by_id(tool_id)
        self.status_var.set(f"{status}: {tool.name if tool else tool_id}")

    def _remember_recent_tool(self, tool_id: str) -> None:
        recent = [existing_id for existing_id in self._recent_ids() if existing_id != tool_id]
        recent.insert(0, tool_id)
        self.settings.recent_ids = recent[:12]
        self._save_settings()

    def _add_tool(self) -> None:
        selected_tool = self._selected_tool()
        prompt_example_code = selected_tool.code if selected_tool else ""
        dialog = ToolEditorDialog(
            self.root,
            prompt_example_code=prompt_example_code,
            existing_tools=self.tools,
            settings=self.settings,
            save_settings=self._save_settings,
        )
        result = dialog.show()
        if result is None:
            return
        if isinstance(result, ToolImportBatch):
            resolution = apply_import_policy(self.tools, result.tools, result.policy)
            self.tools = resolution.tools
            if resolution.last_tool_id:
                self.current_tool_id = resolution.last_tool_id
            self._save_and_refresh()
            parts = [
                f"{resolution.added_count} added",
                f"{resolution.replaced_count} replaced",
                f"{resolution.skipped_count} skipped",
            ]
            if resolution.renamed_count:
                parts.append(f"{resolution.renamed_count} renamed")
            self.status_var.set(f"Import complete: {', '.join(parts)}")
            return
        new_tools = result if isinstance(result, list) else [result]
        self.tools.extend(new_tools)
        self.current_tool_id = new_tools[-1].id
        self._save_and_refresh()
        if len(new_tools) == 1:
            self.status_var.set(f"Saved to current library: {new_tools[0].name}. Restart not required.")
        else:
            self.status_var.set(f"Imported {len(new_tools)} tools to current library. Restart not required.")

    def _edit_tool(self, tool_id: str | None = None) -> None:
        tool = self._tool_by_id(tool_id) if tool_id else self._selected_tool()
        if tool is None:
            return
        self.current_tool_id = tool.id
        dialog = ToolEditorDialog(
            self.root,
            tool,
            existing_tools=self.tools,
            settings=self.settings,
            save_settings=self._save_settings,
        )
        updated = dialog.show()
        if updated is None:
            return
        self.tools = [updated if existing.id == updated.id else existing for existing in self.tools]
        self.current_tool_id = updated.id
        self._save_and_refresh()
        self.status_var.set(f"Updated tool: {updated.name}")

    def _duplicate_tool(self, tool_id: str | None = None) -> None:
        tool = self._tool_by_id(tool_id) if tool_id else self._selected_tool()
        if tool is None:
            return
        duplicate = tool.duplicate()
        self.tools.append(duplicate)
        self.current_tool_id = duplicate.id
        self._save_and_refresh()
        self.status_var.set(f"Duplicated tool: {duplicate.name}")

    def _delete_tool(self, tool_id: str | None = None) -> None:
        tool = self._tool_by_id(tool_id) if tool_id else self._selected_tool()
        if tool is None:
            return
        if not messagebox.askyesno("Delete Tool?", f"Delete '{tool.name}'?", parent=self.root):
            return
        self.tools = [existing for existing in self.tools if existing.id != tool.id]
        self.current_tool_id = self.tools[0].id if self.tools else ""
        self._save_and_refresh()
        self.status_var.set(f"Deleted tool: {tool.name}")

    def _copy_code(self, tool_id: str | None = None) -> None:
        tool = self._tool_by_id(tool_id) if tool_id else self._selected_tool()
        if tool is None:
            return
        self.current_tool_id = tool.id
        params = parse_tool_params(tool.code)
        values = {}
        if params:
            self._ensure_param_vars(tool.id, params)
            if not self._validate_tool_params(tool.id, params):
                self.current_tool_id = tool.id
                self.expanded_tool_id = tool.id
                self._rebuild_tool_rows()
                self._render_details()
                self.status_var.set("Fix highlighted parameter values before copying.")
                return
            values = self._get_param_values(tool.id, params)
        try:
            rendered_code = render_tool_code(tool.code, values)
        except ParamRenderError as exc:
            messagebox.showwarning("Invalid Parameter", str(exc), parent=self.root)
            self._render_details()
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(rendered_code)
        if params:
            self._persist_param_values(tool.id, params)
        self._remember_recent_tool(tool.id)
        self._show_copy_feedback(tool.id, tool.name)

    def _show_copy_feedback(self, tool_id: str, tool_name: str) -> None:
        previous_tool_id = self.copy_feedback_tool_id
        self.copy_feedback_tool_id = tool_id
        self._copy_feedback_token += 1
        token = self._copy_feedback_token
        self.status_var.set(f"Copied: {tool_name}")
        if previous_tool_id and previous_tool_id != tool_id:
            self._set_copy_button_feedback(previous_tool_id, active=False)
        self._set_copy_button_feedback(tool_id, active=True)
        self.root.after(1300, lambda current_token=token: self._clear_copy_feedback(current_token))

    def _clear_copy_feedback(self, token: int) -> None:
        if token != self._copy_feedback_token:
            return
        if not self.copy_feedback_tool_id:
            return
        tool_id = self.copy_feedback_tool_id
        self.copy_feedback_tool_id = ""
        self._set_copy_button_feedback(tool_id, active=False)

    def _set_copy_button_feedback(self, tool_id: str, active: bool) -> None:
        button = self.copy_button_by_tool_id.get(tool_id)
        if button is None:
            return
        try:
            button.configure(
                text="Copied" if active else "Copy",
                fg="#0b1110",
                bg=SUCCESS,
                activebackground=SUCCESS_HOVER,
                highlightbackground=SUCCESS_HOVER,
                highlightcolor=SUCCESS_HOVER,
            )
        except tk.TclError:
            pass

    def _reset_params(self, tool_id: str) -> None:
        tool = self._tool_by_id(tool_id)
        if tool is None:
            return
        params = parse_tool_params(tool.code)
        self.param_values[tool.id] = {}
        self.param_error_vars[tool.id] = {}
        if self.settings.param_values:
            self.settings.param_values.pop(tool.id, None)
            self._save_settings()
        self._ensure_param_vars(tool.id, params)
        self.current_tool_id = tool.id
        self.expanded_tool_id = tool.id
        self._rebuild_tool_rows()
        self._render_details()
        self.status_var.set(f"Reset parameters: {tool.name}")

    def _copy_fix_prompt(self, tool_id: str) -> None:
        tool = self._tool_by_id(tool_id)
        if tool is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(build_fix_prompt(tool.name, tool.code))
        self.root.update()
        self.status_var.set(f"Fix prompt copied: {tool.name}")

    def _show_fix_prompt_dialog(self, tool_id: str) -> None:
        tool = self._tool_by_id(tool_id)
        if tool is None:
            return
        self.current_tool_id = tool.id
        dialog = FixPromptDialog(self.root, tool)
        copied = dialog.show()
        if copied:
            self.status_var.set(f"Fix prompt copied: {tool.name}")

    def _export_tool(self, tool_id: str) -> None:
        tool = self._tool_by_id(tool_id)
        if tool is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export Tool",
            initialfile=f"{_safe_filename(tool.name)}.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        _write_tools_export(path, [tool])
        self.status_var.set(f"Exported tool: {tool.name}")

    def _export_all_tools(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export All Tools",
            initialfile="editorbinder-tools.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        _write_tools_export(path, self.tools)
        self.status_var.set(f"Exported {len(self.tools)} tools")

    def _backup_library(self) -> None:
        backup_path = self.store.create_timestamped_backup()
        if backup_path == self.store.path:
            self.status_var.set("No library file to back up yet")
            return
        self.status_var.set(f"Backup: {backup_path.name}")

    def _restore_backup(self) -> None:
        backups = self.store.list_backups()
        if not backups:
            self.status_var.set("No backups found")
            messagebox.showinfo("Restore Backup", "No backups found for this library.", parent=self.root)
            return
        dialog = RestoreBackupDialog(self.root, backups)
        backup = dialog.show()
        if backup is None:
            return
        if not messagebox.askyesno(
            "Restore Backup?",
            (
                f"Restore '{backup.filename}'?\n\n"
                "The current library will be backed up before restore."
            ),
            parent=self.root,
        ):
            return
        try:
            result = self.store.restore_backup(backup.path)
        except (OSError, ValueError) as exc:
            messagebox.showwarning("Restore Failed", str(exc), parent=self.root)
            self.status_var.set("Restore failed")
            return

        self.tools = result.restored_tools
        self.current_tool_id = self.tools[0].id if self.tools else ""
        self.expanded_tool_id = ""
        self.param_values = {}
        self.param_error_vars = {}
        self._refresh_list()
        safety = f" Safety backup: {result.safety_backup_path.name}." if result.safety_backup_path else ""
        self.status_var.set(f"Restored {len(self.tools)} tool(s) from {backup.filename}.{safety}")

    def _open_data_folder(self) -> None:
        folder = self.store.path.parent
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(folder)
            self.status_var.set("Opened data folder")
        except OSError as exc:
            messagebox.showwarning("Open Folder Failed", str(exc), parent=self.root)

    def _open_license(self) -> None:
        self._open_app_file("LICENSE.txt", "license")

    def _open_changelog(self) -> None:
        self._open_app_file("CHANGELOG.md", "changelog")

    def _open_app_file(self, filename: str, label: str) -> None:
        path = app_file_path(filename)
        if not path.exists():
            messagebox.showwarning(
                "File Not Found",
                f"Could not find {filename}.\n\nExpected location:\n{path}",
                parent=self.root,
            )
            self.status_var.set(f"{label.title()} file not found")
            return
        try:
            os.startfile(path)
            self.status_var.set(f"Opened {label}")
        except OSError as exc:
            messagebox.showwarning(f"Open {label.title()} Failed", str(exc), parent=self.root)

    def _open_settings_file(self) -> None:
        self._save_settings()
        self.settings_store.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(self.settings_store.path)
            self.status_var.set("Opened settings file")
        except OSError as exc:
            messagebox.showwarning("Open Settings Failed", str(exc), parent=self.root)

    def _show_about_dialog(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("About EditorBinder")
        window.configure(bg=PANEL)
        window.resizable(False, False)
        window.transient(self.root)

        shell = tk.Frame(window, bg=PANEL, padx=18, pady=16)
        shell.grid(row=0, column=0, sticky="nsew")
        tk.Label(
            shell,
            text="EditorBinder",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            shell,
            text=f"Version {__version__}",
            bg=PANEL,
            fg=MUTED,
            font=UI_FONT,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 12))
        tk.Label(
            shell,
            text=self._about_text(),
            bg=PANEL,
            fg=TEXT,
            font=UI_FONT,
            justify="left",
            anchor="w",
            wraplength=460,
        ).grid(row=2, column=0, sticky="ew")

        actions = tk.Frame(shell, bg=PANEL)
        actions.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        for index, (label, command) in enumerate(
            [
                ("Open License", self._open_license),
                ("Open Changelog", self._open_changelog),
                ("Open Data Folder", self._open_data_folder),
                ("Copy App Info", self._copy_app_info),
                ("Close", window.destroy),
            ]
        ):
            make_button(actions, label, command, variant="secondary", padx=9, pady=4).grid(
                row=0,
                column=index,
                padx=(0, 6 if index < 4 else 0),
            )

        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = max(self.root.winfo_width(), 1)
        root_height = max(self.root.winfo_height(), 1)
        x = root_x + max((root_width - width) // 2, 0)
        y = root_y + max((root_height - height) // 2, 0)
        window.geometry(f"+{x}+{y}")
        window.grab_set()

    def _about_text(self) -> str:
        return (
            "AI-assisted clipboard library for Unreal Engine Python Console tools.\n\n"
            "Created by Bartosz Rozmus, 2026.\n"
            "Copyright (c) 2026 Bartosz Rozmus.\n"
            "Released under the MIT License.\n\n"
            "EditorBinder is a standalone local desktop utility.\n"
            "It is not an Unreal Engine plugin and does not execute scripts automatically.\n\n"
            "Unreal Engine is a trademark of Epic Games, Inc.\n"
            "EditorBinder is independent and is not affiliated with, endorsed by, or sponsored by Epic Games."
        )

    def _copy_app_info(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self._app_info_text())
        self.status_var.set("Copied app info")

    def _app_info_text(self) -> str:
        return (
            f"EditorBinder {__version__}\n"
            "Author: Bartosz Rozmus\n"
            "Runtime: local desktop app\n"
            f"Storage: {self.store.path.parent}\n"
            "Unreal integration: clipboard / Python Console only\n"
            "License: see LICENSE.txt"
        )

    def _show_app_info(self) -> None:
        messagebox.showinfo(
            "EditorBinder",
            (
                f"EditorBinder {__version__}\n\n"
                f"Tools: {len(self.tools)}\n"
                f"Visible: {len(self.filtered_tools)}\n\n"
                f"Library:\n{self.store.path}\n\n"
                f"Settings:\n{self.settings_store.path}"
            ),
            parent=self.root,
        )

    def _ensure_param_vars(self, tool_id: str, params: list) -> None:
        existing = self.param_values.setdefault(tool_id, {})
        for param in params:
            current = existing.get(param.name)
            initial_value = self._initial_param_value(tool_id, param)
            if param.kind == "bool":
                if not isinstance(current, tk.BooleanVar):
                    existing[param.name] = tk.BooleanVar(value=_parse_bool_default(initial_value))
            elif current is None or isinstance(current, tk.BooleanVar):
                existing[param.name] = tk.StringVar(value=initial_value)
            self._param_error_var(tool_id, param.name)

    def _initial_param_value(self, tool_id: str, param: ToolParam) -> str:
        saved = (self.settings.param_values or {}).get(tool_id, {}).get(param.name)
        if saved is not None:
            try:
                validate_param_value(param, saved)
                return saved
            except ParamRenderError:
                pass
        return param.default

    def _param_error_var(self, tool_id: str, param_name: str) -> tk.StringVar:
        tool_errors = self.param_error_vars.setdefault(tool_id, {})
        error_var = tool_errors.get(param_name)
        if error_var is None:
            error_var = tk.StringVar(value="")
            tool_errors[param_name] = error_var
        return error_var

    def _get_param_values(self, tool_id: str, params: list[ToolParam]) -> dict[str, str]:
        values: dict[str, str] = {}
        for param in params:
            variable = self.param_values[tool_id][param.name]
            if param.kind == "bool":
                values[param.name] = "true" if bool(variable.get()) else "false"
            else:
                values[param.name] = str(variable.get())
        return values

    def _validate_tool_params(self, tool_id: str, params: list[ToolParam]) -> bool:
        ok = True
        for param in params:
            if not self._validate_param_on_change(tool_id, param, save=False):
                ok = False
        return ok

    def _validate_param_on_change(self, tool_id: str, param: ToolParam, save: bool = False) -> bool:
        if tool_id not in self.param_values or param.name not in self.param_values[tool_id]:
            return True
        raw_value = self._get_param_values(tool_id, [param])[param.name]
        error_var = self._param_error_var(tool_id, param.name)
        try:
            validate_param_value(param, raw_value)
        except ParamRenderError as exc:
            error_var.set(str(exc))
            self._set_param_error_state(tool_id, param.name, has_error=True)
            return False
        error_var.set("")
        self._set_param_error_state(tool_id, param.name, has_error=False)
        if save:
            self._persist_param_values(tool_id, [param])
            self._copy_code(tool_id)
        return True

    def _register_param_input_widget(self, tool_id: str, param_name: str, widget: tk.Widget) -> None:
        tool_widgets = self.param_input_widgets.setdefault(tool_id, {})
        tool_widgets.setdefault(param_name, []).append(widget)

    def _set_param_error_state(self, tool_id: str, param_name: str, has_error: bool) -> None:
        for widget in self.param_input_widgets.get(tool_id, {}).get(param_name, []):
            try:
                if isinstance(widget, tk.Entry):
                    widget.configure(
                        highlightbackground=WARNING if has_error else BORDER,
                        highlightcolor=WARNING if has_error else ACCENT,
                    )
                elif isinstance(widget, tk.Checkbutton):
                    widget.configure(fg=WARNING if has_error else TEXT)
                elif isinstance(widget, tk.Frame):
                    parent_bg = str(widget.master.cget("bg")) if widget.master is not None else PANEL
                    widget.configure(bg=WARNING if has_error else parent_bg)
            except tk.TclError:
                continue
        label = self.param_error_labels.get(tool_id, {}).get(param_name)
        if label is not None:
            try:
                if has_error:
                    label.grid()
                else:
                    label.grid_remove()
            except tk.TclError:
                pass

    def _persist_param_values(self, tool_id: str, params: list[ToolParam]) -> None:
        if not params or tool_id not in self.param_values:
            return
        param_values = self.settings.param_values or {}
        stored_values = dict(param_values.get(tool_id, {}))
        stored_values.update(self._get_param_values(tool_id, params))
        param_values[tool_id] = stored_values
        self.settings.param_values = param_values
        self._save_settings()

    def _persist_all_current_param_values(self) -> None:
        for tool in self.tools:
            params = parse_tool_params(tool.code)
            if params and tool.id in self.param_values:
                self._persist_param_values(tool.id, params)

    def _create_param_control(self, parent: tk.Widget, tool_id: str, param: ToolParam) -> tk.Widget:
        variable = self.param_values[tool_id][param.name]
        parent_bg = str(parent.cget("bg")) if hasattr(parent, "cget") else PANEL
        if param.kind == "bool":
            checkbox = tk.Checkbutton(
                parent,
                text="",
                variable=variable,
                command=lambda p=param: self._validate_param_on_change(tool_id, p, save=True),
                bg=parent_bg,
                fg=TEXT,
                activebackground=parent_bg,
                activeforeground=TEXT,
                selectcolor=CODE_BG,
                font=UI_FONT,
                cursor="hand2",
                relief="flat",
                anchor="w",
                padx=0,
                pady=0,
            )
            self._register_param_input_widget(tool_id, param.name, checkbox)
            return checkbox

        if param.kind == "enum" and param.options:
            combo = ttk.Combobox(
                parent,
                textvariable=variable,
                values=param.options,
                state="readonly",
                font=UI_FONT,
                style="Dark.TCombobox",
            )
            combo.configure(width=16)
            combo.bind(
                "<<ComboboxSelected>>",
                lambda _event, p=param: self._validate_param_on_change(tool_id, p, save=True),
            )
            self._register_param_input_widget(tool_id, param.name, combo)
            return combo

        if param.kind in {"int", "float"}:
            return self._create_numeric_control(parent, tool_id, param)

        if param.kind == "path":
            return self._create_path_param_control(parent, tool_id, param, variable)

        return self._create_param_entry(
            parent,
            variable,
            lambda p=param: self._validate_param_on_change(tool_id, p, save=True),
            tool_id,
            param.name,
        )

    def _create_numeric_control(
        self,
        parent: tk.Widget,
        tool_id: str,
        param: ToolParam,
        axis_color: str | None = None,
        width_px: int | None = None,
    ) -> UnrealNumericField:
        variable = self.param_values[tool_id][param.name]
        control = UnrealNumericField(
            parent,
            param=param,
            variable=variable,
            on_validate=lambda save=False, p=param: self._validate_param_on_change(tool_id, p, save=save),
            axis_color=axis_color,
            width_px=width_px,
        )
        self._register_param_input_widget(tool_id, param.name, control.entry)
        self._register_param_input_widget(tool_id, param.name, control)
        return control

    def _create_path_param_control(
        self,
        parent: tk.Widget,
        tool_id: str,
        param: ToolParam,
        variable: tk.Variable,
    ) -> tk.Widget:
        spec = self._layout_spec()
        parent_bg = str(parent.cget("bg")) if hasattr(parent, "cget") else PANEL
        control = tk.Frame(parent, bg=parent_bg)
        control.columnconfigure(0, weight=1, minsize=spec.param_entry_minsize)
        entry = self._create_param_entry(
            control,
            variable,
            lambda p=param: self._validate_param_on_change(tool_id, p, save=True),
            tool_id,
            param.name,
        )
        entry.grid(row=0, column=0, sticky="ew", ipady=_param_entry_ipady(spec))

        dialog_mode = self._path_param_file_dialog_mode(tool_id, param)
        next_column = 1
        if dialog_mode:
            button_text = "Save As" if dialog_mode == "save" else "Browse"
            make_toolbar_button(
                control,
                button_text,
                lambda p=param, v=variable, mode=dialog_mode: self._browse_path_param(tool_id, p, v, mode),
            ).grid(row=0, column=next_column, padx=(6, 4), sticky="ns")
            next_column += 1

        make_toolbar_button(control, "Copy", lambda v=variable: self._copy_param_value(v)).grid(
            row=0, column=next_column, padx=(6 if next_column == 1 else 0, 4), sticky="ns"
        )
        next_column += 1
        make_toolbar_button(control, "Clear", lambda p=param, v=variable: self._clear_param_value(tool_id, p, v)).grid(
            row=0, column=next_column, sticky="ns"
        )
        return control

    def _path_param_file_dialog_mode(self, tool_id: str, param: ToolParam) -> str:
        name = param.name.casefold()
        default = str(param.default).strip().casefold()
        is_disk_file = name in {"csv_path", "txt_path"} or default.endswith((".csv", ".txt"))
        if not is_disk_file:
            return ""

        tool = self._tool_by_id(tool_id)
        context = f"{param.name} {param.label} {tool.name if tool else ''}".casefold()
        if any(keyword in context for keyword in ("export", "save", "write")):
            return "save"
        return "open"

    def _browse_path_param(
        self,
        tool_id: str,
        param: ToolParam,
        variable: tk.Variable,
        mode: str,
    ) -> None:
        current_value = str(variable.get()).strip()
        initial_dir = self._path_dialog_initial_dir(current_value)
        initial_file = self._path_dialog_initial_file(current_value, param)
        filetypes = self._path_dialog_filetypes(current_value, param)
        extension = self._path_dialog_default_extension(current_value, param)

        if mode == "save":
            selected = filedialog.asksaveasfilename(
                parent=self.root,
                title=f"Choose {param.label}",
                initialdir=initial_dir,
                initialfile=initial_file,
                defaultextension=extension,
                filetypes=filetypes,
            )
        else:
            selected = filedialog.askopenfilename(
                parent=self.root,
                title=f"Choose {param.label}",
                initialdir=initial_dir,
                filetypes=filetypes,
            )

        if not selected:
            return

        variable.set(selected)
        self._validate_param_on_change(tool_id, param, save=True)
        self.status_var.set(f"{param.label} selected.")

    def _path_dialog_initial_dir(self, value: str) -> str:
        expanded = os.path.expandvars(os.path.expanduser(value.strip()))
        if expanded and os.path.isdir(expanded):
            return expanded
        directory = os.path.dirname(expanded)
        if directory and os.path.isdir(directory):
            return directory
        return os.getcwd()

    def _path_dialog_initial_file(self, value: str, param: ToolParam) -> str:
        expanded = os.path.expandvars(os.path.expanduser(value.strip()))
        filename = os.path.basename(expanded)
        if filename:
            return filename
        return os.path.basename(str(param.default).strip()) or "untitled"

    def _path_dialog_default_extension(self, value: str, param: ToolParam) -> str:
        extension = os.path.splitext(value.strip())[1] or os.path.splitext(str(param.default).strip())[1]
        return extension or ""

    def _path_dialog_filetypes(self, value: str, param: ToolParam) -> list[tuple[str, str]]:
        extension = self._path_dialog_default_extension(value, param).casefold()
        if extension == ".csv":
            return [("CSV files", "*.csv"), ("All files", "*.*")]
        if extension == ".txt":
            return [("Text files", "*.txt"), ("All files", "*.*")]
        return [("All files", "*.*")]

    def _create_param_entry(
        self,
        parent: tk.Widget,
        variable: tk.Variable,
        on_change=None,
        tool_id: str | None = None,
        param_name: str | None = None,
    ) -> tk.Entry:
        entry = make_dark_entry(parent, variable, width=18)
        if on_change is not None:
            entry.bind("<KeyRelease>", lambda _event: on_change())
            entry.bind("<FocusOut>", lambda _event: on_change())
        if tool_id and param_name:
            self._register_param_input_widget(tool_id, param_name, entry)
        return entry

    def _copy_param_value(self, variable: tk.Variable) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(str(variable.get()))
        self.root.update()
        self.status_var.set("Parameter value copied.")

    def _clear_param_value(self, tool_id: str, param: ToolParam, variable: tk.Variable) -> None:
        variable.set("")
        self._validate_param_on_change(tool_id, param, save=True)

    def _step_and_validate_param(
        self,
        tool_id: str,
        param: ToolParam,
        variable: tk.Variable,
        direction: int,
    ) -> None:
        self._step_numeric_param(param, variable, direction)
        self._validate_param_on_change(tool_id, param, save=True)

    def _step_numeric_param(self, param: ToolParam, variable: tk.Variable, direction: int) -> None:
        variable.set(_step_numeric_value(param, str(variable.get()).strip(), direction))

    def _on_list_inner_configure(self, _event: tk.Event) -> None:
        self._refresh_list_scrollregion()

    def _refresh_list_scrollregion(self) -> None:
        try:
            width = max(self.list_canvas.winfo_width(), self.list_inner.winfo_reqwidth(), 1)
            self.list_canvas.configure(scrollregion=(0, 0, width, self._list_content_height()))
        except tk.TclError:
            pass

    def _on_details_inner_configure(self, _event: tk.Event) -> None:
        self._refresh_details_scrollregion()

    def _on_details_canvas_configure(self, event: tk.Event) -> None:
        self.details_canvas.itemconfigure(self.details_window, width=event.width)
        self._refresh_details_scrollregion()

    def _refresh_details_scrollregion(self) -> None:
        try:
            width = max(self.details_canvas.winfo_width(), self.details_inner.winfo_reqwidth(), 1)
            height = max(self.details_inner.winfo_reqheight(), self.details_inner.winfo_height(), 1)
            self.details_canvas.configure(scrollregion=(0, 0, width, height))
        except tk.TclError:
            pass

    def _scroll_expanded_tool_into_view(self) -> None:
        if not self.expanded_tool_id:
            return
        self._scroll_tool_into_view(self.expanded_tool_id)

    def _scroll_tool_into_view(self, tool_id: str) -> None:
        row = self.tool_row_by_id.get(tool_id)
        if row is None:
            return

        try:
            if not row.winfo_exists():
                return
            self.root.update_idletasks()
            if not row.winfo_exists():
                return
            scroll_region = self.list_canvas.bbox("all")
            if not scroll_region:
                return
            row_top = row.winfo_y()
            row_bottom = row_top + row.winfo_height()
        except tk.TclError:
            return

        total_height = max(scroll_region[3] - scroll_region[1], 1)
        canvas_height = max(self.list_canvas.winfo_height(), 1)
        visible_top = self.list_canvas.canvasy(0)
        visible_bottom = visible_top + canvas_height

        if row_top < visible_top:
            self.list_canvas.yview_moveto(max(row_top / total_height, 0))
        elif row_bottom > visible_bottom:
            target = max((row_bottom - canvas_height) / total_height, 0)
            self.list_canvas.yview_moveto(min(target, 1))

    def _on_list_canvas_configure(self, event: tk.Event) -> None:
        width = self._event_int(event, "width", self.list_canvas.winfo_width())
        self._pending_list_canvas_width = width
        self._schedule_list_canvas_width_sync()
        width_changed = abs(width - self._last_canvas_width) > 96
        self._last_canvas_width = width
        if width_changed:
            self._schedule_tool_wrap_refresh()

    def _schedule_list_canvas_width_sync(self) -> None:
        if self._list_canvas_width_after_id:
            return
        self._list_canvas_width_after_id = self.root.after(32, self._sync_list_canvas_width)

    def _sync_list_canvas_width(self) -> None:
        self._list_canvas_width_after_id = ""
        width = self._pending_list_canvas_width or self.list_canvas.winfo_width()
        if width <= 1:
            return
        if abs(width - self._last_list_window_width) < 2:
            return
        self._last_list_window_width = width
        try:
            self.list_canvas.itemconfigure(self.list_window, width=width)
        except tk.TclError:
            return
        self._refresh_list_scrollregion()

    def _on_list_mousewheel(self, event: tk.Event) -> str:
        self._cancel_scroll_overscroll_animation()
        self._set_scroll_overscroll_offset(0)
        self._scroll_list_by_pixels(self._mousewheel_pixels(event))
        return "break"


def _group_tool_params(params: list[ToolParam]) -> list[ParamRenderGroup]:
    by_name = {param.name: param for param in params}
    used: set[str] = set()
    groups: list[ParamRenderGroup] = []
    for param in params:
        if param.name in used:
            continue
        if param.name.startswith("min_"):
            suffix = param.name[4:]
            max_name = f"max_{suffix}"
            max_param = by_name.get(max_name)
            if max_param is not None and _is_numeric_param(param) and _is_numeric_param(max_param):
                groups.append(ParamRenderGroup("range", _ue_property_label_for_name(suffix), (param, max_param)))
                used.update({param.name, max_name})
                continue
        if param.name.endswith("_x") and _is_numeric_param(param):
            prefix = param.name[:-2]
            y_param = by_name.get(f"{prefix}_y")
            z_param = by_name.get(f"{prefix}_z")
            if y_param is not None and z_param is not None and _is_numeric_param(y_param) and _is_numeric_param(z_param):
                groups.append(ParamRenderGroup("vector", _ue_property_label_for_name(prefix), (param, y_param, z_param)))
                used.update({param.name, y_param.name, z_param.name})
                continue
        if param.name == "yaw_degrees" and _is_numeric_param(param):
            groups.append(ParamRenderGroup("single", "Rotation", (param,)))
            used.add(param.name)
            continue
        if param.name in {"scale_multiplier", "scale"} and _is_numeric_param(param):
            groups.append(ParamRenderGroup("single", "Scale", (param,)))
            used.add(param.name)
            continue
        groups.append(ParamRenderGroup("single", param.label, (param,)))
        used.add(param.name)
    return groups


def _is_numeric_param(param: ToolParam) -> bool:
    return param.kind in {"int", "float"}


def _label_from_param_name(name: str) -> str:
    return name.replace("_", " ").strip().title()


def _ue_property_label_for_name(name: str) -> str:
    normalized = name.casefold().strip()
    if normalized in {"offset", "location", "position"} or normalized.endswith("location"):
        return "Location"
    if normalized in {"yaw", "rotation", "rotator"} or normalized.endswith("yaw"):
        return "Rotation"
    if normalized in {"scale", "scale_multiplier", "multiplier"} or normalized.endswith("scale"):
        return "Scale"
    return _label_from_param_name(name)


SHOW_RECOMMENDED = "Recommended"
SHOW_ALL_WORKFLOW_TOOLS = "All Workflow Tools"
SHOW_HIDDEN_LEGACY = "Hidden / Legacy"
SHOW_FILTERS = [SHOW_RECOMMENDED, SHOW_ALL_WORKFLOW_TOOLS, SHOW_HIDDEN_LEGACY]


def _primary_workflow(tool: Tool) -> str:
    return tool.workflows[0] if tool.workflows else "Custom"


def _workflow_color(workflow: str) -> str:
    colors = {
        "Place & Arrange": ACCENT_DARK,
        "Set Dressing": "#39765b",
        "Scene Cleanup": DANGER,
        "Naming & Organization": SUCCESS,
        "Collision & Physics": WARNING,
        "Materials": "#765d93",
        "Textures": "#9a7643",
        "Instancing": "#4f7eaa",
        "Import / DCC": "#617d52",
        "Optimization": "#a86c58",
        "Reports / Handoff": "#66758a",
        "Custom": "#675a86",
    }
    return colors.get(workflow, "#675a86")


def _visibility_badge_text(tool: Tool) -> str:
    return "" if tool.visibility == VISIBILITY_PRIMARY else tool.visibility.title()


def _visibility_color(visibility: str) -> str:
    if visibility == VISIBILITY_HIDDEN:
        return "#5d6470"
    if visibility == VISIBILITY_SECONDARY:
        return "#425169"
    return PANEL_ALT


def _category_color(category: str) -> str:
    colors = {
        CATEGORY_TRANSFORM: ACCENT_DARK,
        CATEGORY_ORGANIZATION: SUCCESS,
        CATEGORY_SELECTION: WARNING,
        CATEGORY_DEBUG: DANGER,
        CATEGORY_CUSTOM: "#675a86",
    }
    return colors.get(category, "#675a86")


def _category_text_color(category: str) -> str:
    return TEXT


def _collapsed_tool_text(tool: Tool, favorite: bool) -> str:
    title = f"* {tool.name}" if favorite else tool.name
    description = " ".join(tool.description.split())
    if len(description) > 118:
        description = f"{description[:115].rstrip()}..."
    return f"{title}\n{tool.category} | {description}" if description else f"{title}\n{tool.category}"


def _first_focusable_descendant(widget: tk.Widget) -> tk.Widget | None:
    if isinstance(widget, (tk.Entry, tk.Text, tk.Button, tk.Checkbutton, ttk.Combobox)):
        return widget
    for child in widget.winfo_children():
        found = _first_focusable_descendant(child)
        if found is not None:
            return found
    return None


def _numeric_multiplier_from_event(param: ToolParam, event: tk.Event | None) -> float:
    state = _event_state(event)
    multiplier = 1.0
    if state & 0x0001:
        multiplier *= 10.0
    if state & 0x0004:
        multiplier *= 0.1
    if param.kind == "int":
        return max(multiplier, 0.1)
    return multiplier


def _event_has_ctrl(event: tk.Event | None) -> bool:
    return bool(_event_state(event) & 0x0004)


def _event_state(event: tk.Event | None) -> int:
    if event is None:
        return 0
    try:
        return int(getattr(event, "state", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _step_numeric_value(param: ToolParam, raw_value: str, direction: int, multiplier: float = 1.0) -> str:
    try:
        if param.kind == "int":
            step = max(1, int(round(_int_step_for_param(param) * multiplier)))
            value = int(str(raw_value).strip() or param.default or "0") + (step * direction)
            return str(_clamp_int(value, param))

        value = _parse_float_input(str(raw_value).strip() or param.default or "0")
        step = _float_step_for_param(param) * multiplier
        return _format_float_input(_clamp_float(value + (step * direction), param))
    except ValueError:
        return param.default


def _parse_bool_default(value: str) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "y", "on"}


def _int_step_for_param(param: ToolParam) -> int:
    if param.step:
        try:
            return max(1, int(_parse_float_input(param.step)))
        except ValueError:
            pass
    return 1


def _float_step_for_param(param: ToolParam) -> float:
    if param.step:
        try:
            return _parse_float_input(param.step)
        except ValueError:
            pass
    name = param.name.casefold()
    if "scale" in name or "multiplier" in name:
        return 0.1
    try:
        default = _parse_float_input(param.default)
    except ValueError:
        return 0.1
    if abs(default) >= 10 and default.is_integer():
        return 1.0
    return 0.1


def _clamp_int(value: int, param: ToolParam) -> int:
    if param.min_value:
        try:
            value = max(value, int(_parse_float_input(param.min_value)))
        except ValueError:
            pass
    if param.max_value:
        try:
            value = min(value, int(_parse_float_input(param.max_value)))
        except ValueError:
            pass
    return value


def _clamp_float(value: float, param: ToolParam) -> float:
    if param.min_value:
        try:
            value = max(value, _parse_float_input(param.min_value))
        except ValueError:
            pass
    if param.max_value:
        try:
            value = min(value, _parse_float_input(param.max_value))
        except ValueError:
            pass
    return value


def _format_float_input(value: float) -> str:
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    return formatted if formatted and formatted != "-0" else "0"


def _parse_float_input(value: str) -> float:
    return float(str(value).strip().replace(",", "."))


def _param_entry_ipady(spec: LayoutSpec) -> int:
    if spec.mode == "compact":
        return 1
    if spec.mode == "normal":
        return 2
    return 3



