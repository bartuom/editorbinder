from __future__ import annotations

import re
import unittest
from pathlib import Path

from unreal_utility_tool import __version__


class VersionConsistencyTests(unittest.TestCase):
    def test_runtime_version_matches_project_metadata(self) -> None:
        root = Path(__file__).resolve().parents[1]
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(__version__, match.group(1))

    def test_current_version_has_a_changelog_entry(self) -> None:
        root = Path(__file__).resolve().parents[1]
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {__version__} - ", changelog)


if __name__ == "__main__":
    unittest.main()
