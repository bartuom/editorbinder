from __future__ import annotations

from .settings import AppSettingsStore, resolve_default_settings_path
from .storage import (
    ToolLibraryStore,
    ensure_default_storage_seeded,
    resolve_default_storage_path,
)
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

    storage_path = resolve_default_storage_path()
    store = ToolLibraryStore(storage_path)
    settings_store = AppSettingsStore(resolve_default_settings_path())
    settings = settings_store.load()
    ensure_default_storage_seeded(
        storage_path,
        store=store,
        ignored_ids=set(settings.deleted_preset_ids or []),
    )
    root = tk.Tk()
    UnrealUtilityApp(root, store, settings_store=settings_store)
    configure_windows_window(root)
    root.mainloop()
    return 0
