from __future__ import annotations

import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "EditorBinder"
FREE_CORE_COUNT = 15
PLATFORM_TAG = "win-x64"
REQUIRED_RELEASE_FILES = {
    "README.md",
    "QUICKSTART.md",
    "CHANGELOG.md",
    "LICENSE.txt",
    "NOTICE.txt",
    "SUPPORT_POLICY.md",
    "data/tools.json",
}
DISALLOWED_PATH_PARTS = {
    "src/unreal_utility_tool/preset_packs/",
}
DISALLOWED_TEXT_PATTERNS = (
    "may not " + "redistribute",
    "all rights " + "reserved",
)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    checks: list[str]


def project_version(root: Path) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError("pyproject.toml does not contain a project version.")
    return match.group(1)


def verify_release_artifacts(root: Path) -> VerificationResult:
    checks: list[str] = []
    version = project_version(root)
    _verify_source_zip(root, version, checks)
    _verify_windows_release(root, version, checks)
    return VerificationResult(checks=checks)


def _verify_source_zip(root: Path, version: str, checks: list[str]) -> None:
    source_zip = root / "dist" / f"{APP_NAME}-source-{version}.zip"
    if not source_zip.is_file():
        raise RuntimeError(f"Missing source ZIP: {source_zip}")

    with zipfile.ZipFile(source_zip) as archive:
        names = set(archive.namelist())
        _require_names(source_zip.name, names, REQUIRED_RELEASE_FILES)
        _reject_disallowed_paths(source_zip.name, names)
        _reject_disallowed_text(source_zip.name, archive)
        seed = json.loads(archive.read("data/tools.json").decode("utf-8"))

    _require_tool_count("source Free Core seed", seed, FREE_CORE_COUNT)
    checks.append(f"source ZIP OK: {source_zip.name}")


def _verify_windows_release(root: Path, version: str, checks: list[str]) -> None:
    release_dir = root / "dist" / f"{APP_NAME}-{version}-{PLATFORM_TAG}"
    release_zip = root / "dist" / f"{APP_NAME}-{version}-{PLATFORM_TAG}.zip"
    exe = release_dir / f"{APP_NAME}.exe"
    if not release_dir.is_dir():
        raise RuntimeError(f"Missing Windows release directory: {release_dir}")
    if not release_zip.is_file():
        raise RuntimeError(f"Missing Windows release ZIP: {release_zip}")
    if not exe.is_file():
        raise RuntimeError(f"Missing Windows executable: {exe}")

    for relative in REQUIRED_RELEASE_FILES:
        if not (release_dir / relative).is_file():
            raise RuntimeError(f"Windows release missing {relative}")

    seed = json.loads((release_dir / "data" / "tools.json").read_text(encoding="utf-8"))
    _require_tool_count("Windows Free Core seed", seed, FREE_CORE_COUNT)

    with zipfile.ZipFile(release_zip) as archive:
        names = set(archive.namelist())
        _reject_disallowed_paths(release_zip.name, names)
        _reject_disallowed_text(release_zip.name, archive)

    checks.append(f"Windows release OK: {release_dir.name}")


def _require_names(label: str, names: set[str], required: set[str]) -> None:
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"{label} missing required files: {', '.join(missing)}")


def _reject_disallowed_paths(label: str, names: set[str]) -> None:
    for name in names:
        normalized = name.replace("\\", "/")
        if any(part in normalized for part in DISALLOWED_PATH_PARTS):
            raise RuntimeError(f"{label} contains private path: {name}")


def _reject_disallowed_text(label: str, archive: zipfile.ZipFile) -> None:
    for name in archive.namelist():
        if not name.lower().endswith((".md", ".txt", ".py", ".json", ".toml", ".yml", ".yaml")):
            continue
        try:
            text = archive.read(name).decode("utf-8")
        except UnicodeDecodeError:
            continue
        lowered = text.casefold()
        for pattern in DISALLOWED_TEXT_PATTERNS:
            if pattern in lowered:
                raise RuntimeError(f"{label} contains disallowed text in {name}: {pattern}")


def _require_tool_count(label: str, payload: object, expected: int) -> None:
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} payload is not a JSON object.")
    tools = payload.get("tools")
    if not isinstance(tools, list):
        raise RuntimeError(f"{label} payload does not contain a tools array.")
    if len(tools) != expected:
        raise RuntimeError(f"{label} expected {expected} tools, found {len(tools)}.")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        result = verify_release_artifacts(root)
    except Exception as exc:
        print(f"Release verification failed: {exc}", file=sys.stderr)
        return 1

    for check in result.checks:
        print(check)
    print("Release verification OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
