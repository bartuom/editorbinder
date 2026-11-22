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


if __name__ == "__main__":
    unittest.main()
