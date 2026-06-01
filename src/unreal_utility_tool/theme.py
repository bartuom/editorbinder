from __future__ import annotations

import tkinter as tk
from tkinter import ttk

APP_BG = "#101317"
DOCK_BG = "#12161b"
PANEL_BG = "#181d23"
PANEL_BG_ALT = "#20262d"
HEADER_BG = "#252c34"
INPUT_BG = "#11161c"
BORDER = "#333c46"
BORDER_DARK = "#252c33"
ROW_BG = "#151a20"
ROW_BG_ALT = "#181e25"
ROW_HOVER = "#242c35"
SELECTION_BLUE = "#2f86c8"
TEXT = "#dce3ea"
MUTED = "#a1abb6"
SUBTLE = "#788390"
ACCENT = SELECTION_BLUE
ACCENT_HOVER = "#3f94d4"
ACCENT_DARK = "#205d8e"
DANGER = "#9a5a55"
DANGER_HOVER = "#aa6963"
SUCCESS = "#75ad4b"
SUCCESS_HOVER = "#84bd59"
WARNING = "#b69a4a"
X_AXIS = "#a95e52"
Y_AXIS = "#6e9d59"
Z_AXIS = "#547fb6"

# Backwards-compatible aliases used throughout the existing tkinter UI.
BG = APP_BG
PANEL = PANEL_BG
PANEL_ALT = PANEL_BG_ALT
CODE_BG = INPUT_BG

UI_FONT = ("Segoe UI", 8)
UI_FONT_BOLD = ("Segoe UI", 8, "bold")
TITLE_FONT = ("Segoe UI", 9, "bold")
PANEL_TITLE_FONT = ("Segoe UI", 8, "bold")
CARD_TITLE_FONT = ("Segoe UI", 8, "bold")
SMALL_FONT = ("Segoe UI", 8)
CODE_FONT = ("Consolas", 10)
ICON_FONT = ("Segoe UI Symbol", 9)


def configure_ttk_style() -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    root = style.master
    root.option_add("*TCombobox*Listbox.background", CODE_BG)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_DARK)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=PANEL_BG_ALT,
        troughcolor=DOCK_BG,
        bordercolor=BORDER,
        arrowcolor=MUTED,
        darkcolor=PANEL_BG_ALT,
        lightcolor=PANEL_BG_ALT,
        relief="flat",
        borderwidth=0,
        arrowsize=11,
        width=10,
    )
    style.map(
        "Dark.Vertical.TScrollbar",
        background=[("active", HEADER_BG), ("pressed", ACCENT_DARK)],
        arrowcolor=[("active", TEXT), ("pressed", TEXT)],
    )
    style.configure(
        "Dark.Horizontal.TScrollbar",
        background=PANEL_BG_ALT,
        troughcolor=INPUT_BG,
        bordercolor=BORDER,
        arrowcolor=MUTED,
        darkcolor=PANEL_BG_ALT,
        lightcolor=PANEL_BG_ALT,
        relief="flat",
        borderwidth=0,
        arrowsize=11,
        width=10,
    )
    style.map(
        "Dark.Horizontal.TScrollbar",
        background=[("active", HEADER_BG), ("pressed", ACCENT_DARK)],
        arrowcolor=[("active", TEXT), ("pressed", TEXT)],
    )
    style.configure(
        "Dark.TCombobox",
        fieldbackground=CODE_BG,
        background=PANEL_BG_ALT,
        foreground=TEXT,
        arrowcolor=MUTED,
        bordercolor=BORDER,
        darkcolor=BORDER,
        lightcolor=BORDER,
        selectbackground=ACCENT_DARK,
        selectforeground=TEXT,
        relief="flat",
        borderwidth=1,
        padding=(4, 1, 3, 1),
    )
    style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", CODE_BG), ("active", CODE_BG)],
        background=[("readonly", PANEL_BG_ALT), ("active", HEADER_BG)],
        foreground=[("readonly", TEXT), ("disabled", SUBTLE)],
        arrowcolor=[("active", TEXT), ("disabled", SUBTLE)],
    )


def make_button(
    parent: tk.Widget,
    text: str,
    command,
    variant: str = "secondary",
    padx: int = 13,
    pady: int = 8,
    font=None,
) -> tk.Button:
    colors = {
        "primary": (ACCENT_DARK, ACCENT, TEXT, ACCENT),
        "success": (SUCCESS, SUCCESS_HOVER, "#101510", SUCCESS_HOVER),
        "secondary": (PANEL_BG_ALT, "#2a333d", TEXT, BORDER),
        "danger": (DANGER, DANGER_HOVER, TEXT, DANGER_HOVER),
    }
    bg, active_bg, fg, border = colors[variant]
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=active_bg,
        activeforeground=fg,
        disabledforeground=SUBTLE,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=border,
        highlightcolor=border,
        padx=padx,
        pady=pady,
        font=font or (UI_FONT_BOLD if variant in {"primary", "success"} else UI_FONT),
        cursor="hand2",
    )


def make_icon_button(parent: tk.Widget, text: str, command, variant: str = "secondary") -> tk.Button:
    colors = {
        "secondary": (PANEL_BG_ALT, "#2a333d", TEXT),
        "primary": (PANEL_BG_ALT, "#2a333d", TEXT),
        "success": (PANEL_BG_ALT, "#2a333d", SUCCESS),
        "danger": (PANEL_BG_ALT, "#3b2d30", "#f0a29f"),
    }
    bg, active_bg, fg = colors[variant]
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=active_bg,
        activeforeground=fg,
        disabledforeground=SUBTLE,
        relief="flat",
        bd=0,
        width=2,
        padx=3,
        pady=3,
        font=ICON_FONT,
        cursor="hand2",
    )


def make_step_button(parent: tk.Widget, text: str, command) -> tk.Button:
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=HEADER_BG,
        fg=TEXT,
        activebackground="#2a333d",
        activeforeground=TEXT,
        relief="flat",
        bd=0,
        width=2,
        padx=4,
        pady=3,
        font=UI_FONT_BOLD,
        cursor="hand2",
    )


def make_toolbar_button(parent: tk.Widget, text: str, command, variant: str = "secondary") -> tk.Button:
    return make_button(parent, text, command, variant=variant, padx=10, pady=5, font=UI_FONT)


def make_dark_entry(parent: tk.Widget, variable: tk.Variable | None = None, width: int = 18) -> tk.Entry:
    return tk.Entry(
        parent,
        textvariable=variable,
        bg=INPUT_BG,
        fg=TEXT,
        insertbackground=TEXT,
        selectbackground=ACCENT_DARK,
        selectforeground=TEXT,
        relief="flat",
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
        font=UI_FONT,
        width=width,
    )


def make_panel_header(parent: tk.Widget, text: str) -> tk.Frame:
    header = tk.Frame(parent, bg=HEADER_BG, padx=7, pady=3)
    tk.Label(header, text=text, bg=HEADER_BG, fg=TEXT, font=PANEL_TITLE_FONT, anchor="w").grid(
        row=0,
        column=0,
        sticky="ew",
    )
    header.columnconfigure(0, weight=1)
    return header


def make_property_row(parent: tk.Widget) -> tk.Frame:
    row = tk.Frame(parent, bg=PANEL_BG, padx=6, pady=2)
    row.columnconfigure(1, weight=1)
    return row


def make_dark_listbox(parent: tk.Widget) -> tk.Listbox:
    return tk.Listbox(
        parent,
        bg=INPUT_BG,
        fg=TEXT,
        selectbackground=ACCENT_DARK,
        selectforeground=TEXT,
        activestyle="none",
        relief="flat",
        borderwidth=0,
        font=UI_FONT,
    )


def make_dark_text(parent: tk.Widget, font=None, wrap: str = "word") -> tk.Text:
    return tk.Text(
        parent,
        bg=INPUT_BG,
        fg=TEXT,
        insertbackground=TEXT,
        selectbackground=ACCENT_DARK,
        selectforeground=TEXT,
        borderwidth=0,
        font=font or UI_FONT,
        padx=10,
        pady=8,
        relief="flat",
        wrap=wrap,
        undo=True,
    )


def make_static_icon(
    parent: tk.Widget,
    icon: str,
    *,
    size: int = 16,
    bg: str | None = None,
    fg: str = MUTED,
) -> tk.Canvas:
    canvas = tk.Canvas(
        parent,
        width=size,
        height=size,
        bg=bg or PANEL_BG_ALT,
        highlightthickness=0,
        bd=0,
    )
    _draw_icon(canvas, icon, size=size, fg=fg)
    return canvas


def make_tab(parent: tk.Widget, text: str, active: bool = True, close: bool = False, icon: str | None = None) -> tk.Frame:
    bg = PANEL_BG_ALT if active else APP_BG
    fg = TEXT if active else MUTED
    tab = tk.Frame(parent, bg=bg, padx=8, pady=4, highlightthickness=1, highlightbackground=BORDER_DARK)
    label_column = 0
    if icon:
        make_static_icon(tab, icon, size=15, bg=bg, fg=fg).grid(row=0, column=0, sticky="w", padx=(0, 5))
        label_column = 1
    tk.Label(tab, text=text, bg=bg, fg=fg, font=TITLE_FONT, anchor="w").grid(row=0, column=label_column, sticky="w")
    if close:
        tk.Label(tab, text="x", bg=bg, fg=MUTED, font=SMALL_FONT, anchor="e").grid(row=0, column=label_column + 1, padx=(12, 0))
    return tab


def make_search_shell(parent: tk.Widget) -> tk.Frame:
    shell = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
    shell.columnconfigure(1, weight=1)
    make_static_icon(shell, "search", size=15, bg=INPUT_BG, fg=MUTED).grid(
        row=0,
        column=0,
        sticky="ns",
        padx=(5, 0),
    )
    return shell


def make_table_header(parent: tk.Widget, labels: list[str]) -> tk.Frame:
    header = tk.Frame(parent, bg=HEADER_BG, highlightthickness=1, highlightbackground=BORDER_DARK)
    for column, label in enumerate(labels):
        header.columnconfigure(column, weight=1 if column == 0 else 0)
        tk.Label(
            header,
            text=label,
            bg=HEADER_BG,
            fg=TEXT,
            font=UI_FONT,
            anchor="w",
            padx=5,
            pady=4,
        ).grid(row=0, column=column, sticky="ew")
    return header


def make_reset_button(parent: tk.Widget, command) -> tk.Button:
    return tk.Button(
        parent,
        text="<",
        command=command,
        bg=PANEL_BG_ALT,
        fg=MUTED,
        activebackground=ROW_HOVER,
        activeforeground=TEXT,
        relief="flat",
        bd=0,
        padx=4,
        pady=1,
        font=UI_FONT_BOLD,
        cursor="hand2",
    )


def _draw_icon(canvas: tk.Canvas, icon: str, *, size: int, fg: str) -> None:
    pad = max(2, size // 6)
    mid = size / 2
    if icon == "search":
        r = size * 0.28
        cx = size * 0.43
        cy = size * 0.42
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=fg, width=2)
        canvas.create_line(cx + r * 0.7, cy + r * 0.7, size - pad, size - pad, fill=fg, width=2)
        return
    if icon == "outliner":
        for index, y in enumerate((pad + 2, mid, size - pad - 2)):
            canvas.create_rectangle(pad, y - 2, pad + 4, y + 2, outline=fg, fill=fg)
            canvas.create_line(pad + 7, y, size - pad, y, fill=fg, width=2 if index == 0 else 1)
        return
    if icon == "details":
        canvas.create_rectangle(pad, pad, size - pad, size - pad, outline=fg, width=1)
        for y in (pad + 4, mid, size - pad - 4):
            canvas.create_line(pad + 4, y, size - pad - 3, y, fill=fg, width=1)
        return
    if icon == "tool":
        canvas.create_rectangle(pad, pad + 2, size - pad, size - pad - 2, outline=fg, width=1)
        canvas.create_line(pad + 3, mid, size - pad - 3, mid, fill=fg, width=1)
        canvas.create_line(mid, pad + 5, mid, size - pad - 5, fill=fg, width=1)
        return
    canvas.create_rectangle(pad, pad, size - pad, size - pad, outline=fg, width=1)
