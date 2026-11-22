from __future__ import annotations

import importlib.util
import unittest

from unreal_utility_tool.ui.code_editor import (
    BUILTINS,
    PYTHON_KEYWORDS,
    apply_python_highlighting,
    configure_code_tags,
)


@unittest.skipIf(importlib.util.find_spec("tkinter") is None, "tkinter is not installed")
class CodeEditorHighlightingTests(unittest.TestCase):
    def setUp(self) -> None:
        import tkinter as tk

        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"tkinter root window is unavailable on this runner: {exc}")
        self.root.withdraw()
        self.text = tk.Text(self.root)
        configure_code_tags(self.text)

    def tearDown(self) -> None:
        if hasattr(self, "root"):
            try:
                self.root.destroy()
            except Exception:
                pass

    def _effective_tag(self, index: str) -> str | None:
        """Return the highest-priority syntax tag applied at a given text index.

        In Tkinter, widget.tag_names(index) returns tags ordered from lowest to
        highest priority. The last syntax tag is the one determining visible highlighting.
        """
        tags = [t for t in self.text.tag_names(index) if t in {"keyword", "string", "comment", "builtin"}]
        return tags[-1] if tags else None

    def _index_of(self, substring: str) -> str:
        content = self.text.get("1.0", "end-1c")
        pos = content.index(substring)
        return f"1.0+{pos}c"

    def test_tag_priority_hierarchy(self) -> None:
        tags = list(self.text.tag_names())
        self.assertGreater(tags.index("string"), tags.index("keyword"))
        self.assertGreater(tags.index("string"), tags.index("builtin"))
        self.assertGreater(tags.index("comment"), tags.index("keyword"))
        self.assertGreater(tags.index("comment"), tags.index("builtin"))

    def test_keywords_inside_comments_highlighted_as_comment(self) -> None:
        self.text.insert("1.0", "# import unreal\n# def test(): pass\n")
        apply_python_highlighting(self.text)

        import_idx = self._index_of("import")
        self.assertIn("comment", self.text.tag_names(import_idx))
        self.assertEqual(self._effective_tag(import_idx), "comment")

        unreal_idx = self._index_of("unreal")
        self.assertIn("comment", self.text.tag_names(unreal_idx))
        self.assertEqual(self._effective_tag(unreal_idx), "comment")

        def_idx = self._index_of("def")
        self.assertIn("comment", self.text.tag_names(def_idx))
        self.assertEqual(self._effective_tag(def_idx), "comment")

    def test_keywords_inside_strings_highlighted_as_string(self) -> None:
        self.text.insert("1.0", 'name = "class MyActor"\nimport_text = "import unreal"\n')
        apply_python_highlighting(self.text)

        class_idx = self._index_of("class")
        self.assertIn("string", self.text.tag_names(class_idx))
        self.assertEqual(self._effective_tag(class_idx), "string")

        import_idx = self._index_of("import unreal")
        self.assertIn("string", self.text.tag_names(import_idx))
        self.assertEqual(self._effective_tag(import_idx), "string")

        unreal_idx = self._index_of("unreal")
        self.assertIn("string", self.text.tag_names(unreal_idx))
        self.assertEqual(self._effective_tag(unreal_idx), "string")

    def test_multiline_triple_quoted_docstrings_double_quotes(self) -> None:
        docstring = '"""line 1\ndef function_in_doc():\n    import unreal\n    return True\n"""'
        code = f"{docstring}\nclass OutsideClass:\n    pass\n"
        self.text.insert("1.0", code)
        apply_python_highlighting(self.text)

        # Check start of docstring
        start_idx = self._index_of('"""line 1')
        self.assertEqual(self._effective_tag(start_idx), "string")

        # Check keyword inside multiline docstring
        def_idx = self._index_of("def function_in_doc")
        self.assertEqual(self._effective_tag(def_idx), "string")

        import_idx = self._index_of("import unreal")
        self.assertEqual(self._effective_tag(import_idx), "string")

        return_idx = self._index_of("return True")
        self.assertEqual(self._effective_tag(return_idx), "string")

        # Check outside class is tagged as keyword
        outside_class_idx = self._index_of("class OutsideClass")
        self.assertEqual(self._effective_tag(outside_class_idx), "keyword")

    def test_multiline_triple_quoted_docstrings_single_quotes(self) -> None:
        docstring = "'''first line\ndef inner():\n    pass\n'''"
        self.text.insert("1.0", docstring)
        apply_python_highlighting(self.text)

        start_idx = self._index_of("'''first line")
        self.assertEqual(self._effective_tag(start_idx), "string")

        def_idx = self._index_of("def inner")
        self.assertEqual(self._effective_tag(def_idx), "string")

    def test_regular_keywords_and_builtins(self) -> None:
        self.text.insert("1.0", "def process():\n    return len([1, 2, 3])\n")
        apply_python_highlighting(self.text)

        def_idx = self._index_of("def")
        self.assertEqual(self._effective_tag(def_idx), "keyword")

        return_idx = self._index_of("return")
        self.assertEqual(self._effective_tag(return_idx), "keyword")

        len_idx = self._index_of("len")
        self.assertEqual(self._effective_tag(len_idx), "builtin")


if __name__ == "__main__":
    unittest.main()
