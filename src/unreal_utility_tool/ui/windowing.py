from __future__ import annotations

import os
import re
import sys
import tkinter as tk
from pathlib import Path

from ..theme import ACCENT, BG, SUCCESS


def resolve_app_icon_path() -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
        candidates.append(root / "assets" / "editorbinder.ico")
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(Path(meipass) / "assets" / "editorbinder.ico")
    else:
        from ..storage import project_root

        root = project_root()
        candidates.append(root / "assets" / "editorbinder.ico")

    for path in candidates:
        if path.exists():
            return path
    return None


def set_app_icon(root: tk.Tk) -> tk.PhotoImage | str | None:
    icon_path = resolve_app_icon_path()
    if icon_path is not None and os.name == "nt":
        try:
            root.iconbitmap(default=str(icon_path))
            return str(icon_path)
        except tk.TclError:
            pass
    return set_generated_app_icon(root)


def set_generated_app_icon(root: tk.Tk) -> tk.PhotoImage | None:
    try:
        icon = tk.PhotoImage(width=32, height=32)
        icon.put(BG, to=(0, 0, 32, 32))
        icon.put(ACCENT, to=(3, 3, 29, 29))
        icon.put(BG, to=(5, 5, 27, 27))
        icon.put(SUCCESS, to=(8, 8, 12, 24))
        icon.put(SUCCESS, to=(12, 20, 22, 24))
        icon.put(ACCENT, to=(22, 8, 25, 24))
        root.iconphoto(True, icon)
        return icon
    except tk.TclError:
        return None


def is_valid_geometry(geometry: str) -> bool:
    return bool(re.match(r"^\d+x\d+[+-]\d+[+-]\d+$", geometry.strip()))


def set_initial_window_size(root: tk.Tk) -> None:
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    width = min(max(int(screen_width * 0.22), 420), max(screen_width - 80, 380), 500)
    height = min(max(int(screen_height * 0.45), 460), max(screen_height - 80, 320), 560)
    x = max((screen_width - width) // 2, 0)
    y = max((screen_height - height) // 2, 0)
    root.geometry(f"{width}x{height}+{x}+{y}")


def configure_windows_window(root: tk.Tk) -> None:
    try:
        import ctypes

        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()

        true_value = ctypes.c_int(1)
        for attribute in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(true_value),
                ctypes.sizeof(true_value),
            )

        caption_color = ctypes.c_int(0x001A130F)
        text_color = ctypes.c_int(0x00F3EDE6)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            35,
            ctypes.byref(caption_color),
            ctypes.sizeof(caption_color),
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            36,
            ctypes.byref(text_color),
            ctypes.sizeof(text_color),
        )
    except Exception:
        pass


def _compute_dialog_geometry(
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    work_area: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int]:
    min_width = 820
    min_height = 620
    margin = 16

    width = min(max(parent_width + 360, 840), 980)
    height = min(max(parent_height + 220, 640), 820)

    if work_area is not None:
        left, top, right, bottom = work_area
        work_width = max(right - left, 1)
        work_height = max(bottom - top, 1)
        max_width = max(work_width - (margin * 2), min_width)
        max_height = max(work_height - (margin * 2), min_height)
        width = min(width, max_width)
        height = min(height, max_height)

    x = parent_x + ((parent_width - width) // 2)
    y = parent_y + ((parent_height - height) // 2)

    if work_area is None:
        return width, height, x, y

    left, top, right, bottom = work_area
    x = _clamp_window_axis(x, width, left, right, margin)
    y = _clamp_window_axis(y, height, top, bottom, margin)
    return width, height, x, y


def _clamp_window_axis(position: int, size: int, start: int, end: int, margin: int) -> int:
    min_position = start + margin
    max_position = end - size - margin
    if max_position < min_position:
        return min_position
    return min(max(position, min_position), max_position)


def _monitor_work_area_for_widget(widget: tk.Misc) -> tuple[int, int, int, int] | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        widget.update_idletasks()
        hwnd = int(widget.winfo_id())
        parent_hwnd = ctypes.windll.user32.GetParent(wintypes.HWND(hwnd))
        if parent_hwnd:
            hwnd = int(parent_hwnd)

        monitor = ctypes.windll.user32.MonitorFromWindow(wintypes.HWND(hwnd), 2)
        if not monitor:
            return None

        class Rect(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("rcMonitor", Rect),
                ("rcWork", Rect),
                ("dwFlags", ctypes.c_ulong),
            ]

        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        if not ctypes.windll.user32.GetMonitorInfoW(wintypes.HMONITOR(monitor), ctypes.byref(info)):
            return None

        return (
            int(info.rcWork.left),
            int(info.rcWork.top),
            int(info.rcWork.right),
            int(info.rcWork.bottom),
        )
    except Exception:
        return None


def _fallback_work_area_for_widget(widget: tk.Misc) -> tuple[int, int, int, int] | None:
    try:
        return (0, 0, int(widget.winfo_screenwidth()), int(widget.winfo_screenheight()))
    except tk.TclError:
        return None
