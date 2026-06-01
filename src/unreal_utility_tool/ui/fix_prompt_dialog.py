from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..models import Tool
from ..prompts import build_fix_prompt
from ..theme import BG, BORDER, CODE_BG, HEADER_BG, MUTED, PANEL, SMALL_FONT, TEXT, TITLE_FONT, UI_FONT, make_button
from .windowing import _compute_dialog_geometry, _fallback_work_area_for_widget, _monitor_work_area_for_widget


class FixPromptDialog:
    def __init__(self, parent: tk.Tk, tool: Tool) -> None:
        self.parent = parent
        self.tool = tool
        self.copied = False

        self.window = tk.Toplevel(parent)
        self.window.title("Copy Fix Prompt")
        self.window.minsize(520, 420)
        self._set_initial_dialog_geometry()
        self.window.configure(bg=BG)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)

        self.status_var = tk.StringVar(value="Paste the Unreal error, then copy a fix prompt for AI.")
        self.error_text: tk.Text | None = None

        self._build_ui()
        self._raise_near_parent()
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

    def _set_initial_dialog_geometry(self) -> None:
        self.parent.update_idletasks()
        work_area = _monitor_work_area_for_widget(self.parent) or _fallback_work_area_for_widget(self.parent)
        width, height, x, y = _compute_dialog_geometry(
            parent_x=self.parent.winfo_rootx(),
            parent_y=self.parent.winfo_rooty(),
            parent_width=max(self.parent.winfo_width(), 380),
            parent_height=max(self.parent.winfo_height(), 320),
            work_area=work_area,
        )
        self.window.geometry(f"{min(width, 640)}x{min(height, 560)}+{x}+{y}")

    def _raise_near_parent(self) -> None:
        self.window.update_idletasks()
        self.window.lift(self.parent)
        self.window.focus_force()
        self.window.after(50, lambda: self.window.lift(self.parent))

    def _build_ui(self) -> None:
        header = tk.Frame(self.window, bg=HEADER_BG, padx=18, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        tk.Label(header, text="Fix Prompt", bg=HEADER_BG, fg=TEXT, font=TITLE_FONT).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text=self.tool.name,
            bg=HEADER_BG,
            fg=MUTED,
            font=SMALL_FONT,
            wraplength=560,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        body = tk.Frame(self.window, bg=BG, padx=18)
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)
        tk.Label(
            body,
            text="Unreal Python Error",
            bg=BG,
            fg=TEXT,
            font=UI_FONT,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        shell = tk.Frame(body, bg=BORDER, padx=1, pady=1)
        shell.grid(row=1, column=0, sticky="nsew")
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)

        self.error_text = tk.Text(
            shell,
            bg=CODE_BG,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#17345f",
            selectforeground=TEXT,
            borderwidth=0,
            font=UI_FONT,
            padx=12,
            pady=10,
            relief="flat",
            wrap="word",
            undo=True,
        )
        self.error_text.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(shell, orient="vertical", command=self.error_text.yview, style="Dark.Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.error_text.configure(yscrollcommand=scroll.set)

        footer = tk.Frame(self.window, bg=HEADER_BG, padx=18, pady=12)
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=HEADER_BG,
            fg=MUTED,
            font=SMALL_FONT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        make_button(footer, "Cancel", self._cancel, variant="secondary").grid(row=0, column=1, padx=(12, 0))
        make_button(footer, "Copy Prompt", self._copy_prompt, variant="primary").grid(row=0, column=2, padx=(8, 0))

    def _copy_prompt(self) -> None:
        error = ""
        if self.error_text is not None:
            error = self.error_text.get("1.0", "end-1c")
        self.parent.clipboard_clear()
        self.parent.clipboard_append(build_fix_prompt(self.tool.name, self.tool.code, error))
        self.parent.update()
        self.copied = True
        self.status_var.set("Fix prompt copied. Paste it into ChatGPT/Gemini.")

    def show(self) -> bool:
        self.parent.wait_window(self.window)
        return self.copied

    def _cancel(self) -> None:
        self.window.destroy()
