from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from unreal_utility_tool.models import (
    CATEGORY_CUSTOM,
    CATEGORY_DEBUG,
    CATEGORY_TRANSFORM,
    ROLE_LEVEL_ARTIST,
    ROLE_PIPELINE_ARTIST,
    VISIBILITY_PRIMARY,
    VISIBILITY_SECONDARY,
    WORKFLOW_CUSTOM,
    WORKFLOW_PLACE_ARRANGE,
    Tool,
    category_options,
)
from unreal_utility_tool import storage
from unreal_utility_tool.storage import ToolLibraryStore


class ToolLibraryStoreTests(unittest.TestCase):
    def test_missing_library_loads_empty(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = ToolLibraryStore(Path(temp_dir) / "tools.json")

            tools = store.load_tools()

            self.assertEqual(tools, [])
            self.assertEqual(store.last_load_error, "")

    def test_save_and_reload_tool(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            store = ToolLibraryStore(path)
            tool = Tool.create(
                name="Print",
                description="Logs something",
                tags=["log"],
                code="print('ok')",
                category=CATEGORY_DEBUG,
            )

            store.save_tools([tool])
            loaded = ToolLibraryStore(path).load_tools()

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].name, "Print")
            self.assertEqual(loaded[0].tags, ["log"])
            self.assertEqual(loaded[0].category, CATEGORY_DEBUG)
            self.assertEqual(loaded[0].code, "print('ok')")

    def test_loads_old_tool_without_category(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            tool = Tool.create(name="Move", tags=["transform"], code="print('move')")
            payload = tool.to_dict()
            payload.pop("category")
            path.write_text(json.dumps({"version": 1, "tools": [payload]}), encoding="utf-8")

            loaded = ToolLibraryStore(path).load_tools()

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].category, CATEGORY_TRANSFORM)

    def test_loads_old_custom_tool_without_category(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            tool = Tool.create(name="Custom", tags=[], code="print('custom')")
            payload = tool.to_dict()
            payload.pop("category")
            path.write_text(json.dumps({"version": 1, "tools": [payload]}), encoding="utf-8")

            loaded = ToolLibraryStore(path).load_tools()

            self.assertEqual(loaded[0].category, CATEGORY_CUSTOM)

    def test_preserves_imported_custom_category(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            store = ToolLibraryStore(path)
            tool = Tool.create(
                name="Material Audit",
                code="print('material')",
                category="Material Tools",
            )

            store.save_tools([tool])
            loaded = ToolLibraryStore(path).load_tools()

            self.assertEqual(loaded[0].category, "Material Tools")
            self.assertIn("Material Tools", category_options(loaded))

    def test_loads_old_tool_without_workflow_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            tool = Tool.create(name="Old Metadata", tags=[], code="print('old')")
            payload = tool.to_dict()
            payload.pop("workflows")
            payload.pop("roles")
            payload.pop("visibility")
            path.write_text(json.dumps({"version": 1, "tools": [payload]}), encoding="utf-8")

            loaded = ToolLibraryStore(path).load_tools()

            self.assertEqual(loaded[0].workflows, [WORKFLOW_CUSTOM])
            self.assertEqual(loaded[0].roles, [ROLE_PIPELINE_ARTIST])
            self.assertEqual(loaded[0].visibility, VISIBILITY_PRIMARY)

    def test_workflow_metadata_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            store = ToolLibraryStore(path)
            tool = Tool.create(
                name="Workflow Tool",
                code="print('workflow')",
                workflows=[WORKFLOW_PLACE_ARRANGE],
                roles=[ROLE_LEVEL_ARTIST],
                visibility=VISIBILITY_SECONDARY,
            )

            store.save_tools([tool])
            loaded = ToolLibraryStore(path).load_tools()

            self.assertEqual(loaded[0].workflows, [WORKFLOW_PLACE_ARRANGE])
            self.assertEqual(loaded[0].roles, [ROLE_LEVEL_ARTIST])
            self.assertEqual(loaded[0].visibility, VISIBILITY_SECONDARY)

    def test_update_tool_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            store = ToolLibraryStore(path)
            tool = Tool.create(name="Old", code="print('old')")
            store.save_tools([tool])

            updated = tool.with_updates(
                name="New",
                description="Changed",
                tags=["changed"],
                code="print('new')",
            )
            store.save_tools([updated])
            loaded = ToolLibraryStore(path).load_tools()

            self.assertEqual(loaded[0].id, tool.id)
            self.assertEqual(loaded[0].name, "New")
            self.assertEqual(loaded[0].description, "Changed")
            self.assertEqual(loaded[0].tags, ["changed"])
            self.assertEqual(loaded[0].code, "print('new')")
            self.assertTrue((Path(temp_dir) / "tools.backup.json").exists())

    def test_timestamped_backup_copies_library(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            store = ToolLibraryStore(path)
            tool = Tool.create(name="Backup", code="print('backup')")
            store.save_tools([tool])

            backup_path = store.create_timestamped_backup()

            self.assertTrue(backup_path.exists())
            self.assertIn("tools.backup-", backup_path.name)

    def test_corrupt_json_is_backed_up_and_returns_empty(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            path.write_text("{not-json", encoding="utf-8")
            store = ToolLibraryStore(path)

            tools = store.load_tools()

            backups = list(Path(temp_dir).glob("tools.corrupt-*.json.bak"))
            self.assertEqual(tools, [])
            self.assertEqual(len(backups), 1)
            self.assertFalse(path.exists())
            self.assertIn("Could not load tool library", store.last_load_error)

    def test_list_backups_reports_tool_count(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            store = ToolLibraryStore(path)
            store.save_tools(
                [
                    Tool.create(name="One", code="print('one')"),
                    Tool.create(name="Two", code="print('two')"),
                ]
            )
            backup_path = store.create_timestamped_backup()

            backups = store.list_backups()

            matching = [backup for backup in backups if backup.path == backup_path]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0].filename, backup_path.name)
            self.assertEqual(matching[0].tool_count, 2)
            self.assertEqual(matching[0].error, "")

    def test_list_backups_reports_unreadable_backup(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            backup_path = Path(temp_dir) / "tools.backup-20260529-120000.json.bak"
            backup_path.write_text("{not-json", encoding="utf-8")
            store = ToolLibraryStore(path)

            backups = store.list_backups()

            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].path, backup_path)
            self.assertEqual(backups[0].tool_count, 0)
            self.assertIn("Expecting property name", backups[0].error)

    def test_restore_backup_restores_tools_and_saves_current_safety_backup(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            store = ToolLibraryStore(path)
            old_tool = Tool.create(name="Old", code="print('old')")
            new_tool = Tool.create(name="New", code="print('new')")
            store.save_tools([old_tool])
            backup_path = store.create_timestamped_backup()
            store.save_tools([new_tool])

            result = store.restore_backup(backup_path)
            loaded = ToolLibraryStore(path).load_tools()
            safety_loaded = ToolLibraryStore(result.safety_backup_path).load_tools()

            self.assertEqual([tool.name for tool in result.restored_tools], ["Old"])
            self.assertEqual([tool.name for tool in loaded], ["Old"])
            self.assertIsNotNone(result.safety_backup_path)
            self.assertTrue(result.safety_backup_path.exists())
            self.assertEqual([tool.name for tool in safety_loaded], ["New"])

    def test_restore_backup_rejects_unknown_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            unknown_backup = Path(temp_dir) / "other.json"
            unknown_backup.write_text("[]", encoding="utf-8")
            store = ToolLibraryStore(path)

            with self.assertRaises(ValueError):
                store.restore_backup(unknown_backup)

    def test_frozen_storage_uses_appdata_by_default(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "app"
            app_root.mkdir()
            appdata = Path(temp_dir) / "AppData"

            with _patched_runtime(frozen=True, executable=app_root / "EditorBinder.exe"):
                with _patched_env(APPDATA=str(appdata), UNREAL_UTILITY_TOOL_PORTABLE=None):
                    self.assertEqual(
                        storage.resolve_default_storage_path(),
                        appdata / "EditorBinder" / "tools.json",
                    )

    def test_source_storage_uses_working_copy_not_release_seed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "app"
            app_root.mkdir()

            with _patched_project_root(app_root):
                with _patched_runtime(frozen=False, executable=app_root / "python.exe"):
                    self.assertEqual(
                        storage.resolve_default_storage_path(),
                        app_root / "data" / "user_tools.json",
                    )
                    self.assertEqual(
                        storage.resolve_release_seed_path(),
                        app_root / "data" / "tools.json",
                    )

    def test_seeded_source_storage_copies_release_seed_to_working_library(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "app"
            seed_path = app_root / "data" / "tools.json"
            runtime_path = app_root / "data" / "user_tools.json"
            seed_tool = Tool.create(name="Seed Tool", code="print('seed')")
            ToolLibraryStore(seed_path).save_tools([seed_tool])

            with _patched_project_root(app_root):
                with _patched_runtime(frozen=False, executable=app_root / "python.exe"):
                    seeded_path = storage.ensure_default_storage_seeded()

            self.assertEqual(seeded_path, runtime_path)
            self.assertTrue(seed_path.exists())
            self.assertEqual([tool.name for tool in ToolLibraryStore(runtime_path).load_tools()], ["Seed Tool"])

    def test_seeded_source_storage_merges_new_release_presets_into_existing_working_library(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "app"
            seed_path = app_root / "data" / "tools.json"
            runtime_path = app_root / "data" / "user_tools.json"
            old_seed_tool = Tool.create(name="Old Seed Tool", code="print('old')")
            new_seed_tool = Tool.create(name="New Seed Tool", code="print('new')")
            custom_tool = Tool.create(name="Custom Tool", code="print('custom')")
            ToolLibraryStore(seed_path).save_tools([old_seed_tool, new_seed_tool])
            ToolLibraryStore(runtime_path).save_tools([custom_tool, old_seed_tool])

            with _patched_project_root(app_root):
                with _patched_runtime(frozen=False, executable=app_root / "python.exe"):
                    seeded_path = storage.ensure_default_storage_seeded()

            loaded_names = [tool.name for tool in ToolLibraryStore(runtime_path).load_tools()]
            self.assertEqual(seeded_path, runtime_path)
            self.assertEqual(loaded_names, ["Custom Tool", "Old Seed Tool", "New Seed Tool"])

    def test_refresh_bundled_presets_updates_existing_adds_missing_and_preserves_custom_tools(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "user_tools.json"
            old_bundled = Tool(
                id="preset-existing",
                name="Old Bundled",
                description="Old description",
                tags=["transform"],
                code="print('old')",
                created_at="2026-05-26T00:00:00+00:00",
                updated_at="2026-05-26T00:00:00+00:00",
                category=CATEGORY_TRANSFORM,
            )
            updated_bundled = Tool(
                id="preset-existing",
                name="Updated Bundled",
                description="Updated description",
                tags=["transform"],
                code="print('updated')",
                created_at="2026-05-26T00:00:00+00:00",
                updated_at="2026-05-30T00:00:00+00:00",
                category=CATEGORY_TRANSFORM,
            )
            new_bundled = Tool(
                id="preset-new",
                name="New Bundled",
                description="New description",
                tags=["transform"],
                code="print('new')",
                created_at="2026-05-30T00:00:00+00:00",
                updated_at="2026-05-30T00:00:00+00:00",
                category=CATEGORY_TRANSFORM,
            )
            custom_tool = Tool.create(name="Custom Tool", code="print('custom')")
            ToolLibraryStore(path).save_tools([custom_tool, old_bundled])

            result = storage.refresh_bundled_presets(path, [updated_bundled, new_bundled])

            loaded = ToolLibraryStore(path).load_tools()
            self.assertEqual(result.added_count, 1)
            self.assertEqual(result.updated_count, 1)
            self.assertEqual([tool.name for tool in loaded], ["Custom Tool", "Updated Bundled", "New Bundled"])
            self.assertEqual(loaded[1].code, "print('updated')")

    def test_frozen_storage_can_use_portable_marker(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "app"
            app_root.mkdir()
            (app_root / "portable.flag").write_text("", encoding="utf-8")

            with _patched_runtime(frozen=True, executable=app_root / "EditorBinder.exe"):
                with _patched_env(APPDATA=str(Path(temp_dir) / "AppData"), UNREAL_UTILITY_TOOL_PORTABLE=None):
                    self.assertEqual(
                        storage.resolve_default_storage_path(),
                        app_root / "data" / "user_tools.json",
                    )

    def test_frozen_storage_can_use_portable_env(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "app"
            app_root.mkdir()

            with _patched_runtime(frozen=True, executable=app_root / "EditorBinder.exe"):
                with _patched_env(APPDATA=str(Path(temp_dir) / "AppData"), UNREAL_UTILITY_TOOL_PORTABLE="1"):
                    self.assertEqual(
                        storage.resolve_default_storage_path(),
                        app_root / "data" / "user_tools.json",
                    )

    def test_release_seed_can_be_loaded_from_pyinstaller_onefile_resource_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "app"
            resource_root = Path(temp_dir) / "meipass"
            seed_path = resource_root / "data" / "tools.json"
            seed_tool = Tool.create(name="Bundled Tool", code="print('bundled')")
            ToolLibraryStore(seed_path).save_tools([seed_tool])
            app_root.mkdir()

            with _patched_runtime(frozen=True, executable=app_root / "EditorBinder.exe", meipass=resource_root):
                self.assertEqual(storage.resource_root(), resource_root)
                self.assertEqual(storage.resolve_release_seed_path(), seed_path)

    def test_app_file_path_falls_back_to_pyinstaller_onefile_resource_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "app"
            resource_root = Path(temp_dir) / "meipass"
            license_path = resource_root / "LICENSE.txt"
            app_root.mkdir()
            resource_root.mkdir()
            license_path.write_text("MIT", encoding="utf-8")

            with _patched_runtime(frozen=True, executable=app_root / "EditorBinder.exe", meipass=resource_root):
                self.assertEqual(storage.app_file_path("LICENSE.txt"), license_path)


class _patched_runtime:
    def __init__(self, *, frozen: bool, executable: Path, meipass: Path | None = None) -> None:
        self.frozen = frozen
        self.executable = str(executable)
        self.meipass = str(meipass) if meipass is not None else None
        self.had_frozen = hasattr(sys, "frozen")
        self.had_meipass = hasattr(sys, "_MEIPASS")
        self.old_frozen = getattr(sys, "frozen", None)
        self.old_meipass = getattr(sys, "_MEIPASS", None)
        self.old_executable = sys.executable

    def __enter__(self):
        sys.frozen = self.frozen
        sys.executable = self.executable
        if self.meipass is not None:
            sys._MEIPASS = self.meipass
        return self

    def __exit__(self, *_exc):
        if self.had_frozen:
            sys.frozen = self.old_frozen
        else:
            delattr(sys, "frozen")
        if self.had_meipass:
            sys._MEIPASS = self.old_meipass
        elif hasattr(sys, "_MEIPASS"):
            delattr(sys, "_MEIPASS")
        sys.executable = self.old_executable


class _patched_project_root:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.old_project_root = storage.project_root

    def __enter__(self):
        storage.project_root = lambda: self.root
        return self

    def __exit__(self, *_exc):
        storage.project_root = self.old_project_root


class _patched_env:
    def __init__(self, **values: str | None) -> None:
        self.values = values
        self.old_values: dict[str, str | None] = {}

    def __enter__(self):
        for key, value in self.values.items():
            self.old_values[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return self

    def __exit__(self, *_exc):
        for key, value in self.old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
