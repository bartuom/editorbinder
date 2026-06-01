from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path


INCLUDE_FILES = [
    "README.md",
    "QUICKSTART.md",
    "CHANGELOG.md",
    "LICENSE.txt",
    "NOTICE.txt",
    "SUPPORT_POLICY.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "requirements.txt",
    "pyproject.toml",
    "run_app.bat",
    "run_app.pyw",
    "install_shortcuts.bat",
    "reset_window.bat",
    "enable_portable_mode.bat",
]

INCLUDE_DIRS = [
    "assets",
    "docs",
    "src",
]

EXCLUDED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".tmp",
    ".bak",
}

EXCLUDED_PATH_PREFIXES = {
    "src/unreal_utility_tool/preset_packs/",
}


def project_version(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        return "0.0.0"
    return match.group(1)


def iter_release_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for relative in INCLUDE_FILES:
        path = root / relative
        if path.is_file():
            files.append(path)

    tools_json = root / "data" / "tools.json"
    if tools_json.is_file():
        files.append(tools_json)

    for relative_dir in INCLUDE_DIRS:
        base = root / relative_dir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if _should_include_file(root, path):
                files.append(path)

    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix().casefold())


def build_source_zip(root: Path, output_path: Path | None = None) -> Path:
    version = project_version(root)
    output = output_path or root / "dist" / f"EditorBinder-source-{version}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)

    files = iter_release_files(root)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    return output


def _should_include_file(root: Path, path: Path) -> bool:
    if not path.is_file():
        return False
    relative_parts = path.relative_to(root).parts
    relative_posix = path.relative_to(root).as_posix()
    if any(relative_posix.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
        return False
    if any(part in EXCLUDED_NAMES for part in relative_parts):
        return False
    if path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the lightweight source/BAT release ZIP.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output ZIP path. Defaults to dist/EditorBinder-source-<version>.zip.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = build_source_zip(root, args.output)
    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"Created: {output}")
    print(f"Size: {size_mb:.2f} MB")
    print("This package keeps the lightweight source/BAT workflow and requires a local Python install.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
