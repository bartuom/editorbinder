from __future__ import annotations

import json
import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from unreal_utility_tool.models import CATEGORY_CUSTOM, CATEGORY_ORGANIZATION, CATEGORY_SELECTION, Tool
from unreal_utility_tool.tool_importer import (
    IMPORT_POLICY_COPY,
    IMPORT_POLICY_REPLACE,
    IMPORT_POLICY_SKIP,
    ToolImportBatch,
    _import_tools_from_zip,
    _zip_pack_payload_name,
    apply_import_policy,
    import_tools_from_paths,
    import_tools_from_text,
)


def _tool_with_id(tool_id: str, name: str, code: str = "import unreal\nunreal.log('ok')") -> Tool:
    tool = Tool.create(name=name, code=code)
    return Tool(
        id=tool_id,
        name=tool.name,
        description=tool.description,
        tags=tool.tags,
        code=tool.code,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
        category=tool.category,
        workflows=tool.workflows,
        roles=tool.roles,
        visibility=tool.visibility,
    )


class ToolImporterTests(unittest.TestCase):
    def test_imports_python_file_with_filename_as_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "offset_selected.py"
            path.write_text("import unreal\nunreal.log('ok')\n", encoding="utf-8")

            tools, errors = import_tools_from_paths([path])

        self.assertEqual(errors, [])
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "Offset Selected")
        self.assertEqual(tools[0].code, "import unreal\nunreal.log('ok')")

    def test_imports_ai_text_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ai_output.txt"
            path.write_text(
                """<<<UUT_NAME>>>
Randomize Yaw
<<<UUT_NOTES>>>
min_yaw and max_yaw are editable.
<<<UUT_CODE>>>
```python
import unreal
unreal.log("ok")
```
<<<UUT_END>>>
""",
                encoding="utf-8",
            )

            tools, errors = import_tools_from_paths([path])

        self.assertEqual(errors, [])
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "Randomize Yaw")
        self.assertEqual(tools[0].description, "min_yaw and max_yaw are editable.")
        self.assertEqual(tools[0].code, 'import unreal\nunreal.log("ok")')

    def test_imports_json_library(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "tools": [
                            {
                                "name": "Tool A",
                                "description": "First",
                                "tags": ["selection"],
                                "category": "Selection",
                                "code": "import unreal\nunreal.log('a')",
                            },
                            {
                                "name": "Tool B",
                                "notes": "Second",
                                "code": "import unreal\nunreal.log('b')",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            tools, errors = import_tools_from_paths([path])

        self.assertEqual(errors, [])
        self.assertEqual([tool.name for tool in tools], ["Tool A", "Tool B"])
        self.assertEqual(tools[0].tags, ["selection"])
        self.assertEqual(tools[0].category, CATEGORY_SELECTION)
        self.assertEqual(tools[1].description, "Second")
        self.assertEqual(tools[1].category, CATEGORY_CUSTOM)

    def test_imports_json_pack_with_new_category(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "editorbinder-pack.json"
            path.write_text(
                json.dumps(
                    {
                        "pack_id": "material_tools",
                        "pack_name": "Material Tools",
                        "version": "1.0.0",
                        "tools": [
                            {
                                "name": "Audit Materials",
                                "description": "Checks material setup.",
                                "category": "Material Tools",
                                "code": "import unreal\nunreal.log('materials')",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            tools, errors = import_tools_from_paths([path])

        self.assertEqual(errors, [])
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].category, "Material Tools")

    def test_imports_pack_with_new_workflow_and_role_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "editorbinder-pack.json"
            path.write_text(
                json.dumps(
                    {
                        "pack_id": "quest_tools",
                        "tools": [
                            {
                                "name": "Quest Bounds Audit",
                                "description": "Checks VR bounds.",
                                "workflow": "ignored",
                                "workflows": ["VR Review"],
                                "roles": ["VR Designer"],
                                "code": "import unreal\nunreal.log('vr')",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            tools, errors = import_tools_from_paths([path])

        self.assertEqual(errors, [])
        self.assertEqual(tools[0].workflows, ["VR Review"])
        self.assertEqual(tools[0].roles, ["VR Designer"])

    def test_imports_zip_tool_pack(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "material-pack.zip"
            payload = {
                "pack_id": "material_tools",
                "pack_name": "Material Tools",
                "version": "1.0.0",
                "recommended_import_policy": "skip",
                "tools": [
                    {
                        "id": "material-audit-tool",
                        "created_at": "2026-05-31T00:00:00+00:00",
                        "updated_at": "2026-05-31T00:00:00+00:00",
                        "name": "Audit Materials",
                        "description": "Checks material setup.",
                        "category": "Material Tools",
                        "code": "import unreal\nunreal.log('materials')",
                    }
                ],
            }
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("editorbinder-pack.json", json.dumps(payload))

            tools, errors = import_tools_from_paths([path])

        self.assertEqual(errors, [])
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].id, "material-audit-tool")
        self.assertEqual(tools[0].name, "Audit Materials")
        self.assertEqual(tools[0].category, "Material Tools")

    def test_imports_unpacked_bundle_folder_as_root_pack_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            root_payload = {
                "pack_id": "bundle",
                "tools": [
                    {
                        "id": "root-tool",
                        "name": "Root Bundle Tool",
                        "code": "import unreal\nunreal.log('root')",
                    }
                ],
            }
            nested_payload = {
                "pack_id": "nested",
                "tools": [
                    {
                        "id": "nested-tool",
                        "name": "Nested Pack Tool",
                        "code": "import unreal\nunreal.log('nested')",
                    }
                ],
            }
            (root / "editorbinder-pack.json").write_text(json.dumps(root_payload), encoding="utf-8")
            (root / "bundle-manifest.json").write_text(json.dumps({"packs": []}), encoding="utf-8")
            packs_dir = root / "packs"
            packs_dir.mkdir()
            with zipfile.ZipFile(packs_dir / "nested-pack.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("editorbinder-pack.json", json.dumps(nested_payload))

            tools, errors = import_tools_from_paths([root])

        self.assertEqual(errors, [])
        self.assertEqual([tool.id for tool in tools], ["root-tool"])
        self.assertEqual([tool.name for tool in tools], ["Root Bundle Tool"])

    def test_docs_import_examples_remain_importable(self) -> None:
        examples_root = Path(__file__).resolve().parents[1] / "docs" / "examples"
        paths = [
            examples_root / "import_json_tool.json",
            examples_root / "import_pack.json",
            examples_root / "import_marker_tool.txt",
            examples_root / "import_python_tool.py",
            examples_root / "pack_folder",
        ]

        tools, errors = import_tools_from_paths(paths)

        self.assertEqual(errors, [])
        self.assertEqual(
            [tool.name for tool in tools],
            [
                "Select Point Lights",
                "Log Selected Actor Count",
                "Hide Selected Actors In Editor",
                "Print Selected Actor Names",
                "Move Selected Actors Up",
                "Log Current Level Name",
            ],
        )

    def test_zip_without_pack_payload_reports_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty-pack.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("README.md", "# Empty")

            tools, errors = import_tools_from_paths([path])

        self.assertEqual(tools, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("editorbinder-pack.json", errors[0])

    def test_import_text_file_with_utf8_bom(self) -> None:
        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "bom_tool.txt"
            content = (
                "<<<UUT_NAME>>>\n"
                "BOM Marker Tool\n"
                "<<<UUT_NOTES>>>\n"
                "Created with BOM\n"
                "<<<UUT_CODE>>>\n"
                "import unreal\n"
                "unreal.log('bom')\n"
                "<<<UUT_END>>>\n"
            )
            file_path.write_bytes(content.encode("utf-8-sig"))

            tools, errors = import_tools_from_paths([file_path])

            self.assertEqual(errors, [])
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0].name, "BOM Marker Tool")
            self.assertEqual(tools[0].description, "Created with BOM")
            self.assertFalse(tools[0].name.startswith("\ufeff"))

            py_path = Path(temp_dir) / "bom_script.py"
            py_path.write_bytes("import unreal\nunreal.log('script')\n".encode("utf-8-sig"))
            py_tools, py_errors = import_tools_from_paths([py_path])
            self.assertEqual(py_errors, [])
            self.assertEqual(len(py_tools), 1)
            self.assertEqual(py_tools[0].name, "Bom Script")

    def test_import_json_file_with_utf8_bom(self) -> None:
        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "bom_tool.json"
            payload = {
                "name": "BOM JSON Tool",
                "code": "import unreal\nunreal.log('json_bom')",
            }
            file_path.write_bytes(json.dumps(payload).encode("utf-8-sig"))

            tools, errors = import_tools_from_paths([file_path])

            self.assertEqual(errors, [])
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0].name, "BOM JSON Tool")

    def test_import_invalid_utf8_reports_decode_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid.py"
            file_path.write_bytes(b"\x80\x81invalid")

            tools, errors = import_tools_from_paths([file_path])

            self.assertEqual(tools, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("invalid.py", errors[0])
            self.assertTrue(
                "codec can't decode" in errors[0] or "UnicodeDecodeError" in errors[0] or "decode" in errors[0]
            )

    def test_import_invalid_utf8_json_reports_decode_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid.json"
            file_path.write_bytes(b"\x80\x81{\"name\": \"test\"}")

            tools, errors = import_tools_from_paths([file_path])

            self.assertEqual(tools, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("invalid.json", errors[0])
            self.assertTrue(
                "codec can't decode" in errors[0] or "UnicodeDecodeError" in errors[0] or "decode" in errors[0]
            )

    def test_import_invalid_utf8_zip_payload_reports_decode_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid_payload.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("editorbinder-pack.json", b"\x80\x81{\"tools\": []}")

            tools, errors = import_tools_from_paths([path])

            self.assertEqual(tools, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("invalid_payload.zip", errors[0])
            self.assertTrue(
                "codec can't decode" in errors[0] or "UnicodeDecodeError" in errors[0] or "decode" in errors[0]
            )

    def test_zip_with_path_traversal_is_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "malicious.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("../../etc/passwd", "root:x:0:0:::")
                archive.writestr("editorbinder-pack.json", json.dumps({"tools": []}))

            tools, errors = import_tools_from_paths([path])

            self.assertEqual(tools, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("Unsafe archive member path", errors[0])
            with self.assertRaises(ValueError):
                _import_tools_from_zip(path)
            with zipfile.ZipFile(path) as archive:
                with self.assertRaises(ValueError):
                    _zip_pack_payload_name(archive)

    def test_zip_with_leading_slash_traversal_is_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "absolute_member.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("/etc/passwd", "root:x:0:0:::")
                archive.writestr("editorbinder-pack.json", json.dumps({"tools": []}))

            tools, errors = import_tools_from_paths([path])

            self.assertEqual(tools, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("Unsafe archive member path", errors[0])
            with self.assertRaises(ValueError):
                _import_tools_from_zip(path)

    def test_import_batch_defaults_to_skip_duplicates(self) -> None:
        self.assertEqual(ToolImportBatch([]).policy, IMPORT_POLICY_SKIP)

    def test_imports_folder_and_reports_bad_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "good.py").write_text("import unreal\nunreal.log('ok')\n", encoding="utf-8")
            (root / "bad.json").write_text("{not json", encoding="utf-8")

            tools, errors = import_tools_from_paths([root])

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "Good")
        self.assertEqual(len(errors), 1)
        self.assertIn("bad.json", errors[0])

    def test_imports_multiple_marker_blocks_from_text(self) -> None:
        tools = import_tools_from_text(
            """Intro ignored.
<<<UUT_NAME>>>
Tool One
<<<UUT_NOTES>>>
None
<<<UUT_CODE>>>
import unreal
unreal.log("one")
<<<UUT_END>>>
Between ignored.
<<<UUT_NAME>>>
Tool Two
<<<UUT_NOTES>>>
Second note
<<<UUT_CODE>>>
import unreal
unreal.log("two")
<<<UUT_END>>>
"""
        )

        self.assertEqual([tool.name for tool in tools], ["Tool One", "Tool Two"])
        self.assertEqual(tools[0].description, "")
        self.assertEqual(tools[1].description, "Second note")
        self.assertEqual(tools[0].code, 'import unreal\nunreal.log("one")')
        self.assertEqual(tools[1].code, 'import unreal\nunreal.log("two")')

    def test_python_file_can_use_tool_comment_as_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "fallback_name.py"
            path.write_text(
                """# Tool: Better Imported Name
# Param: amount | int | 10 | Amount
import unreal
amount = {{amount}}
unreal.log(amount)
""",
                encoding="utf-8",
            )

            tools, errors = import_tools_from_paths([path])

        self.assertEqual(errors, [])
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "Better Imported Name")
        self.assertTrue(tools[0].code.startswith("# Tool: Better Imported Name"))
        self.assertIn("# Param: amount", tools[0].code)

    def test_import_policy_copy_renames_duplicate_names(self) -> None:
        existing = [Tool.create(name="Tool A", code="import unreal\nunreal.log('old')")]
        imported = [
            Tool.create(name="Tool A", code="import unreal\nunreal.log('new')"),
            Tool.create(name="Tool A", code="import unreal\nunreal.log('newer')"),
        ]

        resolution = apply_import_policy(existing, imported, IMPORT_POLICY_COPY)

        self.assertEqual([tool.name for tool in resolution.tools], ["Tool A", "Tool A Copy", "Tool A Copy 2"])
        self.assertEqual(resolution.added_count, 2)
        self.assertEqual(resolution.replaced_count, 0)
        self.assertEqual(resolution.skipped_count, 0)
        self.assertEqual(resolution.renamed_count, 2)

    def test_import_policy_skip_ignores_existing_and_batch_duplicates(self) -> None:
        existing = [Tool.create(name="Tool A", code="import unreal\nunreal.log('old')")]
        imported = [
            Tool.create(name="Tool A", code="import unreal\nunreal.log('new')"),
            Tool.create(name="Tool B", code="import unreal\nunreal.log('b')"),
            Tool.create(name="Tool B", code="import unreal\nunreal.log('b2')"),
        ]

        resolution = apply_import_policy(existing, imported, IMPORT_POLICY_SKIP)

        self.assertEqual([tool.name for tool in resolution.tools], ["Tool A", "Tool B"])
        self.assertEqual(resolution.added_count, 1)
        self.assertEqual(resolution.replaced_count, 0)
        self.assertEqual(resolution.skipped_count, 2)

    def test_import_policy_skip_uses_stable_ids_before_names(self) -> None:
        existing = [_tool_with_id("stable-tool", "Old Tool Name")]
        imported = [
            _tool_with_id("stable-tool", "Renamed Tool"),
            _tool_with_id("new-tool", "Old Tool Name"),
            _tool_with_id("unique-tool", "Unique Tool"),
        ]

        resolution = apply_import_policy(existing, imported, IMPORT_POLICY_SKIP)

        self.assertEqual([tool.id for tool in resolution.tools], ["stable-tool", "unique-tool"])
        self.assertEqual(resolution.added_count, 1)
        self.assertEqual(resolution.skipped_count, 2)

    def test_import_policy_replace_uses_stable_id_for_renamed_tools(self) -> None:
        existing = [_tool_with_id("stable-tool", "Old Tool Name", "import unreal\nunreal.log('old')")]
        imported = [_tool_with_id("stable-tool", "Renamed Tool", "import unreal\nunreal.log('new')")]

        resolution = apply_import_policy(existing, imported, IMPORT_POLICY_REPLACE)

        self.assertEqual(len(resolution.tools), 1)
        self.assertEqual(resolution.tools[0].id, "stable-tool")
        self.assertEqual(resolution.tools[0].name, "Renamed Tool")
        self.assertEqual(resolution.tools[0].code, "import unreal\nunreal.log('new')")
        self.assertEqual(resolution.replaced_count, 1)

    def test_import_policy_replace_preserves_existing_id(self) -> None:
        existing_tool = Tool.create(name="Tool A", code="import unreal\nunreal.log('old')")
        imported = [
            Tool.create(
                name="Tool A",
                description="Updated",
                tags=["custom"],
                category=CATEGORY_ORGANIZATION,
                code="import unreal\nunreal.log('new')",
            ),
            Tool.create(name="Tool B", code="import unreal\nunreal.log('b')"),
        ]

        resolution = apply_import_policy([existing_tool], imported, IMPORT_POLICY_REPLACE)

        self.assertEqual([tool.name for tool in resolution.tools], ["Tool A", "Tool B"])
        self.assertEqual(resolution.tools[0].id, existing_tool.id)
        self.assertEqual(resolution.tools[0].description, "Updated")
        self.assertEqual(resolution.tools[0].tags, ["custom"])
        self.assertEqual(resolution.tools[0].category, CATEGORY_ORGANIZATION)
        self.assertEqual(resolution.tools[0].code, "import unreal\nunreal.log('new')")
        self.assertEqual(resolution.added_count, 1)
        self.assertEqual(resolution.replaced_count, 1)
        self.assertEqual(resolution.skipped_count, 0)


if __name__ == "__main__":
    unittest.main()
