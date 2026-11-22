from __future__ import annotations

import tkinter as tk
import unittest

from unreal_utility_tool.ui.editor_dialog import ToolEditorDialog
from unreal_utility_tool.ui.restore_dialog import RestoreBackupDialog


class DialogCallbackLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk display is unavailable: {exc}")

    def tearDown(self) -> None:
        try:
            self.root.destroy()
        except (AttributeError, tk.TclError):
            pass

    def test_tool_editor_close_cancels_delayed_raise_callback(self) -> None:
        dialog = ToolEditorDialog(self.root)
        pending_id = dialog._raise_after_id
        self.assertTrue(pending_id)

        dialog._cancel()

        self.assertTrue(dialog._dialog_closed)
        self.assertEqual(dialog._raise_after_id, "")
        self.root.update()

    def test_tool_editor_ignores_ai_completion_after_close(self) -> None:
        dialog = ToolEditorDialog(self.root)
        dialog._cancel()

        dialog._finish_ai_generation(None, "late response")

        self.assertTrue(dialog._dialog_closed)
        self.root.update()

    def test_restore_dialog_close_cancels_delayed_raise_callback(self) -> None:
        dialog = RestoreBackupDialog(self.root, [])
        pending_id = dialog._raise_after_id
        self.assertTrue(pending_id)

        dialog._cancel()

        self.assertTrue(dialog._dialog_closed)
        self.assertEqual(dialog._raise_after_id, "")
        self.root.update()

    def test_tool_editor_on_cancel_cancels_all_active_timers_and_clears_set(self) -> None:
        dialog = ToolEditorDialog(self.root)
        custom_id = dialog.after(10000, lambda: None)
        self.assertTrue(dialog.active_timer_ids)
        self.assertIn(custom_id, dialog.active_timer_ids)
        self.assertIn(dialog._raise_after_id, dialog.active_timer_ids)

        cancelled: list[str] = []
        original_after_cancel = dialog.window.after_cancel

        def record_cancel(timer_id: str) -> None:
            cancelled.append(timer_id)
            original_after_cancel(timer_id)

        dialog.window.after_cancel = record_cancel

        dialog._on_cancel()

        self.assertTrue(dialog._dialog_closed)
        self.assertEqual(len(dialog.active_timer_ids), 0)
        self.assertEqual(dialog._raise_after_id, "")
        self.assertIn(custom_id, cancelled)

    def test_tool_editor_destroy_safely_cancels_timers_and_handles_destroyed_window(self) -> None:
        dialog = ToolEditorDialog(self.root)
        custom_id = dialog.after(10000, lambda: None)
        self.assertIn(custom_id, dialog.active_timer_ids)

        dialog.window.destroy()
        self.root.update()

        self.assertTrue(dialog._dialog_closed)
        self.assertEqual(len(dialog.active_timer_ids), 0)

        # Calling _on_cancel, _close_dialog, or _on_window_destroy on destroyed dialog should not raise
        dialog._on_cancel()
        dialog._close_dialog()
        dialog._on_window_destroy(None)
        dialog._finish_ai_generation(None, "error after destroy")


if __name__ == "__main__":
    unittest.main()
