from __future__ import annotations

from .storage import ToolLibraryStore, ensure_default_storage_seeded
from .ui.windowing import configure_windows_window


def main() -> int:
    try:
        import tkinter as tk
    except ImportError as exc:
        print("tkinter is required to run the GUI. Install a standard Python build that includes Tcl/Tk.")
        print(exc)
        return 1

    from .ui.main_window import UnrealUtilityApp

    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EditorBinder.Desktop")
    except Exception:
        pass

    storage_path = ensure_default_storage_seeded()
    store = ToolLibraryStore(storage_path)
    root = tk.Tk()
    UnrealUtilityApp(root, store)
    configure_windows_window(root)
    root.mainloop()
    return 0
