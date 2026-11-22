from __future__ import annotations

import math
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
    return bool(re.match(r"^\d+x\d+[+-][+-]?\d+[+-][+-]?\d+$", geometry.strip()))


DEFAULT_MIN_WINDOW_WIDTH = 380
DEFAULT_MIN_WINDOW_HEIGHT = 320


def clamp_geometry_to_screen(
    geometry: str,
    screen_width: int,
    screen_height: int,
    min_visible: int = 40,
    *,
    min_width: int = DEFAULT_MIN_WINDOW_WIDTH,
    min_height: int = DEFAULT_MIN_WINDOW_HEIGHT,
) -> str | None:
    try:
        if not (math.isfinite(screen_width) and math.isfinite(screen_height)):
            return None
        screen_width = int(screen_width)
        screen_height = int(screen_height)
    except (TypeError, ValueError, OverflowError):
        return None

    if screen_width <= 0 or screen_height <= 0:
        return None
    if not isinstance(geometry, str):
        return None

    try:
        min_visible = int(min_visible) if math.isfinite(min_visible) else 40
        min_width = int(min_width) if math.isfinite(min_width) else DEFAULT_MIN_WINDOW_WIDTH
        min_height = int(min_height) if math.isfinite(min_height) else DEFAULT_MIN_WINDOW_HEIGHT
    except (TypeError, ValueError, OverflowError):
        min_visible = 40
        min_width = DEFAULT_MIN_WINDOW_WIDTH
        min_height = DEFAULT_MIN_WINDOW_HEIGHT

    if min_visible <= 0:
        min_visible = 40
    if min_width <= 0:
        min_width = DEFAULT_MIN_WINDOW_WIDTH
    if min_height <= 0:
        min_height = DEFAULT_MIN_WINDOW_HEIGHT

    match = re.match(r"^(\d+)x(\d+)([+-][+-]?\d+)([+-][+-]?\d+)$", geometry.strip())
    if not match:
        return None

    try:
        width = int(match.group(1))
        height = int(match.group(2))
        x_str = match.group(3).replace("+", "")
        y_str = match.group(4).replace("+", "")
        x = int(x_str) if x_str else 0
        y = int(y_str) if y_str else 0
    except (ValueError, TypeError):
        return None

    if width <= 0 or height <= 0:
        return None

    effective_min_width = max(min_width, min_visible)
    effective_min_height = max(min_height, min_visible)

    if width < effective_min_width or height < effective_min_height:
        return None
    if screen_width < effective_min_width or screen_height < effective_min_height:
        return None

    width = min(width, screen_width)
    height = min(height, screen_height)

    max_x = max(0, screen_width - width)
    max_y = max(0, screen_height - height)

    clamped_x = max(0, min(x, max_x))
    clamped_y = max(0, min(y, max_y))

    return f"{width}x{height}+{clamped_x}+{clamped_y}"


def clamp_geometry_to_work_area(
    geometry: str,
    work_area: tuple[int, int, int, int],
    *,
    min_width: int = DEFAULT_MIN_WINDOW_WIDTH,
    min_height: int = DEFAULT_MIN_WINDOW_HEIGHT,
) -> str | None:
    if not isinstance(geometry, str) or not isinstance(work_area, (tuple, list)) or len(work_area) != 4:
        return None

    try:
        min_width = int(min_width) if math.isfinite(min_width) else DEFAULT_MIN_WINDOW_WIDTH
        min_height = int(min_height) if math.isfinite(min_height) else DEFAULT_MIN_WINDOW_HEIGHT
    except (TypeError, ValueError, OverflowError):
        min_width = DEFAULT_MIN_WINDOW_WIDTH
        min_height = DEFAULT_MIN_WINDOW_HEIGHT

    if min_width <= 0:
        min_width = DEFAULT_MIN_WINDOW_WIDTH
    if min_height <= 0:
        min_height = DEFAULT_MIN_WINDOW_HEIGHT

    match = re.match(r"^(\d+)x(\d+)([+-][+-]?\d+)([+-][+-]?\d+)$", geometry.strip())
    if not match:
        return None

    try:
        width = int(match.group(1))
        height = int(match.group(2))
        x = int(match.group(3).replace("+", ""))
        y = int(match.group(4).replace("+", ""))
        coords = [float(value) for value in work_area]
        if not all(math.isfinite(c) for c in coords):
            return None
        left, top, right, bottom = (int(c) for c in coords)
    except (TypeError, ValueError, OverflowError):
        return None

    if width <= 0 or height <= 0:
        return None

    work_width = right - left
    work_height = bottom - top
    if work_width <= 0 or work_height <= 0:
        return None
    if width < min_width or height < min_height:
        return None
    if work_width < min_width or work_height < min_height:
        return None

    width = min(width, work_width)
    height = min(height, work_height)
    clamped_x = max(left, min(x, right - width))
    clamped_y = max(top, min(y, bottom - height))
    return f"{width}x{height}{clamped_x:+d}{clamped_y:+d}"


def set_initial_window_size(root: tk.Tk) -> None:
    try:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
    except tk.TclError:
        screen_width = 1920
        screen_height = 1080
    try:
        if not (math.isfinite(screen_width) and math.isfinite(screen_height)):
            screen_width, screen_height = 1920, 1080
        else:
            screen_width, screen_height = int(screen_width), int(screen_height)
    except (TypeError, ValueError, OverflowError):
        screen_width, screen_height = 1920, 1080

    if screen_width <= 0:
        screen_width = 1920
    if screen_height <= 0:
        screen_height = 1080

    width = min(max(int(screen_width * 0.22), 420), max(screen_width - 80, 380), 500)
    height = min(max(int(screen_height * 0.45), 460), max(screen_height - 80, 320), 560)
    x = max((screen_width - width) // 2, 0)
    y = max((screen_height - height) // 2, 0)
    root.geometry(f"{width}x{height}+{x}+{y}")


def configure_windows_window(root: tk.Tk | tk.Toplevel) -> None:
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

    try:
        parent_x = int(parent_x) if math.isfinite(parent_x) else 0
    except (TypeError, ValueError, OverflowError):
        parent_x = 0
    try:
        parent_y = int(parent_y) if math.isfinite(parent_y) else 0
    except (TypeError, ValueError, OverflowError):
        parent_y = 0
    try:
        parent_width = int(parent_width) if math.isfinite(parent_width) else DEFAULT_MIN_WINDOW_WIDTH
        if parent_width <= 0:
            parent_width = DEFAULT_MIN_WINDOW_WIDTH
    except (TypeError, ValueError, OverflowError):
        parent_width = DEFAULT_MIN_WINDOW_WIDTH
    try:
        parent_height = int(parent_height) if math.isfinite(parent_height) else DEFAULT_MIN_WINDOW_HEIGHT
        if parent_height <= 0:
            parent_height = DEFAULT_MIN_WINDOW_HEIGHT
    except (TypeError, ValueError, OverflowError):
        parent_height = DEFAULT_MIN_WINDOW_HEIGHT

    valid_work_area: tuple[int, int, int, int] | None = None
    if work_area is not None:
        try:
            if isinstance(work_area, (tuple, list)) and len(work_area) == 4:
                coords = [float(v) for v in work_area]
                if all(math.isfinite(c) for c in coords):
                    l, t, r, b = (int(c) for c in coords)
                    if r > l and b > t:
                        valid_work_area = (l, t, r, b)
        except (TypeError, ValueError, OverflowError):
            valid_work_area = None

    width = min(max(parent_width + 360, 840), 980)
    height = min(max(parent_height + 220, 640), 820)

    if valid_work_area is not None:
        left, top, right, bottom = valid_work_area
        work_width = max(right - left, 1)
        work_height = max(bottom - top, 1)
        max_width = max(work_width - (margin * 2), min_width)
        max_height = max(work_height - (margin * 2), min_height)
        width = min(width, max_width)
        height = min(height, max_height)

    x = parent_x + ((parent_width - width) // 2)
    y = parent_y + ((parent_height - height) // 2)

    if valid_work_area is None:
        return width, height, x, y

    left, top, right, bottom = valid_work_area
    x = _clamp_window_axis(x, width, left, right, margin)
    y = _clamp_window_axis(y, height, top, bottom, margin)
    return width, height, x, y


def _clamp_window_axis(position: int, size: int, start: int, end: int, margin: int) -> int:
    try:
        if not (math.isfinite(position) and math.isfinite(size) and math.isfinite(start) and math.isfinite(end) and math.isfinite(margin)):
            return 0
        position = int(position)
        size = max(0, int(size))
        start = int(start)
        end = int(end)
        margin = max(0, int(margin))
    except (TypeError, ValueError, OverflowError):
        return 0

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

        left = int(info.rcWork.left)
        top = int(info.rcWork.top)
        right = int(info.rcWork.right)
        bottom = int(info.rcWork.bottom)
        if right <= left or bottom <= top:
            return None
        return (left, top, right, bottom)
    except Exception:
        return None


def _fallback_work_area_for_widget(widget: tk.Misc) -> tuple[int, int, int, int] | None:
    try:
        sw = widget.winfo_screenwidth()
        sh = widget.winfo_screenheight()
        if not (math.isfinite(sw) and math.isfinite(sh)) or sw <= 0 or sh <= 0:
            return None
        return (0, 0, int(sw), int(sh))
    except (tk.TclError, TypeError, ValueError):
        return None
