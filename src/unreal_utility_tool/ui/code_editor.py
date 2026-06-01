from __future__ import annotations

import re
import tkinter as tk


PYTHON_KEYWORDS = {
    "and",
    "as",
    "assert",
    "break",
    "class",
    "continue",
    "def",
    "elif",
    "else",
    "except",
    "False",
    "finally",
    "for",
    "from",
    "if",
    "import",
    "in",
    "is",
    "None",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "True",
    "try",
    "while",
    "with",
}

BUILTINS = {"unreal", "print", "len", "list", "dict", "set", "str", "int", "float", "enumerate"}


def configure_code_tags(widget: tk.Text) -> None:
    widget.tag_configure("keyword", foreground="#82aaff")
    widget.tag_configure("string", foreground="#c3e88d")
    widget.tag_configure("comment", foreground="#637777")
    widget.tag_configure("builtin", foreground="#ffcb6b")


def apply_python_highlighting(widget: tk.Text) -> None:
    code = widget.get("1.0", "end-1c")
    for tag in ["keyword", "string", "comment", "builtin"]:
        widget.tag_remove(tag, "1.0", tk.END)

    for match in re.finditer(r"#[^\n]*", code):
        _tag_range(widget, "comment", match.start(), match.end())

    for match in re.finditer(r'"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\'', code):
        _tag_range(widget, "string", match.start(), match.end())

    for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", code):
        word = match.group(0)
        if word in PYTHON_KEYWORDS:
            _tag_range(widget, "keyword", match.start(), match.end())
        elif word in BUILTINS:
            _tag_range(widget, "builtin", match.start(), match.end())


def _tag_range(widget: tk.Text, tag: str, start: int, end: int) -> None:
    widget.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")
