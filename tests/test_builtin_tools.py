from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from unreal_utility_tool.params import parse_tool_params, render_tool_code
from unreal_utility_tool.tool_linter import lint_tool_code


ROOT = Path(__file__).resolve().parents[1]
NEW_TOOL_IDS = {
    "preset-select-actors-by-material",
    "preset-batch-update-actor-tags",
    "preset-audit-missing-material-slots",
}


class BuiltinToolCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads((ROOT / "data" / "tools.json").read_text(encoding="utf-8"))
        cls.tools = cls.catalog["tools"]
        cls.by_id = {tool["id"]: tool for tool in cls.tools}

    def test_builtin_tool_ids_are_unique(self) -> None:
        ids = [tool["id"] for tool in self.tools]
        self.assertEqual(len(ids), len(set(ids)))

    def test_free_core_catalog_contains_new_material_and_tag_tools(self) -> None:
        self.assertEqual(len(self.tools), 21)
        self.assertTrue(NEW_TOOL_IDS.issubset(self.by_id))
        for tool_id in NEW_TOOL_IDS:
            with self.subTest(tool_id=tool_id):
                self.assertEqual(self.by_id[tool_id]["visibility"], "primary")

    def test_new_bundled_tools_render_and_pass_static_checks(self) -> None:
        for tool_id in NEW_TOOL_IDS:
            with self.subTest(tool_id=tool_id):
                code = self.by_id[tool_id]["code"]
                self.assertTrue(parse_tool_params(code))
                rendered = render_tool_code(code, {})
                ast.parse(rendered)
                blocking_issues = [
                    issue.title
                    for issue in lint_tool_code(rendered)
                    if issue.severity in {"warning", "error"}
                ]
                self.assertEqual(blocking_issues, [])


if __name__ == "__main__":
    unittest.main()
