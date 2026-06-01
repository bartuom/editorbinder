from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_packaging_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "package_source_release.py"
    spec = importlib.util.spec_from_file_location("package_source_release", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load package_source_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_windows_packaging_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "package_windows_release.py"
    spec = importlib.util.spec_from_file_location("package_windows_release", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load package_windows_release.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_verify_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "verify_release_artifacts.py"
    spec = importlib.util.spec_from_file_location("verify_release_artifacts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load verify_release_artifacts.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PackagingTests(unittest.TestCase):
    def test_source_release_manifest_keeps_runtime_small(self) -> None:
        module = _load_packaging_module()
        root = Path(__file__).resolve().parents[1]

        files = {path.relative_to(root).as_posix() for path in module.iter_release_files(root)}

        for required_file in [
            "README.md",
            "QUICKSTART.md",
            "CHANGELOG.md",
            "LICENSE.txt",
            "NOTICE.txt",
            "SUPPORT_POLICY.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "CODE_OF_CONDUCT.md",
            "run_app.bat",
            "run_app.pyw",
            "assets/editorbinder.ico",
            "data/tools.json",
            "docs/deployment.md",
            "docs/preset_test_matrix.md",
            "docs/tool_packs.md",
        ]:
            self.assertIn(required_file, files)

        self.assertNotIn("data/user_tools.json", files)
        self.assertNotIn("data/settings.json", files)
        self.assertIn("src/editorbinder/app.py", files)
        self.assertIn("src/unreal_utility_tool/app.py", files)
        self.assertFalse(any(path.startswith("src/unreal_utility_tool/preset_packs/") for path in files))
        self.assertFalse(any(path.startswith("tests/") for path in files))
        self.assertFalse(any(path.startswith("tools/") for path in files))
        self.assertFalse(any("__pycache__" in path for path in files))

    def test_source_release_zip_contains_expected_files(self) -> None:
        module = _load_packaging_module()
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "release.zip"

            built = module.build_source_zip(root, output)

            self.assertEqual(built, output)
            self.assertGreater(output.stat().st_size, 0)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertIn("README.md", names)
            self.assertIn("CHANGELOG.md", names)
            self.assertIn("QUICKSTART.md", names)
            self.assertIn("LICENSE.txt", names)
            self.assertIn("SUPPORT_POLICY.md", names)
            self.assertIn("CONTRIBUTING.md", names)
            self.assertIn("SECURITY.md", names)
            self.assertIn("CODE_OF_CONDUCT.md", names)
            self.assertIn("assets/editorbinder.ico", names)
            self.assertIn("data/tools.json", names)
            self.assertIn("docs/deployment.md", names)
            self.assertIn("docs/preset_test_matrix.md", names)
            self.assertNotIn("data/user_tools.json", names)
            self.assertNotIn("data/settings.json", names)
            self.assertFalse(any(path.startswith("src/unreal_utility_tool/preset_packs/") for path in names))
            self.assertFalse(any(path.startswith("tests/") for path in names))
            self.assertFalse(any(path.startswith("tools/") for path in names))

    def test_license_file_is_mit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "LICENSE.txt").read_text(encoding="utf-8")

        self.assertIn("MIT License", text)
        self.assertIn("Copyright (c) 2026 Bartosz Rozmus", text)
        self.assertIn("Permission is hereby granted", text)
        self.assertNotIn("may not " + "redistribute", text.casefold())
        self.assertNotIn("all rights " + "reserved", text.casefold())

    def test_changelog_and_support_policy_are_oss_focused(self) -> None:
        root = Path(__file__).resolve().parents[1]
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        support = (root / "SUPPORT_POLICY.md").read_text(encoding="utf-8")

        self.assertIn("Initial open-source Free Core release", changelog)
        self.assertIn("18-tool Free Core", changelog)
        self.assertIn("community-supported open source", support)
        self.assertNotIn("pur" + "chase", support.casefold())
        self.assertNotIn("re" + "fund", support.casefold())

    def test_windows_release_paths_are_versioned(self) -> None:
        module = _load_windows_packaging_module()
        root = Path(__file__).resolve().parents[1]

        paths = module.release_paths(root)

        self.assertEqual(paths.version, module.project_version(root))
        self.assertEqual(paths.package_name, f"EditorBinder-{paths.version}-win-x64")
        self.assertEqual(paths.release_dir, root / "dist" / paths.package_name)
        self.assertEqual(paths.archive_path, root / "dist" / f"{paths.package_name}.zip")

    def test_windows_release_support_files_include_runtime_seed(self) -> None:
        module = _load_windows_packaging_module()

        targets = {target for _source, target in module.SUPPORT_FILES}

        self.assertIn("data/tools.json", targets)
        self.assertIn("assets/editorbinder.ico", targets)
        self.assertIn("LICENSE.txt", targets)
        self.assertIn("CHANGELOG.md", targets)
        self.assertIn("QUICKSTART.md", targets)
        self.assertIn("SUPPORT_POLICY.md", targets)
        self.assertIn("SECURITY.md", targets)
        self.assertIn("CODE_OF_CONDUCT.md", targets)
        self.assertIn("enable_portable_mode.bat", targets)
        self.assertIn("reset_window.bat", targets)
        self.assertIn("install_windows_shortcuts.bat", targets)
        self.assertIn("docs/tool_packs.md", targets)

    def test_windows_pyinstaller_command_bundles_runtime_seed(self) -> None:
        module = _load_windows_packaging_module()
        root = Path(__file__).resolve().parents[1]

        command = module.pyinstaller_command(
            root,
            "pyinstaller.exe",
            root / "build" / "windows-release" / "pyinstaller-dist",
            root / "build" / "windows-release" / "pyinstaller-work",
            root / "build" / "windows-release" / "pyinstaller-spec",
        )
        command_text = "\n".join(str(part) for part in command)

        self.assertIn("--onedir", command)
        self.assertIn("--windowed", command)
        self.assertIn(str(root / "run_app.pyw"), command)
        self.assertIn(str(root / "data" / "tools.json"), command_text)
        self.assertIn(str(root / "assets" / "editorbinder.ico"), command_text)

    def test_readme_matches_public_source_release_manifest(self) -> None:
        module = _load_packaging_module()
        root = Path(__file__).resolve().parents[1]
        files = {path.relative_to(root).as_posix() for path in module.iter_release_files(root)}
        text = (root / "README.md").read_text(encoding="utf-8")
        lowered = text.casefold()

        for excluded_reference in [
            "src\\unreal_utility_tool\\preset_packs",
            "paid solution " + "pack",
            "may not " + "redistribute",
            "all rights " + "reserved",
        ]:
            self.assertNotIn(excluded_reference.casefold(), lowered)

        for required_file in [
            "run_app.bat",
            "install_shortcuts.bat",
            "reset_window.bat",
            "enable_portable_mode.bat",
            "run_app.pyw",
            "assets/editorbinder.ico",
            "data/tools.json",
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
        ]:
            self.assertIn(required_file, files)
            self.assertIn(required_file.replace("/", "\\"), text)

        self.assertTrue(any(path.startswith("docs/") for path in files))
        self.assertTrue(any(path.startswith("src/") for path in files))
        self.assertIn("docs\\", text)
        self.assertIn("src\\", text)
        self.assertIn("18-tool Free Core", text)

    def test_public_git_index_does_not_include_private_artifacts(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        files = completed.stdout.casefold()

        self.assertNotIn("src/unreal_utility_tool/preset_packs/", files)
        self.assertNotIn("package_" + "gum" + "road" + "_packs.py", files)
        self.assertNotIn("gum" + "road" + ".md", files)
        self.assertNotIn("tool_implementation_tracker.md", files)

    def test_release_verifier_rejects_private_paths_in_archives(self) -> None:
        module = _load_verify_module()

        with TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "release.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("src/unreal_utility_tool/preset_packs/private.py", "print('private')")

            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaisesRegex(RuntimeError, "private path"):
                    module._reject_disallowed_paths(archive_path.name, set(archive.namelist()))


if __name__ == "__main__":
    unittest.main()
