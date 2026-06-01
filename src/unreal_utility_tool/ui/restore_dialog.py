from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..storage import BackupInfo
from ..theme import BG, CODE_BG, HEADER_BG, MUTED, PANEL, SMALL_FONT, SUBTLE, TEXT, TITLE_FONT, UI_FONT, make_button
from .windowing import _compute_dialog_geometry, _fallback_work_area_for_widget, _monitor_work_area_for_widget


class RestoreBackupDialog:
    def __init__(self, parent: tk.Tk, backups: list[BackupInfo]) -> None:
        self.parent = parent
        self.backups = backups
        self.result: BackupInfo | None = None

        self.window = tk.Toplevel(parent)
        self.window.title("Restore Backup")
        self.window.minsize(520, 360)
        self._set_initial_dialog_geometry()
        self.window.configure(bg=BG)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)

        self.status_var = tk.StringVar(value="Select a backup to restore.")
        self.restore_button: tk.Button | None = None
        self.listbox: tk.Listbox | None = None

        self._build_ui()
        self._refresh_restore_button()
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
        self.window.geometry(f"{min(width, 620)}x{min(height, 520)}+{x}+{y}")

    def _raise_near_parent(self) -> None:
        self.window.update_idletasks()
        self.window.lift(self.parent)
        self.window.focus_force()
        self.window.after(50, lambda: self.window.lift(self.parent))

    def _build_ui(self) -> None:
        header = tk.Frame(self.window, bg=HEADER_BG, padx=18, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        tk.Label(header, text="Restore Backup", bg=HEADER_BG, fg=TEXT, font=TITLE_FONT).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="Current library will be backed up before restore.",
            bg=HEADER_BG,
            fg=MUTED,
            font=SMALL_FONT,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        body = tk.Frame(self.window, bg=BG, padx=18)
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        list_shell = tk.Frame(body, bg=PANEL, padx=1, pady=1)
        list_shell.grid(row=0, column=0, sticky="nsew")
        list_shell.rowconfigure(0, weight=1)
        list_shell.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_shell,
            bg=CODE_BG,
            fg=TEXT,
            selectbackground="#17345f",
            selectforeground=TEXT,
            activestyle="none",
            relief="flat",
            borderwidth=0,
            font=UI_FONT,
            height=10,
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", lambda _event: self._refresh_restore_button())
        self.listbox.bind("<Double-Button-1>", lambda _event: self._restore())

        scroll = ttk.Scrollbar(list_shell, orient="vertical", command=self.listbox.yview, style="Dark.Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scroll.set)

        for backup in self.backups:
            marker = "!" if backup.error else " "
            count = "unreadable" if backup.error else f"{backup.tool_count} tools"
            self.listbox.insert(tk.END, f"{marker} {backup.modified_at} | {count} | {backup.filename}")

        if self.backups:
            self.listbox.selection_set(0)

        footer = tk.Frame(self.window, bg=HEADER_BG, padx=18, pady=12)
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=HEADER_BG,
            fg=SUBTLE,
            font=SMALL_FONT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        make_button(footer, "Cancel", self._cancel, variant="secondary").grid(row=0, column=1, padx=(12, 0))
        self.restore_button = make_button(footer, "Restore", self._restore, variant="primary")
        self.restore_button.grid(row=0, column=2, padx=(8, 0))

    def _selected_backup(self) -> BackupInfo | None:
        if self.listbox is None:
            return None
        selection = self.listbox.curselection()
        if not selection:
            return None
        index = int(selection[0])
        if index < 0 or index >= len(self.backups):
            return None
        return self.backups[index]

    def _refresh_restore_button(self) -> None:
        backup = self._selected_backup()
        can_restore = backup is not None and not backup.error
        if self.restore_button is not None:
            self.restore_button.configure(state=tk.NORMAL if can_restore else tk.DISABLED)
        if backup is None:
            self.status_var.set("Select a backup to restore.")
        elif backup.error:
            self.status_var.set(f"Cannot restore this backup: {backup.error}")
        else:
            self.status_var.set(f"Ready to restore {backup.tool_count} tool(s) from {backup.filename}.")

    def _restore(self) -> None:
        backup = self._selected_backup()
        if backup is None or backup.error:
            self._refresh_restore_button()
            return
        self.result = backup
        self.window.destroy()

    def show(self) -> BackupInfo | None:
        self.parent.wait_window(self.window)
        return self.result

    def _cancel(self) -> None:
        self.window.destroy()
