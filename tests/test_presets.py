from __future__ import annotations

import json
import unittest
from pathlib import Path

from unreal_utility_tool.models import CATEGORIES, ROLES, VISIBILITIES, WORKFLOWS, WORKFLOW_CUSTOM
from unreal_utility_tool.presets import PRESET_PACKS_DIR, _preset_script_paths, default_presets
from unreal_utility_tool.release_catalog import FREE_CORE_COUNT, FREE_CORE_TOOL_IDS
from unreal_utility_tool.storage import ToolLibraryStore
from unreal_utility_tool.validation import validate_tool_code


class PresetTests(unittest.TestCase):
    maxDiff = None

    def test_public_repo_does_not_ship_private_preset_pack_sources(self) -> None:
        self.assertFalse(any(PRESET_PACKS_DIR.glob("*/*.py")))
        self.assertEqual(_preset_script_paths(), [])

    def test_default_presets_are_empty_without_private_pack_sources(self) -> None:
        self.assertEqual(default_presets(), [])

    def test_free_core_release_seed_has_expected_tools(self) -> None:
        seed_tools = self._seed_tools()

        self.assertEqual(len(seed_tools), FREE_CORE_COUNT)
        self.assertEqual([tool.id for tool in seed_tools], list(FREE_CORE_TOOL_IDS))
        self.assertEqual(
            [tool.name for tool in seed_tools],
            [
                "Scene Cleanup Audit Report",
                "Distribute Selected Actors In Grid",
                "Organize Selected Actors By Static Mesh",
                "Find Broken Or Suspicious Actors",
                "Transform Selected Actors",
                "Randomize Selected Transform",
                "Snap Selected Actors To Ground",
                "Move Selected Actors To Folder",
                "Rename Selected Actors Pattern",
                "Replace Text In Selected Actor Labels",
                "Set Selected Collision Profile",
                "Select Same Static Mesh As Selected",
                "Set Selected Actors Mobility",
                "Flatten Selected Actors To Same Z",
                "Reset Bad Scale On Selected Actors",
                "Select Actors By Label Text",
                "Select Actors By Class Name",
                "Report Selected Actors Summary",
            ],
        )

    def test_free_core_release_seed_is_valid_paste_ready_python(self) -> None:
        for tool in self._seed_tools():
            with self.subTest(tool=tool.name):
                result = validate_tool_code(tool.code)
                self.assertTrue(result.ok, result.message)

    def test_free_core_release_seed_has_explicit_supported_categories(self) -> None:
        root = Path(__file__).resolve().parents[1]
        seed_path = root / "data" / "tools.json"
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        raw_tools = payload.get("tools", [])

        self.assertEqual(len(raw_tools), FREE_CORE_COUNT)
        for raw_tool in raw_tools:
            with self.subTest(tool=raw_tool.get("name")):
                self.assertIn("category", raw_tool)
                self.assertIn(raw_tool["category"], CATEGORIES)
                self.assertIn("workflows", raw_tool)
                self.assertTrue(set(raw_tool["workflows"]).issubset(set(WORKFLOWS) | {WORKFLOW_CUSTOM}))
                self.assertIn("roles", raw_tool)
                self.assertTrue(set(raw_tool["roles"]).issubset(set(ROLES)))
                self.assertIn("visibility", raw_tool)
                self.assertIn(raw_tool["visibility"], VISIBILITIES)

        loaded_categories = {tool.category for tool in ToolLibraryStore(seed_path).load_tools()}
        self.assertTrue(loaded_categories.issubset(set(CATEGORIES)))

        hero_tools = [raw_tool for raw_tool in raw_tools if "hero" in raw_tool.get("tags", [])]
        self.assertGreaterEqual(len(hero_tools), 4)

    def test_free_core_avoids_known_bad_unreal_python_calls(self) -> None:
        combined_code = "\n".join(tool.code for tool in self._seed_tools())

        self.assertNotIn("is_pending_kill", combined_code)
        self.assertNotIn("if not hit[0]", combined_code)
        self.assertNotIn("hit[1].impact_point", combined_code)
        self.assertNotIn("root_component = actor.get_root_component()", combined_code)
        self.assertIn("ScopedEditorTransaction", combined_code)

    def test_mutating_free_core_tools_use_editor_transactions(self) -> None:
        mutating_names = {
            "Transform Selected Actors",
            "Randomize Selected Transform",
            "Snap Selected Actors To Ground",
            "Move Selected Actors To Folder",
            "Set Selected Actors Mobility",
            "Rename Selected Actors Pattern",
            "Replace Text In Selected Actor Labels",
            "Set Selected Collision Profile",
            "Distribute Selected Actors In Grid",
            "Organize Selected Actors By Static Mesh",
            "Flatten Selected Actors To Same Z",
            "Reset Bad Scale On Selected Actors",
        }

        by_name = {tool.name: tool for tool in self._seed_tools()}
        for name in mutating_names:
            with self.subTest(tool=name):
                self.assertIn("unreal.ScopedEditorTransaction", by_name[name].code)

    def test_audit_free_core_tools_do_not_change_scene_data(self) -> None:
        scene_mutators = [
            "set_actor_location",
            "set_folder_path",
            "set_actor_scale3d",
            "set_collision_profile_name",
            "set_editor_property",
            "set_actor_label",
        ]
        audit_names = {
            "Scene Cleanup Audit Report",
            "Find Broken Or Suspicious Actors",
            "Select Same Static Mesh As Selected",
            "Select Actors By Label Text",
            "Select Actors By Class Name",
            "Report Selected Actors Summary",
        }
        by_name = {tool.name: tool for tool in self._seed_tools()}

        for name in audit_names:
            with self.subTest(tool=name):
                for mutator in scene_mutators:
                    self.assertNotIn(mutator, by_name[name].code)

    def _seed_tools(self):
        root = Path(__file__).resolve().parents[1]
        return ToolLibraryStore(root / "data" / "tools.json").load_tools()


if __name__ == "__main__":
    unittest.main()
