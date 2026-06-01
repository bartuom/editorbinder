from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".pyw",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


class PublicHygieneTests(unittest.TestCase):
    maxDiff = None

    def test_tracked_paths_do_not_include_private_or_commercial_artifacts(self) -> None:
        paths = _tracked_paths()
        normalized_paths = [path.as_posix().casefold() for path in paths]
        disallowed_fragments = [
            "src/unreal_utility_tool/preset" + "_packs/",
            "package_" + "gum" + "road" + "_packs.py",
            "gum" + "road" + ".md",
            "tool_implementation_tracker.md",
            "business_docs/",
            "internal_tracker",
        ]

        hits = [
            path
            for path in normalized_paths
            for fragment in disallowed_fragments
            if fragment in path
        ]

        self.assertEqual(hits, [])

    def test_tracked_text_does_not_include_blocking_commercial_terms(self) -> None:
        disallowed_terms = [
            "gum" + "road",
            "paid solution " + "pack",
            "may not " + "redistribute",
            "all rights " + "reserved",
        ]
        hits: list[str] = []

        for path in _tracked_text_paths():
            text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            for term in disallowed_terms:
                if term in text:
                    hits.append(f"{path.as_posix()}: {term}")

        self.assertEqual(hits, [])

    def test_tracked_text_does_not_include_common_secret_tokens(self) -> None:
        secret_patterns = [
            re.compile("github" + r"_pat_[A-Za-z0-9_]{20,}"),
            re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
            re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        ]
        hits: list[str] = []

        for path in _tracked_text_paths():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in secret_patterns:
                if pattern.search(text):
                    hits.append(f"{path.as_posix()}: {pattern.pattern}")

        self.assertEqual(hits, [])


def _tracked_paths() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [root / line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _tracked_text_paths() -> list[Path]:
    return [
        path
        for path in _tracked_paths()
        if path.suffix.casefold() in TEXT_SUFFIXES and path.is_file()
    ]


if __name__ == "__main__":
    unittest.main()
