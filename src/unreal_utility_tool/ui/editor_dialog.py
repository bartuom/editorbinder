from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from ..ai_provider import (
    AiProviderConfig,
    AiProviderError,
    api_key_status,
    generate_tool_with_repair,
    provider_names,
    provider_preset,
)
from ..ai_parser import parse_ai_tool_response
from ..compatibility_templates import infer_tool_type, tool_type_names
from ..models import (
    CATEGORY_CUSTOM,
    ROLE_PIPELINE_ARTIST,
    VISIBILITIES,
    VISIBILITY_PRIMARY,
    WORKFLOW_CUSTOM,
    Tool,
    category_options,
)
from ..prompts import PromptExample, build_ai_prompt, build_runtime_fix_prompt, select_prompt_examples
from ..settings import AppSettings
from ..theme import (
    ACCENT,
    ACCENT_DARK,
    ACCENT_HOVER,
    BG,
    BORDER,
    BORDER_DARK,
    CODE_BG,
    MUTED,
    HEADER_BG,
    PANEL,
    PANEL_ALT,
    SMALL_FONT,
    SUBTLE,
    SUCCESS,
    TEXT,
    TITLE_FONT,
    UI_FONT,
    UI_FONT_BOLD,
    WARNING,
    CODE_FONT,
    make_button,
)
from ..tool_importer import (
    IMPORT_POLICY_COPY,
    IMPORT_POLICY_REPLACE,
    IMPORT_POLICY_SKIP,
    ToolImportBatch,
    import_tools_from_paths,
    import_tools_from_text,
)
from ..validation import validate_tool_code, validate_tool_fields
from ..tool_linter import has_warning_or_error, lint_summary, lint_tool_code
from .code_editor import apply_python_highlighting, configure_code_tags
from .windowing import (
    _compute_dialog_geometry,
    _fallback_work_area_for_widget,
    _monitor_work_area_for_widget,
    configure_windows_window,
)


class ToolEditorDialog:
    def __init__(
        self,
        parent: tk.Tk,
        tool: Tool | None = None,
        prompt_example_code: str = "",
        existing_tools: list[Tool] | None = None,
        settings: AppSettings | None = None,
        save_settings: Callable[[], None] | None = None,
    ) -> None:
        self.parent = parent
        self.tool = tool
        self.prompt_example_code = prompt_example_code
        self.existing_tools = list(existing_tools or [])
        self.settings = settings or AppSettings()
        self.save_settings_callback = save_settings
        self.result: Tool | list[Tool] | ToolImportBatch | None = None
        self.mode = "manual" if tool else "paste"
        self.code_text: tk.Text | None = None
        self.ai_text: tk.Text | None = None
        self.request_text: tk.Text | None = None
        self.runtime_logs_text: tk.Text | None = None
        self.troubleshooting_text: tk.Text | None = None
        self.import_text: tk.Text | None = None
        self.imported_tools: list[Tool] = []
        self.import_errors: list[str] = []
        self.import_preview_text = ""
        self.import_policy_var = tk.StringVar(value=IMPORT_POLICY_SKIP)
        self.mode_buttons: dict[str, tk.Button] = {}
        self.manual_code = tool.code if tool else ""
        self.paste_and_save_button: tk.Button | None = None
        self.save_ai_button: tk.Button | None = None
        self.generate_ai_button: tk.Button | None = None
        self.api_settings_panel: tk.Frame | None = None
        self.api_settings_toggle_button: tk.Button | None = None
        self.api_settings_visible = False
        self.parse_status_label: tk.Label | None = None
        self.ai_key_status_label: tk.Label | None = None
        self.ai_generation_in_progress = False
        self.ai_last_response_text = ""
        self.ai_last_error_text = ""

        self.window = tk.Toplevel(parent)
        self.window.title("Edit Tool" if tool else "Add Tool")
        self.window.minsize(820, 620)
        self._set_initial_dialog_geometry()
        self.window.configure(bg=BG)
        self.window.transient(parent)
        self.window.grab_set()
        configure_windows_window(self.window)

        self.name_var = tk.StringVar(value=tool.name if tool else "")
        self.notes_var = tk.StringVar(value=tool.description if tool else "")
        self.category_var = tk.StringVar(value=tool.category if tool else CATEGORY_CUSTOM)
        self.workflows_var = tk.StringVar(value=", ".join(tool.workflows if tool else [WORKFLOW_CUSTOM]))
        self.roles_var = tk.StringVar(value=", ".join(tool.roles if tool else [ROLE_PIPELINE_ARTIST]))
        self.visibility_var = tk.StringVar(value=tool.visibility if tool else VISIBILITY_PRIMARY)
        self.validation_var = tk.StringVar()
        self.parse_status_var = tk.StringVar(value="Describe the tool, copy the prompt, then paste the AI answer.")
        self.import_status_var = tk.StringVar(value="Choose files or a folder to import tools.")
        self.preview_name_var = tk.StringVar(value="")
        self.preview_notes_var = tk.StringVar(value="")
        self.preview_code_var = tk.StringVar(value="")
        self.tool_type_var = tk.StringVar(value=tool_type_names()[-1])
        self.troubleshooting_summary_var = tk.StringVar(value="Troubleshooting: describe a tool or paste AI output.")
        self.ai_provider_var = tk.StringVar(value=self.settings.ai_provider or provider_names()[0])
        self.ai_base_url_var = tk.StringVar(value=self.settings.ai_base_url or "")
        self.ai_model_var = tk.StringVar(value=self.settings.ai_model or "")
        self.ai_api_key_env_var = tk.StringVar(value=self.settings.ai_api_key_env or "EDITORBINDER_API_KEY")
        self.ai_timeout_var = tk.StringVar(value=str(self.settings.ai_timeout_seconds or 45))
        self.ai_temperature_var = tk.StringVar(value=str(self.settings.ai_temperature if self.settings.ai_temperature is not None else 0.2))
        self.ai_max_tokens_var = tk.StringVar(value=str(self.settings.ai_max_tokens or 3000))
        self.ai_key_status_var = tk.StringVar(value="")

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)
        self._build_shell()
        self._render_mode()
        self._raise_near_parent()
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

    def _set_initial_dialog_geometry(self) -> None:
        self.parent.update_idletasks()
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = max(self.parent.winfo_width(), 380)
        parent_height = max(self.parent.winfo_height(), 320)

        work_area = _monitor_work_area_for_widget(self.parent) or _fallback_work_area_for_widget(self.parent)
        width, height, x, y = _compute_dialog_geometry(
            parent_x=parent_x,
            parent_y=parent_y,
            parent_width=parent_width,
            parent_height=parent_height,
            work_area=work_area,
        )
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _raise_near_parent(self) -> None:
        self.window.update_idletasks()
        self.window.lift(self.parent)
        self.window.focus_force()
        self.window.after(50, lambda: self.window.lift(self.parent))

    def _build_shell(self) -> None:
        header = tk.Frame(self.window, bg=HEADER_BG, padx=18, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)
        title = "Edit Tool" if self.tool else "Add Tool"
        tk.Label(header, text=title, bg=HEADER_BG, fg=TEXT, font=TITLE_FONT).grid(row=0, column=0, sticky="w")
        subtitle = "Create a tool" if self.tool is None else "Update metadata and script"
        tk.Label(header, text=subtitle, bg=HEADER_BG, fg=MUTED, font=SMALL_FONT).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(3, 0),
        )

        self.mode_bar = tk.Frame(header, bg=HEADER_BG)
        self.mode_bar.grid(row=0, column=1, rowspan=2, sticky="e")
        if self.tool is None:
            self._add_mode_tab("paste", "AI Flow", 0, padx=(0, 6))
            self._add_mode_tab("import", "Import Files", 1, padx=(0, 6))
            self._add_mode_tab("manual", "Manual", 2)

        self.body = tk.Frame(self.window, bg=BG, padx=16, pady=14)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)

        self.footer = tk.Frame(self.window, bg=HEADER_BG, padx=16, pady=10)
        self.footer.grid(row=2, column=0, sticky="ew")
        self.footer.columnconfigure(0, weight=1)

    def _add_mode_tab(self, mode: str, label: str, column: int, padx: tuple[int, int] = (0, 0)) -> None:
        button = make_button(
            self.mode_bar,
            label,
            lambda selected_mode=mode: self._set_mode(selected_mode),
            variant="secondary",
            padx=13,
            pady=5,
        )
        button.grid(row=0, column=column, padx=padx)
        self.mode_buttons[mode] = button

    def _refresh_mode_tabs(self) -> None:
        for mode, button in self.mode_buttons.items():
            active = mode == self.mode
            button.configure(
                bg=ACCENT_DARK if active else PANEL_ALT,
                activebackground=ACCENT if active else "#2a333d",
                fg=TEXT if active else MUTED,
                activeforeground=TEXT,
                font=UI_FONT_BOLD if active else UI_FONT,
                cursor="arrow" if active else "hand2",
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=ACCENT if active else BORDER_DARK,
            )

    def _set_mode(self, mode: str) -> None:
        if self.mode == mode:
            return
        if self.mode == "paste" and mode == "manual":
            self._pull_ai_into_manual()
        elif self.mode == "manual" and self.code_text is not None:
            self.manual_code = self.code_text.get("1.0", "end-1c")
        self.mode = mode
        self._render_mode()

    def _render_mode(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        for child in self.footer.winfo_children():
            child.destroy()
        self._reset_grid(self.body, rows=6, columns=4)
        self._reset_grid(self.footer, rows=2, columns=4)
        self.code_text = None
        self.ai_text = None
        self.request_text = None
        self.runtime_logs_text = None
        self.troubleshooting_text = None
        self.import_text = None
        self.paste_and_save_button = None
        self.save_ai_button = None
        self.generate_ai_button = None
        self.api_settings_panel = None
        self.api_settings_toggle_button = None
        self.parse_status_label = None
        self.ai_key_status_label = None

        if self.mode == "paste":
            self._build_paste_mode()
        elif self.mode == "import":
            self._build_import_mode()
        else:
            self._build_manual_mode()
        self._refresh_mode_tabs()

    def _reset_grid(self, widget: tk.Widget, *, rows: int, columns: int) -> None:
        for row in range(rows):
            widget.rowconfigure(row, weight=0, minsize=0)
        for column in range(columns):
            widget.columnconfigure(column, weight=0, minsize=0)

    def _make_card(self, parent: tk.Widget, row: int, column: int = 0, **grid_options) -> tk.Frame:
        card = tk.Frame(parent, bg=PANEL, padx=16, pady=14, highlightthickness=1, highlightbackground=BORDER_DARK)
        default_grid = {"sticky": "nsew", "padx": 0, "pady": 0}
        default_grid.update(grid_options)
        card.grid(row=row, column=column, **default_grid)
        return card

    def _section_title(self, parent: tk.Widget, title: str, row: int, subtitle: str = "") -> None:
        tk.Label(parent, text=title, bg=PANEL, fg=TEXT, font=UI_FONT_BOLD, anchor="w").grid(
            row=row,
            column=0,
            sticky="w",
        )
        if subtitle:
            tk.Label(parent, text=subtitle, bg=PANEL, fg=MUTED, font=SMALL_FONT, anchor="w", justify="left").grid(
                row=row + 1,
                column=0,
                sticky="ew",
                pady=(4, 0),
            )

    def _footer_status(self, variable: tk.StringVar, *, color: str = MUTED) -> tk.Label:
        status = tk.Label(
            self.footer,
            textvariable=variable,
            bg=HEADER_BG,
            fg=color,
            font=SMALL_FONT,
            anchor="w",
            justify="left",
            wraplength=360,
        )
        status.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        return status

    def _footer_actions(self) -> tk.Frame:
        actions = tk.Frame(self.footer, bg=HEADER_BG)
        actions.grid(row=0, column=1, sticky="e")
        return actions

    def _apply_paste_and_save_state(self, enabled: bool) -> None:
        if self.paste_and_save_button is None:
            return
        self.paste_and_save_button.configure(
            state=tk.NORMAL if enabled else tk.DISABLED,
            cursor="hand2" if enabled else "arrow",
            bg=ACCENT_DARK if enabled else PANEL_ALT,
            activebackground=ACCENT if enabled else PANEL_ALT,
        )

    def _make_entry(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        *,
        width: int = 18,
        font=None,
    ) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=variable,
            bg=CODE_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=font or UI_FONT,
            width=width,
        )

    def _add_entry_row(self, parent: tk.Widget, label: str, variable: tk.StringVar, *, row: int) -> tk.Entry:
        tk.Label(parent, text=label, bg=PANEL, fg=SUBTLE, font=SMALL_FONT).grid(
            row=row,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=(8, 0),
        )
        entry = self._make_entry(parent, variable, font=SMALL_FONT)
        entry.grid(row=row, column=1, sticky="ew", pady=(8, 0), ipady=3)
        entry.bind("<FocusOut>", self._on_ai_setting_changed)
        entry.bind("<Return>", self._on_ai_setting_changed)
        return entry

    def _add_combobox_row(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        *,
        row: int,
    ) -> ttk.Combobox:
        tk.Label(parent, text=label, bg=PANEL, fg=SUBTLE, font=SMALL_FONT).grid(
            row=row,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=(8, 0),
        )
        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly",
            font=SMALL_FONT,
            width=24,
            style="Dark.TCombobox",
        )
        combo.grid(row=row, column=1, sticky="ew", pady=(8, 0))
        return combo

    def _build_paste_mode(self) -> None:
        self.body.rowconfigure(0, weight=1)
        self.body.columnconfigure(0, weight=0, minsize=320)
        self.body.columnconfigure(1, weight=1, minsize=360)

        left = tk.Frame(self.body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        prompt = self._make_card(left, 0, sticky="nsew", pady=(0, 10))
        prompt.columnconfigure(0, weight=1)
        prompt.rowconfigure(4, weight=1)
        self._section_title(prompt, "Prompt", 0, "Describe the tool once, then generate or copy the prompt.")

        tk.Label(prompt, text="Tool Type", bg=PANEL, fg=SUBTLE, font=SMALL_FONT).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(12, 4),
        )
        type_combo = ttk.Combobox(
            prompt,
            textvariable=self.tool_type_var,
            values=tool_type_names(),
            state="readonly",
            font=SMALL_FONT,
            width=28,
            style="Dark.TCombobox",
        )
        type_combo.grid(row=3, column=0, sticky="ew")

        request_shell = tk.Frame(prompt, bg=BORDER_DARK, padx=1, pady=1)
        request_shell.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        request_shell.rowconfigure(0, weight=1)
        request_shell.columnconfigure(0, weight=1)
        self.request_text = tk.Text(
            request_shell,
            height=5,
            width=1,
            bg=CODE_BG,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=ACCENT_DARK,
            selectforeground=TEXT,
            borderwidth=0,
            font=UI_FONT,
            padx=10,
            pady=8,
            relief="flat",
            wrap="word",
            undo=True,
        )
        self.request_text.grid(row=0, column=0, sticky="nsew")
        self.request_text.bind("<KeyRelease>", self._on_request_changed)

        prompt_actions = tk.Frame(prompt, bg=PANEL)
        prompt_actions.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        prompt_actions.columnconfigure(0, weight=1)
        prompt_actions.columnconfigure(1, weight=1)
        make_button(
            prompt_actions,
            "Copy Prompt",
            self._copy_ai_prompt_from_dialog,
            variant="success",
            padx=12,
            pady=8,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.api_settings_toggle_button = make_button(
            prompt_actions,
            "API Settings",
            self._toggle_api_settings,
            variant="secondary",
            padx=12,
            pady=8,
        )
        self.api_settings_toggle_button.grid(row=0, column=1, sticky="ew")

        api = self._make_card(left, 1, sticky="ew")
        self.api_settings_panel = api
        api.columnconfigure(1, weight=1)
        self._section_title(api, "API", 0)
        self.generate_ai_button = make_button(
            api,
            "Generate via API",
            self._generate_ai_tool,
            variant="primary",
            padx=12,
            pady=7,
        )
        self.generate_ai_button.grid(row=0, column=1, sticky="e")
        provider_combo = self._add_combobox_row(api, "Provider", self.ai_provider_var, provider_names(), row=1)
        provider_combo.bind("<<ComboboxSelected>>", self._on_ai_provider_selected)
        self._add_entry_row(api, "Base URL", self.ai_base_url_var, row=2)
        self._add_entry_row(api, "Model", self.ai_model_var, row=3)
        self._add_entry_row(api, "Key env", self.ai_api_key_env_var, row=4)

        numeric = tk.Frame(api, bg=PANEL)
        numeric.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for column, (label, variable, width) in enumerate(
            [
                ("Temp", self.ai_temperature_var, 5),
                ("Max", self.ai_max_tokens_var, 7),
                ("Timeout", self.ai_timeout_var, 5),
            ]
        ):
            tk.Label(numeric, text=label, bg=PANEL, fg=SUBTLE, font=SMALL_FONT).grid(
                row=0,
                column=column * 2,
                sticky="w",
                padx=(0, 5),
            )
            entry = self._make_entry(numeric, variable, width=width, font=SMALL_FONT)
            entry.grid(row=0, column=column * 2 + 1, sticky="w", padx=(0, 10), ipady=3)
            entry.bind("<FocusOut>", self._on_ai_setting_changed)
            entry.bind("<Return>", self._on_ai_setting_changed)

        self.ai_key_status_label = tk.Label(
            api,
            textvariable=self.ai_key_status_var,
            bg=PANEL,
            fg=MUTED,
            font=SMALL_FONT,
            anchor="w",
            justify="left",
            wraplength=280,
        )
        self.ai_key_status_label.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._refresh_ai_key_status()
        if not self.api_settings_visible:
            api.grid_remove()

        right = tk.Frame(self.body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        answer = self._make_card(right, 0, sticky="nsew", pady=(0, 10))
        answer.columnconfigure(0, weight=1)
        answer.rowconfigure(2, weight=1)
        self._section_title(answer, "AI Answer", 0, "Paste the returned marker block here.")
        paste_shell = tk.Frame(answer, bg=BORDER_DARK, padx=1, pady=1)
        paste_shell.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        paste_shell.rowconfigure(0, weight=1)
        paste_shell.columnconfigure(0, weight=1)

        self.ai_text = tk.Text(
            paste_shell,
            width=1,
            bg=CODE_BG,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=ACCENT_DARK,
            selectforeground=TEXT,
            borderwidth=0,
            font=UI_FONT,
            padx=14,
            pady=12,
            relief="flat",
            wrap="word",
            undo=True,
        )
        self.ai_text.grid(row=0, column=0, sticky="nsew")
        self.ai_text.bind("<KeyRelease>", lambda _event: self._refresh_ai_preview())

        scroll = ttk.Scrollbar(paste_shell, orient="vertical", command=self.ai_text.yview, style="Dark.Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.ai_text.configure(yscrollcommand=scroll.set)

        preview = self._make_card(right, 1, sticky="ew", pady=(0, 10))
        preview.columnconfigure(1, weight=1)
        self._add_preview_row(preview, "Name", self.preview_name_var, 0)
        self._add_preview_row(preview, "Parameters / Notes", self.preview_notes_var, 1)
        self._add_preview_row(preview, "Code", self.preview_code_var, 2)

        runtime = self._make_card(right, 2, sticky="ew")
        runtime.columnconfigure(0, weight=1)
        self._section_title(runtime, "Runtime Log", 0)
        runtime_shell = tk.Frame(runtime, bg=BORDER_DARK, padx=1, pady=1)
        runtime_shell.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        runtime_shell.columnconfigure(0, weight=1)
        self.runtime_logs_text = tk.Text(
            runtime_shell,
            height=4,
            width=1,
            bg=CODE_BG,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=ACCENT_DARK,
            selectforeground=TEXT,
            borderwidth=0,
            font=SMALL_FONT,
            padx=10,
            pady=8,
            relief="flat",
            wrap="word",
            undo=True,
        )
        self.runtime_logs_text.grid(row=0, column=0, sticky="ew")
        self.runtime_logs_text.insert("1.0", "Paste Unreal Output Log here when runtime fails.")

        self.parse_status_label = self._footer_status(self.parse_status_var)
        actions = self._footer_actions()
        self.paste_and_save_button = make_button(
            actions,
            "Paste & Save",
            self._paste_and_save_from_clipboard,
            variant="primary",
        )
        self.paste_and_save_button.grid(row=0, column=0, padx=(0, 6), pady=(0, 4))
        make_button(actions, "Paste", self._paste_clipboard_to_ai, variant="secondary").grid(
            row=0, column=1, padx=(0, 6), pady=(0, 4)
        )
        make_button(actions, "Cancel", self._cancel, variant="secondary").grid(
            row=0, column=2, padx=(0, 6), pady=(0, 4)
        )
        self.save_ai_button = make_button(actions, "Save", self._save_from_ai, variant="success")
        self.save_ai_button.grid(row=0, column=3, pady=(0, 4))

        self._refresh_ai_preview()
        self._refresh_paste_and_save_button()
        self.window.bind("<FocusIn>", lambda _event: self._refresh_paste_and_save_button(), add="+")

    def _copy_ai_prompt_from_dialog(self) -> None:
        request = ""
        if self.request_text is not None:
            request = self.request_text.get("1.0", "end-1c")
        self._persist_ai_settings()
        examples = self._prompt_examples_for_request(request)
        self.window.clipboard_clear()
        self.window.clipboard_append(
            build_ai_prompt(
                self.prompt_example_code,
                request,
                examples=examples,
                tool_type=self.tool_type_var.get(),
            )
        )
        self.window.update()
        self._set_parse_status("Prompt copied. Paste it into AI, then paste the AI answer below.", MUTED)
        self._refresh_paste_and_save_button()

    def _toggle_api_settings(self) -> None:
        self.api_settings_visible = not self.api_settings_visible
        if self.api_settings_panel is not None:
            if self.api_settings_visible:
                self.api_settings_panel.grid()
            else:
                self.api_settings_panel.grid_remove()
        if self.api_settings_toggle_button is not None:
            self.api_settings_toggle_button.configure(
                text="Hide API Settings" if self.api_settings_visible else "API Settings"
            )

    def _generate_ai_tool(self) -> None:
        if self.request_text is None or self.ai_text is None or self.ai_generation_in_progress:
            return
        request = self.request_text.get("1.0", "end-1c").strip()
        if not request:
            self.ai_last_error_text = "Describe the tool before using Generate via API."
            self._set_parse_status(self.ai_last_error_text, WARNING)
            return

        config = self._current_ai_config()
        self._persist_ai_settings()
        has_key, key_message = api_key_status(config)
        self._refresh_ai_key_status()
        if not has_key:
            self.ai_last_error_text = key_message
            self._set_parse_status(key_message, WARNING)
            return

        self.ai_generation_in_progress = True
        self.ai_last_error_text = ""
        self.ai_last_response_text = ""
        if self.generate_ai_button is not None:
            self.generate_ai_button.configure(state=tk.DISABLED, cursor="arrow")
        self._set_parse_status(f"Generating with {config.provider}...", MUTED)

        examples = self._prompt_examples_for_request(request)
        thread = threading.Thread(
            target=self._run_ai_generation,
            args=(config, request, examples, self.tool_type_var.get()),
            daemon=True,
        )
        thread.start()

    def _run_ai_generation(
        self,
        config: AiProviderConfig,
        request: str,
        examples: list[PromptExample],
        tool_type: str,
    ) -> None:
        result = None
        error = ""
        try:
            result = generate_tool_with_repair(config, request, examples, tool_type=tool_type)
        except AiProviderError as exc:
            error = str(exc)
        except Exception as exc:
            error = f"AI generation failed: {exc}"

        def finish() -> None:
            if self.window.winfo_exists():
                self._finish_ai_generation(result, error)

        try:
            self.window.after(0, finish)
        except tk.TclError:
            pass

    def _finish_ai_generation(self, result, error: str) -> None:
        self.ai_generation_in_progress = False
        if self.generate_ai_button is not None:
            self.generate_ai_button.configure(state=tk.NORMAL, cursor="hand2")

        if error:
            self.ai_last_error_text = error
            self._set_parse_status(error, WARNING)
            return
        if result is None:
            self.ai_last_error_text = "AI generation returned no result."
            self._set_parse_status(self.ai_last_error_text, WARNING)
            return

        self.ai_last_response_text = result.raw_response_text or result.response_text
        self.ai_last_error_text = result.error
        if self.ai_text is not None:
            self.ai_text.delete("1.0", tk.END)
            self.ai_text.insert("1.0", result.response_text)
        self._refresh_ai_preview()
        self._refresh_paste_and_save_button()

        if result.ok:
            status = "Generated and validated."
            if result.repaired:
                status += " One automatic repair was applied."
            self._set_parse_status(status, SUCCESS)
        else:
            self._set_parse_status(result.error or "Generated response is not ready to save.", WARNING)

    def _copy_ai_response(self) -> None:
        text = self.ai_last_response_text
        if not text and self.ai_text is not None:
            text = self.ai_text.get("1.0", "end-1c")
        if not text.strip():
            text = "No AI response captured."
        self._copy_text_to_clipboard(text)
        self._set_parse_status("AI response copied.", MUTED)

    def _copy_ai_error(self) -> None:
        text = self.ai_last_error_text.strip() or self.parse_status_var.get().strip() or "No AI error captured."
        self._copy_text_to_clipboard(text)
        self._set_parse_status("AI error/status copied.", MUTED)

    def _copy_fix_prompt_with_logs(self) -> None:
        request = self.request_text.get("1.0", "end-1c") if self.request_text is not None else ""
        runtime_logs = self.runtime_logs_text.get("1.0", "end-1c") if self.runtime_logs_text is not None else ""
        ai_response = self.ai_text.get("1.0", "end-1c") if self.ai_text is not None else ""
        parsed = parse_ai_tool_response(ai_response)
        name = parsed.name or self.preview_name_var.get() or "Imported AI Tool"
        code = parsed.code or ai_response
        diagnostics = list(parsed.diagnostics)
        diagnostics.extend(f"{issue.severity}: {issue.title}: {issue.message}" for issue in lint_tool_code(code))
        prompt = build_runtime_fix_prompt(
            request,
            name,
            code,
            runtime_logs,
            diagnostics,
            tool_type=self.tool_type_var.get(),
        )
        self._copy_text_to_clipboard(prompt)
        self._set_parse_status("Fix prompt with runtime logs copied.", MUTED)

    def _on_request_changed(self, _event: tk.Event | None = None) -> None:
        if self.request_text is None:
            return
        request = self.request_text.get("1.0", "end-1c")
        if self.tool_type_var.get() == "Custom":
            self.tool_type_var.set(infer_tool_type(request))

    def _prompt_examples_for_request(self, request: str) -> list[PromptExample]:
        try:
            from ..presets import default_presets

            bundled_tools = default_presets()
        except Exception:
            bundled_tools = []
        examples = select_prompt_examples(request, bundled_tools, limit=3)
        if examples:
            return examples
        if self.prompt_example_code.strip():
            return [PromptExample("Selected Tool", "Fallback style reference.", self.prompt_example_code)]
        return []

    def _on_ai_provider_selected(self, _event: tk.Event | None = None) -> None:
        preset = provider_preset(self.ai_provider_var.get())
        self.ai_provider_var.set(preset.name)
        self.ai_base_url_var.set(preset.base_url)
        self.ai_model_var.set(preset.model)
        self.ai_api_key_env_var.set(preset.api_key_env)
        self._persist_ai_settings()
        self._refresh_ai_key_status()

    def _on_ai_setting_changed(self, _event: tk.Event | None = None) -> str:
        self._persist_ai_settings()
        self._refresh_ai_key_status()
        return "break"

    def _current_ai_config(self) -> AiProviderConfig:
        return AiProviderConfig(
            provider=self.ai_provider_var.get().strip() or provider_names()[0],
            base_url=self.ai_base_url_var.get().strip(),
            model=self.ai_model_var.get().strip(),
            api_key_env=self.ai_api_key_env_var.get().strip() or "EDITORBINDER_API_KEY",
            timeout_seconds=_parse_positive_int(self.ai_timeout_var.get(), default=45),
            temperature=_parse_float(self.ai_temperature_var.get(), default=0.2),
            max_tokens=_parse_positive_int(self.ai_max_tokens_var.get(), default=3000),
        )

    def _persist_ai_settings(self) -> None:
        config = self._current_ai_config()
        self.settings.ai_provider = config.provider
        self.settings.ai_base_url = config.base_url
        self.settings.ai_model = config.model
        self.settings.ai_api_key_env = config.api_key_env
        self.settings.ai_timeout_seconds = config.timeout_seconds
        self.settings.ai_temperature = config.temperature
        self.settings.ai_max_tokens = config.max_tokens
        if self.save_settings_callback is not None:
            self.save_settings_callback()

    def _refresh_ai_key_status(self) -> None:
        has_key, message = api_key_status(self._current_ai_config())
        self.ai_key_status_var.set(message)
        if self.ai_key_status_label is not None:
            self.ai_key_status_label.configure(fg=SUCCESS if has_key else WARNING)

    def _import_clipboard_as_tool(self) -> None:
        self._paste_and_save_from_clipboard()

    def _paste_and_save_from_clipboard(self) -> None:
        if self.ai_text is None:
            return
        if not self._clipboard_looks_like_ai_tool():
            self._set_parse_status("Clipboard does not contain a ready AI answer yet.", WARNING)
            self._refresh_paste_and_save_button()
            return
        self._paste_clipboard_to_ai()
        self._save_from_ai()

    def _refresh_paste_and_save_button(self) -> None:
        if self.paste_and_save_button is None:
            return
        enabled = self._clipboard_looks_like_ai_tool()
        self._apply_paste_and_save_state(enabled)

    def _clipboard_looks_like_ai_tool(self) -> bool:
        text = self._clipboard_text()
        if not text.strip():
            return False
        lowered = text.casefold()
        prompt_markers = (
            "return only this marker format",
            "tool request",
            "fix this unreal engine python console tool",
            "paste the unreal python error here",
            "current tool code",
        )
        if any(marker in lowered for marker in prompt_markers):
            return False
        parsed = parse_ai_tool_response(text)
        name = parsed.name or "Imported AI Tool"
        if validate_tool_fields(name, parsed.code):
            return False
        return True

    def _clipboard_text(self) -> str:
        try:
            return self.window.clipboard_get()
        except tk.TclError:
            return ""

    def _build_import_mode(self) -> None:
        self.body.rowconfigure(0, weight=1)
        self.body.columnconfigure(0, weight=0, minsize=320)
        self.body.columnconfigure(1, weight=1, minsize=430)

        intro = self._make_card(self.body, 0, column=0, sticky="nsew", padx=(0, 12))
        intro.columnconfigure(0, weight=1)

        tk.Label(
            intro,
            text="Install Tool Pack",
            bg=PANEL,
            fg=TEXT,
            font=UI_FONT_BOLD,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            intro,
            text="Supported: .zip packs, .json libraries, AI .txt/clipboard, and paste-ready .py scripts.",
            bg=PANEL,
            fg=MUTED,
            font=SMALL_FONT,
            anchor="w",
            justify="left",
            wraplength=280,
        ).grid(row=1, column=0, sticky="ew", pady=(6, 0))

        import_actions = tk.Frame(intro, bg=PANEL)
        import_actions.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        import_actions.columnconfigure(0, weight=1)
        import_actions.columnconfigure(1, weight=1)
        make_button(import_actions, "Select Files", self._select_import_files, variant="primary").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 6),
        )
        make_button(import_actions, "Select Folder", self._select_import_folder, variant="secondary").grid(
            row=0,
            column=1,
            sticky="ew",
        )
        make_button(import_actions, "Paste Clipboard", self._load_import_clipboard, variant="secondary").grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )

        duplicate_options = tk.Frame(intro, bg=PANEL)
        duplicate_options.grid(row=3, column=0, sticky="ew", pady=(18, 0))
        tk.Label(
            duplicate_options,
            text="Duplicates:",
            bg=PANEL,
            fg=SUBTLE,
            font=SMALL_FONT,
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        for row, (value, label) in enumerate(
            [
                (IMPORT_POLICY_SKIP, "Skip duplicates"),
                (IMPORT_POLICY_COPY, "Import as copies"),
                (IMPORT_POLICY_REPLACE, "Replace existing"),
            ],
            start=1,
        ):
            tk.Radiobutton(
                duplicate_options,
                text=label,
                variable=self.import_policy_var,
                value=value,
                command=self._refresh_import_preview,
                bg=PANEL,
                fg=TEXT,
                activebackground=PANEL,
                activeforeground=TEXT,
                selectcolor=CODE_BG,
                font=SMALL_FONT,
                cursor="hand2",
                relief="flat",
            ).grid(row=row, column=0, sticky="w", pady=(0, 6))

        preview_card = self._make_card(self.body, 0, column=1, sticky="nsew")
        preview_card.columnconfigure(0, weight=1)
        preview_card.rowconfigure(1, weight=1)
        self._section_title(preview_card, "Import Preview", 0)
        preview_shell = tk.Frame(preview_card, bg=BORDER_DARK, padx=1, pady=1)
        preview_shell.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        preview_shell.rowconfigure(0, weight=1)
        preview_shell.columnconfigure(0, weight=1)

        self.import_text = tk.Text(
            preview_shell,
            width=1,
            bg=CODE_BG,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=ACCENT_DARK,
            selectforeground=TEXT,
            borderwidth=0,
            font=UI_FONT,
            padx=14,
            pady=12,
            relief="flat",
            wrap="word",
            state="disabled",
        )
        self.import_text.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(
            preview_shell,
            orient="vertical",
            command=self.import_text.yview,
            style="Dark.Vertical.TScrollbar",
        )
        scroll.grid(row=0, column=1, sticky="ns")
        self.import_text.configure(yscrollcommand=scroll.set)

        self._footer_status(self.import_status_var)
        actions = self._footer_actions()
        make_button(actions, "Cancel", self._cancel, variant="secondary").grid(row=0, column=0, padx=(0, 6))
        make_button(actions, "Copy Preview", self._copy_import_preview, variant="secondary").grid(
            row=0,
            column=1,
            padx=(0, 6),
        )
        make_button(actions, "Save Imported", self._save_imported, variant="primary").grid(row=0, column=2)
        self._refresh_import_preview()

    def _select_import_files(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self.window,
            title="Import Tool Files",
            filetypes=[
                ("Supported tool files", "*.zip *.json *.py *.txt"),
                ("Tool pack ZIPs", "*.zip"),
                ("JSON libraries", "*.json"),
                ("Python scripts", "*.py"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if paths:
            self._load_import_paths(paths)

    def _select_import_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.window, title="Import Tools From Folder")
        if folder:
            self._load_import_paths([folder])

    def _load_import_paths(self, paths: list[str] | tuple[str, ...]) -> None:
        self.imported_tools, self.import_errors = import_tools_from_paths(paths)
        self._refresh_import_preview()

    def _load_import_clipboard(self) -> None:
        text = self._clipboard_text()
        if not text.strip():
            self.imported_tools = []
            self.import_errors = ["Clipboard is empty."]
            self._refresh_import_preview()
            return
        try:
            self.imported_tools = import_tools_from_text(text, fallback_name="Clipboard Tool")
            self.import_errors = []
        except ValueError as exc:
            self.imported_tools = []
            self.import_errors = [f"Clipboard: {exc}"]
        self._refresh_import_preview()

    def _refresh_import_preview(self) -> None:
        if self.import_text is None:
            return

        lines: list[str] = []
        if self.imported_tools:
            lines.append("Ready to import:")
            lines.append("")
            batch_counts = self._import_batch_name_counts()
            batch_id_counts = self._import_batch_id_counts()
            existing_ids = self._existing_tool_ids()
            seen_names: set[str] = set()
            seen_ids: set[str] = set()
            for index, tool in enumerate(self.imported_tools, start=1):
                name_key = _normalize_preview_name(tool.name)
                id_key = _normalize_preview_id(tool.id)
                duplicate_labels: list[str] = []
                if id_key and id_key in existing_ids:
                    duplicate_labels.append("existing id")
                if name_key in self._existing_tool_names():
                    duplicate_labels.append("existing name")
                if id_key and batch_id_counts.get(id_key, 0) > 1:
                    duplicate_labels.append("repeated id in import")
                if batch_counts.get(name_key, 0) > 1:
                    duplicate_labels.append("repeated in import")
                action = self._preview_import_action(tool, seen_names, seen_ids)
                duplicate_text = f" ({', '.join(duplicate_labels)})" if duplicate_labels else ""
                lines.append(f"{index}. [{action}] {tool.name}{duplicate_text}")
                if tool.description:
                    lines.append(f"   {tool.description}")
                lines.append("")
                if id_key:
                    seen_ids.add(id_key)
                seen_names.add(name_key)

        if self.import_errors:
            lines.append("Skipped:")
            lines.append("")
            lines.extend(f"- {error}" for error in self.import_errors)

        if not lines:
            lines = [
                "Select a pack ZIP, JSON library, folder, clipboard text, or Python script.",
                "",
                "Recommended for paid packs: keep Duplicates set to Skip duplicates.",
                "",
                "Supported:",
                ".zip EditorBinder packs with editorbinder-pack.json",
                ".json tool libraries",
                ".txt/clipboard AI marker blocks",
                ".py paste-ready scripts",
            ]

        skipped = len(self.import_errors)
        if self.imported_tools:
            duplicates = self._import_duplicate_count()
            duplicate_part = f" Duplicates: {duplicates}." if duplicates else ""
            self.import_status_var.set(
                f"Ready to import {len(self.imported_tools)} tool(s). Skipped {skipped}.{duplicate_part}"
            )
        else:
            self.import_status_var.set("Choose files or a folder to import tools.")

        self.import_text.configure(state="normal")
        self.import_text.delete("1.0", tk.END)
        self.import_preview_text = "\n".join(lines).strip()
        self.import_text.insert("1.0", self.import_preview_text)
        self.import_text.configure(state="disabled")

    def _copy_parse_status(self) -> None:
        self._copy_text_to_clipboard(self.parse_status_var.get())
        self._set_parse_status("Status copied.", MUTED)

    def _copy_import_preview(self) -> None:
        self._copy_text_to_clipboard(self.import_preview_text or self.import_status_var.get())
        self.import_status_var.set("Import preview copied.")

    def _copy_text_to_clipboard(self, text: str) -> None:
        self.window.clipboard_clear()
        self.window.clipboard_append(text)
        self.window.update()

    def _save_imported(self) -> None:
        if not self.imported_tools:
            messagebox.showwarning("No Tools Found", "Select files or a folder with importable tools.", parent=self.window)
            return
        self.result = ToolImportBatch(list(self.imported_tools), self.import_policy_var.get())
        self.window.destroy()

    def _existing_tool_names(self) -> set[str]:
        return {_normalize_preview_name(tool.name) for tool in self.existing_tools}

    def _existing_tool_ids(self) -> set[str]:
        return {_normalize_preview_id(tool.id) for tool in self.existing_tools if _normalize_preview_id(tool.id)}

    def _import_batch_name_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for tool in self.imported_tools:
            name_key = _normalize_preview_name(tool.name)
            counts[name_key] = counts.get(name_key, 0) + 1
        return counts

    def _import_batch_id_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for tool in self.imported_tools:
            id_key = _normalize_preview_id(tool.id)
            if id_key:
                counts[id_key] = counts.get(id_key, 0) + 1
        return counts

    def _import_duplicate_count(self) -> int:
        existing_ids = self._existing_tool_ids()
        existing_names = self._existing_tool_names()
        batch_id_counts = self._import_batch_id_counts()
        batch_counts = self._import_batch_name_counts()
        return sum(
            1
            for tool in self.imported_tools
            if (_normalize_preview_id(tool.id) and _normalize_preview_id(tool.id) in existing_ids)
            or _normalize_preview_name(tool.name) in existing_names
            or batch_id_counts.get(_normalize_preview_id(tool.id), 0) > 1
            or batch_counts.get(_normalize_preview_name(tool.name), 0) > 1
        )

    def _preview_import_action(self, tool: Tool, seen_names: set[str], seen_ids: set[str]) -> str:
        id_key = _normalize_preview_id(tool.id)
        name_key = _normalize_preview_name(tool.name)
        duplicate_existing = (id_key and id_key in self._existing_tool_ids()) or name_key in self._existing_tool_names()
        duplicate_in_import = (id_key and id_key in seen_ids) or name_key in seen_names
        policy = self.import_policy_var.get()
        if policy == IMPORT_POLICY_SKIP and (duplicate_existing or duplicate_in_import):
            return "SKIP"
        if policy == IMPORT_POLICY_REPLACE:
            if duplicate_in_import:
                return "SKIP"
            if duplicate_existing:
                return "REPLACE"
        if policy == IMPORT_POLICY_COPY and (duplicate_existing or duplicate_in_import):
            return "ADD COPY"
        return "ADD"

    def _build_manual_mode(self) -> None:
        self.body.rowconfigure(0, weight=1)
        self.body.columnconfigure(0, weight=0, minsize=320)
        self.body.columnconfigure(1, weight=1, minsize=430)

        form = self._make_card(self.body, 0, column=0, sticky="nsew", padx=(0, 12))
        form.columnconfigure(1, weight=1)
        self._section_title(form, "Metadata", 0)
        self._add_field(form, "Name", self.name_var, row=1)
        self._add_field(form, "Parameters / Notes", self.notes_var, row=2)
        self._add_category_field(form, row=3)
        self._add_field(form, "Workflows", self.workflows_var, row=4)
        self._add_field(form, "Roles", self.roles_var, row=5)
        self._add_visibility_field(form, row=6)

        editor_shell = self._make_card(self.body, 0, column=1, sticky="nsew")
        editor_shell.rowconfigure(1, weight=1)
        editor_shell.columnconfigure(0, weight=1)

        tk.Label(editor_shell, text="Script Code", bg=PANEL, fg=TEXT, font=UI_FONT_BOLD).grid(
            row=0, column=0, sticky="w"
        )

        self.code_text = self._create_code_editor(editor_shell, self.manual_code)
        self.code_text.bind("<KeyRelease>", lambda _event: self._on_code_changed())

        self.validation_label = self._footer_status(self.validation_var, color=SUCCESS)
        actions = self._footer_actions()
        make_button(actions, "Copy Error", self._copy_validation_error, variant="secondary").grid(
            row=0,
            column=0,
            padx=(0, 6),
        )
        make_button(actions, "Cancel", self._cancel, variant="secondary").grid(row=0, column=1, padx=(0, 6))
        make_button(actions, "Save", self._save_manual, variant="primary").grid(row=0, column=2)
        self._refresh_validation()

    def _create_code_editor(self, parent: tk.Frame, code: str) -> tk.Text:
        code_border = tk.Frame(parent, bg=BORDER_DARK, padx=1, pady=1)
        code_border.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        code_border.rowconfigure(0, weight=1)
        code_border.columnconfigure(0, weight=1)

        code_frame = tk.Frame(code_border, bg=CODE_BG)
        code_frame.grid(row=0, column=0, sticky="nsew")
        code_frame.rowconfigure(0, weight=1)
        code_frame.columnconfigure(0, weight=1)

        text = tk.Text(
            code_frame,
            width=1,
            bg=CODE_BG,
            fg="#d6deeb",
            insertbackground=TEXT,
            selectbackground=ACCENT_DARK,
            selectforeground=TEXT,
            borderwidth=0,
            font=CODE_FONT,
            padx=14,
            pady=12,
            relief="flat",
            wrap="none",
            undo=True,
            spacing1=2,
            spacing3=2,
        )
        text.grid(row=0, column=0, sticky="nsew")
        text.insert("1.0", code)
        configure_code_tags(text)
        apply_python_highlighting(text)

        y_scroll = ttk.Scrollbar(code_frame, orient="vertical", command=text.yview, style="Dark.Vertical.TScrollbar")
        y_scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(
            code_frame,
            orient="horizontal",
            command=text.xview,
            style="Dark.Horizontal.TScrollbar",
        )
        x_scroll.grid(row=1, column=0, sticky="ew")
        text.configure(xscrollcommand=x_scroll.set)
        return text

    def _add_preview_row(self, parent: tk.Frame, label: str, variable: tk.StringVar, row: int) -> None:
        tk.Label(parent, text=label, bg=PANEL, fg=SUBTLE, font=SMALL_FONT).grid(
            row=row, column=0, sticky="nw", padx=(0, 14), pady=(0, 7)
        )
        tk.Label(
            parent,
            textvariable=variable,
            bg=PANEL,
            fg=TEXT,
            font=UI_FONT,
            anchor="w",
            justify="left",
            wraplength=560,
        ).grid(row=row, column=1, sticky="ew", pady=(0, 7))

    def _add_field(self, parent: tk.Frame, label: str, variable: tk.StringVar, row: int) -> None:
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED, font=SMALL_FONT).grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=(0, 10)
        )
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=CODE_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=UI_FONT,
        )
        entry.grid(row=row, column=1, sticky="ew", pady=(0, 10), ipady=7)

    def _add_category_field(self, parent: tk.Frame, row: int) -> None:
        tk.Label(parent, text="Category", bg=PANEL, fg=MUTED, font=SMALL_FONT).grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=(0, 10)
        )
        combo = ttk.Combobox(
            parent,
            textvariable=self.category_var,
            values=category_options(self.existing_tools, [self.category_var.get()]),
            state="normal",
            font=UI_FONT,
            style="Dark.TCombobox",
        )
        combo.grid(row=row, column=1, sticky="ew", pady=(0, 10), ipady=4)

    def _add_visibility_field(self, parent: tk.Frame, row: int) -> None:
        tk.Label(parent, text="Visibility", bg=PANEL, fg=MUTED, font=SMALL_FONT).grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=(0, 10)
        )
        combo = ttk.Combobox(
            parent,
            textvariable=self.visibility_var,
            values=VISIBILITIES,
            state="readonly",
            font=UI_FONT,
            style="Dark.TCombobox",
        )
        combo.grid(row=row, column=1, sticky="ew", pady=(0, 10), ipady=4)

    def _metadata_workflows(self) -> list[str]:
        return [item.strip() for item in self.workflows_var.get().split(",") if item.strip()]

    def _metadata_roles(self) -> list[str]:
        return [item.strip() for item in self.roles_var.get().split(",") if item.strip()]

    def show(self) -> Tool | list[Tool] | ToolImportBatch | None:
        self.parent.wait_window(self.window)
        return self.result

    def _paste_clipboard_to_ai(self) -> None:
        if self.ai_text is None:
            return
        text = self._clipboard_text()
        if not text:
            return
        self.ai_text.delete("1.0", tk.END)
        self.ai_text.insert("1.0", text)
        self._refresh_ai_preview()
        self._refresh_paste_and_save_button()

    def _refresh_ai_preview(self) -> None:
        if self.ai_text is None:
            return
        raw_text = self.ai_text.get("1.0", "end-1c")
        parsed = parse_ai_tool_response(raw_text)
        name = parsed.name or "Imported AI Tool"
        notes = parsed.notes or "None"
        ready_to_save = False
        if not raw_text.strip():
            code_summary = "No code detected."
            self._set_parse_status("Describe the tool, copy the prompt, then paste the AI answer.", MUTED)
        elif not parsed.code:
            code_summary = "No code detected."
            diagnostics = " / ".join(parsed.diagnostics)
            suffix = f" {diagnostics}" if diagnostics else ""
            self._set_parse_status(f"Not ready: no Python code detected.{suffix}", WARNING)
        else:
            field_errors = validate_tool_fields(name, parsed.code)
            syntax = validate_tool_code(parsed.code)
            if field_errors:
                code_summary = " / ".join(field_errors)
                self._set_parse_status(f"Not ready: {' / '.join(field_errors)}", WARNING)
            elif syntax.ok:
                diagnostics = " / ".join(parsed.diagnostics)
                suffix = f" {diagnostics}" if diagnostics else ""
                if has_warning_or_error(parsed.code):
                    code_summary = "Python syntax ok. Risky Unreal API usage detected."
                    self._set_parse_status(f"Risky Unreal API usage detected.{suffix}", WARNING)
                else:
                    code_summary = "Python syntax looks valid."
                    self._set_parse_status(f"Ready to save.{suffix}", SUCCESS)
                ready_to_save = True
            else:
                code_summary = syntax.message
                self._set_parse_status(
                    f"Parsed with syntax warning: {syntax.message} Save will ask for confirmation.",
                    WARNING,
                )
                ready_to_save = True

        self.preview_name_var.set(name)
        self.preview_notes_var.set(notes)
        self.preview_code_var.set(code_summary)
        self._refresh_troubleshooting(parsed.code if raw_text.strip() else "")
        if self.save_ai_button is not None:
            self.save_ai_button.configure(
                state=tk.NORMAL if ready_to_save else tk.DISABLED,
                cursor="hand2" if ready_to_save else "arrow",
            )

    def _refresh_troubleshooting(self, code: str) -> None:
        if not code.strip():
            summary = "Troubleshooting: paste AI output to see static checks."
            details = (
                "Workflow:\n"
                "1. Choose Tool Type.\n"
                "2. Copy Prompt For AI.\n"
                "3. Paste AI answer.\n"
                "4. If Unreal fails, paste Output Log on the right and copy a fix prompt."
            )
        else:
            issues = lint_tool_code(code)
            if not issues:
                summary = "Troubleshooting: no known risky Unreal Python patterns detected."
            elif any(issue.severity == "warning" for issue in issues):
                summary = "Troubleshooting: risky Unreal API usage found. Runtime test recommended."
            else:
                summary = "Troubleshooting: syntax ok, but runtime diagnostics are recommended."
            details = lint_summary(code)

        self.troubleshooting_summary_var.set(summary)
        if self.troubleshooting_text is not None:
            self.troubleshooting_text.configure(state="normal")
            self.troubleshooting_text.delete("1.0", tk.END)
            self.troubleshooting_text.insert("1.0", details)
            self.troubleshooting_text.configure(state="disabled")

    def _set_parse_status(self, message: str, color: str = MUTED) -> None:
        self.parse_status_var.set(message)
        if self.parse_status_label is not None:
            self.parse_status_label.configure(fg=color)

    def _pull_ai_into_manual(self) -> None:
        if self.ai_text is None:
            return
        parsed = parse_ai_tool_response(self.ai_text.get("1.0", "end-1c"))
        if parsed.name:
            self.name_var.set(parsed.name)
        if parsed.notes and parsed.notes.casefold() != "none":
            self.notes_var.set(parsed.notes)
        if parsed.code:
            self.manual_code = parsed.code

    def _save_from_ai(self) -> None:
        if self.ai_text is None:
            return
        parsed = parse_ai_tool_response(self.ai_text.get("1.0", "end-1c"))
        name = parsed.name or "Imported AI Tool"
        notes = "" if parsed.notes.casefold() == "none" else parsed.notes
        code = parsed.code

        field_errors = validate_tool_fields(name, code)
        if field_errors:
            self._set_parse_status(f"Not ready: {' / '.join(field_errors)}", WARNING)
            messagebox.showwarning("Missing Fields", "\n".join(field_errors), parent=self.window)
            return

        if not self._confirm_syntax_if_needed(code):
            return

        self.result = Tool.create(
            name=name,
            description=notes,
            tags=[],
            code=code,
            category=CATEGORY_CUSTOM,
            workflows=self._metadata_workflows(),
            roles=self._metadata_roles(),
            visibility=self.visibility_var.get(),
        )
        self.window.destroy()

    def _on_code_changed(self) -> None:
        if self.code_text is None:
            return
        self._refresh_validation()
        apply_python_highlighting(self.code_text)

    def _refresh_validation(self) -> None:
        if self.code_text is None:
            return
        result = validate_tool_code(self.code_text.get("1.0", "end-1c"))
        self.validation_var.set("Python syntax looks valid." if result.ok else result.message)
        self.validation_label.configure(fg=SUCCESS if result.ok else WARNING)

    def _copy_validation_error(self) -> None:
        self._copy_text_to_clipboard(self.validation_var.get())
        self.validation_var.set("Validation message copied.")
        self.validation_label.configure(fg=MUTED)

    def _save_manual(self) -> None:
        if self.code_text is None:
            return
        name = self.name_var.get()
        description = self.notes_var.get()
        category = self.category_var.get()
        workflows = self._metadata_workflows()
        roles = self._metadata_roles()
        visibility = self.visibility_var.get()
        tags = list(self.tool.tags) if self.tool else []
        code = self.code_text.get("1.0", "end-1c")

        field_errors = validate_tool_fields(name, code)
        if field_errors:
            messagebox.showwarning("Missing Fields", "\n".join(field_errors), parent=self.window)
            return

        if not self._confirm_syntax_if_needed(code):
            return

        if self.tool:
            self.result = self.tool.with_updates(
                name=name,
                description=description,
                tags=tags,
                code=code,
                category=category,
                workflows=workflows,
                roles=roles,
                visibility=visibility,
            )
        else:
            self.result = Tool.create(
                name=name,
                description=description,
                tags=tags,
                code=code,
                category=category,
                workflows=workflows,
                roles=roles,
                visibility=visibility,
            )
        self.window.destroy()

    def _confirm_syntax_if_needed(self, code: str) -> bool:
        syntax_result = validate_tool_code(code)
        if syntax_result.ok:
            return True
        return messagebox.askyesno(
            "Save With Syntax Error?",
            f"{syntax_result.message}\n\nSave this tool anyway?",
            parent=self.window,
        )

    def _cancel(self) -> None:
        self.window.destroy()


def _normalize_preview_name(name: str) -> str:
    return " ".join(name.casefold().strip().split())


def _normalize_preview_id(tool_id: str) -> str:
    return str(tool_id or "").strip()


def _parse_positive_int(value: str, *, default: int) -> int:
    try:
        number = int(str(value).strip())
    except ValueError:
        return default
    return number if number > 0 else default


def _parse_float(value: str, *, default: float) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return default

