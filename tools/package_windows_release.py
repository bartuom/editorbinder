from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


APP_NAME = "EditorBinder"
PLATFORM_TAG = "win-x64"

SUPPORT_FILES = [
    ("README.md", "README.md"),
    ("QUICKSTART.md", "QUICKSTART.md"),
    ("CHANGELOG.md", "CHANGELOG.md"),
    ("LICENSE.txt", "LICENSE.txt"),
    ("NOTICE.txt", "NOTICE.txt"),
    ("SUPPORT_POLICY.md", "SUPPORT_POLICY.md"),
    ("SECURITY.md", "SECURITY.md"),
    ("CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.md"),
    ("docs/downloads.md", "docs/downloads.md"),
    ("docs/walkthrough.md", "docs/walkthrough.md"),
    ("docs/tool_packs.md", "docs/tool_packs.md"),
    ("enable_portable_mode.bat", "enable_portable_mode.bat"),
    ("reset_window.bat", "reset_window.bat"),
    ("install_windows_shortcuts.bat", "install_windows_shortcuts.bat"),
    ("assets/editorbinder.ico", "assets/editorbinder.ico"),
    ("data/tools.json", "data/tools.json"),
]


@dataclass(frozen=True, slots=True)
class ReleasePaths:
    version: str
    platform_tag: str
    package_name: str
    release_dir: Path
    archive_path: Path
    standalone_exe_path: Path


@dataclass(frozen=True, slots=True)
class BuildResult:
    paths: ReleasePaths
    manifest_path: Path
    archive_path: Path | None
    command: list[str]
    standalone_exe_path: Path | None = None


def project_version(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        return "0.0.0"
    return match.group(1)


def release_basename(version: str, platform_tag: str = PLATFORM_TAG) -> str:
    return f"{APP_NAME}-{version}-{platform_tag}"


def release_paths(root: Path, version: str | None = None, platform_tag: str = PLATFORM_TAG) -> ReleasePaths:
    resolved_version = version or project_version(root)
    package_name = release_basename(resolved_version, platform_tag)
    release_dir = root / "dist" / package_name
    return ReleasePaths(
        version=resolved_version,
        platform_tag=platform_tag,
        package_name=package_name,
        release_dir=release_dir,
        archive_path=release_dir.parent / f"{package_name}.zip",
        standalone_exe_path=release_dir.parent / f"{package_name}.exe",
    )


def resolve_pyinstaller(root: Path, override: str | None = None) -> str:
    if override:
        return override

    local_pyinstaller = root / ".build-venv" / "Scripts" / "pyinstaller.exe"
    if local_pyinstaller.exists():
        return str(local_pyinstaller)

    for executable in ("pyinstaller.exe", "pyinstaller"):
        found = shutil.which(executable)
        if found:
            return found

    raise FileNotFoundError(
        "PyInstaller was not found. Create .build-venv and install pyinstaller, "
        "or pass --pyinstaller PATH."
    )


def pyinstaller_command(
    root: Path,
    pyinstaller: str,
    staging_root: Path,
    work_path: Path,
    spec_path: Path,
    *,
    onefile: bool = False,
) -> list[str]:
    return [
        pyinstaller,
        "--noconfirm",
        "--clean",
        "--onefile" if onefile else "--onedir",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(root / "assets" / "editorbinder.ico"),
        "--paths",
        str(root / "src"),
        "--distpath",
        str(staging_root),
        "--workpath",
        str(work_path),
        "--specpath",
        str(spec_path),
        "--add-data",
        _add_data_arg(root / "assets" / "editorbinder.ico", "assets"),
        "--add-data",
        _add_data_arg(root / "data" / "tools.json", "data"),
        "--add-data",
        _add_data_arg(root / "LICENSE.txt", "."),
        "--add-data",
        _add_data_arg(root / "CHANGELOG.md", "."),
        "--add-data",
        _add_data_arg(root / "NOTICE.txt", "."),
        str(root / "run_app.pyw"),
    ]


def build_windows_release(
    root: Path,
    pyinstaller_override: str | None = None,
    platform_tag: str = PLATFORM_TAG,
    create_zip: bool = True,
    create_standalone_exe: bool = True,
) -> BuildResult:
    _verify_required_files(root)

    paths = release_paths(root, platform_tag=platform_tag)
    staging_root = root / "build" / "windows-release" / "pyinstaller-dist"
    work_path = root / "build" / "windows-release" / "pyinstaller-work"
    spec_path = root / "build" / "windows-release" / "pyinstaller-spec"
    pyinstaller = resolve_pyinstaller(root, pyinstaller_override)
    command = pyinstaller_command(root, pyinstaller, staging_root, work_path, spec_path)

    _safe_rmtree(root, paths.release_dir)
    _safe_unlink(root, paths.archive_path)
    _safe_rmtree(root, staging_root)
    _safe_rmtree(root, work_path)
    _safe_rmtree(root, spec_path)

    subprocess.run(command, cwd=root, check=True)

    built_dir = staging_root / APP_NAME
    if not built_dir.is_dir():
        raise RuntimeError(f"PyInstaller did not create the expected directory: {built_dir}")

    paths.release_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(built_dir), str(paths.release_dir))
    copy_support_files(root, paths.release_dir)
    manifest_path = write_release_manifest(root, paths, pyinstaller)

    archive_path: Path | None = None
    if create_zip:
        archive_path = build_release_zip(paths.release_dir, paths.archive_path)

    standalone_exe_path = None
    if create_standalone_exe:
        standalone_exe_path = build_windows_standalone_exe(
            root,
            pyinstaller_override=pyinstaller_override,
            platform_tag=platform_tag,
        )

    return BuildResult(
        paths=paths,
        manifest_path=manifest_path,
        archive_path=archive_path,
        command=command,
        standalone_exe_path=standalone_exe_path,
    )


def build_windows_standalone_exe(
    root: Path,
    pyinstaller_override: str | None = None,
    platform_tag: str = PLATFORM_TAG,
) -> Path:
    _verify_required_files(root)

    paths = release_paths(root, platform_tag=platform_tag)
    staging_root = root / "build" / "windows-release" / "pyinstaller-onefile-dist"
    work_path = root / "build" / "windows-release" / "pyinstaller-onefile-work"
    spec_path = root / "build" / "windows-release" / "pyinstaller-onefile-spec"
    pyinstaller = resolve_pyinstaller(root, pyinstaller_override)
    command = pyinstaller_command(root, pyinstaller, staging_root, work_path, spec_path, onefile=True)

    _safe_unlink(root, paths.standalone_exe_path)
    _safe_rmtree(root, staging_root)
    _safe_rmtree(root, work_path)
    _safe_rmtree(root, spec_path)

    subprocess.run(command, cwd=root, check=True)

    built_exe = staging_root / f"{APP_NAME}.exe"
    if not built_exe.is_file():
        raise RuntimeError(f"PyInstaller did not create the expected standalone EXE: {built_exe}")

    paths.standalone_exe_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(built_exe), str(paths.standalone_exe_path))
    return paths.standalone_exe_path


def copy_support_files(root: Path, release_dir: Path) -> list[Path]:
    copied: list[Path] = []
    for source_relative, target_relative in SUPPORT_FILES:
        source = root / Path(source_relative)
        if not source.is_file():
            continue
        target = release_dir / Path(target_relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def write_release_manifest(root: Path, paths: ReleasePaths, pyinstaller: str) -> Path:
    executable = paths.release_dir / f"{APP_NAME}.exe"
    manifest = {
        "app": APP_NAME,
        "version": paths.version,
        "platform": paths.platform_tag,
        "package": paths.package_name,
        "entrypoint": executable.name,
        "built_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "python": sys.version.split()[0],
        "system": {
            "os": platform.platform(),
            "machine": platform.machine(),
        },
        "build": {
            "pyinstaller": _capture_first_line([pyinstaller, "--version"]),
            "git_commit": _capture_first_line(["git", "rev-parse", "HEAD"], cwd=root),
            "git_dirty": bool(_capture_first_line(["git", "status", "--short"], cwd=root)),
        },
        "artifacts": {
            "directory": str(paths.release_dir.relative_to(root)),
            "zip": str(paths.archive_path.relative_to(root)),
            "exe_size_bytes": executable.stat().st_size if executable.exists() else 0,
        },
    }
    manifest_path = paths.release_dir / "release.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def build_release_zip(release_dir: Path, archive_path: Path) -> Path:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(release_dir.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if path.is_file():
                archive.write(path, (release_dir.name / path.relative_to(release_dir)).as_posix())
    return archive_path


def _verify_required_files(root: Path) -> None:
    required = [
        root / "run_app.pyw",
        root / "assets" / "editorbinder.ico",
        root / "data" / "tools.json",
        root / "LICENSE.txt",
        root / "CHANGELOG.md",
        root / "NOTICE.txt",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required release files: " + ", ".join(missing))


def _add_data_arg(source: Path, target: str) -> str:
    return f"{source}{os.pathsep}{target}"


def _capture_first_line(command: list[str], cwd: Path | None = None) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return ""
    output = (completed.stdout or completed.stderr).strip()
    if not output:
        return ""
    return output.splitlines()[0].strip()


def _safe_rmtree(root: Path, path: Path) -> None:
    if not path.exists():
        return
    _ensure_build_output_path(root, path)
    shutil.rmtree(path)


def _safe_unlink(root: Path, path: Path) -> None:
    if not path.exists():
        return
    _ensure_build_output_path(root, path)
    path.unlink()


def _ensure_build_output_path(root: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed_roots = [(root / "build").resolve(), (root / "dist").resolve()]
    if any(resolved == allowed or allowed in resolved.parents for allowed in allowed_roots):
        return
    raise ValueError(f"Refusing to remove path outside build outputs: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a versioned Windows EXE release package.")
    parser.add_argument(
        "--pyinstaller",
        default=None,
        help="Optional path to pyinstaller.exe. Defaults to .build-venv or PATH.",
    )
    parser.add_argument(
        "--platform-tag",
        default=PLATFORM_TAG,
        help=f"Package platform tag. Defaults to {PLATFORM_TAG}.",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Create the versioned directory only, without the ZIP archive.",
    )
    parser.add_argument(
        "--no-standalone-exe",
        action="store_true",
        help="Skip the single-file EXE artifact.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    result = build_windows_release(
        root,
        pyinstaller_override=args.pyinstaller,
        platform_tag=args.platform_tag,
        create_zip=not args.no_zip,
        create_standalone_exe=not args.no_standalone_exe,
    )

    print(f"Created directory: {result.paths.release_dir}")
    print(f"Manifest: {result.manifest_path}")
    if result.archive_path is not None:
        size_mb = result.archive_path.stat().st_size / (1024 * 1024)
        print(f"Created ZIP: {result.archive_path}")
        print(f"ZIP size: {size_mb:.2f} MB")
    print(f"EXE: {result.paths.release_dir / (APP_NAME + '.exe')}")
    if result.standalone_exe_path is not None:
        size_mb = result.standalone_exe_path.stat().st_size / (1024 * 1024)
        print(f"Standalone EXE: {result.standalone_exe_path}")
        print(f"Standalone EXE size: {size_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
